"""
app/modules/target_roles/router.py
=====================================
Candidate-owned target roles + private knowledge memory. A candidate can
create many target roles (e.g. "Senior Backend Engineer", "Data Analyst
Internship"), each with an arbitrary number of freely add/edit/removable
(field_title, field_description) pairs they author themselves. Triggering
"analyze" distills those raw notes into structured CandidateKnowledgeEntry
rows (app/modules/target_roles/tasks.py) that the interview agents later
draw on to ground questions (see app/modules/agents/flow_compiler.py).

There is no admin authoring surface here at all, and no vector database —
every endpoint in this router is scoped to the requesting candidate's own
data. This is the single most important correctness property of this
module: every query below filters by candidate_id, not just by row id.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.schemas import success
from app.db.models import (
    CandidateKnowledgeEntry,
    CandidateTargetRole,
    CandidateTargetRoleField,
    TargetRoleStatus,
)
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_candidate_id

router = APIRouter(prefix="/target-roles", tags=["Target Roles"])


# --- Schemas -----------------------------------------------------------------

class CreateTargetRoleRequest(BaseModel):
    title: str
    description: Optional[str] = None


class UpdateTargetRoleRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreateFieldRequest(BaseModel):
    field_title: str
    field_description: str


class UpdateFieldRequest(BaseModel):
    field_title: Optional[str] = None
    field_description: Optional[str] = None
    sort_order: Optional[int] = None


def _serialize_target_role(t: CandidateTargetRole, include_fields: bool = False) -> dict:
    data = {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "status": t.status.value,
        "isActive": t.is_active,
        "createdAt": t.created_at.isoformat(),
        "updatedAt": t.updated_at.isoformat(),
    }
    if include_fields:
        data["fields"] = [_serialize_field(f) for f in sorted(t.fields, key=lambda f: f.sort_order)]
    return data


def _serialize_field(f: CandidateTargetRoleField) -> dict:
    return {
        "id": str(f.id),
        "fieldTitle": f.field_title,
        "fieldDescription": f.field_description,
        "sortOrder": f.sort_order,
    }


def _serialize_knowledge_entry(e: CandidateKnowledgeEntry) -> dict:
    return {
        "id": str(e.id),
        "category": e.category,
        "topic": e.topic,
        "summary": e.summary,
        "timesCovered": e.times_covered,
    }


async def _get_owned_target_role(
    db: AsyncSession, target_role_id: uuid.UUID, candidate_id: str, *, load_fields: bool = False
) -> CandidateTargetRole:
    query = select(CandidateTargetRole).where(
        CandidateTargetRole.id == target_role_id,
        CandidateTargetRole.candidate_id == uuid.UUID(candidate_id),
    )
    if load_fields:
        query = query.options(selectinload(CandidateTargetRole.fields))
    result = await db.execute(query)
    target_role = result.scalar_one_or_none()
    if not target_role:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Target role not found."})
    return target_role


def _mark_stale_if_analyzed(target_role: CandidateTargetRole) -> None:
    """Fields changed — any previously extracted knowledge is now stale."""
    if target_role.status in (TargetRoleStatus.READY, TargetRoleStatus.FAILED):
        target_role.status = TargetRoleStatus.DRAFT


# --- Target role CRUD ----------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_target_role(
    payload: CreateTargetRoleRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = CandidateTargetRole(
        candidate_id=uuid.UUID(candidate_id),
        title=payload.title,
        description=payload.description,
        status=TargetRoleStatus.DRAFT,
    )
    db.add(target_role)
    await db.commit()
    return success({"targetRoleId": str(target_role.id)}, message="Target role created.")


@router.get("/")
async def list_target_roles(
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateTargetRole)
        .where(
            CandidateTargetRole.candidate_id == uuid.UUID(candidate_id),
            CandidateTargetRole.is_active == True,
        )
        .order_by(CandidateTargetRole.created_at.desc())
    )
    roles = result.scalars().all()
    return success([_serialize_target_role(t) for t in roles])


@router.get("/{target_role_id}/")
async def get_target_role(
    target_role_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id, load_fields=True)
    return success(_serialize_target_role(target_role, include_fields=True))


@router.patch("/{target_role_id}/")
async def update_target_role(
    target_role_id: uuid.UUID,
    payload: UpdateTargetRoleRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id)
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(target_role, k, v)
    if "title" in changes or "description" in changes:
        _mark_stale_if_analyzed(target_role)
    await db.commit()
    return success({}, message="Target role updated.")


@router.delete("/{target_role_id}/")
async def delete_target_role(
    target_role_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id)
    await db.delete(target_role)
    await db.commit()
    return success({}, message="Target role deleted.")


# --- Dynamic fields --------------------------------------------------------------

@router.post("/{target_role_id}/fields/", status_code=status.HTTP_201_CREATED)
async def add_field(
    target_role_id: uuid.UUID,
    payload: CreateFieldRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id, load_fields=True)
    next_sort_order = max((f.sort_order for f in target_role.fields), default=-1) + 1
    field = CandidateTargetRoleField(
        target_role_id=target_role.id,
        field_title=payload.field_title,
        field_description=payload.field_description,
        sort_order=next_sort_order,
    )
    db.add(field)
    _mark_stale_if_analyzed(target_role)
    await db.commit()
    return success({"fieldId": str(field.id)}, message="Field added.")


@router.patch("/{target_role_id}/fields/{field_id}/")
async def update_field(
    target_role_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: UpdateFieldRequest,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id)
    result = await db.execute(
        select(CandidateTargetRoleField).where(
            CandidateTargetRoleField.id == field_id,
            CandidateTargetRoleField.target_role_id == target_role.id,
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Field not found."})
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(field, k, v)
    _mark_stale_if_analyzed(target_role)
    await db.commit()
    return success({}, message="Field updated.")


@router.delete("/{target_role_id}/fields/{field_id}/")
async def delete_field(
    target_role_id: uuid.UUID,
    field_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id)
    result = await db.execute(
        select(CandidateTargetRoleField).where(
            CandidateTargetRoleField.id == field_id,
            CandidateTargetRoleField.target_role_id == target_role.id,
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Field not found."})
    await db.delete(field)
    _mark_stale_if_analyzed(target_role)
    await db.commit()
    return success({}, message="Field deleted.")


# --- AI analysis into private knowledge -------------------------------------------

@router.post("/{target_role_id}/analyze/", status_code=status.HTTP_202_ACCEPTED)
async def analyze_target_role(
    target_role_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id, load_fields=True)
    if not target_role.fields:
        raise HTTPException(
            400, detail={"code": "NO_FIELDS", "message": "Add at least one field before analyzing."}
        )
    target_role.status = TargetRoleStatus.ANALYZING
    await db.commit()

    from app.modules.target_roles.tasks import analyze_target_role as analyze_target_role_task
    analyze_target_role_task.delay(str(target_role.id))

    return success({"status": "analyzing"}, message="Analyzing your background into knowledge entries.")


@router.get("/{target_role_id}/knowledge/")
async def list_target_role_knowledge(
    target_role_id: uuid.UUID,
    candidate_id: str = Depends(get_current_candidate_id),
    db: AsyncSession = Depends(get_db),
):
    target_role = await _get_owned_target_role(db, target_role_id, candidate_id)
    result = await db.execute(
        select(CandidateKnowledgeEntry)
        .where(CandidateKnowledgeEntry.target_role_id == target_role.id)
        .order_by(CandidateKnowledgeEntry.created_at.asc())
    )
    entries = result.scalars().all()
    return success([_serialize_knowledge_entry(e) for e in entries])
