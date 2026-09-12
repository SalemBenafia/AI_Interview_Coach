"""
tests/interviews/test_sweep_tasks.py
=======================================
Regression coverage for the stuck-"Active"-sessions safety net
(app/modules/interviews/sweep_tasks.py). This is the second half of the
fix alongside the LiveKit webhook (tests/livekit/test_webhook.py) -- it
catches sessions the webhook never reached (delivery failure, worker crash
without a clean room-leave event, etc). Runs against the real dev Postgres
via get_db_context, same as the webhook test.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db.models import CandidateUser, DifficultyLevel, InterviewMode, InterviewSession, SessionStatus
from app.db.session import get_db_context
from app.modules.interviews.sweep_tasks import STALE_SESSION_TIMEOUT_MINUTES, _sweep_async


async def _make_session(db, *, status: SessionStatus, updated_minutes_ago: float) -> uuid.UUID:
    candidate = (
        await db.execute(select(CandidateUser).where(CandidateUser.email == "demo@interview-coach.ai"))
    ).scalar_one()
    session = InterviewSession(
        candidate_id=candidate.id,
        mode=InterviewMode.MIXED,
        difficulty=DifficultyLevel.MID,
        status=status,
        livekit_room_name=f"sweep-test-{uuid.uuid4()}",
        started_at=datetime.now(tz=timezone.utc) - timedelta(minutes=updated_minutes_ago + 5),
    )
    db.add(session)
    await db.flush()
    session_id = session.id

    # Explicit UPDATE, not an ORM attribute set + flush -- an explicit value
    # in .values() takes precedence over the column's onupdate=func.now(),
    # letting the test backdate updated_at the way a genuinely stale, real
    # session (last touched N minutes ago by engine._run_turn) would look.
    stale_at = datetime.now(tz=timezone.utc) - timedelta(minutes=updated_minutes_ago)
    await db.execute(
        update(InterviewSession).where(InterviewSession.id == session_id).values(updated_at=stale_at)
    )
    return session_id


async def test_sweep_abandons_stale_active_session():
    async with get_db_context() as db:
        stale_id = await _make_session(
            db, status=SessionStatus.ACTIVE, updated_minutes_ago=STALE_SESSION_TIMEOUT_MINUTES + 10
        )
        fresh_id = await _make_session(db, status=SessionStatus.ACTIVE, updated_minutes_ago=1)

    try:
        swept_ids = await _sweep_async()
        assert str(stale_id) in swept_ids
        assert str(fresh_id) not in swept_ids

        async with get_db_context() as db:
            stale_row = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == stale_id))
            ).scalar_one()
            assert stale_row.status == SessionStatus.ABANDONED
            assert stale_row.ended_reason == "timeout"
            assert stale_row.ended_at is not None

            fresh_row = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == fresh_id))
            ).scalar_one()
            assert fresh_row.status == SessionStatus.ACTIVE
            assert fresh_row.ended_at is None
    finally:
        async with get_db_context() as db:
            for sid in (stale_id, fresh_id):
                row = (await db.execute(select(InterviewSession).where(InterviewSession.id == sid))).scalar_one_or_none()
                if row:
                    await db.delete(row)


async def test_sweep_ignores_completed_and_abandoned_sessions():
    async with get_db_context() as db:
        completed_id = await _make_session(
            db, status=SessionStatus.COMPLETED, updated_minutes_ago=STALE_SESSION_TIMEOUT_MINUTES + 10
        )

    try:
        swept_ids = await _sweep_async()
        assert str(completed_id) not in swept_ids
    finally:
        async with get_db_context() as db:
            row = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == completed_id))
            ).scalar_one_or_none()
            if row:
                await db.delete(row)
