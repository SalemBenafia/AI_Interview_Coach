"""
app/modules/agents/graph.py
==============================
Resolves ONE INTERVIEW TURN's compiled LangGraph `StateGraph` from the
session's PUBLISHED InterviewFlow (technologies.txt §4 — "LangGraph: state
machine for interviews, branching logic, memory-based decision system").

The actual node-by-node topology, per-node agent execution, and router
wiring are no longer hardcoded in Python here — they are compiled fresh
from InterviewFlow.graph_json by app/modules/agents/flow_compiler.py. This
module is now a thin resolver: given a flow id, load the (immutable, once
published) InterviewFlow row and hand it to the compiler.

Why "one turn" rather than the whole interview as a single graph run: a
live voice interview is fundamentally turn-based — the graph must pause and
wait for the candidate's next spoken answer, which arrives over
WebRTC/WebSocket as a separate request entirely. Cross-turn memory (the
InterviewState) is persisted in Redis between invocations by the engine
(app/modules/agents/engine.py) — this module only resolves and compiles the
graph; it holds no state of its own.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InterviewFlow
from app.modules.agents.flow_compiler import FlowCompilationError, compile_flow_graph

__all__ = ["FlowCompilationError", "build_turn_graph"]


async def build_turn_graph(db: AsyncSession, flow_id: str):
    """Load the session's published flow and compile it into a fresh,
    executable per-turn LangGraph, bound to this request's DB session."""
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == uuid.UUID(flow_id)))
    flow = result.scalar_one_or_none()
    if not flow:
        raise FlowCompilationError(f"Flow {flow_id} not found.")
    return compile_flow_graph(db, flow)
