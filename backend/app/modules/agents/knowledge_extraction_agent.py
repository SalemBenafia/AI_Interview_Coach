"""
app/modules/agents/knowledge_extraction_agent.py
====================================================
Turns a candidate's raw, free-form target-role fields (title/description
pairs they typed themselves) into structured, private knowledge entries
(app/modules/target_roles/tasks.py writes the output into
CandidateKnowledgeEntry rows).

Deliberately NOT AgentTemplate-backed / admin-configurable, unlike the other
sub-agents — admins must never be able to influence how a candidate's own
knowledge is captured or add content to it (requirement: "admin must not
add knowledge to the AI knowledge agent"). Constructed directly with a
fixed system prompt, exactly like RouterAgent bypasses the Agent Registry's
AgentTemplate lookup for the same "not an admin surface" reason — see
app/modules/agents/registry.py.
"""
from __future__ import annotations

from app.core.settings import settings
from app.modules.agents.base import BaseAgent
from app.modules.agents.schemas import KnowledgeExtractionInput, KnowledgeExtractionOutput

DEFAULT_SYSTEM_PROMPT = """You are an expert resume and background analyst. A job candidate has
described their target role and given you a set of free-form notes about
their own experience, skills, and background for that role.

Your job: distill these raw notes into a set of short, structured knowledge
entries an AI interviewer can later draw on to ask grounded, specific
questions. Do not invent facts the candidate's notes don't support. Each
entry must have:
- category: one of experience | skill | project | achievement | education | other
- topic: a short label (a few words) for what this entry is about
- summary: 1-3 sentences capturing the concrete fact, written in third person

Produce as many distinct entries as the notes genuinely support (typically
3-10). Prefer several specific entries over one vague catch-all one.
"""


class KnowledgeExtractionAgent(BaseAgent[KnowledgeExtractionInput, KnowledgeExtractionOutput]):
    key = "knowledge_extraction"
    input_schema = KnowledgeExtractionInput
    output_schema = KnowledgeExtractionOutput

    def build_user_prompt(self, agent_input: KnowledgeExtractionInput) -> str:
        lines = [f"Target role: {agent_input.target_role_title}"]
        if agent_input.target_role_description:
            lines.append(f"Role description: {agent_input.target_role_description}")
        lines.append("\nCandidate's raw notes:")
        for field in agent_input.fields:
            lines.append(f"- {field.field_title}: {field.field_description}")
        return "\n".join(lines)


def build_knowledge_extraction_agent() -> KnowledgeExtractionAgent:
    return KnowledgeExtractionAgent(
        name="Knowledge Extraction Agent",
        objective="Distill a candidate's raw target-role notes into structured private knowledge entries.",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_provider="groq",
        model_name=settings.GROQ_MODEL,
        temperature=0.3,
        max_tokens=1200,
    )
