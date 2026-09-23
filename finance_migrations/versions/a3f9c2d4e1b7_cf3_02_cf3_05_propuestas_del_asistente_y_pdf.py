"""CF3-02..CF3-05: propuestas del asistente (AiProposal) y PDF en importacion

Revision ID: a3f9c2d4e1b7
Revises: 2e8ab89f9dad
Create Date: 2026-09-15 21:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3f9c2d4e1b7"
down_revision = "2e8ab89f9dad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_proposals",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('category_suggestion','insight','anomaly','budget_adjust')",
            name="ck_ai_proposal_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','applied','dismissed')", name="ck_ai_proposal_status"
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_proposals_household_id"), "ai_proposals", ["household_id"], unique=False
    )

    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_constraint("ck_import_batch_source_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_import_batch_source_kind", "source_kind IN ('csv','excel','pdf')"
        )


def downgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_constraint("ck_import_batch_source_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_import_batch_source_kind", "source_kind IN ('csv','excel')"
        )

    op.drop_index(op.f("ix_ai_proposals_household_id"), table_name="ai_proposals")
    op.drop_table("ai_proposals")
