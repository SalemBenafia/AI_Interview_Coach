"""
app/modules/admin/users/router.py
====================================
Admin -> User Management: view, search, suspend, activate, delete
candidates; view a candidate's interview history, target roles, and
extracted knowledge. Admin visibility here is READ-ONLY — admins can see
everything about a candidate (requirement: "admin can view all candidature
informations"), but can never author or edit a candidate's target roles or
knowledge (see app/modules/target_roles/router.py, which is the only
module that can mutate that data, and is itself candidate-owned/scoped).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.schemas import paginated, success
from app.db.models import (
    AuditLog,
    CandidateKnowledgeEntry,
    CandidateTargetRole,
    CandidateUser,
    InterviewSession,
)
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role

router = APIRouter(prefix="/admin/users", tags=["Admin — Users"])

_MANAGE_ROLES = ("super_admin", "platform_admin", "support")


class SuspendRequest(BaseModel):
    reason: Optional[str] = None


def _serialize_candidate(c: CandidateUser) -> dict:
    return {
        "id": str(c.id),
        "email": c.email,
        "firstName": c.first_name,
        "lastName": c.last_name,
        "isActive": c.is_active,
        "preferredLanguage": c.preferred_language.value,
        "lastLoginAt": c.last_login_at.isoformat() if c.last_login_at else None,
        "createdAt": c.created_at.isoformat(),
    }


@router.get("/")
async def list_candidates(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    query = select(CandidateUser).where(CandidateUser.is_deleted == False)
    if search:
        like = f"%{search}%"
        query = query.where(or_(
            CandidateUser.email.ilike(like),
            CandidateUser.first_name.ilike(like),
            CandidateUser.last_name.ilike(like),
        ))
    if is_active is not None:
        query = query.where(CandidateUser.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.order_by(CandidateUser.created_at.desc()).offset((page - 1) * limit).limit(limit)
    candidates = (await db.execute(query)).scalars().all()

    return paginated([_serialize_candidate(c) for c in candidates], page=page, limit=limit, total=total)


@router.get("/{candidate_id}/")
async def get_candidate(
    candidate_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    return success(_serialize_candidate(candidate))


@router.get("/{candidate_id}/sessions/")
async def get_candidate_sessions(
    candidate_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.candidate_id == candidate_id)
        .options(selectinload(InterviewSession.target_role))
        .order_by(InterviewSession.created_at.desc())
        .limit(100)
    )
    sessions = result.scalars().all()
    return success([
        {
            "id": str(s.id),
            "status": s.status.value,
            "mode": s.mode.value,
            "difficulty": s.difficulty.value,
            "targetRoleId": str(s.target_role_id) if s.target_role_id else None,
            "targetRoleTitle": s.target_role.title if s.target_role else None,
            "overallScore": s.overall_score,
            "createdAt": s.created_at.isoformat(),
        }
        for s in sessions
    ])


# --- Candidate target roles + knowledge (read-only admin visibility) --------

def _serialize_target_role_for_admin(t: CandidateTargetRole, include_fields: bool = False) -> dict:
    data = {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "status": t.status.value,
        "isActive": t.is_active,
        "createdAt": t.created_at.isoformat(),
    }
    if include_fields:
        data["fields"] = [
            {
                "id": str(f.id),
                "fieldTitle": f.field_title,
                "fieldDescription": f.field_description,
                "sortOrder": f.sort_order,
            }
            for f in sorted(t.fields, key=lambda f: f.sort_order)
        ]
    return data


@router.get("/{candidate_id}/target-roles/")
async def get_candidate_target_roles(
    candidate_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateTargetRole)
        .where(CandidateTargetRole.candidate_id == candidate_id)
        .options(selectinload(CandidateTargetRole.fields))
        .order_by(CandidateTargetRole.created_at.desc())
    )
    roles = result.scalars().all()
    return success([_serialize_target_role_for_admin(t) for t in roles])


@router.get("/{candidate_id}/target-roles/{target_role_id}/")
async def get_candidate_target_role_detail(
    candidate_id: uuid.UUID,
    target_role_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateTargetRole)
        .where(CandidateTargetRole.id == target_role_id, CandidateTargetRole.candidate_id == candidate_id)
        .options(selectinload(CandidateTargetRole.fields))
    )
    target_role = result.scalar_one_or_none()
    if not target_role:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Target role not found."})
    return success(_serialize_target_role_for_admin(target_role, include_fields=True))


@router.get("/{candidate_id}/target-roles/{target_role_id}/knowledge/")
async def get_candidate_target_role_knowledge(
    candidate_id: uuid.UUID,
    target_role_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    owned = await db.execute(
        select(CandidateTargetRole.id).where(
            CandidateTargetRole.id == target_role_id, CandidateTargetRole.candidate_id == candidate_id
        )
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Target role not found."})

    result = await db.execute(
        select(CandidateKnowledgeEntry)
        .where(CandidateKnowledgeEntry.target_role_id == target_role_id)
        .order_by(CandidateKnowledgeEntry.created_at.asc())
    )
    entries = result.scalars().all()
    return success([
        {
            "id": str(e.id),
            "category": e.category,
            "topic": e.topic,
            "summary": e.summary,
            "timesCovered": e.times_covered,
        }
        for e in entries
    ])


@router.post("/{candidate_id}/suspend/")
async def suspend_candidate(
    candidate_id: uuid.UUID,
    payload: SuspendRequest,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    candidate.is_active = False
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="candidate.suspend", resource_type="candidate_user",
        resource_id=str(candidate_id), details={"reason": payload.reason},
    ))
    await db.commit()
    return success({}, message="Candidate suspended.")


@router.post("/{candidate_id}/activate/")
async def activate_candidate(
    candidate_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    candidate.is_active = True
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="candidate.activate",
        resource_type="candidate_user", resource_id=str(candidate_id),
    ))
    await db.commit()
    return success({}, message="Candidate activated.")


@router.delete("/{candidate_id}/")
async def delete_candidate(
    candidate_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role("super_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CandidateUser).where(CandidateUser.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    candidate.is_deleted = True
    candidate.deleted_at = datetime.now(tz=timezone.utc)
    candidate.is_active = False
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="candidate.delete",
        resource_type="candidate_user", resource_id=str(candidate_id),
    ))
    await db.commit()
    return success({}, message="Candidate deleted.")
