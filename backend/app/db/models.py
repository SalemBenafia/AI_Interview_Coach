"""
app/db/models.py
=================
All SQLAlchemy ORM models for the AI Interview Coach platform.
Import this module from alembic env.py to auto-detect migrations.

Domain overview (see /docs in repo root, generated from the product spec):

  CandidateUser ──┬─< CandidateTargetRole >──< CandidateTargetRoleField
                  │         │
                  │         └─< CandidateKnowledgeEntry (private, AI-extracted,
                  │              no vector DB — plain SQL retrieval)
                  │
                  ├─< InterviewSession >──┬── CandidateTargetRole (candidate-owned)
                  │         │             ├── InterviewFlow (global per InterviewMode,
                  │         │             │   versioned JSON graph, compiled at runtime)
                  │         │             └── DifficultyLevel / InterviewMode
                  │         ├─< InterviewTurn >── TurnEvaluation
                  │         ├── InterviewFeedbackReport (1:1)
                  │         ├── InterviewFeedbackRating (1:1, CSAT-style)
                  │         └─< AgentExecutionLog (observability)
                  │
  AdminUser ──────┼── AgentTemplate (versioned: Interviewer/Evaluator/Router/Feedback/Coach)
                  ├── InterviewFlow (created_by; global, one per InterviewMode)
                  ├── DifficultyRule (content mgmt — the only content admin still owns)
                  └── AuditLog

This intentionally has NO tenant/organization isolation layer (see
app/common/models.py docstring) — there are exactly three actors:
Candidate, Admin, AI Agent System (roles.txt).

Admins do not author roles or knowledge: candidates own both (see
CandidateTargetRole / CandidateKnowledgeEntry below). There is no vector
database anywhere in this system — knowledge retrieval is a plain SQL
filter scoped to (candidate_id, target_role_id).
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.common.models import BaseModel, SoftDeleteModel, TimestampMixin, UUIDMixin


# ─── Enums ──────────────────────────────────────────────────────────────────────

class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"          # full platform control
    PLATFORM_ADMIN = "platform_admin"    # users, monitoring, security
    AI_MANAGER = "ai_manager"            # agents, prompts, rubrics, knowledge
    FLOW_DESIGNER = "flow_designer"      # flows only, cannot touch agent internals
    SUPPORT = "support"                  # read-only + user support actions


class SupportedLanguage(str, enum.Enum):
    EN = "en"
    FR = "fr"
    AR = "ar"


class DifficultyLevel(str, enum.Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class InterviewMode(str, enum.Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    MIXED = "mixed"
    MOCK_HR_SCREENING = "mock_hr_screening"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONNECTING = "connecting"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class TurnSpeaker(str, enum.Enum):
    AI = "ai"
    CANDIDATE = "candidate"


class FlowStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AgentTemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentKey(str, enum.Enum):
    """The five specialised sub-agents described in roles.txt.

    KNOWLEDGE was removed: there is no shared/vector knowledge base to
    retrieve from anymore. Knowledge grounding is now handled inline by
    the Interviewer agent, reading the candidate's own CandidateKnowledgeEntry
    rows directly (see app/modules/agents/flow_compiler.py).
    """
    INTERVIEWER = "interviewer"
    EVALUATOR = "evaluator"
    ROUTER = "router"
    FEEDBACK = "feedback"
    COACH = "coach"


class TargetRoleStatus(str, enum.Enum):
    """Lifecycle of a candidate-authored target role's knowledge extraction."""
    DRAFT = "draft"           # fields being filled, not yet analyzed
    ANALYZING = "analyzing"   # AI extraction in progress
    READY = "ready"           # knowledge entries available for interviews
    FAILED = "failed"         # last extraction attempt failed


class KnowledgeEntryCategory(str, enum.Enum):
    """Soft taxonomy for AI-extracted candidate knowledge (validated in the
    Pydantic schema, not enforced as a DB enum, so it can grow without a
    migration)."""
    EXPERIENCE = "experience"
    SKILL = "skill"
    PROJECT = "project"
    ACHIEVEMENT = "achievement"
    EDUCATION = "education"
    OTHER = "other"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRIED = "retried"


# ─── Candidate (User) ───────────────────────────────────────────────────────────

