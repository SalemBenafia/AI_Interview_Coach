"""
app/modules/livekit/router.py
================================
WebRTC session endpoints (roles.txt -> User -> Interview Session ->
"Join WebRTC voice room"). Token issuance is intentionally split from
`app/modules/interviews/router.py`'s session-lifecycle endpoints so the
LiveKit-specific surface area (tokens, webhooks) stays in one place.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.core.settings import settings
from app.db.models import CandidateUser, InterviewSession, SessionStatus
from app.db.session import get_db
from app.modules.agents.engine import abandon_session
from app.modules.auth.dependencies import get_current_candidate_id
from app.modules.livekit.service import ensure_room, generate_join_token, verify_webhook

logger = structlog.get_logger()

_NON_TERMINAL_STATUSES = (SessionStatus.SCHEDULED, SessionStatus.CONNECTING, SessionStatus.ACTIVE, SessionStatus.PAUSED)

router = APIRouter(prefix="/livekit", tags=["WebRTC (LiveKit)"])


@router.post("/sessions/{session_id}/token/")
async def get_join_token(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    """Issue a real LiveKit join token so the browser can connect to the interview room."""
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.candidate_id == uuid.UUID(candidate_id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Interview session not found."})
    if session.status not in (SessionStatus.SCHEDULED, SessionStatus.CONNECTING, SessionStatus.ACTIVE, SessionStatus.PAUSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SESSION_NOT_JOINABLE", "message": f"Session is {session.status.value}; cannot join."},
        )
    if not session.livekit_room_name:
        raise HTTPException(500, detail={"code": "ROOM_NOT_PROVISIONED", "message": "Room has not been provisioned yet."})

    # Create the LiveKit room (idempotent) now — at the moment the candidate
    # actually clicks "Join". Provisioning here instead of at session-creation
    # time means the voice-agent job dispatch fires only when the user is ready,
    # so the agent is never busy with a stale room when the user arrives.
    await ensure_room(session.livekit_room_name)

    candidate_result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    candidate = candidate_result.scalar_one_or_none()
    display_name = f"{candidate.first_name} {candidate.last_name}" if candidate else "Candidate"

    token = generate_join_token(
        room_name=session.livekit_room_name,
        identity=str(candidate_id),
        display_name=display_name,
        can_publish=True,
        can_subscribe=True,
    )

    return success({
        "livekitUrl": settings.LIVEKIT_URL,
        "token": token,
        "roomName": session.livekit_room_name,
    })


@router.post("/webhook/", status_code=status.HTTP_200_OK)
async def livekit_webhook(
    request: Request,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """
    Receives real LiveKit room/participant lifecycle events (room_started,
    participant_left, room_finished, recording_started, ...). This is the
    server-side source of truth for disconnects: if a candidate closes the
    tab, loses connectivity, or the call otherwise drops without a clean
    "End interview" click, this webhook is what stops the session from
    staying stuck in ACTIVE forever. See also
    app.modules.interviews.sweep_tasks for a scheduled safety net that
    catches sessions this webhook never reaches (delivery failure, etc).
    """
    body = await request.body()
    try:
        event = verify_webhook(body, authorization)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_WEBHOOK_SIGNATURE", "message": str(exc)},
        )

    room_name = getattr(event.room, "name", None)
    logger.info("livekit_webhook_event", livekit_event=event.event, room=room_name)

    if event.event in ("participant_left", "room_finished") and room_name:
        result = await db.execute(
            select(InterviewSession).where(InterviewSession.livekit_room_name == room_name)
        )
        session = result.scalar_one_or_none()
        if session and session.status in _NON_TERMINAL_STATUSES:
            session.status = SessionStatus.ABANDONED
            session.ended_at = datetime.now(tz=timezone.utc)
            if session.started_at:
                session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
            session.ended_reason = "candidate_left" if event.event == "participant_left" else "room_closed"
            await db.commit()

            await abandon_session(str(session.id))

            from app.modules.interviews.tasks import generate_feedback_report
            generate_feedback_report.delay(str(session.id))

            logger.info(
                "livekit_webhook_session_abandoned",
                session_id=str(session.id),
                room=room_name,
                ended_reason=session.ended_reason,
            )

    return {"received": True}
