"""
tests/agents/test_flow_compiler.py
=====================================
Minimum-viable coverage for the dynamic flow compiler
(app/modules/agents/flow_compiler.py) -- this is now the single global
runtime path for every interview on the platform, and there is nothing
else in the repo that would catch a broken published flow before it
reached real candidates. Agent calls are stubbed (deterministic canned
outputs) so these tests exercise real graph wiring/traversal without
hitting Groq or a real database.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models import AgentKey
from app.modules.agents import flow_compiler
from app.modules.agents.schemas import CoachOutput, EvaluatorOutput, InterviewerOutput, RouterOutput
from tests.agents.test_flow_validation import _valid_graph


class _FakeResult:
    def __init__(self, output):
        self.output = output
        self.latency_ms = 1
        self.model_name = "fake"
        self.tokens_used = 0


class _FakeInterviewer:
    def __init__(self, knowledge_entry_id_used=None):
        self._entry_id = knowledge_entry_id_used

    async def run(self, agent_input):
        return _FakeResult(InterviewerOutput(
            question="Tell me about a challenging project.",
            is_followup=agent_input.is_followup,
            knowledge_entry_id_used=self._entry_id,
        ))


class _FakeEvaluator:
    async def run(self, agent_input):
        return _FakeResult(EvaluatorOutput(
            relevance=80, clarity=80, communication=80, technical_depth=80,
            problem_solving=80, confidence=80, composite_score=80, weak_signal=False,
        ))


class _FakeCoach:
    async def run(self, agent_input):
        return _FakeResult(CoachOutput(hint="Try the STAR method."))


class _ScriptedRouter:
    """Returns actions from a fixed script, one per call, defaulting to
    'end' once the script is exhausted so a test can never hang."""

    def __init__(self, actions: list[str]):
        self._actions = list(actions)

    async def run(self, agent_input):
        action = self._actions.pop(0) if self._actions else "end"
        return _FakeResult(RouterOutput(action=action, reason="scripted"))


class _FakeFlow:
    def __init__(self, graph_json: dict):
        self.id = uuid.uuid4()
        self.graph_json = graph_json


def _patch_registry(monkeypatch, *, router_actions, interviewer_knowledge_entry_id=None):
    interviewer = _FakeInterviewer(interviewer_knowledge_entry_id)
    evaluator = _FakeEvaluator()
    coach = _FakeCoach()
    router = _ScriptedRouter(router_actions)

    async def fake_build_agent(db, key):
        return {
            AgentKey.INTERVIEWER: interviewer,
            AgentKey.EVALUATOR: evaluator,
            AgentKey.ROUTER: router,
            AgentKey.COACH: coach,
        }[key]

    async def fake_get_evaluator_rubric(db):
        return []

    async def fake_get_router_decision_rules(db):
        return []

    monkeypatch.setattr(flow_compiler.registry, "build_agent", fake_build_agent)
    monkeypatch.setattr(flow_compiler.registry, "get_evaluator_rubric", fake_get_evaluator_rubric)
    monkeypatch.setattr(flow_compiler.registry, "get_router_decision_rules", fake_get_router_decision_rules)


def _initial_state() -> dict:
    return {
        "session_id": "s1", "candidate_id": "c1", "role_name": "Frontend Developer",
        "mode": "mixed", "difficulty": "mid", "current_stage": "core",
        "questions_asked": [], "follow_up_count": 0, "knowledge_entries": [],
        "covered_knowledge_entry_ids": [], "execution_log": [],
    }


async def test_compiled_graph_reaches_end_via_router():
    """The core correctness property: every reachable path through a valid
    published flow must actually terminate (should_end=True) within a
    bounded number of turns -- this is the live-ainvoke complement to
    flow_validation's static reachability check."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        _patch_registry(monkeypatch, router_actions=["next_question", "next_question", "end"])
        compiled = flow_compiler.compile_flow_graph(None, _FakeFlow(_valid_graph()))

        state = _initial_state()
        state = await compiled.ainvoke(state)  # turn 1: no answer yet -> first question
        assert state["current_question"] == "Tell me about a challenging project."
        assert not state.get("should_end")

        for _ in range(2):
            state["last_candidate_answer"] = "An answer."
            state = await compiled.ainvoke(state)

        state["last_candidate_answer"] = "Final answer."
        state = await compiled.ainvoke(state)
        assert state["should_end"] is True
        assert state["end_reason"] == "scripted"
    finally:
        monkeypatch.undo()


async def test_compiled_graph_reaches_end_via_coaching_path():
    """Exercises the one node type whose contract is more than 'one node
    type -> one agent': the coaching node calls BOTH the Coach and the
    Interviewer agent in sequence (see make_coaching_node)."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        _patch_registry(monkeypatch, router_actions=["coaching", "end"])
        compiled = flow_compiler.compile_flow_graph(None, _FakeFlow(_valid_graph()))

        state = _initial_state()
        state = await compiled.ainvoke(state)
        state["last_candidate_answer"] = "A weak answer."
        state = await compiled.ainvoke(state)  # router -> coaching -> (coach + interviewer) -> END
        assert state["last_hint"] == "Try the STAR method."
        assert not state.get("should_end")

        state["last_candidate_answer"] = "Better answer."
        state = await compiled.ainvoke(state)  # router -> end
        assert state["should_end"] is True
    finally:
        monkeypatch.undo()


async def test_invalid_flow_raises_compilation_error_not_silent_fallback():
    graph = _valid_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["type"] != "start"]  # now structurally invalid
    with pytest.raises(flow_compiler.FlowCompilationError):
        flow_compiler.compile_flow_graph(None, _FakeFlow(graph))


async def test_hallucinated_knowledge_entry_id_is_not_trusted():
    """The Interviewer agent's output is untrusted input -- a fabricated
    knowledge_entry_id_used must never reach engine.py's uuid.UUID(...)
    cast (see make_question_node's known_ids guard)."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        _patch_registry(monkeypatch, router_actions=["end"], interviewer_knowledge_entry_id="not-a-real-id")
        compiled = flow_compiler.compile_flow_graph(None, _FakeFlow(_valid_graph()))

        state = _initial_state()
        state["knowledge_entries"] = [{"id": "real-id-1", "category": "skill", "topic": "React", "summary": "..."}]
        state = await compiled.ainvoke(state)

        assert state.get("covered_knowledge_entry_ids", []) == []
        assert state.get("knowledge_entries_used_this_turn", []) == []
    finally:
        monkeypatch.undo()