class CandidateUser(Base, SoftDeleteModel):
    """The job seeker / candidate practicing interviews."""
    __tablename__ = "candidate_users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    resume_url: Mapped[Optional[str]] = mapped_column(String(500))
    headline: Mapped[Optional[str]] = mapped_column(String(200))  # e.g. "Junior Frontend Developer"
    preferred_language: Mapped[SupportedLanguage] = mapped_column(
        Enum(SupportedLanguage), default=SupportedLanguage.EN, nullable=False
    )
    notification_prefs: Mapped[Optional[dict]] = mapped_column(
        JSON, default={"email_report_ready": True, "email_reminders": True, "in_app": True}
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list[InterviewSession]] = relationship(back_populates="candidate")
    target_roles: Mapped[list[CandidateTargetRole]] = relationship(back_populates="candidate")


class AdminUser(Base, SoftDeleteModel):
    """Platform admin / HR trainer — manages flows, agents, knowledge, analytics."""
    __tablename__ = "admin_users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole), default=AdminRole.PLATFORM_ADMIN, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="admin")


class RefreshToken(Base, BaseModel):
    __tablename__ = "refresh_tokens"

    principal_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "admin" | "candidate"
    jti: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base, BaseModel):
    __tablename__ = "audit_logs"

    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    admin: Mapped[Optional[AdminUser]] = relationship(back_populates="audit_logs")


# ─── Candidate-Owned Target Roles & Private Knowledge Memory ───────────────────
#
# Candidates author their own target roles (no admin catalog). A target role is
# a shell (title + optional description) the candidate fills in with an
# arbitrary number of free-form (field_title, field_description) pairs, which
# the AI then distills into structured, private CandidateKnowledgeEntry rows.
# There is no vector database: retrieval at interview time is a plain SQL
# filter on (candidate_id, target_role_id).

class CandidateTargetRole(Base, BaseModel):
    """A candidate-authored target role shell. A candidate may create many."""
    __tablename__ = "candidate_target_roles"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TargetRoleStatus] = mapped_column(
        Enum(TargetRoleStatus), default=TargetRoleStatus.DRAFT, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    candidate: Mapped[CandidateUser] = relationship(back_populates="target_roles")
    fields: Mapped[list[CandidateTargetRoleField]] = relationship(
        back_populates="target_role", cascade="all, delete-orphan",
        order_by="CandidateTargetRoleField.sort_order",
    )
    knowledge_entries: Mapped[list[CandidateKnowledgeEntry]] = relationship(
        back_populates="target_role", cascade="all, delete-orphan",
    )
    sessions: Mapped[list[InterviewSession]] = relationship(back_populates="target_role")


class CandidateTargetRoleField(Base, BaseModel):
    """One dynamic (title, description) pair the candidate pushed onto a target
    role, e.g. field_title="Experience", field_description="Worked at Acme as
    a backend developer building payments infra for 3 years." Freely
    addable/editable/removable."""
    __tablename__ = "candidate_target_role_fields"

    target_role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_target_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_title: Mapped[str] = mapped_column(String(200), nullable=False)
    field_description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    target_role: Mapped[CandidateTargetRole] = relationship(back_populates="fields")


class CandidateKnowledgeEntry(Base, BaseModel):
    """A structured knowledge fact the AI extracted from a candidate's raw
    target-role fields. Private to the candidate + target role. No vector
    index — retrieval is a plain SQL filter (see flow_compiler.py)."""
    __tablename__ = "candidate_knowledge_entries"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_target_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_field_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_target_role_fields.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(60), nullable=False)  # see KnowledgeEntryCategory
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    times_covered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    candidate: Mapped[CandidateUser] = relationship()
    target_role: Mapped[CandidateTargetRole] = relationship(back_populates="knowledge_entries")


# ─── Content Management (roles.txt → Admin → Content Management) ──────────────
#
# Admins no longer manage role/skill/competency content — candidates own their
# target roles (above) and admins no longer author knowledge (deleted below).
# The only content-authoring surface admins retain is difficulty scaling.

class DifficultyRule(Base, BaseModel):
    """
    No-code difficulty scaling rule, editable from the admin "Rule Builder" UI
    (admin_ai_manage_ui.txt → Difficulty Scaling).
    """
    __tablename__ = "difficulty_rules"

    level: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    advance_score_threshold: Mapped[int] = mapped_column(Integer, default=80)   # score > X -> harder
    regress_score_threshold: Mapped[int] = mapped_column(Integer, default=50)   # score < X -> coaching
    description: Mapped[Optional[str]] = mapped_column(Text)


# ─── AI Studio: Agent Templates (agent_compose.txt) ────────────────────────────

