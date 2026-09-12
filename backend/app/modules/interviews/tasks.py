"""
app/modules/interviews/tasks.py
==================================
Background generation of the post-interview coaching report
(roles.txt -> AI Sub-Agent Architecture -> Feedback Agent). Runs the real
Feedback Agent (an LLM call) plus the MetricsEngine score rollup, renders
the real PDF, uploads it to MinIO, and queues the "your report is ready"
email.
"""
from __future__ import annotations

import asyncio
import io
import uuid
from collections import Counter
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.db.models import (
    CandidateUser,
    InterviewFeedbackReport,
    InterviewSession,
    InterviewTurn,
)
from app.db.session import get_db_context
from app.modules.agents.llm_client import AgentOutputParseError, AgentServiceError
from app.modules.agents.registry import build_agent, get_feedback_coaching_style
from app.modules.agents.schemas import FeedbackInput
from app.modules.interviews.report_pdf import build_report_pdf
from app.modules.metrics.engine import MetricsEngine
from app.modules.signals.analyzer import compute_speech_metrics
from app.modules.storage.object_store import upload_bytes

logger = structlog.get_logger()


@celery_app.task(
    name="app.modules.interviews.tasks.generate_feedback_report",
    bind=True,
    max_retries=3,
    default_retry_delay=20,
)
def generate_feedback_report(self, session_id: str) -> None:
    try:
        asyncio.run(_generate_feedback_report_async(session_id))
    except (AgentServiceError, AgentOutputParseError) as exc:
        logger.warning("feedback_report_retry", session_id=session_id, error=str(exc))
        raise self.retry(exc=exc)


async def _generate_feedback_report_async(session_id: str) -> None:
    from app.db.models import AgentKey

    async with get_db_context() as db:
        result = await db.execute(
            select(InterviewSession)
            .where(InterviewSession.id == uuid.UUID(session_id))
            .options(selectinload(InterviewSession.target_role), selectinload(InterviewSession.turns).selectinload(InterviewTurn.evaluation))
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.warning("feedback_report_session_missing", session_id=session_id)
            return

        candidate_result = await db.execute(select(CandidateUser).where(CandidateUser.id == session.candidate_id))
        candidate = candidate_result.scalar_one_or_none()

        # --- Roll up scores with the real MetricsEngine (not the LLM) ---
        engine = MetricsEngine()
        scores = engine.compute_session_scores(session.turns)
        session.overall_score = scores.overall
        session.communication_score = scores.communication
        session.technical_score = scores.technical
        session.behavioral_score = scores.behavioral
        session.confidence_score = scores.confidence
        session.star_method_score = scores.star_method

        # --- Real (non-ML) speech metrics from the full candidate transcript ---
        candidate_turns = [t for t in session.turns if t.speaker.value == "candidate"]
        candidate_text = " ".join(t.text for t in candidate_turns)
        if candidate_text.strip() and session.duration_seconds:
            speech_metrics = compute_speech_metrics(candidate_text, float(session.duration_seconds))
            session.avg_words_per_minute = speech_metrics.words_per_minute
            session.filler_word_count = speech_metrics.filler_word_count

        # --- Sentiment distribution across candidate turns (signals.analyzer,
        # populated live per-turn by the interview engine) -- a secondary
        # emotional-tone signal, not folded into any score. Computed here
        # rather than stored, so it's derived fresh from InterviewTurn rows
        # each time a report is (re)generated. ---
        candidate_sentiments = [t.sentiment for t in candidate_turns if t.sentiment]
        sentiment_summary = None
        if candidate_sentiments:
            counts = Counter(candidate_sentiments)
            total = len(candidate_sentiments)
            sentiment_summary = ", ".join(
                f"{label} {round(count / total * 100)}%" for label, count in counts.most_common()
            )

        # --- Real Feedback Agent call ---
        transcript = [{"speaker": t.speaker.value, "text": t.text} for t in session.turns]
        score_history = [
            {
                "composite_score": t.evaluation.composite_score,
                "star_detected": t.evaluation.star_detected,
                "weak_signal": t.evaluation.weak_signal,
            }
            for t in session.turns
            if t.evaluation is not None
        ]
        coaching_style = await get_feedback_coaching_style(db)
        agent = await build_agent(db, AgentKey.FEEDBACK)
        result = await agent.run(FeedbackInput(
            role_name=session.target_role.title if session.target_role else "the target role",
            mode=session.mode.value,
            transcript=transcript,
            score_history=score_history,
            coaching_style=coaching_style,
            sentiment_summary=sentiment_summary,
        ))
        feedback = result.output

        existing = await db.execute(
            select(InterviewFeedbackReport).where(InterviewFeedbackReport.session_id == session.id)
        )
        report = existing.scalar_one_or_none()
        if not report:
            report = InterviewFeedbackReport(session_id=session.id)
            db.add(report)

        report.summary = feedback.summary
        report.strengths = feedback.strengths
        report.weaknesses = feedback.weaknesses
        report.suggestions = feedback.suggestions
        report.example_better_answers = [b.model_dump() for b in feedback.example_better_answers]
        report.recommended_practice = feedback.recommended_practice
        report.coaching_style = coaching_style
        report.generated_at = datetime.now(tz=timezone.utc)

        # --- Render and upload the real PDF ---
        pdf_bytes = build_report_pdf(
            candidate_name=f"{candidate.first_name} {candidate.last_name}" if candidate else "Candidate",
            role_name=session.target_role.title if session.target_role else "Target Role",
            mode=session.mode.value,
            difficulty=session.difficulty.value,
            generated_at=report.generated_at,
            overall_score=session.overall_score,
            communication_score=session.communication_score,
            technical_score=session.technical_score,
            behavioral_score=session.behavioral_score,
            confidence_score=session.confidence_score,
            summary=report.summary,
            strengths=report.strengths,
            weaknesses=report.weaknesses,
            suggestions=report.suggestions,
            recommended_practice=report.recommended_practice,
            example_better_answers=report.example_better_answers,
            sentiment_summary=sentiment_summary,
        )
        object_key = f"reports/{session.id}.pdf"
        report.pdf_url = await upload_bytes(
            bucket="reports", object_key=object_key, data=pdf_bytes, content_type="application/pdf"
        )

        await db.commit()

    if candidate and candidate.notification_prefs and candidate.notification_prefs.get("email_report_ready", True):
        from app.modules.notifications.tasks import send_report_ready_email
        send_report_ready_email.delay(candidate.email, session_id)
