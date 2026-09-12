"""
app/modules/catalog/router.py
================================
Candidate-facing catalog browsing: pick difficulty, pick mode. Target
roles are no longer a browsable admin catalog — candidates author their
own (see app/modules/target_roles/router.py). Mutations on what remains
here live in app/modules/admin/content/router.py — this router is
read-only by design.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import DifficultyRule, InterviewMode
from app.db.session import get_db

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/modes/")
async def list_modes():
    """Static enum — exposed for the practice-setup wizard's dropdown."""
    return success([
        {"value": InterviewMode.BEHAVIORAL.value, "label": "Behavioral",
         "description": "STAR-method storytelling: \u201cTell me about a time you...\u201d"},
        {"value": InterviewMode.TECHNICAL.value, "label": "Technical",
         "description": "Role-specific technical depth questions."},
        {"value": InterviewMode.MIXED.value, "label": "Mixed",
         "description": "A blend of behavioral and technical questions."},
        {"value": InterviewMode.MOCK_HR_SCREENING.value, "label": "Mock HR Screening",
         "description": "A first-round recruiter call: background, motivation, fit."},
    ])


@router.get("/difficulty-levels/")
async def list_difficulty_levels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DifficultyRule).order_by(DifficultyRule.advance_score_threshold))
    rules = result.scalars().all()
    if not rules:
        # Sensible fallback if the admin hasn't configured custom rules yet.
        return success([
            {"value": "junior", "label": "Junior", "description": "Foundational questions, generous follow-ups."},
            {"value": "mid", "label": "Mid-level", "description": "Standard depth, some adaptive follow-ups."},
            {"value": "senior", "label": "Senior", "description": "High depth, pushes for trade-offs and metrics."},
        ])
    return success([
        {"value": r.level.value, "label": r.label, "description": r.description}
        for r in rules
    ])
