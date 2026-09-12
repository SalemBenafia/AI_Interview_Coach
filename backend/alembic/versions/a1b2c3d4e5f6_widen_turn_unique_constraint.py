"""widen turn unique constraint to include speaker

Revision ID: a1b2c3d4e5f6
Revises: d6d3823658fa
Create Date: 2026-06-30

The original constraint UNIQUE(session_id, turn_number) prevented storing both
the candidate's answer and the AI's reply under the same turn number, which is
the intended design: both sides of a conversation exchange share the same
turn_number. Add 'speaker' to make the pair (session_id, turn_number, speaker)
the uniqueness key instead.
"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d6d3823658fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_session_turn_number", "interview_turns", type_="unique")
    op.create_unique_constraint(
        "uq_session_turn_number",
        "interview_turns",
        ["session_id", "turn_number", "speaker"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_session_turn_number", "interview_turns", type_="unique")
    op.create_unique_constraint(
        "uq_session_turn_number",
        "interview_turns",
        ["session_id", "turn_number"],
    )
