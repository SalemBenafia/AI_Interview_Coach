"""
app/modules/admin/agents/router.py
=====================================
AI Studio -> Agent management (admin_ai_manage_ui.txt). Agents are never
edited in place once published -- clone -> edit -> test -> publish
("Agent Versioning"). The /test/ endpoint runs a real agent invocation
(a real LLM call) against sample input with NO database session/turn
persistence, exactly matching admin_ai_manage_ui.txt's "Agent Testing UI":
"No real interview needed."
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
from app.db.models import AgentKey, AgentTemplate, AgentTemplateStatus, AuditLog
from app.db.session import get_db
from app.modules.agents import registry
from app.modules.agents.evaluator_agent import EvaluatorAgent
from app.modules.agents.feedback_agent import FeedbackAgent
from app.modules.agents.coach_agent import CoachAgent
from app.modules.agents.interviewer_agent import InterviewerAgent
from app.modules.agents.llm_client import AgentOutputParseError, AgentServiceError
from app.modules.agents.router_agent import RouterAgent
from app.modules.agents.schemas import (
    CoachInput,
    EvaluatorInput,
    FeedbackInput,
    InterviewerInput,
    RouterInput,
)
from app.modules.auth.dependencies import CurrentPrincipal, require_admin_role

router = APIRouter(prefix="/admin/agents", tags=["Admin — AI Studio — Agents"])

_AI_MANAGER_ROLES = ("super_admin", "ai_manager")

# Broader than _AI_MANAGER_ROLES: flow designers need to see the selectable
# agent list to populate the flow builder's node editor dropdown, even
# though they can't edit agent templates themselves.
_AGENT_KEY_VIEWER_ROLES = ("super_admin", "platform_admin", "ai_manager", "flow_designer")

_INPUT_SCHEMAS = {
    AgentKey.INTERVIEWER: InterviewerInput,
    AgentKey.EVALUATOR: EvaluatorInput,
    AgentKey.FEEDBACK: FeedbackInput,
    AgentKey.COACH: CoachInput,
}
_AGENT_CLASSES = {
    AgentKey.INTERVIEWER: InterviewerAgent,
    AgentKey.EVALUATOR: EvaluatorAgent,
    AgentKey.FEEDBACK: FeedbackAgent,
    AgentKey.COACH: CoachAgent,
}


class AgentTemplateCreate(BaseModel):
    key: AgentKey
    name: str
    description: Optional[str] = None
    model_provider: str = "groq"
    model_name: str = "allam-2-7b"
    temperature: float = 0.7
    max_tokens: int = 600
    system_prompt: str
    rubric: list[dict] = []
    decision_rules: list[dict] = []
    coaching_style: Optional[str] = None
    config: dict = {}


class AgentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    rubric: Optional[list[dict]] = None
    decision_rules: Optional[list[dict]] = None
    coaching_style: Optional[str] = None
    config: Optional[dict] = None


def _serialize(a: AgentTemplate) -> dict:
    return {
        "id": str(a.id),
        "key": a.key.value,
        "name": a.name,
        "description": a.description,
        "version": a.version,
        "status": a.status.value,
        "parentId": str(a.parent_id) if a.parent_id else None,
        "modelProvider": a.model_provider,
        "modelName": a.model_name,
        "temperature": a.temperature,
        "maxTokens": a.max_tokens,
        "systemPrompt": a.system_prompt,
        "rubric": a.rubric,
        "decisionRules": a.decision_rules,
        "coachingStyle": a.coaching_style,
        "publishedAt": a.published_at.isoformat() if a.published_at else None,
        "createdAt": a.created_at.isoformat(),
    }


@router.get("/")
async def list_agents(
    key: Optional[AgentKey] = Query(default=None),
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgentTemplate)
    if key:
        query = query.where(AgentTemplate.key == key)
    query = query.order_by(AgentTemplate.key, AgentTemplate.version.desc())
    agents = (await db.execute(query)).scalars().all()
    return success([_serialize(a) for a in agents])


@router.get("/keys/")
async def list_agent_keys(
    admin: CurrentPrincipal = Depends(require_admin_role(*_AGENT_KEY_VIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    The REAL, backend-validated list of selectable agents for the flow
    builder's node editor -- powers a dropdown, not a free-text field (see
    frontend/app/admin/flows/[flowId]/page.tsx). One entry per AgentKey,
    with the currently-ACTIVE AgentTemplate's name for extra context where
    one has been published.
    """
    entries = []
    for key in AgentKey:
        template = await registry.get_active_template(db, key)
        entries.append({
            "key": key.value,
            "label": key.value.replace("_", " ").title(),
            "hasActiveTemplate": template is not None,
            "activeTemplateName": template.name if template else None,
        })
    return success(entries)


@router.post("/", status_code=201)
async def create_agent(
    payload: AgentTemplateCreate,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    agent = AgentTemplate(**payload.model_dump(), created_by=uuid.UUID(admin.id), status=AgentTemplateStatus.DRAFT)
    db.add(agent)
    await db.flush()
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.create",
        resource_type="agent_template", resource_id=str(agent.id),
        details={"key": agent.key.value, "name": agent.name},
    ))
    await db.commit()
    return success({"agentId": str(agent.id)}, message="Agent draft created.")


