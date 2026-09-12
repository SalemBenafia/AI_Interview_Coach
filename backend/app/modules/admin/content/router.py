"""
app/modules/admin/content/router.py
=======================================
Admin -> Content Management: Difficulty scaling only. Roles are no longer
admin-authored (candidates own their own target roles, see
app/modules/target_roles/) and Skills/Competencies had zero downstream
consumers anywhere in the codebase, so both were removed entirely along
with this module's old role/skill/competency CRUD sections.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import DifficultyLevel, DifficultyRule
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role

router = APIRouter(prefix="/admin/content", tags=["Admin — Content Management"])

_CONTENT_ROLES = ("super_admin", "platform_admin", "ai_manager", "flow_designer")


# --- Difficulty Rules (admin_ai_manage_ui.txt -> "Difficulty Scaling") ----------

class DifficultyRuleUpdate(BaseModel):
    label: Optional[str] = None
    advance_score_threshold: Optional[int] = None
    regress_score_threshold: Optional[int] = None
    description: Optional[str] = None


@router.get("/difficulty-rules/")
async def list_difficulty_rules(admin: CurrentPrincipal = Depends(require_admin_role(*_CONTENT_ROLES)), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DifficultyRule).order_by(DifficultyRule.advance_score_threshold))
    return success([
        {
            "id": str(r.id), "level": r.level.value, "label": r.label,
            "advanceScoreThreshold": r.advance_score_threshold,
            "regressScoreThreshold": r.regress_score_threshold,
            "description": r.description,
        }
        for r in result.scalars().all()
    ])


@router.patch("/difficulty-rules/{level}/")
async def update_difficulty_rule(
    level: DifficultyLevel,
    payload: DifficultyRuleUpdate,
    admin: CurrentPrincipal = Depends(require_admin_role(*_CONTENT_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DifficultyRule).where(DifficultyRule.level == level))
    rule = result.scalar_one_or_none()
    if not rule:
        rule = DifficultyRule(level=level, label=level.value.title())
        db.add(rule)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    await db.commit()
    return success({}, message="Difficulty rule updated.")
