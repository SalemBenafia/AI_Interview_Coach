"""
tests/livekit/test_webhook.py
================================
Regression coverage for the stuck-"Active"-sessions fix
(app/modules/livekit/router.py::livekit_webhook). Before this fix, a
participant_left/room_finished LiveKit event was logged and discarded --
sessions never left ACTIVE when a candidate closed the tab or the call
dropped. This exercises the real DB transition against the actual dev
Postgres (uses get_db_context, not a mock session) and the real Redis
instance (delete_session_state is a real call); Celery's
generate_feedback_report.delay(...) fires for real too, since this suite
runs against the live dev stack rather than mocked infrastructure.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import CandidateUser, DifficultyLevel, InterviewMode, InterviewSession, SessionStatus
from app.db.session import get_db_context
from app.modules.livekit import router as livekit_router


class _FakeRoom:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeWebhookEvent:
    def __init__(self, event: str, room_name: str) -> None:
        self.event = event
        self.room = _FakeRoom(room_name)


class _FakeRequest:
    async def body(self) -> bytes:
        return b""


async def _make_session(db, *, room_name: str, status: SessionStatus) -> InterviewSession:
    candidate = (
        await db.execute(select(CandidateUser).where(CandidateUser.email == "demo@interview-coach.ai"))
    ).scalar_one()
    session = InterviewSession(
        candidate_id=candidate.id,
        mode=InterviewMode.MIXED,
        difficulty=DifficultyLevel.MID,
        status=status,
        livekit_room_name=room_name,
        started_at=datetime.now(tz=timezone.utc) - timedelta(minutes=5),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@pytest.mark.parametrize("livekit_event", ["participant_left", "room_finished"])
async def test_webhook_abandons_non_terminal_session(monkeypatch, livekit_event):
    room_name = f"test-room-{uuid.uuid4()}"

    async with get_db_context() as db:
        session = await _make_session(db, room_name=room_name, status=SessionStatus.ACTIVE)
        session_id = session.id

    try:
        monkeypatch.setattr(
            livekit_router, "verify_webhook",
            lambda body, auth: _FakeWebhookEvent(livekit_event, room_name),
        )

        async with get_db_context() as db:
            result = await livekit_router.livekit_webhook(_FakeRequest(), "fake-auth", db)
        assert result == {"received": True}

        async with get_db_context() as db:
            refreshed = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
            ).scalar_one()
            assert refreshed.status == SessionStatus.ABANDONED
            assert refreshed.ended_at is not None
            assert refreshed.ended_reason == ("candidate_left" if livekit_event == "participant_left" else "room_closed")
    finally:
        async with get_db_context() as db:
            row = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
            ).scalar_one_or_none()
            if row:
                await db.delete(row)


async def test_webhook_is_noop_for_already_terminal_session(monkeypatch):
    """A webhook arriving after the candidate already cleanly ended the
    interview (or the sweep task already caught it) must not clobber
    ended_at/ended_reason a second time."""
    room_name = f"test-room-{uuid.uuid4()}"

    async with get_db_context() as db:
        session = await _make_session(db, room_name=room_name, status=SessionStatus.COMPLETED)
        session.ended_at = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        session.ended_reason = "completed"
        session_id = session.id

    try:
        monkeypatch.setattr(
            livekit_router, "verify_webhook",
            lambda body, auth: _FakeWebhookEvent("participant_left", room_name),
        )

        async with get_db_context() as db:
            await livekit_router.livekit_webhook(_FakeRequest(), "fake-auth", db)

        async with get_db_context() as db:
            refreshed = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
            ).scalar_one()
            assert refreshed.status == SessionStatus.COMPLETED
            assert refreshed.ended_reason == "completed"  # unchanged, not overwritten to "candidate_left"
    finally:
        async with get_db_context() as db:
            row = (
                await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
            ).scalar_one_or_none()
            if row:
                await db.delete(row)


async def test_webhook_ignores_unknown_room(monkeypatch):
    """An event for a room with no matching session (e.g. a stale/replayed
    webhook) must not raise -- it's silently ignored."""
    monkeypatch.setattr(
        livekit_router, "verify_webhook",
        lambda body, auth: _FakeWebhookEvent("participant_left", f"nonexistent-{uuid.uuid4()}"),
    )
    async with get_db_context() as db:
        result = await livekit_router.livekit_webhook(_FakeRequest(), "fake-auth", db)
    assert result == {"received": True}
