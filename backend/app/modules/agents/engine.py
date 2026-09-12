"""
app/modules/agents/engine.py
===============================
The single entry point the rest of the backend calls to advance an
interview by one turn. Wires together:

  Redis (InterviewState memory) <-> graph.py (LangGraph turn graph) <-> Postgres (durable log)

This is intentionally the ONLY module that:
  * loads/saves InterviewState to Redis (app/core/redis.py)
  * invokes the compiled LangGraph turn graph
  * persists InterviewTurn / TurnEvaluation / AgentExecutionLog rows

Callers (the WebRTC/WebSocket turn handler in app/modules/ws/router.py, and
the REST session-control endpoints in app/modules/interviews/router.py)
never touch Redis or the graph directly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, update

from app.core.redis import (
    acquire_turn_lock,
    delete_session_state,
    get_session_state,
    publish_event,
    release_turn_lock,
    set_session_state,
)
from app.db.models import (
    AgentExecutionLog,
    AgentKey,
    CandidateKnowledgeEntry,
    InterviewSession,
    InterviewTurn,
    SessionStatus,
    TurnEvaluation,
    TurnSpeaker,
)
from app.modules.agents.flow_compiler import FlowCompilationError
from app.modules.agents.graph import build_turn_graph
from app.modules.agents.llm_client import AgentOutputParseError, AgentServiceError
from app.modules.agents.state import InterviewState, KnowledgeEntrySnapshot, initial_state
from app.modules.signals.analyzer import analyze_sentiment

logger = structlog.get_logger()


class InterviewEngineError(RuntimeError):
    """Raised for any unrecoverable engine-level failure surfaced to the API/WS layer."""


@dataclass
class TurnResult:
    ai_message: str               # the question/follow-up/hint the candidate hears next
    hint: Optional[str]
    should_end: bool
    end_reason: Optional[str]
    difficulty: str
    turn_number: int
    stage: str


async def _load_candidate_knowledge_context(
    db: AsyncSession, target_role_id: Optional[uuid.UUID]
) -> list[KnowledgeEntrySnapshot]:
    """Plain SQL filter, no vector search — a candidate's own knowledge for
    the target role they're interviewing against, least-covered first so
    the Interviewer agent naturally spreads coverage across repeat practice
    sessions rather than always grounding on the same entries."""
    if not target_role_id:
        return []
    result = await db.execute(
        select(CandidateKnowledgeEntry)
        .where(CandidateKnowledgeEntry.target_role_id == target_role_id)
        .order_by(CandidateKnowledgeEntry.times_covered.asc(), CandidateKnowledgeEntry.created_at.asc())
    )
    return [
        KnowledgeEntrySnapshot(id=str(e.id), category=e.category, topic=e.topic, summary=e.summary)
        for e in result.scalars().all()
    ]


async def start_session(
    db: AsyncSession,
    session: InterviewSession,
    *,
    role_name: str,
    live_coaching_enabled: bool = False,
) -> TurnResult:
    """Initialise Redis state for a brand-new session and produce the opening question."""
    knowledge_entries = await _load_candidate_knowledge_context(db, session.target_role_id)
    state = initial_state(
        session_id=str(session.id),
        candidate_id=str(session.candidate_id),
        role_name=role_name,
        mode=session.mode.value,
        difficulty=session.difficulty.value,
        flow_id=str(session.flow_id) if session.flow_id else None,
        target_role_id=str(session.target_role_id) if session.target_role_id else None,
        knowledge_entries=knowledge_entries,
        live_coaching_enabled=live_coaching_enabled,
    )
    return await _run_turn(db, session, state, candidate_answer=None)


async def submit_answer(
    db: AsyncSession,
    session: InterviewSession,
    candidate_answer: str,
) -> TurnResult:
    """Advance an in-progress session by one turn given the candidate's latest spoken answer."""
    import asyncio as _asyncio

    session_id = str(session.id)

    if not await acquire_turn_lock(session_id):
        raise InterviewEngineError("A turn is already being processed for this session. Please wait.")

    try:
        # Retry loop: the voice pipeline can detect candidate speech and call
        # submit_answer while start_session (which runs a Groq API call to
        # generate the opening question) is still in-flight and hasn't yet
        # persisted state to Redis. Retry for up to ~3 s to let it finish.
        state: Optional[dict] = None
        for _wait in (0, 1.0, 2.0):
            if _wait:
                await _asyncio.sleep(_wait)
            state = await get_session_state(session_id)
            if state is not None:
                break

        if state is None:
            raise InterviewEngineError(
                "No active interview state found for this session - it may have expired or already ended."
            )
        return await _run_turn(db, session, state, candidate_answer=candidate_answer)
    finally:
        await release_turn_lock(session_id)


