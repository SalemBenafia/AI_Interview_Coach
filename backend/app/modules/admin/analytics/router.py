"""
app/modules/admin/analytics/router.py
========================================
Admin -> Analytics (metrics.txt §2 -- "Is the AI system performing well at
scale?"). Real-time KPIs are computed directly from Postgres with SQL
aggregation; the historical trend chart reads the nightly DailyMetricSnapshot
rollup (app/modules/admin/analytics/tasks.py) so the dashboard stays fast
regardless of how many interviews have ever run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import (
    AgentExecutionLog,
    CandidateUser,
    DailyMetricSnapshot,
    InterviewFeedbackRating,
    InterviewSession,
    InterviewTurn,
    SessionStatus,
    TurnSpeaker,
)
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role

router = APIRouter(prefix="/admin/analytics", tags=["Admin — Analytics"])

_ANALYTICS_ROLES = ("super_admin", "platform_admin", "ai_manager", "support")


@router.get("/overview/")
async def get_overview(
    admin: CurrentPrincipal = Depends(require_admin_role(*_ANALYTICS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(tz=timezone.utc)
    last_30_days = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count()).select_from(CandidateUser))).scalar_one()

    dau_cutoff = now - timedelta(days=1)
    dau = (await db.execute(
        select(func.count()).select_from(CandidateUser).where(CandidateUser.last_login_at >= dau_cutoff)
    )).scalar_one()
    mau = (await db.execute(
        select(func.count()).select_from(CandidateUser).where(CandidateUser.last_login_at >= now - timedelta(days=30))
    )).scalar_one()

    total_interviews = (await db.execute(
        select(func.count()).select_from(InterviewSession).where(InterviewSession.created_at >= last_30_days)
    )).scalar_one()
    completed_interviews = (await db.execute(
        select(func.count()).select_from(InterviewSession).where(
            InterviewSession.created_at >= last_30_days, InterviewSession.status == SessionStatus.COMPLETED
        )
    )).scalar_one()
    completion_rate = round((completed_interviews / total_interviews) * 100, 1) if total_interviews else None

    avg_score = (await db.execute(
        select(func.avg(InterviewSession.overall_score)).where(
            InterviewSession.created_at >= last_30_days, InterviewSession.overall_score.isnot(None)
        )
    )).scalar_one()

    avg_latency = (await db.execute(
        select(func.avg(AgentExecutionLog.latency_ms)).where(AgentExecutionLog.timestamp >= last_30_days)
    )).scalar_one()

    avg_rating = (await db.execute(
        select(func.avg(InterviewFeedbackRating.score)).where(InterviewFeedbackRating.submitted_at >= last_30_days)
    )).scalar_one()

    return success({
        "totalUsers": total_users,
        "dau": dau,
        "mau": mau,
        "interviewsLast30Days": total_interviews,
        "completedInterviewsLast30Days": completed_interviews,
        "completionRate": completion_rate,
        "avgOverallScore": round(avg_score, 1) if avg_score is not None else None,
        "avgAiLatencyMs": round(avg_latency, 0) if avg_latency is not None else None,
        "avgFeedbackRating": round(avg_rating, 2) if avg_rating is not None else None,
    })


@router.get("/agent-performance/")
async def get_agent_performance(
    admin: CurrentPrincipal = Depends(require_admin_role(*_ANALYTICS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent latency, success rate, and call volume (metrics.txt §B.7)."""
    result = await db.execute(
        select(
            AgentExecutionLog.agent_key,
            func.count().label("calls"),
            func.avg(AgentExecutionLog.latency_ms).label("avg_latency_ms"),
            func.sum(func.cast(AgentExecutionLog.success, Integer)).label("successes"),
        ).group_by(AgentExecutionLog.agent_key)
    )
    rows = result.all()
    return success([
        {
            "agentKey": row.agent_key.value,
            "calls": row.calls,
            "avgLatencyMs": round(row.avg_latency_ms, 0) if row.avg_latency_ms is not None else None,
            "successRate": round((row.successes / row.calls) * 100, 1) if row.calls else None,
        }
        for row in rows
    ])


