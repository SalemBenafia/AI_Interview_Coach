"""
app/modules/agents/registry.py
=================================
Agent Registry (intraction_admin_ai.txt §"Better Architecture: Agent
Registry"). Flow nodes reference agents only by key
(`{"node_type": "question", "agent": "interviewer"}`); this module resolves
that key + the active AgentTemplate row in Postgres into a constructed,
runnable agent instance.

Developer-owned: the Python classes (InterviewerAgent, EvaluatorAgent, ...).
Admin-owned: the AgentTemplate row's prompt/model/rubric/rules — see
admin_ai_manage_ui.txt's "Locked (Developer)" vs "Configurable (Admin)" split.

If no ACTIVE AgentTemplate exists yet for a key (e.g. a brand new install
before an admin has configured anything), we fall back to a sensible
developer-provided default prompt — this is normal application defaulting,
not a substitute for the real LLM call.
"""
from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.models import AgentKey, AgentTemplate, AgentTemplateStatus
from app.modules.agents.coach_agent import DEFAULT_SYSTEM_PROMPT as COACH_DEFAULT_PROMPT
from app.modules.agents.coach_agent import CoachAgent
from app.modules.agents.evaluator_agent import DEFAULT_SYSTEM_PROMPT as EVALUATOR_DEFAULT_PROMPT
from app.modules.agents.evaluator_agent import EvaluatorAgent
from app.modules.agents.feedback_agent import DEFAULT_SYSTEM_PROMPT as FEEDBACK_DEFAULT_PROMPT
from app.modules.agents.feedback_agent import FeedbackAgent
from app.modules.agents.interviewer_agent import DEFAULT_SYSTEM_PROMPT as INTERVIEWER_DEFAULT_PROMPT
from app.modules.agents.interviewer_agent import InterviewerAgent
from app.modules.agents.router_agent import DEFAULT_DECISION_RULES, RouterAgent

logger = structlog.get_logger()

_AGENT_CLASSES = {
    AgentKey.INTERVIEWER: InterviewerAgent,
    AgentKey.EVALUATOR: EvaluatorAgent,
    AgentKey.FEEDBACK: FeedbackAgent,
    AgentKey.COACH: CoachAgent,
}

_DEFAULT_PROMPTS = {
    AgentKey.INTERVIEWER: INTERVIEWER_DEFAULT_PROMPT,
    AgentKey.EVALUATOR: EVALUATOR_DEFAULT_PROMPT,
    AgentKey.FEEDBACK: FEEDBACK_DEFAULT_PROMPT,
    AgentKey.COACH: COACH_DEFAULT_PROMPT,
}


async def get_active_template(db: AsyncSession, key: AgentKey) -> Optional[AgentTemplate]:
    result = await db.execute(
        select(AgentTemplate)
        .where(AgentTemplate.key == key, AgentTemplate.status == AgentTemplateStatus.ACTIVE)
        .order_by(AgentTemplate.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_agent(db: AsyncSession, key: AgentKey):
    """
    Construct a runtime agent instance for `key`, parameterised by its
    active AgentTemplate (or sane defaults if none is configured yet).
    """
    if key == AgentKey.ROUTER:
        return RouterAgent()

    template = await get_active_template(db, key)
    agent_cls = _AGENT_CLASSES[key]

    if template:
        # If the stored provider has changed (e.g. migrated from openrouter to
        # groq) the DB still holds the old model ID which will 404 on the new
        # provider. Reset to the current configured model in that case.
        if template.model_provider != "groq":
            logger.warning(
                "agent_provider_override",
                template_id=str(template.id),
                agent_key=key.value,
                stored_provider=template.model_provider,
                stored_model=template.model_name,
                forced_provider="groq",
                forced_model=settings.GROQ_MODEL,
            )
            model_provider = "groq"
            model_name = settings.GROQ_MODEL
        else:
            model_provider = template.model_provider
            model_name = template.model_name

        # FeedbackOutput is large (summary + multiple lists + nested objects);
        # 600 tokens is never enough. Raise the floor regardless of what the
        # DB row says so that Celery feedback tasks don't silently truncate.
        max_tokens = template.max_tokens
        if key == AgentKey.FEEDBACK:
            max_tokens = max(max_tokens, 2000)

        return agent_cls(
            name=template.name,
            objective=template.description or "",
            system_prompt=template.system_prompt,
            model_provider=model_provider,
            model_name=model_name,
            temperature=template.temperature,
            max_tokens=max_tokens,
            template_id=str(template.id),
            template_version=template.version,
        )

    # No DB template yet — use code defaults.
    # Feedback output is large; ensure the token budget is adequate.
    extra: dict = {"max_tokens": 2000} if key == AgentKey.FEEDBACK else {}
    return agent_cls(
        name=f"Default {key.value.title()} Agent",
        objective="",
        system_prompt=_DEFAULT_PROMPTS[key],
        **extra,
    )


async def get_router_decision_rules(db: AsyncSession) -> list[dict[str, str]]:
    template = await get_active_template(db, AgentKey.ROUTER)
    if template and template.decision_rules:
        return template.decision_rules
    return DEFAULT_DECISION_RULES


async def get_evaluator_rubric(db: AsyncSession) -> list[dict]:
    template = await get_active_template(db, AgentKey.EVALUATOR)
    if template and template.rubric:
        return template.rubric
    return [
        {"key": "relevance", "label": "Relevance", "weight": 0.2},
        {"key": "clarity", "label": "Clarity", "weight": 0.2},
        {"key": "communication", "label": "Communication", "weight": 0.2},
        {"key": "technical_depth", "label": "Technical Depth", "weight": 0.2},
        {"key": "problem_solving", "label": "Problem Solving", "weight": 0.2},
    ]


async def get_feedback_coaching_style(db: AsyncSession) -> str:
    template = await get_active_template(db, AgentKey.FEEDBACK)
    if template and template.coaching_style:
        return template.coaching_style
    return "professional"