@router.get("/{agent_id}/")
async def get_agent(
    agent_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})
    return success(_serialize(agent))


@router.patch("/{agent_id}/")
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentTemplateUpdate,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})
    if agent.status != AgentTemplateStatus.DRAFT:
        raise HTTPException(409, detail={
            "code": "NOT_EDITABLE",
            "message": "Published/archived agents are immutable. Clone this agent to create an editable draft.",
        })
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(agent, k, v)
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.update",
        resource_type="agent_template", resource_id=str(agent.id),
        details={"fields": list(changes.keys())},
    ))
    await db.commit()
    return success({}, message="Agent updated.")


@router.post("/{agent_id}/clone/", status_code=201)
async def clone_agent(
    agent_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})

    max_version_result = await db.execute(
        select(AgentTemplate.version).where(AgentTemplate.key == source.key).order_by(AgentTemplate.version.desc())
    )
    latest_version = max_version_result.scalars().first() or 0

    clone = AgentTemplate(
        key=source.key,
        name=f"{source.name} (v{latest_version + 1})",
        description=source.description,
        version=latest_version + 1,
        status=AgentTemplateStatus.DRAFT,
        parent_id=source.id,
        model_provider=source.model_provider,
        model_name=source.model_name,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        system_prompt=source.system_prompt,
        rubric=source.rubric,
        decision_rules=source.decision_rules,
        coaching_style=source.coaching_style,
        config=source.config,
        created_by=uuid.UUID(admin.id),
    )
    db.add(clone)
    await db.flush()
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.clone",
        resource_type="agent_template", resource_id=str(clone.id),
        details={"sourceAgentId": str(source.id), "key": clone.key.value, "version": clone.version},
    ))
    await db.commit()
    return success({"agentId": str(clone.id)}, message="Cloned into a new editable draft.")


@router.post("/{agent_id}/publish/")
async def publish_agent(
    agent_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})

    # Archive any currently-active version of the same key -- only one
    # ACTIVE template per key at a time (the Agent Registry always resolves
    # the single active row, see app/modules/agents/registry.py).
    previously_active = await db.execute(
        select(AgentTemplate).where(AgentTemplate.key == agent.key, AgentTemplate.status == AgentTemplateStatus.ACTIVE)
    )
    for old in previously_active.scalars().all():
        old.status = AgentTemplateStatus.ARCHIVED

    agent.status = AgentTemplateStatus.ACTIVE
    agent.published_at = datetime.now(tz=timezone.utc)
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.publish",
        resource_type="agent_template", resource_id=str(agent.id),
        details={"key": agent.key.value, "version": agent.version},
    ))
    await db.commit()
    return success({}, message="Agent published and is now live.")


@router.post("/{agent_id}/archive/")
async def archive_agent(
    agent_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})
    agent.status = AgentTemplateStatus.ARCHIVED
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.archive",
        resource_type="agent_template", resource_id=str(agent.id),
        details={"key": agent.key.value, "version": agent.version},
    ))
    await db.commit()
    return success({}, message="Agent archived.")


@router.delete("/{agent_id}/")
async def delete_agent(
    agent_id: uuid.UUID,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})
    if agent.status != AgentTemplateStatus.DRAFT:
        raise HTTPException(409, detail={"code": "NOT_DELETABLE", "message": "Only draft agents can be deleted."})
    db.add(AuditLog(
        admin_id=uuid.UUID(admin.id), action="agent.delete",
        resource_type="agent_template", resource_id=str(agent.id),
        details={"key": agent.key.value, "name": agent.name, "version": agent.version},
    ))
    await db.delete(agent)
    await db.commit()
    return success({}, message="Draft deleted.")


# --- Test sandbox (admin_ai_manage_ui.txt: "No real interview needed.") ----

@router.post("/{agent_id}/test/")
async def test_agent(
    agent_id: uuid.UUID,
    sample_input: dict,
    admin: CurrentPrincipal = Depends(require_admin_role(*_AI_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Runs a REAL invocation of this agent template (a genuine LLM call,
    or the real rule engine for the Router agent) against admin-supplied
    sample input, with no InterviewSession/transcript persistence.
    """
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.id == agent_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})

    try:
        if template.key == AgentKey.ROUTER:
            agent = RouterAgent()
            agent_input = RouterInput(**sample_input)
        else:
            input_schema = _INPUT_SCHEMAS[template.key]
            agent_cls = _AGENT_CLASSES[template.key]
            agent = agent_cls(
                name=template.name, objective=template.description or "",
                system_prompt=template.system_prompt, model_provider=template.model_provider,
                model_name=template.model_name, temperature=template.temperature, max_tokens=template.max_tokens,
            )
            agent_input = input_schema(**sample_input)

        run_result = await agent.run(agent_input)
    except (AgentServiceError, AgentOutputParseError) as exc:
        raise HTTPException(503, detail={"code": "AGENT_SERVICE_UNAVAILABLE", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(400, detail={"code": "INVALID_SAMPLE_INPUT", "message": str(exc)})

    return success({
        "output": run_result.output.model_dump(),
        "latencyMs": run_result.latency_ms,
        "modelName": run_result.model_name,
    })
