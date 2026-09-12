"""
app/core/celery_app.py
========================
Celery application — background processing for everything that should
NOT block the real-time interview loop:

* post-interview scoring aggregation
* feedback report generation (Feedback Agent runs here, not inline)
* transcript persistence / cleanup
* candidate target-role knowledge extraction (Knowledge Extraction Agent)
* nightly platform metrics snapshot (admin analytics)
* notification delivery (report-ready emails, reminders)

Broker + result backend are both Redis, per technologies.txt
("Celery + Redis").
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.core.settings import settings


@worker_process_init.connect
def _switch_to_null_pool(**kwargs: object) -> None:
    """Replace the shared asyncpg pool with NullPool in every forked worker.

    asyncpg connections are not safe to use across fork(). During ForkPoolWorker
    teardown there is no event loop, so the pool's cleanup path (greenlet_spawn →
    asyncpg close/cancel) raises the 'Exception terminating connection' error.
    NullPool opens a fresh connection per task and closes it synchronously after,
    leaving nothing to clean up at process exit.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import app.db.session as db

    # close=False: don't try to close inherited connections in the child —
    # the parent's event loop owns them and they are unusable here anyway.
    db.engine.dispose(close=False)
    db.engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=settings.DB_ECHO,
    )
    db.AsyncSessionLocal = async_sessionmaker(
        bind=db.engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


celery_app = Celery(
    "interview_coach",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.modules.interviews.tasks",
        "app.modules.interviews.sweep_tasks",
        "app.modules.target_roles.tasks",
        "app.modules.notifications.tasks",
        "app.modules.admin.analytics.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 10,
    # Recycle the worker process every 100 tasks to prevent memory creep
    # (LangGraph / transformers leave residual allocations after each run).
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
    # Never pre-fetch: with concurrency=1 on a 2-core box, holding extra
    # tasks in memory just wastes RAM without improving throughput.
    worker_prefetch_multiplier=1,
    # Acknowledge only after the task finishes so a killed worker doesn't
    # silently drop a feedback-generation job.
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "daily-platform-metrics-snapshot": {
        "task": "app.modules.admin.analytics.tasks.compute_daily_metrics_snapshot",
        "schedule": crontab(hour=0, minute=15),
    },
    "sweep-stale-interview-sessions": {
        "task": "app.modules.interviews.sweep_tasks.sweep_stale_sessions",
        "schedule": crontab(minute="*/15"),
    },
}
