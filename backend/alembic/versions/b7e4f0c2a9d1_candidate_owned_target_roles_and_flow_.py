"""candidate-owned target roles, private knowledge, global flows

Revision ID: b7e4f0c2a9d1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02

Flips the ownership model: candidates now author their own target roles and
private knowledge memory (CandidateTargetRole / CandidateTargetRoleField /
CandidateKnowledgeEntry, no vector index — retrieval is a plain SQL filter).
The old global, admin-curated InterviewRole catalog and the Qdrant-backed
KnowledgeBase/KnowledgeDocument pipeline are dropped outright, along with the
Skill/Competency content-authoring tables (zero downstream consumers).
InterviewFlow becomes global-per-InterviewMode (role_id dropped). AgentKey
loses KNOWLEDGE (no more standalone knowledge-lookup node; the Interviewer
agent reads the candidate's own knowledge directly). Confirmed with product:
no data migration needed for any of the dropped tables/columns.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4f0c2a9d1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New candidate-owned tables ──────────────────────────────────────────
    op.create_table(
        "candidate_target_roles",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ANALYZING", "READY", "FAILED", name="targetrolestatus"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_target_roles_candidate_id"), "candidate_target_roles", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_target_roles_id"), "candidate_target_roles", ["id"], unique=False)

    op.create_table(
        "candidate_target_role_fields",
        sa.Column("target_role_id", sa.UUID(), nullable=False),
        sa.Column("field_title", sa.String(length=200), nullable=False),
        sa.Column("field_description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["target_role_id"], ["candidate_target_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_target_role_fields_id"), "candidate_target_role_fields", ["id"], unique=False)
    op.create_index(op.f("ix_candidate_target_role_fields_target_role_id"), "candidate_target_role_fields", ["target_role_id"], unique=False)

    op.create_table(
        "candidate_knowledge_entries",
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("target_role_id", sa.UUID(), nullable=False),
        sa.Column("source_field_id", sa.UUID(), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("times_covered", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_role_id"], ["candidate_target_roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_field_id"], ["candidate_target_role_fields.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_knowledge_entries_candidate_id"), "candidate_knowledge_entries", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_knowledge_entries_target_role_id"), "candidate_knowledge_entries", ["target_role_id"], unique=False)
    op.create_index(op.f("ix_candidate_knowledge_entries_id"), "candidate_knowledge_entries", ["id"], unique=False)

    # ── interview_sessions: role_id -> target_role_id ───────────────────────
    op.add_column("interview_sessions", sa.Column("target_role_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "interview_sessions_target_role_id_fkey", "interview_sessions",
        "candidate_target_roles", ["target_role_id"], ["id"],
    )
    op.drop_constraint("interview_sessions_role_id_fkey", "interview_sessions", type_="foreignkey")
    op.drop_column("interview_sessions", "role_id")

    # ── interview_flows: drop role_id (flows are now global per InterviewMode) ──
    op.drop_constraint("interview_flows_role_id_fkey", "interview_flows", type_="foreignkey")
    op.drop_column("interview_flows", "role_id")

    # ── knowledge_documents / knowledge_bases: dropped outright, no data preserved ──
    op.drop_index(op.f("ix_knowledge_documents_knowledge_base_id"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_id"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index(op.f("ix_knowledge_bases_id"), table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
    op.execute("DROP TYPE IF EXISTS knowledgesourcetype")
    op.execute("DROP TYPE IF EXISTS embeddingstatus")

    # ── interview_roles: dropped outright, target roles are now candidate-owned ──
    op.drop_index(op.f("ix_interview_roles_slug"), table_name="interview_roles")
    op.drop_index(op.f("ix_interview_roles_id"), table_name="interview_roles")
    op.drop_table("interview_roles")

    # ── skills / competencies: unused admin content-authoring tables ────────
    op.drop_index(op.f("ix_skills_id"), table_name="skills")
    op.drop_table("skills")
    op.drop_index(op.f("ix_competencies_id"), table_name="competencies")
    op.drop_table("competencies")

    # ── agent_templates: drop knowledge_base_ids / question_source ──────────
    op.drop_column("agent_templates", "knowledge_base_ids")
    op.drop_column("agent_templates", "question_source")
    op.execute("DROP TYPE IF EXISTS questionsource")

    # ── AgentKey enum: remove the KNOWLEDGE value. Postgres has no direct
    # "DROP VALUE" for enums, so the type is recreated. Any existing rows
    # referencing 'knowledge' are removed first (the Knowledge Agent / Qdrant
    # retrieval path is deleted outright elsewhere in this refactor).
    # NOTE: SQLAlchemy's Enum(PythonEnumClass) stores the member NAME
    # ("KNOWLEDGE"), not its .value ("knowledge") -- confirmed by the
    # initial migration's own auto-generated DDL (e.g. AdminRole's
    # 'SUPER_ADMIN' label for a "super_admin" .value). Every raw-SQL literal
    # below must use the uppercase name form to match what's actually stored.
    op.execute("DELETE FROM agent_execution_logs WHERE agent_key = 'KNOWLEDGE'")
    op.execute("DELETE FROM agent_templates WHERE key = 'KNOWLEDGE'")
    op.execute("ALTER TYPE agentkey RENAME TO agentkey_old")
    op.execute("CREATE TYPE agentkey AS ENUM ('INTERVIEWER', 'EVALUATOR', 'ROUTER', 'FEEDBACK', 'COACH')")
    op.execute("ALTER TABLE agent_templates ALTER COLUMN key TYPE agentkey USING key::text::agentkey")
    op.execute("ALTER TABLE agent_execution_logs ALTER COLUMN agent_key TYPE agentkey USING agent_key::text::agentkey")
    op.execute("DROP TYPE agentkey_old")


def downgrade() -> None:
    # Structure-only reversal; none of the dropped data (roles, knowledge
    # base documents, skills/competencies) is recoverable — it was
    # intentionally not preserved (see revision docstring).
    op.execute("ALTER TYPE agentkey RENAME TO agentkey_old")
    op.execute("CREATE TYPE agentkey AS ENUM ('INTERVIEWER', 'EVALUATOR', 'ROUTER', 'FEEDBACK', 'KNOWLEDGE', 'COACH')")
    op.execute("ALTER TABLE agent_templates ALTER COLUMN key TYPE agentkey USING key::text::agentkey")
    op.execute("ALTER TABLE agent_execution_logs ALTER COLUMN agent_key TYPE agentkey USING agent_key::text::agentkey")
    op.execute("DROP TYPE agentkey_old")

    # The questionsource enum TYPE (not just the column) was dropped in
    # upgrade() -- unlike op.create_table, op.add_column does not
    # auto-create an inline enum type, so it must be recreated explicitly
    # before the column that uses it can be added back.
    op.execute("CREATE TYPE questionsource AS ENUM ('GENERATED', 'KNOWLEDGE_BASE', 'HYBRID')")
    op.add_column(
        "agent_templates",
        sa.Column("question_source", sa.Enum("GENERATED", "KNOWLEDGE_BASE", "HYBRID", name="questionsource"), nullable=True),
    )
    op.add_column("agent_templates", sa.Column("knowledge_base_ids", sa.JSON(), nullable=True))

    op.create_table(
        "competencies",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_competencies_id"), "competencies", ["id"], unique=False)

    op.create_table(
        "skills",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_skills_id"), "skills", ["id"], unique=False)

    op.create_table(
        "interview_roles",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("skill_tags", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_roles_id"), "interview_roles", ["id"], unique=False)
    op.create_index(op.f("ix_interview_roles_slug"), "interview_roles", ["slug"], unique=True)

    op.create_table(
        "knowledge_bases",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("source_type", sa.Enum("PDF", "MANUAL", "QUESTION_BANK", "RUBRIC", "FAQ", name="knowledgesourcetype"), nullable=False),
        sa.Column("qdrant_collection", sa.String(length=150), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_bases_id"), "knowledge_bases", ["id"], unique=False)

    op.create_table(
        "knowledge_documents",
        sa.Column("knowledge_base_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("embedding_status", sa.Enum("PENDING", "INDEXED", "FAILED", name="embeddingstatus"), nullable=False),
        sa.Column("vector_id", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_documents_id"), "knowledge_documents", ["id"], unique=False)
    op.create_index(op.f("ix_knowledge_documents_knowledge_base_id"), "knowledge_documents", ["knowledge_base_id"], unique=False)

    op.add_column("interview_flows", sa.Column("role_id", sa.UUID(), nullable=True))
    op.create_foreign_key("interview_flows_role_id_fkey", "interview_flows", "interview_roles", ["role_id"], ["id"])

    op.add_column("interview_sessions", sa.Column("role_id", sa.UUID(), nullable=True))
    op.create_foreign_key("interview_sessions_role_id_fkey", "interview_sessions", "interview_roles", ["role_id"], ["id"])
    op.drop_constraint("interview_sessions_target_role_id_fkey", "interview_sessions", type_="foreignkey")
    op.drop_column("interview_sessions", "target_role_id")

    op.drop_index(op.f("ix_candidate_knowledge_entries_id"), table_name="candidate_knowledge_entries")
    op.drop_index(op.f("ix_candidate_knowledge_entries_target_role_id"), table_name="candidate_knowledge_entries")
    op.drop_index(op.f("ix_candidate_knowledge_entries_candidate_id"), table_name="candidate_knowledge_entries")
    op.drop_table("candidate_knowledge_entries")

    op.drop_index(op.f("ix_candidate_target_role_fields_target_role_id"), table_name="candidate_target_role_fields")
    op.drop_index(op.f("ix_candidate_target_role_fields_id"), table_name="candidate_target_role_fields")
    op.drop_table("candidate_target_role_fields")

    op.drop_index(op.f("ix_candidate_target_roles_id"), table_name="candidate_target_roles")
    op.drop_index(op.f("ix_candidate_target_roles_candidate_id"), table_name="candidate_target_roles")
    op.drop_table("candidate_target_roles")
    op.execute("DROP TYPE IF EXISTS targetrolestatus")