async def _run_turn(
    db: AsyncSession,
    session: InterviewSession,
    state: InterviewState,
    candidate_answer: Optional[str],
) -> TurnResult:
    session_id = str(session.id)
    turn_number = state.get("turn_number", 0) + 1

    if turn_number == 1:
        from datetime import datetime, timezone
        session.status = SessionStatus.ACTIVE
        session.started_at = datetime.now(tz=timezone.utc)

    candidate_turn_id: Optional[str] = None
    if candidate_answer is not None:
        state["last_candidate_answer"] = candidate_answer
        state["transcript"] = state.get("transcript", []) + [
            {"speaker": "candidate", "text": candidate_answer, "turn_number": turn_number}
        ]
        candidate_turn = InterviewTurn(
            session_id=session.id,
            turn_number=turn_number,
            speaker=TurnSpeaker.CANDIDATE,
            text=candidate_answer,
        )
        sentiment = await analyze_sentiment(candidate_answer)
        if sentiment is not None:
            candidate_turn.sentiment = sentiment.label
            candidate_turn.sentiment_score = sentiment.score
        db.add(candidate_turn)
        await db.flush()
        candidate_turn_id = str(candidate_turn.id)

    if not session.flow_id:
        raise InterviewEngineError("This interview session has no flow configured. Please contact support.")

    try:
        graph = await build_turn_graph(db, str(session.flow_id))
        new_state: InterviewState = await graph.ainvoke(state)  # type: ignore[assignment]
    except FlowCompilationError as exc:
        # Should only happen from a bug in publish-time validation itself or
        # a manual DB edit bypassing it (see flow_validation.py) -- hard-fail
        # loudly rather than silently falling back to some other graph.
        logger.error("flow_compilation_failed", session_id=session_id, flow_id=str(session.flow_id), error=str(exc))
        raise InterviewEngineError(
            "This interview flow is currently unavailable. Please contact support or try a different session."
        ) from exc
    except (AgentServiceError, AgentOutputParseError) as exc:
        logger.error("interview_turn_failed", session_id=session_id, error=str(exc))
        raise InterviewEngineError(
            "Our AI interviewer is temporarily unavailable. Please try again in a moment."
        ) from exc

    # Persist the evaluation for the candidate's turn we just scored.
    if candidate_turn_id and new_state.get("last_evaluation"):
        ev = new_state["last_evaluation"]
        db.add(TurnEvaluation(
            turn_id=uuid.UUID(candidate_turn_id),
            session_id=session.id,
            relevance=ev.get("relevance"),
            clarity=ev.get("clarity"),
            communication=ev.get("communication"),
            technical_depth=ev.get("technical_depth"),
            problem_solving=ev.get("problem_solving"),
            confidence=ev.get("confidence"),
            composite_score=ev.get("composite_score"),
            star_detected=ev.get("star_detected", False),
            weak_signal=ev.get("weak_signal", False),
        ))

    ai_message = new_state.get("current_question") or "Thank you for your answer."
    new_state["transcript"] = new_state.get("transcript", []) + [
        {"speaker": "ai", "text": ai_message, "turn_number": turn_number}
    ]
    new_state["turn_number"] = turn_number

    ai_turn = InterviewTurn(
        session_id=session.id,
        turn_number=turn_number,
        speaker=TurnSpeaker.AI,
        text=ai_message,
        is_followup=(new_state.get("follow_up_count", 0) > 0 and new_state.get("next_action") != "next_question"),
    )
    db.add(ai_turn)
    await db.flush()

    # Drain the execution log produced by this turn's graph run.
    for entry in new_state.get("execution_log", []):
        db.add(AgentExecutionLog(
            session_id=session.id,
            turn_id=ai_turn.id if entry["agent_key"] != AgentKey.EVALUATOR.value else None,
            node_id=entry["node_id"],
            agent_key=AgentKey(entry["agent_key"]),
            model_name=entry.get("model_name"),
            tokens_used=entry.get("tokens_used"),
            latency_ms=entry.get("latency_ms", 0),
            success=entry.get("success", True),
            error_message=entry.get("error_message"),
        ))
    new_state["execution_log"] = []  # don't let the Redis blob grow unbounded

    # Increment times_covered for any candidate knowledge entries the
    # Interviewer grounded a question in this turn (flow_compiler.py's
    # make_question_node) -- lets the ordering in _load_candidate_knowledge_
    # context naturally spread coverage across repeat practice sessions.
    used_entry_ids = new_state.get("knowledge_entries_used_this_turn", [])
    if used_entry_ids:
        await db.execute(
            update(CandidateKnowledgeEntry)
            .where(CandidateKnowledgeEntry.id.in_([uuid.UUID(i) for i in used_entry_ids]))
            .values(times_covered=CandidateKnowledgeEntry.times_covered + 1)
        )
    new_state["knowledge_entries_used_this_turn"] = []

    # Update the session's live progress fields.
    session.current_stage = new_state.get("current_stage", session.current_stage)
    session.questions_asked = len(new_state.get("questions_asked", []))
    session.current_question = ai_message
    session.difficulty = session.difficulty.__class__(new_state["difficulty"])

    should_end = bool(new_state.get("should_end"))
    if should_end:
        from datetime import datetime, timezone
        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.now(tz=timezone.utc)
        if session.started_at:
            session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
        await delete_session_state(session_id)
    else:
        await set_session_state(session_id, dict(new_state))

    await db.commit()

    if should_end:
        from app.modules.interviews.tasks import generate_feedback_report
        generate_feedback_report.delay(session_id)

    if candidate_answer is not None:
        await publish_event(session_id, {
            "type": "candidate_turn",
            "session_id": session_id,
            "turn_number": turn_number,
            "text": candidate_answer,
        })

    await publish_event(session_id, {
        "type": "ai_turn",
        "session_id": session_id,
        "turn_number": turn_number,
        "text": ai_message,
        "hint": new_state.get("last_hint"),
        "should_end": should_end,
    })

    return TurnResult(
        ai_message=ai_message,
        hint=new_state.get("last_hint"),
        should_end=should_end,
        end_reason=new_state.get("end_reason"),
        difficulty=new_state["difficulty"],
        turn_number=turn_number,
        stage=new_state.get("current_stage", "core"),
    )


async def pause_session(session_id: str) -> None:
    state = await get_session_state(session_id)
    if state is not None:
        await set_session_state(session_id, state)  # state already in Redis; this just refreshes the TTL


async def abandon_session(session_id: str) -> None:
    await delete_session_state(session_id)
