"""
seed.py
=========
Populates the database with everything needed for the platform to be
immediately usable after a fresh install: a super admin, a demo candidate
with a starter target role (ready for the candidate to fill in and analyze
themselves), ACTIVE default agent templates (so interviews work without an
admin configuring anything first), default difficulty rules, and one
published, global, default InterviewFlow per InterviewMode (so a session
can always be created for any mode — see app/modules/interviews/router.py's
mode-based flow resolution).

There is no admin-seeded role catalog and no seeded knowledge base:
candidates own their own target roles and knowledge (see
app/modules/target_roles/), so the demo candidate's target role starts in
DRAFT — running "Analyze" is a real, live Groq call the candidate/admin
triggers themselves after signing in, not something this script fakes.

Run with:
    python seed.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.core.settings import settings
from app.db.models import (
    AdminRole,
    AdminUser,
    AgentKey,
    AgentTemplate,
    AgentTemplateStatus,
    CandidateTargetRole,
    CandidateTargetRoleField,
    CandidateUser,
    DifficultyLevel,
    DifficultyRule,
    FlowStatus,
    InterviewFlow,
    InterviewMode,
    SupportedLanguage,
    TargetRoleStatus,
)
from app.db.session import AsyncSessionLocal
from app.modules.agents.coach_agent import DEFAULT_SYSTEM_PROMPT as COACH_PROMPT
from app.modules.agents.evaluator_agent import DEFAULT_SYSTEM_PROMPT as EVALUATOR_PROMPT
from app.modules.agents.feedback_agent import DEFAULT_SYSTEM_PROMPT as FEEDBACK_PROMPT
from app.modules.agents.interviewer_agent import DEFAULT_SYSTEM_PROMPT as INTERVIEWER_PROMPT
from app.modules.auth.jwt import hash_password

logger = structlog.get_logger()


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await _seed_admin(db)
        candidate = await _seed_candidate(db)
        await _seed_difficulty_rules(db)
        await _seed_agents(db)
        await db.commit()
        await _seed_target_role(db, candidate)
        await _seed_flows(db)
        await db.commit()
    print("Seed complete.")


async def _seed_admin(db) -> None:
    result = await db.execute(select(AdminUser).where(AdminUser.email == "admin@interview-coach.ai"))
    if result.scalar_one_or_none():
        return
    db.add(AdminUser(
        email="admin@interview-coach.ai",
        username="admin",
        hashed_password=hash_password("Admin@123456"),
        first_name="Platform",
        last_name="Admin",
        role=AdminRole.SUPER_ADMIN,
        is_active=True,
    ))


async def _seed_candidate(db) -> CandidateUser:
    result = await db.execute(select(CandidateUser).where(CandidateUser.email == "demo@interview-coach.ai"))
    candidate = result.scalar_one_or_none()
    if candidate:
        return candidate
    candidate = CandidateUser(
        email="demo@interview-coach.ai",
        hashed_password=hash_password("Demo@123456"),
        first_name="Demo",
        last_name="Candidate",
        preferred_language=SupportedLanguage.EN,
        is_active=True,
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def _seed_target_role(db, candidate: CandidateUser) -> None:
    """A starter target role for the demo candidate, in DRAFT status —
    candidates (or whoever is demoing) fill in / adjust the fields and hit
    "Analyze" themselves; this script never fakes an AI extraction."""
    result = await db.execute(
        select(CandidateTargetRole).where(
            CandidateTargetRole.candidate_id == candidate.id,
            CandidateTargetRole.title == "Frontend Developer",
        )
    )
    if result.scalar_one_or_none():
        return

    target_role = CandidateTargetRole(
        candidate_id=candidate.id,
        title="Frontend Developer",
        description="Practicing for mid-level frontend roles focused on React.",
        status=TargetRoleStatus.DRAFT,
    )
    db.add(target_role)
    await db.flush()

    field_specs = [
        ("Experience", "Worked as a frontend developer for 2 years at a startup, "
                        "building and maintaining a React + TypeScript dashboard product."),
        ("Key project", "Led a rewrite of the company's design system to React, "
                         "cutting new-page development time by roughly 30%."),
        ("Skills", "Strong in React, TypeScript, and CSS; comfortable with performance "
                    "profiling and basic accessibility audits."),
    ]
    for i, (field_title, field_description) in enumerate(field_specs):
        db.add(CandidateTargetRoleField(
            target_role_id=target_role.id,
            field_title=field_title,
            field_description=field_description,
            sort_order=i,
        ))


async def _seed_difficulty_rules(db) -> None:
    specs = [
        (DifficultyLevel.JUNIOR, "Junior", 80, 40, "Foundational questions, generous follow-ups."),
        (DifficultyLevel.MID, "Mid-level", 80, 50, "Standard depth, adaptive follow-ups."),
        (DifficultyLevel.SENIOR, "Senior", 90, 55, "High depth, pushes for trade-offs and metrics."),
    ]
    for level, label, advance, regress, desc in specs:
        result = await db.execute(select(DifficultyRule).where(DifficultyRule.level == level))
        if result.scalar_one_or_none():
            continue
        db.add(DifficultyRule(level=level, label=label, advance_score_threshold=advance,
                               regress_score_threshold=regress, description=desc))


async def _seed_agents(db) -> None:
    specs = [
        (AgentKey.INTERVIEWER, "Default Interviewer", INTERVIEWER_PROMPT, {}),
        (AgentKey.EVALUATOR, "Default Evaluator", EVALUATOR_PROMPT, {
            "temperature": 0.2,
            "rubric": [
                {"key": "relevance", "label": "Relevance", "weight": 0.2},
                {"key": "clarity", "label": "Clarity", "weight": 0.2},
                {"key": "communication", "label": "Communication", "weight": 0.2},
                {"key": "technical_depth", "label": "Technical Depth", "weight": 0.2},
                {"key": "problem_solving", "label": "Problem Solving", "weight": 0.2},
            ],
        }),
        (AgentKey.FEEDBACK, "Default Feedback Coach", FEEDBACK_PROMPT, {
            "coaching_style": "professional",
        }),
        (AgentKey.COACH, "Default Live Coach", COACH_PROMPT, {}),
    ]
    for key, name, prompt, extra in specs:
        result = await db.execute(
            select(AgentTemplate).where(AgentTemplate.key == key, AgentTemplate.status == AgentTemplateStatus.ACTIVE)
        )
        if result.scalar_one_or_none():
            continue
        db.add(AgentTemplate(
            key=key, name=name, version=1, status=AgentTemplateStatus.ACTIVE,
            model_provider="groq", model_name=settings.GROQ_MODEL,
            temperature=extra.pop("temperature", 0.7), max_tokens=600,
            system_prompt=prompt, published_at=datetime.now(tz=timezone.utc),
            **extra,
        ))

    # Router agent uses the default rule-based decision logic baked into
    # app/modules/agents/router_agent.py -- seeding an explicit template
    # here just lets admins see/edit the rules from the AI Studio UI.
    result = await db.execute(
        select(AgentTemplate).where(AgentTemplate.key == AgentKey.ROUTER, AgentTemplate.status == AgentTemplateStatus.ACTIVE)
    )
    if not result.scalar_one_or_none():
        from app.modules.agents.router_agent import DEFAULT_DECISION_RULES
        db.add(AgentTemplate(
            key=AgentKey.ROUTER, name="Default Router", version=1, status=AgentTemplateStatus.ACTIVE,
            system_prompt="(unused — the Router Agent is a deterministic rule engine, not an LLM call)",
            decision_rules=DEFAULT_DECISION_RULES, published_at=datetime.now(tz=timezone.utc),
        ))


def _default_graph_json() -> dict:
    """One reusable question node the router loops back onto for follow-ups,
    the next question, and difficulty bumps alike — the Interviewer agent
    varies what it actually asks by drawing on the candidate's own knowledge
    each time (see app/modules/agents/flow_compiler.py), not by admins
    pre-authoring a fixed sequence of topics."""
    return {
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "q1", "type": "question", "position": {"x": 250, "y": 0}, "data": {"agent": "interviewer"}},
            {"id": "eval1", "type": "evaluation", "position": {"x": 500, "y": 0}, "data": {"agent": "evaluator"}},
            {"id": "router1", "type": "router", "position": {"x": 750, "y": 0}, "data": {"agent": "router"}},
            {"id": "coach1", "type": "coaching", "position": {"x": 750, "y": 200}, "data": {"agent": "coach"}},
            {"id": "end1", "type": "end", "position": {"x": 1000, "y": 0}, "data": {}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "q1"},
            {"id": "e2", "source": "eval1", "target": "router1"},
            {"id": "e3", "source": "router1", "target": "q1", "data": {"action": "ask_followup"}},
            {"id": "e4", "source": "router1", "target": "q1", "data": {"action": "next_question"}},
            {"id": "e5", "source": "router1", "target": "q1", "data": {"action": "increase_difficulty"}},
            {"id": "e6", "source": "router1", "target": "coach1", "data": {"action": "coaching"}},
            {"id": "e7", "source": "router1", "target": "end1", "data": {"action": "end"}},
        ],
    }


async def _seed_flows(db) -> None:
    """One published, is_default=True flow per InterviewMode — global,
    applies to every candidate and every target role in that mode (see
    app/modules/admin/flows/router.py's per-mode default exclusivity)."""
    mode_labels = {
        InterviewMode.BEHAVIORAL: "Behavioral",
        InterviewMode.TECHNICAL: "Technical",
        InterviewMode.MIXED: "Mixed",
        InterviewMode.MOCK_HR_SCREENING: "Mock HR Screening",
    }
    for mode, label in mode_labels.items():
        name = f"{label} — Default"
        result = await db.execute(select(InterviewFlow).where(InterviewFlow.name == name))
        if result.scalar_one_or_none():
            continue
        db.add(InterviewFlow(
            name=name,
            description=f"Starter global flow for {label.lower()} interviews.",
            mode=mode,
            default_difficulty=DifficultyLevel.MID,
            status=FlowStatus.PUBLISHED,
            is_default=True,
            graph_json=_default_graph_json(),
            published_at=datetime.now(tz=timezone.utc),
        ))


if __name__ == "__main__":
    asyncio.run(seed())
