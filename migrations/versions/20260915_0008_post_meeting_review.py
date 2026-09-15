"""Add explicit post-meeting review state.

Revision ID: 20260915_0008
Revises: 20260915_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0008"
down_revision: str | None = "20260915_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table(
        "meetings",
        table_args=(
            sa.CheckConstraint(
                "status IN ('scheduled','completed','cancelled')",
                name="ck_meetings_status",
            ),
        ),
    ) as batch_op:
        batch_op.add_column(sa.Column("review_decision", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("review_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_meeting_review_decision",
            "review_decision IS NULL OR review_decision IN ('actions_captured','no_follow_up')",
        )
        batch_op.create_check_constraint(
            "ck_meeting_review_complete",
            "(review_decision IS NULL AND review_summary IS NULL "
            "AND reviewed_by IS NULL AND reviewed_at IS NULL) OR "
            "(review_decision IS NOT NULL AND review_summary IS NOT NULL "
            "AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
        )
        batch_op.create_index("ix_meetings_reviewed_at", ["reviewed_at"])


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_index("ix_meetings_reviewed_at")
        batch_op.drop_constraint("ck_meeting_review_complete", type_="check")
        batch_op.drop_constraint("ck_meeting_review_decision", type_="check")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("review_summary")
        batch_op.drop_column("review_decision")
