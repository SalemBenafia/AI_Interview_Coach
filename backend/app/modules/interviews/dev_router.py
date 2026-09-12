"""
app/modules/interviews/dev_router.py
=======================================
Dev/test-only text-turn endpoint. The real interview loop only runs over
WebRTC voice, driven by the voice worker (app/voice_worker/llm_plugin.py)
calling app.modules.agents.engine directly -- there is no REST path to
advance a turn. That makes it impossible for automated tests (Playwright)
to exercise the real flow/router/evaluator/coach logic without synthesizing
audio through a real microphone.

This router bypasses ONLY the audio transport, not the agent logic itself
-- it calls the exact same engine.start_session/submit_answer functions the
voice worker calls, so a test driving this endpoint exercises the real
LangGraph flow compilation, the real Router decision rules, and (module
API keys permitting) real LLM calls, just with typed text instead of
speech-to-text output as input.

Mounted in app.main only when settings.is_development is True (see
create_app()) -- never present in a production deployment.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.schemas import success
from app.db.models import InterviewSession
from app.db.session import get_db
from app.modules.agents.engine import InterviewEngineError, start_session, submit_answer
from app.modules.auth.dependencies import get_current_candidate_id

router = APIRouter(prefix="/dev/interviews", tags=["Dev — Test-only"])


class DevTurnRequest(BaseModel):
    answer: str | None = None  # None -> start_session (turn 1), else submit_answer


@router.post("/sessions/{session_id}/turn/")
async def dev_submit_turn(
    session_id: uuid.UUID,
    payload: DevTurnRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.id == session_id, InterviewSession.candidate_id == uuid.UUID(candidate_id))
        .options(selectinload(InterviewSession.target_role))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Session not found."})

    try:
        if payload.answer is None:
            turn = await start_session(
                db, session, role_name=session.target_role.title if session.target_role else "this role"
            )
        else:
            turn = await submit_answer(db, session, payload.answer)
    except InterviewEngineError as exc:
        raise HTTPException(503, detail={"code": "ENGINE_ERROR", "message": str(exc)})

    return success({
        "aiMessage": turn.ai_message,
        "hint": turn.hint,
        "shouldEnd": turn.should_end,
        "endReason": turn.end_reason,
        "difficulty": turn.difficulty,
        "turnNumber": turn.turn_number,
        "stage": turn.stage,
    })
