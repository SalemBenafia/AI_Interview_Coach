"""
app/modules/admin/analytics/tasks.py
=======================================
Nightly rollup (Celery beat, see app/core/celery_app.py) that powers the
admin analytics trend chart without re-scanning the full interview history
on every dashboard load.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select

from app.core.celery_app import celery_app
from app.db.models import CandidateUser, DailyMetricSnapshot, InterviewFeedbackRating, InterviewSession, SessionStatus
from app.db.session import get_db_context

logger = structlog.get_logger()


@celery_app.task(name="app.modules.admin.analytics.tasks.compute_daily_metrics_snapshot")
def compute_daily_metrics_snapshot() -> None:
    asyncio.run(_compute_snapshot_async())


async def _compute_snapshot_async() -> None:
    today = datetime.now(tz=timezone.utc).date()
    yesterday = today - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    async with get_db_context() as db:
        total_interviews = (await db.execute(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.created_at >= day_start, InterviewSession.created_at < day_end
            )
        )).scalar_one()

        completed_interviews = (await db.execute(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.created_at >= day_start, InterviewSession.created_at < day_end,
                InterviewSession.status == SessionStatus.COMPLETED,
            )
        )).scalar_one()

        active_users = (await db.execute(
            select(func.count(func.distinct(CandidateUser.id))).where(
                CandidateUser.last_login_at >= day_start, CandidateUser.last_login_at < day_end
            )
        )).scalar_one()

        new_users = (await db.execute(
            select(func.count()).select_from(CandidateUser).where(
                CandidateUser.created_at >= day_start, CandidateUser.created_at < day_end
            )
        )).scalar_one()

        avg_score = (await db.execute(
            select(func.avg(InterviewSession.overall_score)).where(
                InterviewSession.created_at >= day_start, InterviewSession.created_at < day_end,
                InterviewSession.overall_score.isnot(None),
            )
        )).scalar_one()

        avg_rating = (await db.execute(
            select(func.avg(InterviewFeedbackRating.score)).where(
                InterviewFeedbackRating.submitted_at >= day_start, InterviewFeedbackRating.submitted_at < day_end
            )
        )).scalar_one()

        completion_rate = round((completed_interviews / total_interviews) * 100, 1) if total_interviews else None

        existing = await db.execute(select(DailyMetricSnapshot).where(DailyMetricSnapshot.snapshot_date == yesterday))
        snapshot = existing.scalar_one_or_none()
        if not snapshot:
            snapshot = DailyMetricSnapshot(snapshot_date=yesterday)
            db.add(snapshot)

        snapshot.total_interviews = total_interviews
        snapshot.completed_interviews = completed_interviews
        snapshot.active_users = active_users
        snapshot.new_users = new_users
        snapshot.avg_overall_score = round(avg_score, 1) if avg_score is not None else None
        snapshot.completion_rate = completion_rate
        snapshot.avg_feedback_rating = round(avg_rating, 2) if avg_rating is not None else None

        await db.commit()

    logger.info("daily_metrics_snapshot_computed", date=yesterday.isoformat())
