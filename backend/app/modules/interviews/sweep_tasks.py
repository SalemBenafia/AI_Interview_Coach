"""
app/modules/interviews/sweep_tasks.py
========================================
Safety-net sweep for interview sessions the LiveKit webhook never reached
(webhook delivery failure, voice worker crash without a clean room-leave
event, etc). Without this, a session that never gets a proper "end" signal
stays ACTIVE in Postgres forever, even though the interview is long over.

Runs on Celery beat (see app.core.celery_app) every 15 minutes and
force-abandons any session that's been sitting in ACTIVE/CONNECTING/PAUSED
with no turn activity for longer than STALE_SESSION_TIMEOUT_MINUTES.
InterviewSession.updated_at moves on every turn (engine._run_turn writes
status/questions_asked/current_question each turn), so it's a reliable
activity signal here.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.models import InterviewSession, SessionStatus
from app.db.session import get_db_context

logger = structlog.get_logger()

STALE_SESSION_TIMEOUT_MINUTES = 45

_STALE_STATUSES = (SessionStatus.ACTIVE, SessionStatus.CONNECTING, SessionStatus.PAUSED)


@celery_app.task(name="app.modules.interviews.sweep_tasks.sweep_stale_sessions")
def sweep_stale_sessions() -> None:
    asyncio.run(_sweep_async())


async def _sweep_async() -> list[str]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=STALE_SESSION_TIMEOUT_MINUTES)
    session_ids: list[str] = []

    async with get_db_context() as db:
        result = await db.execute(
            select(InterviewSession).where(
                InterviewSession.status.in_(_STALE_STATUSES),
                InterviewSession.updated_at < cutoff,
            )
        )
        stale_sessions = result.scalars().all()

        for stale_session in stale_sessions:
            stale_session.status = SessionStatus.ABANDONED
            stale_session.ended_at = datetime.now(tz=timezone.utc)
            if stale_session.started_at:
                stale_session.duration_seconds = int(
                    (stale_session.ended_at - stale_session.started_at).total_seconds()
                )
            stale_session.ended_reason = "timeout"
            session_ids.append(str(stale_session.id))

    if not session_ids:
        return session_ids

    # Redis/report cleanup happens outside the DB transaction above, after
    # it has committed, same as the pattern in interviews.router.end_interview_early.
    from app.modules.agents.engine import abandon_session
    from app.modules.interviews.tasks import generate_feedback_report

    for session_id in session_ids:
        await abandon_session(session_id)
        generate_feedback_report.delay(session_id)

    logger.info("stale_sessions_swept", count=len(session_ids), session_ids=session_ids)
    return session_ids
