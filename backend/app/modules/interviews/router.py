"""
app/modules/interviews/router.py
===================================
Candidate-facing interview session lifecycle (roles.txt -> User Role ->
Interview Session / Feedback & Reports / History).

This router owns session CRUD and lifecycle transitions. The actual
turn-by-turn conversation happens over WebRTC, driven by the voice worker
(app/voice_worker/worker.py) which calls app.modules.agents.engine
directly -- this router never invokes the engine itself except indirectly
through status checks the voice worker respects (see PAUSE below).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.schemas import paginated, success
from app.db.models import (
    CandidateTargetRole,
    DifficultyLevel,
    FlowStatus,
    InterviewFeedbackRating,
    InterviewFlow,
    InterviewMode,
    InterviewSession,
    InterviewTurn,
    SessionStatus,
    TurnSpeaker,
)
from app.db.session import get_db
from app.modules.agents.engine import abandon_session, pause_session
from app.modules.auth.dependencies import get_current_candidate_id
from app.modules.livekit.service import end_room
from app.modules.storage.object_store import ObjectStoreError, get_presigned_url

logger = structlog.get_logger()

router = APIRouter(prefix="/interviews", tags=["Interviews"])


# --- Schemas -------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    target_role_id: Optional[uuid.UUID] = None
    flow_id: Optional[uuid.UUID] = None
    mode: InterviewMode = InterviewMode.MIXED
    difficulty: DifficultyLevel = DifficultyLevel.MID
    live_coaching_enabled: bool = False
    recording_consent: bool = False


class RatingRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: Optional[str] = None


def _serialize_session(s: InterviewSession) -> dict:
    return {
        "id": str(s.id),
        "status": s.status.value,
        "mode": s.mode.value,
        "difficulty": s.difficulty.value,
        "targetRoleId": str(s.target_role_id) if s.target_role_id else None,
        "targetRoleTitle": s.target_role.title if s.target_role else None,
        "flowId": str(s.flow_id) if s.flow_id else None,
        "livekitRoomName": s.livekit_room_name,
        "currentStage": s.current_stage,
        "currentQuestion": s.current_question,
        "questionsAsked": s.questions_asked,
        "startedAt": s.started_at.isoformat() if s.started_at else None,
        "endedAt": s.ended_at.isoformat() if s.ended_at else None,
        "endedReason": s.ended_reason,
        "durationSeconds": s.duration_seconds,
        "overallScore": s.overall_score,
        "communicationScore": s.communication_score,
        "technicalScore": s.technical_score,
        "behavioralScore": s.behavioral_score,
        "confidenceScore": s.confidence_score,
        "createdAt": s.created_at.isoformat(),
    }


# --- Create / list ---------------------------------------------------------

@router.post("/sessions/", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateSessionRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role: Optional[CandidateTargetRole] = None
    if payload.target_role_id:
        # Ownership-scoped: target roles are private, candidate-owned data.
        # A candidate must never be able to start a session against another
        # candidate's target role by guessing an id.
        result = await db.execute(
            select(CandidateTargetRole).where(
                CandidateTargetRole.id == payload.target_role_id,
                CandidateTargetRole.candidate_id == uuid.UUID(candidate_id),
            )
        )
        target_role = result.scalar_one_or_none()
        if not target_role:
            raise HTTPException(404, detail={"code": "TARGET_ROLE_NOT_FOUND", "message": "Target role not found."})

    flow: Optional[InterviewFlow] = None
    if payload.flow_id:
        result = await db.execute(
            select(InterviewFlow).where(InterviewFlow.id == payload.flow_id, InterviewFlow.status == FlowStatus.PUBLISHED)
        )
        flow = result.scalar_one_or_none()
        if not flow:
            raise HTTPException(404, detail={"code": "FLOW_NOT_FOUND", "message": "Interview flow not found."})
    else:
        # Global, one-per-mode resolution: the flow an admin marked as the
        # default for this InterviewMode (see admin/flows/router.py's
        # publish_flow, which enforces at most one per mode).
        result = await db.execute(
            select(InterviewFlow).where(
                InterviewFlow.mode == payload.mode,
                InterviewFlow.status == FlowStatus.PUBLISHED,
                InterviewFlow.is_default == True,
            )
        )
        flow = result.scalar_one_or_none()
        if not flow:
            raise HTTPException(409, detail={
                "code": "NO_FLOW_CONFIGURED",
                "message": "No published interview flow is configured for this mode yet. Please contact support.",
            })

    session = InterviewSession(
        candidate_id=uuid.UUID(candidate_id),
        target_role_id=target_role.id if target_role else None,
        flow_id=flow.id,
        flow_version=flow.version,
        mode=payload.mode,
        difficulty=payload.difficulty,
        status=SessionStatus.SCHEDULED,
        recording_consent=payload.recording_consent,
        current_stage="warmup",
    )
    db.add(session)
    await db.flush()

    room_name = f"interview-{session.id}"
    session.livekit_room_name = room_name
    await db.commit()

    # Room is NOT provisioned here. It is created lazily in the token endpoint
    # when the candidate actually clicks "Join" (see livekit/router.py).
    # Creating the room here caused the voice-agent job to be dispatched before
    # the user was ready: if the agent was initialising a subprocess for any
    # other room, the CPU load exceeded the 0.7 threshold and the dispatch was
    # refused — the new room would never get an agent, leaving the candidate in
    # silence for the entire session.

    return success({"sessionId": str(session.id), "livekitRoomName": room_name}, message="Interview session created.")


@router.get("/sessions/")
async def list_sessions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(InterviewSession)
        .where(InterviewSession.candidate_id == uuid.UUID(candidate_id))
        .options(selectinload(InterviewSession.target_role))
    )
    if status_filter:
        query = query.where(InterviewSession.status == SessionStatus(status_filter))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.order_by(InterviewSession.created_at.desc()).offset((page - 1) * limit).limit(limit)
    sessions = (await db.execute(query)).scalars().all()

    return paginated([_serialize_session(s) for s in sessions], page=page, limit=limit, total=total)


@router.get("/sessions/{session_id}/")
async def get_session(
    session_id: uuid.UUID,
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
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Interview session not found."})
    return success(_serialize_session(session))


@router.get("/sessions/{session_id}/transcript/")
async def get_transcript(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.candidate_id == uuid.UUID(candidate_id)
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Interview session not found."})

    turns_result = await db.execute(
        select(InterviewTurn).where(InterviewTurn.session_id == session_id).order_by(InterviewTurn.turn_number)
    )
    turns = turns_result.scalars().all()
    return success([
        {
            "turnNumber": t.turn_number,
            "speaker": t.speaker.value,
            "text": t.text,
            "isFollowup": t.is_followup,
            "timestamp": t.timestamp.isoformat(),
            "sentiment": t.sentiment,
            "sentimentScore": t.sentiment_score,
        }
        for t in turns
    ])


# --- Lifecycle transitions --------------------------------------------------

@router.post("/sessions/{session_id}/pause/")
async def pause_interview(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, candidate_id)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(409, detail={"code": "NOT_ACTIVE", "message": "Only an active session can be paused."})
    session.status = SessionStatus.PAUSED
    await db.commit()
    await pause_session(str(session.id))
    return success({}, message="Interview paused.")


@router.post("/sessions/{session_id}/resume/")
async def resume_interview(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, candidate_id)
    if session.status != SessionStatus.PAUSED:
        raise HTTPException(409, detail={"code": "NOT_PAUSED", "message": "Only a paused session can be resumed."})
    session.status = SessionStatus.ACTIVE
    await db.commit()
    return success({}, message="Interview resumed.")


@router.post("/sessions/{session_id}/end/")
async def end_interview_early(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, candidate_id)
    if session.status in (SessionStatus.COMPLETED, SessionStatus.ABANDONED, SessionStatus.FAILED):
        return success({}, message="Interview already ended.")

    session.status = SessionStatus.ABANDONED
    session.ended_at = datetime.now(tz=timezone.utc)
    if session.started_at:
        session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
    await db.commit()

    await abandon_session(str(session.id))
    if session.livekit_room_name:
        try:
            await end_room(session.livekit_room_name)
        except Exception:
            pass  # Room may already be empty/closed -- not a hard failure for the candidate.

    from app.modules.interviews.tasks import generate_feedback_report
    generate_feedback_report.delay(str(session.id))

    return success({}, message="Interview ended. Your feedback report is being generated.")


# --- Feedback & ratings ------------------------------------------------------

@router.get("/sessions/{session_id}/report/")
async def get_report(
    session_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models import InterviewFeedbackReport

    session = await _get_owned_session(db, session_id, candidate_id)
    result = await db.execute(select(InterviewFeedbackReport).where(InterviewFeedbackReport.session_id == session.id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={"code": "REPORT_PENDING", "message": "Your feedback report is still being generated."},
        )
    pdf_download_url = None
    if report.pdf_url:
        # report.pdf_url stores upload_bytes()'s stable internal reference
        # ("bucket/object_key"), not a fetchable URL -- MinIO objects are
        # private, so every request needs a freshly time-limited presigned
        # URL rather than serving that raw reference straight to the browser.
        bucket_name, _, object_key = report.pdf_url.partition("/")
        try:
            pdf_download_url = await get_presigned_url(bucket=bucket_name, object_key=object_key)
        except ObjectStoreError:
            logger.error("report_pdf_presign_failed", session_id=str(session.id), pdf_url=report.pdf_url)

    # Secondary emotional-tone signal, computed fresh from InterviewTurn rows
    # on every fetch (not stored on the report) -- see signals.analyzer.
    sentiment_rows = await db.execute(
        select(InterviewTurn.sentiment, func.count())
        .where(
            InterviewTurn.session_id == session.id,
            InterviewTurn.speaker == TurnSpeaker.CANDIDATE,
            InterviewTurn.sentiment.isnot(None),
        )
        .group_by(InterviewTurn.sentiment)
    )
    sentiment_distribution = {label: count for label, count in sentiment_rows.all()} or None

    return success({
        "summary": report.summary,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "suggestions": report.suggestions,
        "exampleBetterAnswers": report.example_better_answers,
        "recommendedPractice": report.recommended_practice,
        "coachingStyle": report.coaching_style,
        "pdfUrl": pdf_download_url,
        "generatedAt": report.generated_at.isoformat(),
        "sentimentDistribution": sentiment_distribution,
        "scores": {
            "overall": session.overall_score,
            "communication": session.communication_score,
            "technical": session.technical_score,
            "behavioral": session.behavioral_score,
            "confidence": session.confidence_score,
            "starMethod": session.star_method_score,
        },
    })


@router.post("/sessions/{session_id}/rating/", status_code=status.HTTP_201_CREATED)
async def submit_rating(
    session_id: uuid.UUID,
    payload: RatingRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, candidate_id)

    existing = await db.execute(
        select(InterviewFeedbackRating).where(InterviewFeedbackRating.session_id == session.id)
    )
    rating = existing.scalar_one_or_none()
    if rating:
        rating.score = payload.score
        rating.comment = payload.comment
    else:
        db.add(InterviewFeedbackRating(
            session_id=session.id,
            candidate_id=uuid.UUID(candidate_id),
            score=payload.score,
            comment=payload.comment,
        ))
    await db.commit()
    return success({}, message="Thanks for your feedback.")


# --- Helpers -----------------------------------------------------------------

async def _get_owned_session(db: AsyncSession, session_id: uuid.UUID, candidate_id: str) -> InterviewSession:
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.candidate_id == uuid.UUID(candidate_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Interview session not found."})
    return session


# --- Candidate progress dashboard (metrics.txt §1 -- User Dashboard) --------

@router.get("/me/stats/")
async def get_my_stats(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    """
    'Am I improving as a candidate?' -- metrics.txt §8. Returns the score
    trend across completed sessions plus the weakest scoring dimension so
    the dashboard can recommend what to practice next.
    """
    result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.candidate_id == uuid.UUID(candidate_id),
            InterviewSession.status == SessionStatus.COMPLETED,
        )
        .order_by(InterviewSession.ended_at.asc())
    )
    sessions = result.scalars().all()

    trend = [
        {
            "sessionId": str(s.id),
            "date": s.ended_at.isoformat() if s.ended_at else s.created_at.isoformat(),
            "overallScore": s.overall_score,
        }
        for s in sessions
    ]

    dimension_totals = {"communication": [], "technical": [], "behavioral": [], "confidence": []}
    for s in sessions:
        if s.communication_score is not None:
            dimension_totals["communication"].append(s.communication_score)
        if s.technical_score is not None:
            dimension_totals["technical"].append(s.technical_score)
        if s.behavioral_score is not None:
            dimension_totals["behavioral"].append(s.behavioral_score)
        if s.confidence_score is not None:
            dimension_totals["confidence"].append(s.confidence_score)

    averages = {
        k: round(sum(v) / len(v), 1) if v else None
        for k, v in dimension_totals.items()
    }
    weakest = min(
        (k for k, v in averages.items() if v is not None),
        key=lambda k: averages[k],
        default=None,
    )

    recommended_practice = {
        "communication": "Practice mock HR screening interviews to sharpen clarity and pacing.",
        "technical": "Run a few more technical-mode interviews at your current role.",
        "behavioral": "Practice behavioral interviews focused on the STAR method.",
        "confidence": "Try a junior-difficulty warm-up session to rebuild confidence before going harder.",
    }.get(weakest)

    return success({
        "totalCompletedInterviews": len(sessions),
        "scoreTrend": trend,
        "averageScoresByDimension": averages,
        "weakestDimension": weakest,
        "recommendedPractice": recommended_practice,
    })
