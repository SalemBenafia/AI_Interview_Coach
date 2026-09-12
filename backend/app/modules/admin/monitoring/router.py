"""
app/modules/admin/monitoring/router.py
=========================================
Admin -> Monitoring (roles.txt): live interview sessions, system health,
AI latency, STT/TTS performance, error logs.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.schemas import success
from app.core.redis import get_redis
from app.core.settings import settings
from app.db.models import AgentExecutionLog, CandidateUser, InterviewSession, SessionStatus
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role
from app.modules.livekit.service import generate_join_token

router = APIRouter(prefix="/admin/monitoring", tags=["Admin — Monitoring"])

_MONITORING_ROLES = ("super_admin", "platform_admin", "support")


def _classify_health(status_code: int) -> dict:
    """
    2xx -> ok. 401/403 -> error (bad/missing API key — not a transient
    issue). 429 -> degraded (reachable, just rate-limited right now, which
    is expected/normal on OpenRouter's free tier). Anything else 4xx/5xx ->
    degraded so a single bad response doesn't read as a hard outage.
    """
    if status_code < 300:
        return {"status": "ok", "httpStatus": status_code}
    if status_code in (401, 403):
        return {"status": "error", "httpStatus": status_code}
    if status_code == 429:
        return {"status": "degraded", "httpStatus": status_code, "detail": "rate limited"}
    return {"status": "degraded", "httpStatus": status_code}


@router.get("/live-sessions/")
async def list_live_sessions(
    admin: CurrentPrincipal = Depends(require_admin_role(*_MONITORING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.status.in_([SessionStatus.ACTIVE, SessionStatus.CONNECTING, SessionStatus.PAUSED]))
        .options(selectinload(InterviewSession.candidate), selectinload(InterviewSession.target_role))
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = result.scalars().all()
    return success([
        {
            "id": str(s.id),
            "status": s.status.value,
            "candidateName": f"{s.candidate.first_name} {s.candidate.last_name}",
            "targetRoleTitle": s.target_role.title if s.target_role else None,
            "mode": s.mode.value,
            "difficulty": s.difficulty.value,
            "questionsAsked": s.questions_asked,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "livekitRoomName": s.livekit_room_name,
        }
        for s in sessions
    ])


@router.post("/live-sessions/{session_id}/observe-token/")
async def get_observer_token(
    session_id: str,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MONITORING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Issue a real, listen-only LiveKit token so an admin can observe a live interview."""
    import uuid

    result = await db.execute(select(InterviewSession).where(InterviewSession.id == uuid.UUID(session_id)))
    session = result.scalar_one_or_none()
    if not session or not session.livekit_room_name:
        return success(None, message="Session not found or has no active room.")

    token = generate_join_token(
        room_name=session.livekit_room_name,
        identity=f"observer-{admin.id}",
        display_name="Admin Observer",
        can_publish=False,
        can_subscribe=True,
    )
    return success({"livekitUrl": settings.LIVEKIT_URL, "token": token, "roomName": session.livekit_room_name})


@router.get("/health/")
async def system_health(admin: CurrentPrincipal = Depends(require_admin_role(*_MONITORING_ROLES))):
    """Real connectivity checks against every backing service."""
    checks: dict[str, dict] = {}

    try:
        await get_redis().ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}

    async with httpx.AsyncClient(timeout=5) as client:
        # Groq needs the Authorization header — also doubles as a real check
        # that GROQ_API_KEY is valid, not just that the API is up.
        try:
            r = await client.get(
                f"{settings.GROQ_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            )
            checks["groq"] = _classify_health(r.status_code)
        except Exception as exc:
            checks["groq"] = {"status": "error", "detail": str(exc)}

        for name, url in [
            ("whisper_stt", f"{settings.WHISPER_SERVICE_URL}/health"),
            ("piper_tts", f"{settings.PIPER_TTS_URL}/health"),
            ("sentiment_service", f"{settings.SENTIMENT_SERVICE_URL}/health"),
            ("livekit", settings.LIVEKIT_HTTP_URL),
        ]:
            try:
                r = await client.get(url)
                checks[name] = _classify_health(r.status_code)
            except Exception as exc:
                checks[name] = {"status": "error", "detail": str(exc)}

    overall_ok = all(c["status"] == "ok" for c in checks.values())
    return success({"overall": "ok" if overall_ok else "degraded", "services": checks})


@router.get("/error-logs/")
async def list_error_logs(
    admin: CurrentPrincipal = Depends(require_admin_role(*_MONITORING_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentExecutionLog)
        .where(AgentExecutionLog.success == False)
        .order_by(AgentExecutionLog.timestamp.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return success([
        {
            "id": str(l.id),
            "sessionId": str(l.session_id) if l.session_id else None,
            "agentKey": l.agent_key.value,
            "nodeId": l.node_id,
            "errorMessage": l.error_message,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ])
