"""
app/modules/agents/flow_compiler.py
======================================
Compiles a PUBLISHED InterviewFlow's graph_json into a real, executable
LangGraph StateGraph for one turn. Unlike the old hardcoded-in-Python
turn topology this replaces, the flow's node/edge JSON genuinely drives
which agent handles each stage and where the router sends the conversation
next — see app/db/models.py's InterviewFlow docstring for the exact
graph_json shape this compiler consumes, and flow_validation.py for the
publish-time gate that guarantees every published flow compiles cleanly.

Two entry points into one turn's compiled graph (mirrors the original
hardcoded graph.py's `entry_router`):
  * turn 1 (no candidate answer yet) enters at the "start" node's single
    target, which must be a "question" node.
  * every later turn (the candidate just answered) enters directly at the
    flow's one "evaluation" node -- NOT via a graph edge from the question
    node, since the question and the answer it provokes happen in two
    separate LangGraph invocations (a live voice interview is fundamentally
    turn-based; cross-turn memory lives in Redis, threaded through by
    engine.py, not in this graph).

"question" and "coaching" nodes need no outgoing edges of their own in
graph_json -- each is a per-turn leaf, explicitly wired straight to
LangGraph's END here. Reaching END only ends THIS turn's graph invocation;
it does not end the interview. The interview itself only ends when the
router routes to the flow's "end" node, which sets should_end=True.

Only the structural PARSE of graph_json (node/edge lookup tables) is
cached, keyed by flow.id -- a compiled StateGraph closes over this call's
AsyncSession, which must never be reused across requests, so the graph
object itself is rebuilt (cheap, pure Python, no I/O) on every turn exactly
as the old build_turn_graph(db) already did. Published flows are immutable
(app/modules/admin/flows/router.py blocks edits once a flow leaves DRAFT;
a "new version" is always a new row via clone()), so caching by flow.id
needs no invalidation logic.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Awaitable, Callable, Optional

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import AgentKey, DifficultyLevel, InterviewFlow
from app.modules.agents import registry
from app.modules.agents.flow_validation import validate_flow_graph
from app.modules.agents.schemas import (
    CandidateKnowledgeEntryContext,
    CoachInput,
    EvaluatorInput,
    InterviewerInput,
    RouterInput,
)
from app.modules.agents.state import InterviewState

logger = structlog.get_logger()

_DIFFICULTY_ORDER = [DifficultyLevel.JUNIOR.value, DifficultyLevel.MID.value, DifficultyLevel.SENIOR.value]

NodeExecutor = Callable[[InterviewState], Awaitable[dict]]


class FlowCompilationError(RuntimeError):
    """Raised when a supposedly-published flow fails to compile. Should only
    happen from a bug in validate_flow_graph itself or a manual DB edit
    bypassing the publish endpoint -- publish-time validation is the real
    gate (see flow_validation.py). Callers must hard-fail the session start
    on this, not silently fall back to some other graph -- a silent
    fallback would itself be an untested code path."""


def _next_difficulty(current: str) -> str:
    try:
        idx = _DIFFICULTY_ORDER.index(current)
    except ValueError:
        return current
    return _DIFFICULTY_ORDER[min(idx + 1, len(_DIFFICULTY_ORDER) - 1)]


def _log_entry(node_id: str, agent_key: AgentKey, run_result, success: bool = True, error: Optional[str] = None) -> dict:
    return {
        "node_id": node_id,
        "agent_key": agent_key.value,
        "model_name": getattr(run_result, "model_name", None),
        "tokens_used": getattr(run_result, "tokens_used", None),
        "latency_ms": getattr(run_result, "latency_ms", 0),
        "success": success,
        "error_message": error,
    }


class _ParsedFlow:
    __slots__ = ("nodes", "edges", "start_target", "evaluation_node_id", "router_action_lookups")

    def __init__(self, nodes, edges, start_target, evaluation_node_id, router_action_lookups):
        self.nodes = nodes
        self.edges = edges
        self.start_target = start_target
        self.evaluation_node_id = evaluation_node_id
        self.router_action_lookups = router_action_lookups


def _router_action_lookup(edges: list[dict], router_node_id: str) -> dict[str, str]:
    return {
        (e.get("data") or {}).get("action"): e["target"]
        for e in edges
        if e.get("source") == router_node_id and (e.get("data") or {}).get("action")
    }


@lru_cache(maxsize=64)
def _parse_flow_structure(flow_id: str, graph_json_repr: str) -> _ParsedFlow:
    """Pure-Python parse of graph_json into lookup tables -- no `db`, no
    agents, no LangGraph objects, fully cacheable. Re-validates defensively
    (publish already enforces this; a cheap re-check here costs nothing and
    means this function alone is sufficient to reason about correctness)."""
    graph_json = json.loads(graph_json_repr)
    errors = validate_flow_graph(graph_json)
    if errors:
        raise FlowCompilationError(f"Flow {flow_id} failed compilation validation: {errors}")

    nodes = {n["id"]: n for n in graph_json.get("nodes", [])}
    edges = graph_json.get("edges", [])

    start_node_id = next(n["id"] for n in nodes.values() if n["type"] == "start")
    start_target = next(e["target"] for e in edges if e["source"] == start_node_id)
    evaluation_node_id = next(n["id"] for n in nodes.values() if n["type"] == "evaluation")

    router_action_lookups = {
        node_id: _router_action_lookup(edges, node_id)
        for node_id, node in nodes.items()
        if node["type"] == "router"
    }

    return _ParsedFlow(nodes, edges, start_target, evaluation_node_id, router_action_lookups)


# --- Generic node executors, one factory per node type ---------------------------

def make_question_node(db: AsyncSession, agent_key: AgentKey, node_id: str) -> NodeExecutor:
    """Handles the first question, follow-ups, and "next question" alike --
    the only real behavioral difference between them is `is_followup`,
    which is derived from the router's last decision (state["next_action"]),
    not from being three separate node types as in the old hardcoded graph."""

    async def node_fn(state: InterviewState) -> dict:
        agent = await registry.build_agent(db, agent_key)
        last_eval = state.get("last_evaluation") or {}
        is_followup = state.get("next_action") == "ask_followup"
        knowledge_entries = [CandidateKnowledgeEntryContext(**e) for e in state.get("knowledge_entries", [])]

        result = await agent.run(InterviewerInput(
            role_name=state["role_name"],
            mode=state["mode"],
            difficulty=state["difficulty"],
            stage=state.get("current_stage", "core"),
            questions_already_asked=state.get("questions_asked", []),
            last_candidate_answer=state.get("last_candidate_answer") if is_followup else None,
            last_evaluation_summary=(
                f"weak_signal={last_eval.get('weak_signal')}; composite_score={last_eval.get('composite_score')}"
                if is_followup else None
            ),
            knowledge_entries=knowledge_entries,
            covered_entry_ids=state.get("covered_knowledge_entry_ids", []),
            is_followup=is_followup,
            coaching_hint_enabled=state.get("live_coaching_enabled", False),
        ))

        questions_asked = state.get("questions_asked", [])
        follow_up_count = state.get("follow_up_count", 0)
        if is_followup:
            follow_up_count += 1
        else:
            questions_asked = questions_asked + [result.output.question]
            follow_up_count = 0

        covered = state.get("covered_knowledge_entry_ids", [])
        used_this_turn = state.get("knowledge_entries_used_this_turn", [])
        entry_used = result.output.knowledge_entry_id_used
        # Trust but verify: only accept an id the LLM was actually offered.
        # A hallucinated id would otherwise reach engine.py's uuid.UUID(...)
        # cast and crash the turn.
        known_ids = {e.id for e in knowledge_entries}
        if entry_used and entry_used in known_ids:
            used_this_turn = used_this_turn + [entry_used]
            if entry_used not in covered:
                covered = covered + [entry_used]

        log = [_log_entry(node_id, agent_key, result)]
        return {
            "current_question": result.output.question,
            "questions_asked": questions_asked,
            "follow_up_count": follow_up_count,
            "last_hint": result.output.hint,
            "current_node_id": node_id,
            "covered_knowledge_entry_ids": covered,
            "knowledge_entries_used_this_turn": used_this_turn,
            "execution_log": state.get("execution_log", []) + log,
        }

    return node_fn


def make_evaluation_node(db: AsyncSession, agent_key: AgentKey, node_id: str) -> NodeExecutor:
    async def node_fn(state: InterviewState) -> dict:
        rubric = await registry.get_evaluator_rubric(db)
        agent = await registry.build_agent(db, agent_key)
        result = await agent.run(EvaluatorInput(
            question=state.get("current_question") or "",
            answer=state.get("last_candidate_answer") or "",
            role_name=state["role_name"],
            mode=state["mode"],
            difficulty=state["difficulty"],
            rubric=rubric,
        ))
        out = result.output
        snapshot = {
            "relevance": out.relevance,
            "clarity": out.clarity,
            "communication": out.communication,
            "technical_depth": out.technical_depth,
            "problem_solving": out.problem_solving,
            "confidence": out.confidence,
            "composite_score": out.composite_score,
            "star_detected": out.star_detected,
            "weak_signal": out.weak_signal,
        }
        log = [_log_entry(node_id, agent_key, result)]
        return {
            "last_evaluation": snapshot,
            "score_history": state.get("score_history", []) + [snapshot],
            "current_node_id": node_id,
            "execution_log": state.get("execution_log", []) + log,
        }

    return node_fn


def make_router_node(db: AsyncSession, agent_key: AgentKey, node_id: str) -> NodeExecutor:
    async def node_fn(state: InterviewState) -> dict:
        decision_rules = await registry.get_router_decision_rules(db)
        agent = await registry.build_agent(db, agent_key)
        last_eval = state.get("last_evaluation") or {}
        result = await agent.run(RouterInput(
            composite_score=last_eval.get("composite_score", 60.0),
            weak_signal=last_eval.get("weak_signal", False),
            follow_up_count=state.get("follow_up_count", 0),
            questions_asked_count=len(state.get("questions_asked", [])),
            max_questions=settings.MAX_QUESTIONS_PER_INTERVIEW,
            min_questions=settings.MIN_QUESTIONS_PER_INTERVIEW,
            difficulty=str(state.get("difficulty", "medium")),
            decision_rules=decision_rules,
        ))
        action = result.output.action
        log = [_log_entry(node_id, agent_key, result)]
        patch: dict = {
            "next_action": action,
            "last_routing_reason": result.output.reason,
            "current_node_id": node_id,
            "execution_log": state.get("execution_log", []) + log,
        }
        # The router node is the one place that already knows which action
        # was chosen, before the branch is taken -- so it performs this
        # small, pure state mutation itself rather than needing a separate
        # "increase_difficulty" node type.
        if action == "increase_difficulty":
            patch["difficulty"] = _next_difficulty(state["difficulty"])
        return patch

    return node_fn


def make_coaching_node(db: AsyncSession, agent_key: AgentKey, node_id: str) -> NodeExecutor:
    async def node_fn(state: InterviewState) -> dict:
        coach = await registry.build_agent(db, agent_key)
        coach_result = await coach.run(CoachInput(
            question=state.get("current_question") or "",
            last_answer=state.get("last_candidate_answer"),
            weak_signal=(state.get("last_evaluation") or {}).get("weak_signal", True),
        ))
        interviewer = await registry.build_agent(db, AgentKey.INTERVIEWER)
        result = await interviewer.run(InterviewerInput(
            role_name=state["role_name"],
            mode=state["mode"],
            difficulty=state["difficulty"],
            stage=state.get("current_stage", "core"),
            questions_already_asked=state.get("questions_asked", []),
            last_candidate_answer=state.get("last_candidate_answer"),
            last_evaluation_summary=f"Coaching hint to weave in: {coach_result.output.hint}",
            is_followup=True,
            coaching_hint_enabled=True,
        ))
        log = [
            _log_entry(node_id, agent_key, coach_result),
            _log_entry(node_id, AgentKey.INTERVIEWER, result),
        ]
        return {
            "current_question": result.output.question,
            "last_hint": coach_result.output.hint,
            "follow_up_count": state.get("follow_up_count", 0) + 1,
            "current_node_id": node_id,
            "execution_log": state.get("execution_log", []) + log,
        }

    return node_fn


async def _end_finalize(state: InterviewState) -> dict:
    return {"should_end": True, "end_reason": state.get("last_routing_reason") or "interview_complete"}


_NODE_FACTORIES: dict[str, Callable[[AsyncSession, AgentKey, str], NodeExecutor]] = {
    "question": make_question_node,
    "evaluation": make_evaluation_node,
    "router": make_router_node,
    "coaching": make_coaching_node,
}


def compile_flow_graph(db: AsyncSession, flow: InterviewFlow) -> CompiledStateGraph:
    """Build and compile a fresh LangGraph StateGraph for one turn, bound to
    this call's DB session, from the published flow's graph_json."""
    graph_json = flow.graph_json or {"nodes": [], "edges": []}
    try:
        parsed = _parse_flow_structure(str(flow.id), json.dumps(graph_json, sort_keys=True))
    except (StopIteration, KeyError) as exc:
        raise FlowCompilationError(f"Flow {flow.id} is structurally incomplete: {exc}") from exc

    builder = StateGraph(InterviewState)
    wired_sources: set[str] = set()

    for node_id, node in parsed.nodes.items():
        ntype = node["type"]
        if ntype == "start":
            continue  # no real graph node -- START wiring is handled below
        if ntype == "end":
            builder.add_node(node_id, _end_finalize)
            builder.add_edge(node_id, END)
            wired_sources.add(node_id)
            continue
        agent_key = AgentKey(node["data"]["agent"])
        builder.add_node(node_id, _NODE_FACTORIES[ntype](db, agent_key, node_id))

    def entry_router(state: InterviewState) -> str:
        return parsed.start_target if not state.get("last_candidate_answer") else parsed.evaluation_node_id

    builder.add_conditional_edges(START, entry_router, [parsed.start_target, parsed.evaluation_node_id])

    # Explicit, non-router-sourced edges (e.g. evaluation -> router). Always
    # target the REAL node id, even for an "end"-typed target -- routing
    # straight to LangGraph's END here would skip that node's own
    # _end_finalize call and should_end would never get set. Each real node
    # (including "end" nodes, wired above) owns its own edge to END.
    for e in parsed.edges:
        src, tgt = e["source"], e["target"]
        src_type = parsed.nodes.get(src, {}).get("type")
        if src_type in ("start", "router"):
            continue  # start is wired via entry_router; router via conditional edges below
        builder.add_edge(src, tgt)
        wired_sources.add(src)

    # Router nodes: conditional edges keyed by the action RouterAgent returns.
    for node_id, action_lookup in parsed.router_action_lookups.items():
        def route_decision(state: InterviewState, _lookup=action_lookup) -> str:
            action = state.get("next_action") or "next_question"
            return _lookup.get(action) or _lookup["next_question"]

        targets = {target: target for target in action_lookup.values()}
        builder.add_conditional_edges(node_id, route_decision, targets)
        wired_sources.add(node_id)

    # Any real node that ended up with no outgoing edge (question / coaching
    # leaves -- see module docstring) implicitly ends this turn's graph run.
    for node_id, node in parsed.nodes.items():
        if node["type"] in ("start",) or node_id in wired_sources:
            continue
        builder.add_edge(node_id, END)

    return builder.compile()