@router.get("/trend/")
async def get_trend(
    days: int = Query(default=30, ge=1, le=365),
    admin: CurrentPrincipal = Depends(require_admin_role(*_ANALYTICS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).date()
    result = await db.execute(
        select(DailyMetricSnapshot)
        .where(DailyMetricSnapshot.snapshot_date >= cutoff)
        .order_by(DailyMetricSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()
    return success([
        {
            "date": s.snapshot_date.isoformat(),
            "totalInterviews": s.total_interviews,
            "completedInterviews": s.completed_interviews,
            "activeUsers": s.active_users,
            "newUsers": s.new_users,
            "avgOverallScore": s.avg_overall_score,
            "avgAiLatencyMs": s.avg_ai_latency_ms,
            "completionRate": s.completion_rate,
        }
        for s in snapshots
    ])


@router.get("/token-usage/")
async def get_token_usage(
    days: int = Query(default=30, ge=1, le=365),
    admin: CurrentPrincipal = Depends(require_admin_role(*_ANALYTICS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    AI token consumption breakdown from AgentExecutionLog.tokens_used --
    every graph node execution already records this, it just wasn't
    surfaced anywhere before this endpoint. Deliberately just raw token
    counts (no $/token cost estimation) -- this is usage visibility, not a
    billing system.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    by_agent_result = await db.execute(
        select(
            AgentExecutionLog.agent_key,
            AgentExecutionLog.model_name,
            func.sum(AgentExecutionLog.tokens_used).label("total_tokens"),
            func.count().label("calls"),
        )
        .where(AgentExecutionLog.timestamp >= cutoff, AgentExecutionLog.tokens_used.isnot(None))
        .group_by(AgentExecutionLog.agent_key, AgentExecutionLog.model_name)
        .order_by(func.sum(AgentExecutionLog.tokens_used).desc())
    )
    by_agent = [
        {
            "agentKey": row.agent_key.value,
            "modelName": row.model_name,
            "totalTokens": int(row.total_tokens or 0),
            "calls": row.calls,
        }
        for row in by_agent_result.all()
    ]

    daily_result = await db.execute(
        select(
            func.date(AgentExecutionLog.timestamp).label("day"),
            func.sum(AgentExecutionLog.tokens_used).label("total_tokens"),
        )
        .where(AgentExecutionLog.timestamp >= cutoff, AgentExecutionLog.tokens_used.isnot(None))
        .group_by(func.date(AgentExecutionLog.timestamp))
        .order_by(func.date(AgentExecutionLog.timestamp).asc())
    )
    daily_totals = [
        {"date": row.day.isoformat(), "totalTokens": int(row.total_tokens or 0)}
        for row in daily_result.all()
    ]

    return success({"byAgent": by_agent, "dailyTotals": daily_totals})


@router.get("/sentiment-distribution/")
async def get_sentiment_distribution(
    days: int = Query(default=30, ge=1, le=365),
    admin: CurrentPrincipal = Depends(require_admin_role(*_ANALYTICS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Platform-wide candidate sentiment distribution across recent interview
    turns (app.modules.signals.analyzer) -- surfaces the sentiment signal
    at the platform level, complementing the per-session view on the
    candidate's own report (app.modules.interviews.router.get_report).
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(InterviewTurn.sentiment, func.count())
        .where(
            InterviewTurn.speaker == TurnSpeaker.CANDIDATE,
            InterviewTurn.sentiment.isnot(None),
            InterviewTurn.timestamp >= cutoff,
        )
        .group_by(InterviewTurn.sentiment)
    )
    rows = result.all()
    total = sum(count for _, count in rows) or 1
    return success([
        {"label": label, "count": count, "percentage": round(count / total * 100, 1)}
        for label, count in rows
    ])