class AgentTemplate(Base, BaseModel):
    """
    A configurable, versioned instance of one of the six sub-agents.
    Mirrors agent_compose.txt's "Agent = Identity + Objective + Instructions +
    State + Tools + Knowledge + Decision Logic + I/O Schema + Model Config".

    Never edited in place once published — clone -> edit -> test -> publish
    (admin_ai_manage_ui.txt → Agent Versioning).
    """
    __tablename__ = "agent_templates"

    key: Mapped[AgentKey] = mapped_column(Enum(AgentKey), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[AgentTemplateStatus] = mapped_column(
        Enum(AgentTemplateStatus), default=AgentTemplateStatus.DRAFT, nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_templates.id"), nullable=True
    )

    # ── Model configuration ──
    model_provider: Mapped[str] = mapped_column(String(50), default="groq")
    model_name: Mapped[str] = mapped_column(String(100), default="allam-2-7b")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=600)

    # ── Prompt / persona ──
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Evaluator-specific: rubric criteria + weights, e.g.
    #    [{"key": "communication", "label": "Communication", "weight": 0.3}, ...]
    rubric: Mapped[Optional[list]] = mapped_column(JSON, default=[])

    # ── Router-specific: declarative decision rules, e.g.
    #    [{"condition": "score > 80", "action": "increase_difficulty"}, ...]
    #    Action vocabulary: ask_followup | next_question | increase_difficulty |
    #    coaching | end (see app/modules/agents/router_agent.py _VALID_ACTIONS).
    decision_rules: Mapped[Optional[list]] = mapped_column(JSON, default=[])

    # ── Feedback-specific ──
    coaching_style: Mapped[Optional[str]] = mapped_column(String(50))  # friendly|professional|strict|mentor

    # ── Catch-all for anything else the admin UI exposes ──
    # NOTE: not currently read anywhere in app/modules/agents/*; reserved for
    # future admin-configurable settings, not wired to any runtime behavior.
    config: Mapped[Optional[dict]] = mapped_column(JSON, default={})

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ─── AI Studio: Visual Flows (scalability.txt — "Conversation = Graph") ───────

class InterviewFlow(Base, BaseModel):
    """
    A declarative interview flow designed visually with React Flow. GLOBAL:
    applies to every candidate and every target role for a given InterviewMode
    — there is no per-role flow anymore (at most one PUBLISHED + is_default
    flow per InterviewMode, enforced in app/modules/admin/flows/router.py).

    Unlike the old admin UI (where this JSON was purely cosmetic), the
    published graph is now REALLY compiled into an executable LangGraph
    StateGraph at runtime by app/modules/agents/flow_compiler.py — every
    node's agent assignment and every router edge's action genuinely drives
    the interview. See app/modules/agents/flow_contracts.py for the
    node-type -> allowed-agent-key contract and the fixed router action
    vocabulary this schema depends on.

    graph_json shape (node.data.topic and edge.condition no longer exist —
    topics are chosen at runtime by the Interviewer agent from the
    candidate's own knowledge, and router edges carry a plain `action` label
    instead of a duplicated condition expression):
      {
        "nodes": [
          {"id": "start", "type": "start", "position": {...}, "data": {}},
          {"id": "q1", "type": "question", "position": {...},
           "data": {"agent": "interviewer"}},
          {"id": "eval1", "type": "evaluation", "data": {"agent": "evaluator"}},
          {"id": "router1", "type": "router", "data": {"agent": "router"}},
          {"id": "coach1", "type": "coaching", "data": {"agent": "coach"}},
          {"id": "end1", "type": "end", "data": {}}
        ],
        "edges": [
          {"id": "e1", "source": "start", "target": "q1"},
          {"id": "e2", "source": "eval1", "target": "router1"},
          {"id": "e3", "source": "router1", "target": "q1", "data": {"action": "ask_followup"}},
          {"id": "e4", "source": "router1", "target": "q1", "data": {"action": "next_question"}},
          {"id": "e5", "source": "router1", "target": "q1", "data": {"action": "increase_difficulty"}},
          {"id": "e6", "source": "router1", "target": "coach1", "data": {"action": "coaching"}},
          {"id": "e7", "source": "router1", "target": "end1", "data": {"action": "end"}}
        ]
      }

    Notes on this shape (enforced by flow_validation.py at publish time):
      - "start" has exactly one outgoing edge, to a "question" node — this
        is where a turn-1 (no answer yet) session begins.
      - "evaluation" has exactly one outgoing edge, to a "router" node. It
        is a SECOND entry point into the compiled per-turn graph (see
        flow_compiler.py's entry_router), not reached via an edge from the
        question node: turn 1 begins at "start"'s target; every later turn
        (the candidate just answered) begins directly at the evaluation
        node instead, since a live voice interview is turn-based and state
        persists across turns in Redis, not within one graph invocation.
      - "question" and "coaching" nodes need no outgoing edges of their own
        — each is a per-turn leaf; the compiler wires it straight to
        LangGraph's END, which only ends that turn's graph run, not the
        interview (the interview itself ends only via a "router" edge with
        action "end", which leads to the "end" node).
      - router edges carry a plain data.action label (one of RouterAgent's
        five action values) instead of a raw condition expression — the
        condition GRAMMAR stays solely on the Router AgentTemplate's
        admin-edited decision_rules; edges are just an action -> target
        lookup table, so admins never duplicate/risk-drifting-from that
        grammar in the visual editor.
    """
    __tablename__ = "interview_flows"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    mode: Mapped[InterviewMode] = mapped_column(Enum(InterviewMode), default=InterviewMode.MIXED)
    default_difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel), default=DifficultyLevel.MID
    )
    status: Mapped[FlowStatus] = mapped_column(Enum(FlowStatus), default=FlowStatus.DRAFT, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_flows.id"), nullable=True
    )
    # The one PUBLISHED flow to auto-select for a given `mode` when a session
    # doesn't pass an explicit flow_id. Exclusivity (at most one default per
    # mode) is enforced at the API layer, not the DB layer.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    graph_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {"nodes": [], "edges": []})

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="flow")


