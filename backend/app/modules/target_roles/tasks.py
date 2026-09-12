"""
app/modules/target_roles/tasks.py
====================================
Background AI analysis: turns a candidate's raw target-role fields into
structured, private CandidateKnowledgeEntry rows (see
app/modules/agents/knowledge_extraction_agent.py). Runs off the request
path so the candidate's "Analyze" action returns immediately — mirrors the
same fire-and-forget-to-Celery pattern used for feedback report generation
(app/modules/interviews/tasks.py).
"""
from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.db.models import CandidateKnowledgeEntry, CandidateTargetRole, TargetRoleStatus
from app.db.session import get_db_context
from app.modules.agents.knowledge_extraction_agent import build_knowledge_extraction_agent
from app.modules.agents.llm_client import AgentOutputParseError, AgentServiceError
from app.modules.agents.schemas import KnowledgeExtractionFieldInput, KnowledgeExtractionInput

logger = structlog.get_logger()


@celery_app.task(
    name="app.modules.target_roles.tasks.analyze_target_role",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def analyze_target_role(self, target_role_id: str) -> None:
    """Extract structured knowledge for one candidate target role."""
    try:
        asyncio.run(_analyze_target_role_async(target_role_id))
    except AgentServiceError as exc:
        # Only retry on a transient Groq outage — an output that fails schema
        # validation (AgentOutputParseError) is not obviously transient and
        # is instead handled as a terminal failure inside the async body.
        logger.warning("target_role_analysis_retry", target_role_id=target_role_id, error=str(exc))
        raise self.retry(exc=exc)


async def _analyze_target_role_async(target_role_id: str) -> None:
    async with get_db_context() as db:
        result = await db.execute(
            select(CandidateTargetRole)
            .where(CandidateTargetRole.id == uuid.UUID(target_role_id))
            .options(selectinload(CandidateTargetRole.fields))
        )
        target_role = result.scalar_one_or_none()
        if not target_role:
            logger.warning("target_role_analysis_not_found", target_role_id=target_role_id)
            return

        if not target_role.fields:
            target_role.status = TargetRoleStatus.FAILED
            return

        agent = build_knowledge_extraction_agent()
        try:
            run_result = await agent.run(KnowledgeExtractionInput(
                target_role_title=target_role.title,
                target_role_description=target_role.description,
                fields=[
                    KnowledgeExtractionFieldInput(
                        field_title=f.field_title, field_description=f.field_description
                    )
                    for f in target_role.fields
                ],
            ))
        except AgentOutputParseError as exc:
            logger.error("target_role_analysis_parse_failed", target_role_id=target_role_id, error=str(exc))
            target_role.status = TargetRoleStatus.FAILED
            return

        # Full replace: fields may have been added/edited/removed since the
        # last analysis, and the candidate's data volume is small enough
        # that a diff-based incremental update isn't worth the complexity.
        await db.execute(
            delete(CandidateKnowledgeEntry).where(CandidateKnowledgeEntry.target_role_id == target_role.id)
        )
        for entry in run_result.output.entries:
            db.add(CandidateKnowledgeEntry(
                candidate_id=target_role.candidate_id,
                target_role_id=target_role.id,
                category=entry.category,
                topic=entry.topic,
                summary=entry.summary,
            ))
        target_role.status = TargetRoleStatus.READY
