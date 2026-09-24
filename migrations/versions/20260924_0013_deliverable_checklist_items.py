"""Add deliverable checklist items with real persistence.

Revision ID: 20260924_0013
Revises: 20260923_0012
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260924_0013"
down_revision: str | None = "20260923_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deliverable_checklist_items",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("deliverable_id", sa.String(length=80), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "deliverable_id", "position", name="uq_deliverable_checklist_position"
        ),
    )
    op.create_index(
        "ix_deliverable_checklist_items_deliverable_id",
        "deliverable_checklist_items",
        ["deliverable_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deliverable_checklist_items_deliverable_id",
        table_name="deliverable_checklist_items",
    )
    op.drop_table("deliverable_checklist_items")