# ─── Interview Sessions (the live WebRTC call) ─────────────────────────────────

class InterviewSession(Base, BaseModel):
    """One live, real-time voice interview — the WebRTC/LiveKit room maps 1:1 to this row."""
    __tablename__ = "interview_sessions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_flows.id"), nullable=True
    )
    flow_version: Mapped[Optional[int]] = mapped_column(Integer)
    target_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_target_roles.id"), nullable=True
    )

    mode: Mapped[InterviewMode] = mapped_column(Enum(InterviewMode), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.SCHEDULED, nullable=False, index=True
    )

    # ── WebRTC / LiveKit ──
    livekit_room_name: Mapped[Optional[str]] = mapped_column(String(150), unique=True)

    # ── Live progress (denormalised from the agent graph's running state) ──
    current_stage: Mapped[Optional[str]] = mapped_column(String(50))      # warmup|core|wrapup
    current_node_id: Mapped[Optional[str]] = mapped_column(String(100))   # last executed graph node
    questions_asked: Mapped[int] = mapped_column(Integer, default=0)
    current_question: Mapped[Optional[str]] = mapped_column(Text)

    # ── Timing ──
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    ended_reason: Mapped[Optional[str]] = mapped_column(String(100))  # completed|candidate_left|error|timeout

    # ── Scores (0-100, computed by MetricsEngine from TurnEvaluations) ──
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    communication_score: Mapped[Optional[float]] = mapped_column(Float)
    technical_score: Mapped[Optional[float]] = mapped_column(Float)
    behavioral_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    star_method_score: Mapped[Optional[float]] = mapped_column(Float)

    # ── Speech metrics (pyannote-style signals, metrics.txt §B) ──
    avg_words_per_minute: Mapped[Optional[float]] = mapped_column(Float)
    pause_ratio: Mapped[Optional[float]] = mapped_column(Float)
    filler_word_count: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Recording / compliance ──
    recording_url: Mapped[Optional[str]] = mapped_column(String(500))
    recording_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript_summary: Mapped[Optional[str]] = mapped_column(Text)

    candidate: Mapped[CandidateUser] = relationship(back_populates="sessions")
    flow: Mapped[Optional[InterviewFlow]] = relationship(back_populates="sessions")
    target_role: Mapped[Optional[CandidateTargetRole]] = relationship(back_populates="sessions")
    turns: Mapped[list[InterviewTurn]] = relationship(back_populates="session", order_by="InterviewTurn.turn_number")
    feedback_report: Mapped[Optional[InterviewFeedbackReport]] = relationship(back_populates="session", uselist=False)
    rating: Mapped[Optional[InterviewFeedbackRating]] = relationship(back_populates="session", uselist=False)


