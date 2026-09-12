"""
app/modules/agents/state.py
=============================
The shared "memory" object every sub-agent reads and writes
(Ai_gentic_conversation.txt §5.A — "State (Memory)").

This dict is what gets persisted to Redis between turns
(app/core/redis.py: get_session_state / set_session_state) and is the
single source of truth the graph engine threads through every node.
It deliberately mirrors the JSON example from Ai_gentic_conversation.txt:

    {
      "candidate_id": "123",
      "role": "frontend developer",
      "questions_asked": [],
      "scores": {},
      "current_stage": "behavioral",
      "difficulty": "medium"
    }

...extended with everything the rest of the platform needs (transcript
history for the Feedback Agent, routing decisions for observability, the
candidate's own private knowledge entries for grounding questions, etc).
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class TranscriptEntry(TypedDict):
    speaker: str          # "ai" | "candidate"
    text: str
    turn_number: int


class ScoreSnapshot(TypedDict, total=False):
    relevance: float
    clarity: float
    communication: float
    technical_depth: float
    problem_solving: float
    confidence: float
    composite_score: float
    star_detected: bool
    weak_signal: bool


class KnowledgeEntrySnapshot(TypedDict):
    id: str
    category: str
    topic: str
    summary: str


class InterviewState(TypedDict, total=False):
    # ── Identity ──
    session_id: str
    candidate_id: str
    role_name: str                  # the candidate's own target role title, or "this role"
    mode: str                       # InterviewMode value
    difficulty: str                 # DifficultyLevel value (mutable — adapts over time)

    # ── Flow wiring ──
    flow_id: Optional[str]          # the published, global-per-mode InterviewFlow driving this session
    current_node_id: Optional[str]
    current_stage: str              # warmup | core | wrapup

    # ── Conversation memory ──
    questions_asked: list[str]
    transcript: list[TranscriptEntry]
    current_question: Optional[str]
    last_candidate_answer: Optional[str]
    follow_up_count: int            # consecutive follow-ups on the *current* question
    turn_number: int

    # ── Evaluation memory ──
    last_evaluation: Optional[ScoreSnapshot]
    score_history: list[ScoreSnapshot]

    # ── Router decision (most recent) ──
    next_action: Optional[str]      # ask_followup | next_question | increase_difficulty | coaching | end
    last_routing_reason: Optional[str]

    # ── Coaching (live hint mode — description.txt §D) ──
    live_coaching_enabled: bool
    last_hint: Optional[str]

    # ── Candidate's own private knowledge (requirement: agent picks topics
    # from the candidate's knowledge, not an admin-authored topic string) ──
    target_role_id: Optional[str]
    knowledge_entries: list[KnowledgeEntrySnapshot]       # loaded once at session start
    covered_knowledge_entry_ids: list[str]                # entries already grounded a question this session
    knowledge_entries_used_this_turn: list[str]           # drained by the engine into times_covered increments

    # ── Termination ──
    should_end: bool
    end_reason: Optional[str]

    # ── Observability (drained into AgentExecutionLog rows by the engine) ──
    execution_log: list[dict[str, Any]]


def initial_state(
    *,
    session_id: str,
    candidate_id: str,
    role_name: str,
    mode: str,
    difficulty: str,
    flow_id: Optional[str],
    target_role_id: Optional[str] = None,
    knowledge_entries: Optional[list[KnowledgeEntrySnapshot]] = None,
    live_coaching_enabled: bool = False,
) -> InterviewState:
    return InterviewState(
        session_id=session_id,
        candidate_id=candidate_id,
        role_name=role_name,
        mode=mode,
        difficulty=difficulty,
        flow_id=flow_id,
        current_node_id=None,
        current_stage="warmup",
        questions_asked=[],
        transcript=[],
        current_question=None,
        last_candidate_answer=None,
        follow_up_count=0,
        turn_number=0,
        last_evaluation=None,
        score_history=[],
        next_action=None,
        last_routing_reason=None,
        live_coaching_enabled=live_coaching_enabled,
        last_hint=None,
        target_role_id=target_role_id,
        knowledge_entries=knowledge_entries or [],
        covered_knowledge_entry_ids=[],
        knowledge_entries_used_this_turn=[],
        should_end=False,
        end_reason=None,
        execution_log=[],
    )
