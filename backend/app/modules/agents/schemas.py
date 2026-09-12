"""
app/modules/agents/schemas.py
================================
Strict input/output schemas for every sub-agent
(agent_compose.txt §8-9 — "Never let agents return raw text. Use
structured outputs."). The LLM is always asked to return JSON matching
one of the *Output schemas below; the agent classes validate it.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ─── Interviewer Agent ─────────────────────────────────────────────────────────

class CandidateKnowledgeEntryContext(BaseModel):
    """One of the candidate's own private knowledge entries, offered to the
    Interviewer agent so it can pick which one to ground the next question
    in (see app/modules/agents/flow_compiler.py). No vector search involved
    — this is the full, already-filtered list for the session's target role."""
    id: str
    category: str
    topic: str
    summary: str


class InterviewerInput(BaseModel):
    role_name: str
    mode: str
    difficulty: str
    stage: str                       # warmup | core | wrapup
    questions_already_asked: list[str] = Field(default_factory=list)
    last_candidate_answer: Optional[str] = None
    last_evaluation_summary: Optional[str] = None
    knowledge_entries: list[CandidateKnowledgeEntryContext] = Field(default_factory=list)
    covered_entry_ids: list[str] = Field(default_factory=list)
    is_followup: bool = False
    coaching_hint_enabled: bool = False


class InterviewerOutput(BaseModel):
    question: str
    is_followup: bool = False
    rationale: Optional[str] = None
    hint: Optional[str] = None       # only populated if coaching_hint_enabled
    knowledge_entry_id_used: Optional[str] = None  # which entry (if any) grounded this question


# ─── Evaluator Agent ────────────────────────────────────────────────────────────

class EvaluatorInput(BaseModel):
    question: str
    answer: str
    role_name: str
    mode: str
    difficulty: str
    rubric: list[dict] = Field(default_factory=list)  # [{"key","label","weight"}]


class EvaluatorOutput(BaseModel):
    relevance: float = Field(ge=0, le=100)
    clarity: float = Field(ge=0, le=100)
    communication: float = Field(ge=0, le=100)
    technical_depth: float = Field(ge=0, le=100)
    problem_solving: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    composite_score: float = Field(ge=0, le=100)
    star_detected: bool = False
    star_components: dict[str, bool] = Field(
        default_factory=lambda: {"situation": False, "task": False, "action": False, "result": False}
    )
    weak_signal: bool = False
    notes: Optional[str] = None


# ─── Router Agent ───────────────────────────────────────────────────────────────

class RouterInput(BaseModel):
    composite_score: float
    weak_signal: bool
    follow_up_count: int
    questions_asked_count: int
    max_questions: int
    min_questions: int
    difficulty: str
    decision_rules: list[dict] = Field(default_factory=list)  # [{"condition","action"}]


class RouterOutput(BaseModel):
    action: str = Field(description="ask_followup | next_question | increase_difficulty | coaching | end")
    reason: str


# ─── Feedback Agent ─────────────────────────────────────────────────────────────

class FeedbackInput(BaseModel):
    role_name: str
    mode: str
    transcript: list[dict] = Field(default_factory=list)       # [{"speaker","text"}]
    score_history: list[dict] = Field(default_factory=list)
    coaching_style: str = "professional"
    sentiment_summary: Optional[str] = None                    # e.g. "neutral 60%, anxious 40%"


class BetterAnswerExample(BaseModel):
    question: str
    your_answer: str
    better_answer: str


class FeedbackOutput(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    example_better_answers: list[BetterAnswerExample] = Field(default_factory=list)
    recommended_practice: list[str] = Field(default_factory=list)


# ─── Knowledge Extraction Agent (candidate's own knowledge, not admin-configurable) ──
#
# Distills a candidate's raw target-role fields into structured private
# CandidateKnowledgeEntry rows (see app/modules/target_roles/tasks.py). Not
# retrieval — there is no vector store. This runs once per "Analyze" action.

class KnowledgeExtractionFieldInput(BaseModel):
    field_title: str
    field_description: str


class KnowledgeExtractionInput(BaseModel):
    target_role_title: str
    target_role_description: Optional[str] = None
    fields: list[KnowledgeExtractionFieldInput] = Field(default_factory=list)


class KnowledgeExtractionEntry(BaseModel):
    category: str = Field(description="experience | skill | project | achievement | education | other")
    topic: str
    summary: str


class KnowledgeExtractionOutput(BaseModel):
    entries: list[KnowledgeExtractionEntry] = Field(default_factory=list)


# ─── Coach Agent (live hint mode) ──────────────────────────────────────────────

class CoachInput(BaseModel):
    question: str
    last_answer: Optional[str] = None
    weak_signal: bool = False


class CoachOutput(BaseModel):
    hint: str