class InterviewTurn(Base, BaseModel):
    """One AI<->candidate exchange within a session."""
    __tablename__ = "interview_turns"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[TurnSpeaker] = mapped_column(Enum(TurnSpeaker), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(500))
    language: Mapped[Optional[str]] = mapped_column(String(10))

    # ── Signals (transformers sentiment model output) ──
    sentiment: Mapped[Optional[str]] = mapped_column(String(30))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)

    # ── Latency breakdown (per metrics.txt §B5) ──
    stt_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    llm_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    tts_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    total_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)

    is_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[InterviewSession] = relationship(back_populates="turns")
    evaluation: Mapped[Optional[TurnEvaluation]] = relationship(back_populates="turn", uselist=False)

    __table_args__ = (
        UniqueConstraint("session_id", "turn_number", "speaker", name="uq_session_turn_number"),
    )


class TurnEvaluation(Base, BaseModel):
    """Evaluator Agent output for one candidate turn."""
    __tablename__ = "turn_evaluations"

    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_turns.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    relevance: Mapped[Optional[float]] = mapped_column(Float)
    clarity: Mapped[Optional[float]] = mapped_column(Float)
    communication: Mapped[Optional[float]] = mapped_column(Float)
    technical_depth: Mapped[Optional[float]] = mapped_column(Float)
    problem_solving: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    composite_score: Mapped[Optional[float]] = mapped_column(Float)  # rubric-weighted aggregate

    star_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    star_components: Mapped[Optional[dict]] = mapped_column(
        JSON, default={"situation": False, "task": False, "action": False, "result": False}
    )
    weak_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    raw_model_output: Mapped[Optional[dict]] = mapped_column(JSON)

    turn: Mapped[InterviewTurn] = relationship(back_populates="evaluation")


class InterviewFeedbackReport(Base, BaseModel):
    """Feedback Agent output — the post-interview coaching report."""
    __tablename__ = "interview_feedback_reports"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[list] = mapped_column(JSON, default=[])
    weaknesses: Mapped[list] = mapped_column(JSON, default=[])
    suggestions: Mapped[list] = mapped_column(JSON, default=[])
    example_better_answers: Mapped[list] = mapped_column(JSON, default=[])  # [{question, your_answer, better_answer}]
    recommended_practice: Mapped[list] = mapped_column(JSON, default=[])
    coaching_style: Mapped[Optional[str]] = mapped_column(String(50))
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[InterviewSession] = relationship(back_populates="feedback_report")


class InterviewFeedbackRating(Base, BaseModel):
    """Candidate's rating of the AI's feedback quality (metrics.txt §10 — Feedback Quality Score)."""
    __tablename__ = "interview_feedback_ratings"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[Optional[str]] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[InterviewSession] = relationship(back_populates="rating")


class AgentExecutionLog(Base, BaseModel):
    """
    Every graph node execution, logged for observability/debugging
    (scalability.txt §10.2 — "every node execution is logged").
    """
    __tablename__ = "agent_execution_logs"

    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    turn_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_turns.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[Optional[str]] = mapped_column(String(100))
    agent_key: Mapped[AgentKey] = mapped_column(Enum(AgentKey), nullable=False)
    agent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_templates.id"), nullable=True
    )
    agent_version: Mapped[Optional[int]] = mapped_column(Integer)
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    input: Mapped[Optional[dict]] = mapped_column(JSON)
    output: Mapped[Optional[dict]] = mapped_column(JSON)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# ─── Platform Metrics (metrics.txt — Admin Dashboard) ──────────────────────────

class DailyMetricSnapshot(Base, BaseModel):
    """
    Nightly rollup computed by Celery beat — backs the admin analytics trend
    charts without re-aggregating the full interview history on every request.
    """
    __tablename__ = "daily_metric_snapshots"

    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    total_interviews: Mapped[int] = mapped_column(Integer, default=0)
    completed_interviews: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    avg_overall_score: Mapped[Optional[float]] = mapped_column(Float)
    avg_ai_latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float)
    webrtc_drop_rate: Mapped[Optional[float]] = mapped_column(Float)
    stt_error_rate: Mapped[Optional[float]] = mapped_column(Float)
    tts_failure_rate: Mapped[Optional[float]] = mapped_column(Float)
    avg_feedback_rating: Mapped[Optional[float]] = mapped_column(Float)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, default={})


# ─── Notifications ────────────────────────────────────────────────────────────

class NotificationTemplate(Base, BaseModel):
    __tablename__ = "notification_templates"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[list]] = mapped_column(JSON, default=[])


class NotificationLog(Base, BaseModel):
    __tablename__ = "notification_logs"

    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_users.id"), nullable=True, index=True
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notification_templates.id"), nullable=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
