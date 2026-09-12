"""
app/modules/admin/flows/router.py
====================================
AI Studio -> Flow Designer. A flow is now GLOBAL: it applies to every
candidate and every target role for a given InterviewMode -- there is no
per-role flow anymore. At most one PUBLISHED flow per InterviewMode may be
marked is_default (enforced here, see publish_flow); that is the flow
app/modules/interviews/router.py resolves a session onto when the
candidate doesn't pass an explicit flow_id.

Unlike the old admin UI, InterviewFlow.graph_json is no longer cosmetic --
publish_flow enforces validate_flow_graph() as a hard gate (see
app/modules/agents/flow_validation.py) because a published flow is REALLY
compiled into an executable LangGraph at interview run time
(app/modules/agents/flow_compiler.py). This router remains pure
CRUD/versioning; compilation never happens here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import success
from app.db.models import AuditLog, DifficultyLevel, FlowStatus, InterviewFlow, InterviewMode
from app.db.session import get_db
from app.modules.agents.flow_validation import validate_flow_graph
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role

router = APIRouter(prefix="/admin/flows", tags=["Admin — AI Studio — Flows"])

_FLOW_EDITOR_ROLES = ("super_admin", "platform_admin", "flow_designer", "ai_manager")

# A brand-new draft flow starts with a minimal valid skeleton (a bare start
# node with no target isn't itself valid, but this is DRAFT-only scaffolding
# the admin fills in before publish -- publish is where validation is a hard
# gate, not create).
_DEFAULT_GRAPH_JSON: dict = {
    "nodes": [{"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
}


class FlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    mode: InterviewMode = InterviewMode.MIXED
    default_difficulty: DifficultyLevel = DifficultyLevel.MID
    graph_json: dict = _DEFAULT_GRAPH_JSON
    is_default: bool = False


class FlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[InterviewMode] = None
    default_difficulty: Optional[DifficultyLevel] = None
    graph_json: Optional[dict] = None
    is_default: Optional[bool] = None


def _serialize(f: InterviewFlow) -> dict:
    return {
        "id": str(f.id),
        "name": f.name,
        "description": f.description,
        "mode": f.mode.value,
        "defaultDifficulty": f.default_difficulty.value,
        "status": f.status.value,
        "version": f.version,
        "parentId": str(f.parent_id) if f.parent_id else None,
        "isDefault": f.is_default,
        "graphJson": f.graph_json,
        "publishedAt": f.published_at.isoformat() if f.published_at else None,
        "createdAt": f.created_at.isoformat(),
    }


@router.get("/")
async def list_flows(
    status_filter: Optional[FlowStatus] = Query(default=None, alias="status"),
    mode_filter: Optional[InterviewMode] = Query(default=None, alias="mode"),
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    query = select(InterviewFlow)
    if status_filter:
        query = query.where(InterviewFlow.status == status_filter)
    if mode_filter:
        query = query.where(InterviewFlow.mode == mode_filter)
    query = query.order_by(InterviewFlow.created_at.desc())
    flows = (await db.execute(query)).scalars().all()
    return success([_serialize(f) for f in flows])


@router.post("/", status_code=201)
async def create_flow(
    payload: FlowCreate,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    flow = InterviewFlow(**payload.model_dump(), status=FlowStatus.DRAFT, created_by=uuid.UUID(admin.id))
    db.add(flow)
    await db.flush()
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.create",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"name": flow.name, "mode": flow.mode.value},
    ))
    await db.commit()
    return success({"flowId": str(flow.id)}, message="Flow draft created.")


@router.get("/{flow_id}/")
async def get_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})
    return success(_serialize(flow))


@router.patch("/{flow_id}/")
async def update_flow(
    flow_id: uuid.UUID,
    payload: FlowUpdate,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})
    if flow.status != FlowStatus.DRAFT:
        raise HTTPException(409, detail={
            "code": "NOT_EDITABLE",
            "message": "Published/archived flows are immutable. Clone this flow to keep editing.",
        })
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(flow, k, v)
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.update",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"fields": list(changes.keys())},
    ))
    await db.commit()
    return success({}, message="Flow updated.")


@router.post("/{flow_id}/clone/", status_code=201)
async def clone_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})

    clone = InterviewFlow(
        name=f"{source.name} (v{source.version + 1})",
        description=source.description,
        mode=source.mode,
        default_difficulty=source.default_difficulty,
        status=FlowStatus.DRAFT,
        version=source.version + 1,
        parent_id=source.id,
        graph_json=source.graph_json,
        is_default=False,
        created_by=uuid.UUID(admin.id),
    )
    db.add(clone)
    await db.flush()
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.clone",
        resource_type="interview_flow", resource_id=str(clone.id),
        details={"sourceFlowId": str(source.id), "version": clone.version},
    ))
    await db.commit()
    return success({"flowId": str(clone.id)}, message="Cloned into a new editable draft.")


@router.post("/{flow_id}/publish/")
async def publish_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})

    # Hard gate: a published flow is REALLY compiled and executed for every
    # interview in this mode (app/modules/agents/flow_compiler.py) -- a
    # structurally broken flow must never reach a live session.
    errors = validate_flow_graph(flow.graph_json)
    if errors:
        raise HTTPException(422, detail={
            "code": "FLOW_INVALID", "message": "Flow failed validation.", "errors": errors,
        })

    if flow.is_default:
        # At most one published + default flow per mode -- this is the one
        # interviews/router.py auto-selects when a session omits flow_id.
        previously_default = await db.execute(
            select(InterviewFlow).where(
                InterviewFlow.mode == flow.mode,
                InterviewFlow.status == FlowStatus.PUBLISHED,
                InterviewFlow.is_default == True,
                InterviewFlow.id != flow.id,
            )
        )
        for old in previously_default.scalars().all():
            old.is_default = False

    flow.status = FlowStatus.PUBLISHED
    flow.published_at = datetime.now(tz=timezone.utc)
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.publish",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"version": flow.version, "isDefault": flow.is_default, "mode": flow.mode.value},
    ))
    await db.commit()
    return success({}, message="Flow published.")


@router.post("/{flow_id}/set-default/")
async def set_default_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote an already-PUBLISHED flow to be THE live flow for its mode --
    the one interviews/router.py auto-selects when a session omits
    flow_id. This is the only way to change which flow is live without
    cloning+republishing: publish_flow's exclusivity swap only runs at the
    moment a flow is published, so switching back to an older published
    version (or correcting a mistake) needs this dedicated action.
    """
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})
    if flow.status != FlowStatus.PUBLISHED:
        raise HTTPException(409, detail={
            "code": "NOT_PUBLISHED",
            "message": "Only a published flow can be made live. Publish it first.",
        })

    previously_default = await db.execute(
        select(InterviewFlow).where(
            InterviewFlow.mode == flow.mode,
            InterviewFlow.status == FlowStatus.PUBLISHED,
            InterviewFlow.is_default == True,
            InterviewFlow.id != flow.id,
        )
    )
    for old in previously_default.scalars().all():
        old.is_default = False

    flow.is_default = True
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.set_default",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"mode": flow.mode.value, "version": flow.version},
    ))
    await db.commit()
    return success({}, message="This is now the live flow for its mode.")


@router.post("/{flow_id}/archive/")
async def archive_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})
    flow.status = FlowStatus.ARCHIVED
    flow.is_default = False  # an archived flow can never be "the live one" for its mode
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.archive",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"mode": flow.mode.value, "version": flow.version},
    ))
    await db.commit()
    return success({}, message="Flow archived.")


@router.delete("/{flow_id}/")
async def delete_flow(
    flow_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_FLOW_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(InterviewFlow).where(InterviewFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Flow not found."})
    if flow.status != FlowStatus.DRAFT:
        raise HTTPException(409, detail={"code": "NOT_DELETABLE", "message": "Only draft flows can be deleted."})
    # Audit row must be written before the delete -- resource_id/details need
    # the row's data while it still exists, and both land in the same commit.
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="flow.delete",
        resource_type="interview_flow", resource_id=str(flow.id),
        details={"name": flow.name, "mode": flow.mode.value, "version": flow.version},
    ))
    await db.delete(flow)
    await db.commit()
    return success({}, message="Draft deleted.")
