"""
tests/agents/test_flow_validation.py
=======================================
Minimum-viable coverage for the publish-time hard gate
(app/modules/agents/flow_validation.py). Every published InterviewFlow
becomes the real, compiled, executable graph for every interview in that
mode (app/modules/agents/flow_compiler.py) -- a structurally broken flow
reaching validate_flow_graph() undetected would break the platform for an
entire InterviewMode, so each rejection case gets its own explicit test.
"""
from __future__ import annotations

import copy

from app.modules.agents.flow_contracts import ROUTER_ACTIONS
from app.modules.agents.flow_validation import validate_flow_graph
from app.modules.agents.router_agent import _VALID_ACTIONS


def _valid_graph() -> dict:
    """Mirrors backend/seed.py's _default_graph_json() -- one reusable
    question node, one evaluation node, one router with full action
    coverage, one coaching node, one end node."""
    return {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "q1", "type": "question", "position": {"x": 250, "y": 0}, "data": {"agent": "interviewer"}},
            {"id": "eval1", "type": "evaluation", "position": {"x": 500, "y": 0}, "data": {"agent": "evaluator"}},
            {"id": "router1", "type": "router", "position": {"x": 750, "y": 0}, "data": {"agent": "router"}},
            {"id": "coach1", "type": "coaching", "position": {"x": 750, "y": 200}, "data": {"agent": "coach"}},
            {"id": "end1", "type": "end", "position": {"x": 1000, "y": 0}, "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "q1"},
            {"id": "e2", "source": "eval1", "target": "router1"},
            {"id": "e3", "source": "router1", "target": "q1", "data": {"action": "ask_followup"}},
            {"id": "e4", "source": "router1", "target": "q1", "data": {"action": "next_question"}},
            {"id": "e5", "source": "router1", "target": "q1", "data": {"action": "increase_difficulty"}},
            {"id": "e6", "source": "router1", "target": "coach1", "data": {"action": "coaching"}},
            {"id": "e7", "source": "router1", "target": "end1", "data": {"action": "end"}},
        ],
    }


def test_router_action_vocabulary_matches_router_agent():
    """flow_contracts.ROUTER_ACTIONS is deliberately duplicated (not
    imported) from router_agent.py's _VALID_ACTIONS to avoid an import-time
    coupling -- this test is the guardrail that keeps the two in sync."""
    assert ROUTER_ACTIONS == _VALID_ACTIONS


def test_valid_minimal_flow_passes():
    assert validate_flow_graph(_valid_graph()) == []


def test_missing_start_node():
    graph = _valid_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["type"] != "start"]
    errors = validate_flow_graph(graph)
    assert any("no 'start' node" in e for e in errors)


def test_duplicate_start_nodes():
    graph = _valid_graph()
    graph["nodes"].append({"id": "start2", "type": "start", "position": {"x": 0, "y": 0}, "data": {}})
    errors = validate_flow_graph(graph)
    assert any("'start' nodes; exactly one is required" in e for e in errors)


def test_missing_evaluation_node():
    graph = _valid_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["type"] != "evaluation"]
    errors = validate_flow_graph(graph)
    assert any("no 'evaluation' node" in e for e in errors)


def test_missing_question_node():
    graph = _valid_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["type"] != "question"]
    errors = validate_flow_graph(graph)
    assert any("no 'question' node" in e for e in errors)


def test_edge_references_unknown_node():
    graph = _valid_graph()
    graph["edges"].append({"id": "bad", "source": "router1", "target": "ghost", "data": {"action": "coaching"}})
    errors = validate_flow_graph(graph)
    assert any("nonexistent target node 'ghost'" in e for e in errors)


def test_node_agent_not_allowed_for_type():
    graph = _valid_graph()
    for n in graph["nodes"]:
        if n["id"] == "q1":
            n["data"] = {"agent": "evaluator"}  # evaluator is not valid for a question node
    errors = validate_flow_graph(graph)
    assert any("cannot use agent 'evaluator'" in e for e in errors)


def test_node_missing_required_agent():
    graph = _valid_graph()
    for n in graph["nodes"]:
        if n["id"] == "q1":
            n["data"] = {}
    errors = validate_flow_graph(graph)
    assert any("missing a required agent" in e for e in errors)


def test_start_must_have_exactly_one_outgoing_edge():
    graph = _valid_graph()
    graph["edges"].append({"id": "e_extra", "source": "start", "target": "q1"})
    errors = validate_flow_graph(graph)
    assert any("'start' node must have exactly one outgoing edge" in e for e in errors)


def test_start_target_must_be_a_question_node():
    graph = _valid_graph()
    for e in graph["edges"]:
        if e["id"] == "e1":
            e["target"] = "eval1"
    errors = validate_flow_graph(graph)
    assert any("'start' node's outgoing edge must point to a 'question' node" in e for e in errors)


def test_evaluation_target_must_be_a_router_node():
    graph = _valid_graph()
    for e in graph["edges"]:
        if e["id"] == "e2":
            e["target"] = "coach1"
    errors = validate_flow_graph(graph)
    assert any("'evaluation' node's outgoing edge must point to a 'router' node" in e for e in errors)


def test_orphan_node_unreachable():
    graph = _valid_graph()
    graph["nodes"].append({
        "id": "orphan", "type": "coaching", "position": {"x": 0, "y": 0}, "data": {"agent": "coach"},
    })
    errors = validate_flow_graph(graph)
    assert any("Unreachable node(s)" in e and "orphan" in e for e in errors)


def test_no_path_to_end_node():
    graph = _valid_graph()
    graph["edges"] = [e for e in graph["edges"] if e["id"] != "e7"]  # drop the only edge reaching 'end1'
    errors = validate_flow_graph(graph)
    assert any("No path from 'start'/'evaluation' to any 'end' node" in e for e in errors)


def test_router_missing_action_coverage_no_fallback():
    graph = _valid_graph()
    graph["edges"] = [e for e in graph["edges"] if (e.get("data") or {}).get("action") != "next_question"]
    errors = validate_flow_graph(graph)
    assert any("no edge for action(s)" in e and "next_question" in e for e in errors)


def test_router_missing_action_coverage_with_fallback_passes():
    graph = _valid_graph()
    # Drop 'increase_difficulty' coverage but keep 'next_question' as a
    # catch-all -- matches RouterAgent's own default-to-next_question
    # behavior when no configured rule matches.
    graph["edges"] = [e for e in graph["edges"] if (e.get("data") or {}).get("action") != "increase_difficulty"]
    assert validate_flow_graph(graph) == []


def test_router_unknown_action_rejected():
    graph = _valid_graph()
    for e in graph["edges"]:
        if e["id"] == "e6":
            e["data"] = {"action": "teleport"}
    errors = validate_flow_graph(graph)
    assert any("unknown action(s)" in e and "teleport" in e for e in errors)


def test_does_not_mutate_input():
    graph = _valid_graph()
    snapshot = copy.deepcopy(graph)
    validate_flow_graph(graph)
    assert graph == snapshot
