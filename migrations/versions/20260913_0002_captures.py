"""Add auditable quick captures.

Revision ID: 20260913_0002
Revises: 20260913_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0002"
down_revision: str | None = "20260913_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "captures",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=True),
        sa.Column("project_id", sa.String(length=80), nullable=True),
        sa.Column("task_id", sa.String(length=80), nullable=True),
        sa.Column("action_item_id", sa.String(length=80), nullable=True),
        sa.Column("disposition_note", sa.Text(), nullable=True),
        sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('inbox','triaged')"),
        sa.CheckConstraint(
            "disposition IS NULL OR disposition IN ('task','action','reference','dismissed')"
        ),
        sa.ForeignKeyConstraint(["action_item_id"], ["action_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("captures")
