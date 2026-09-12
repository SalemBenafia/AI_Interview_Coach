"""
app/modules/agents/flow_validation.py
========================================
Publish-time validation for InterviewFlow.graph_json. This is a hard gate:
app/modules/admin/flows/router.py's publish endpoint rejects a flow with a
422 (listing every problem found) unless validate_flow_graph() returns no
errors. Since a published flow becomes the REAL, compiled, executable
LangGraph for every candidate interviewing in that InterviewMode
(app/modules/agents/flow_compiler.py), a structurally broken flow would
break every interview on the platform for that mode — this check exists so
that can never reach a live session.
"""
from __future__ import annotations

from app.db.models import AgentKey
from app.modules.agents.flow_contracts import (
    NODE_TYPE_AGENT_KEYS,
    NODE_TYPES_REQUIRING_AGENT,
    ROUTER_ACTIONS,
)


def _bfs_reachable(entry_ids: set[str], adjacency: dict[str, list[str]]) -> set[str]:
    seen = set(entry_ids)
    queue = list(entry_ids)
    while queue:
        node_id = queue.pop()
        for target in adjacency.get(node_id, []):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def validate_flow_graph(graph_json: dict) -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    nodes = graph_json.get("nodes", []) if graph_json else []
    edges = graph_json.get("edges", []) if graph_json else []
    node_ids = {n.get("id") for n in nodes}
    node_by_id = {n.get("id"): n for n in nodes}

    # 1. Missing / duplicate entry & evaluation points, and at least one
    # question node -- flow_compiler.py's two entry paths (turn 1 vs. a
    # resuming turn) and question-asking both depend on these existing.
    start_nodes = [n for n in nodes if n.get("type") == "start"]
    if len(start_nodes) == 0:
        errors.append("Flow has no 'start' node.")
    elif len(start_nodes) > 1:
        errors.append(f"Flow has {len(start_nodes)} 'start' nodes; exactly one is required.")

    evaluation_nodes = [n for n in nodes if n.get("type") == "evaluation"]
    if len(evaluation_nodes) == 0:
        errors.append("Flow has no 'evaluation' node.")
    elif len(evaluation_nodes) > 1:
        errors.append(f"Flow has {len(evaluation_nodes)} 'evaluation' nodes; exactly one is required.")

    if not any(n.get("type") == "question" for n in nodes):
        errors.append("Flow has no 'question' node.")

    # 2. Edges referencing nonexistent nodes.
    has_dangling_edge = False
    for e in edges:
        if e.get("source") not in node_ids:
            errors.append(f"Edge '{e.get('id')}' references nonexistent source node '{e.get('source')}'.")
            has_dangling_edge = True
        if e.get("target") not in node_ids:
            errors.append(f"Edge '{e.get('id')}' references nonexistent target node '{e.get('target')}'.")
            has_dangling_edge = True

    # 3. node.data.agent validity against NODE_TYPE_AGENT_KEYS.
    for n in nodes:
        node_id = n.get("id")
        ntype = n.get("type")
        if ntype not in NODE_TYPE_AGENT_KEYS:
            errors.append(f"Node '{node_id}' has unknown type '{ntype}'.")
            continue
        if ntype not in NODE_TYPES_REQUIRING_AGENT:
            continue
        agent_value = (n.get("data") or {}).get("agent")
        if not agent_value:
            errors.append(f"Node '{node_id}' (type={ntype}) is missing a required agent.")
            continue
        try:
            agent_key = AgentKey(agent_value)
        except ValueError:
            errors.append(f"Node '{node_id}' has unknown agent '{agent_value}'.")
            continue
        allowed = NODE_TYPE_AGENT_KEYS[ntype]
        if agent_key not in allowed:
            errors.append(
                f"Node '{node_id}' (type={ntype}) cannot use agent '{agent_value}'; "
                f"allowed: {sorted(k.value for k in allowed)}."
            )

    # Only attempt the structure-dependent checks below once the graph is
    # sane enough to reason about (exactly one start, exactly one
    # evaluation, no dangling edges).
    structurally_sound = len(start_nodes) == 1 and len(evaluation_nodes) == 1 and not has_dangling_edge
    if not structurally_sound:
        return errors

    start_id = start_nodes[0]["id"]
    eval_id = evaluation_nodes[0]["id"]
    adjacency: dict[str, list[str]] = {}
    for e in edges:
        adjacency.setdefault(e["source"], []).append(e["target"])

    # 4. 'start' must have exactly one outgoing edge, to a 'question' node --
    # this is what a turn-1 (no answer yet) session enters.
    start_edges = adjacency.get(start_id, [])
    if len(start_edges) != 1:
        errors.append(f"'start' node must have exactly one outgoing edge; found {len(start_edges)}.")
    elif node_by_id.get(start_edges[0], {}).get("type") != "question":
        errors.append("'start' node's outgoing edge must point to a 'question' node.")

    # 5. 'evaluation' must have exactly one outgoing edge, to a 'router' node
    # -- every turn that evaluates an answer immediately routes on it.
    eval_edges = adjacency.get(eval_id, [])
    if len(eval_edges) != 1:
        errors.append(f"'evaluation' node must have exactly one outgoing edge; found {len(eval_edges)}.")
    elif node_by_id.get(eval_edges[0], {}).get("type") != "router":
        errors.append("'evaluation' node's outgoing edge must point to a 'router' node.")

    # 6/8. Orphan nodes + no path to an 'end' node. Reachability has TWO
    # roots, not one: turn 1 enters at 'start', but every later turn enters
    # directly at 'evaluation' (flow_compiler.py's entry_router) -- there is
    # deliberately no graph edge from a question node to the evaluation
    # node, since the question and its answer happen in separate turns.
    reachable = _bfs_reachable({start_id, eval_id}, adjacency)
    orphans = node_ids - reachable
    if orphans:
        errors.append(f"Unreachable node(s) (from 'start' or 'evaluation'): {sorted(orphans)}.")
    end_ids = {n.get("id") for n in nodes if n.get("type") == "end"}
    if not (end_ids & reachable):
        errors.append("No path from 'start'/'evaluation' to any 'end' node — the interview could loop forever.")

    # 7. Router node action-edge coverage: either every action is covered,
    # or an explicit 'next_question' fallback exists (mirrors RouterAgent's
    # own default-to-next_question behavior when no rule matches).
    for n in nodes:
        if n.get("type") != "router":
            continue
        node_id = n.get("id")
        router_edges = [e for e in edges if e.get("source") == node_id]
        declared_actions = {
            (e.get("data") or {}).get("action") for e in router_edges if (e.get("data") or {}).get("action")
        }
        unknown = declared_actions - ROUTER_ACTIONS
        if unknown:
            errors.append(f"Router node '{node_id}' has edge(s) with unknown action(s): {sorted(unknown)}.")
        missing = ROUTER_ACTIONS - declared_actions
        if missing and "next_question" not in declared_actions:
            errors.append(
                f"Router node '{node_id}' has no edge for action(s) {sorted(missing)} "
                f"and no 'next_question' fallback edge to default to."
            )

    return errors
