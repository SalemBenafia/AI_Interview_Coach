"""
app/modules/agents/flow_contracts.py
=======================================
The single source of truth for what a flow node/edge is allowed to contain.
Both flow_validation.py (publish-time gate) and flow_compiler.py (runtime
compilation) import from here, so the contract can never drift between
"what we validate" and "what we execute" — the two failure modes that made
the old flow builder's JSON purely decorative (see InterviewFlow's
docstring in app/db/models.py).

Node types shrink to exactly six: two structural markers (start/end) and
four agent-executing types. There is no more "knowledge" node type — the
Interviewer agent reads the candidate's own CandidateKnowledgeEntry rows
directly as part of the "question" node (see flow_compiler.py); there is no
standalone retrieval step and no vector database anywhere in this system.
"""
from __future__ import annotations

from typing import Literal

from app.db.models import AgentKey

NodeType = Literal["start", "question", "evaluation", "router", "coaching", "end"]

NODE_TYPES: frozenset[str] = frozenset({"start", "question", "evaluation", "router", "coaching", "end"})

# Node type -> the set of AgentKey values allowed in that node's data.agent.
# Modeled as a set (not a scalar) even though it's 1:1 today so a future
# second interviewer-shaped agent could be added without a data-shape change.
NODE_TYPE_AGENT_KEYS: dict[str, frozenset[AgentKey]] = {
    "start": frozenset(),
    "question": frozenset({AgentKey.INTERVIEWER}),
    "evaluation": frozenset({AgentKey.EVALUATOR}),
    "router": frozenset({AgentKey.ROUTER}),
    "coaching": frozenset({AgentKey.COACH}),
    "end": frozenset(),
}

# Node types whose data.agent is required (start/end are pure structural markers).
NODE_TYPES_REQUIRING_AGENT: frozenset[str] = frozenset({"question", "evaluation", "router", "coaching"})

# The fixed action vocabulary a router node's outgoing edges may use in
# edge.data.action. Mirrors app/modules/agents/router_agent.py's
# _VALID_ACTIONS verbatim — kept as a separate constant here so this module
# has no import-time dependency on router_agent.py's internals; the two are
# expected to always agree (a validation test asserts this — see
# backend/tests/agents/test_flow_validation.py).
ROUTER_ACTIONS: frozenset[str] = frozenset(
    {"ask_followup", "next_question", "increase_difficulty", "coaching", "end"}
)
