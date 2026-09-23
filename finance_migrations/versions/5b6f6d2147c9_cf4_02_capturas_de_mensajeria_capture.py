"""CF4-02: capturas de mensajeria (Capture)

Revision ID: 5b6f6d2147c9
Revises: a3f9c2d4e1b7
Create Date: 2026-09-16 00:35:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5b6f6d2147c9"
down_revision = "a3f9c2d4e1b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "captures",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("raw_text", sa.String(length=2000), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confirmed_transaction_id", sa.String(length=80), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('text','audio','image')", name="ck_capture_kind"),
        sa.CheckConstraint(
            "status IN ('pending','needs_input','confirmed','rejected','discarded')",
            name="ck_capture_status",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["confirmed_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_captures_household_id"), "captures", ["household_id"], unique=False)
    op.create_index(
        op.f("ix_captures_confirmed_transaction_id"),
        "captures",
        ["confirmed_transaction_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_captures_confirmed_transaction_id"), table_name="captures")
    op.drop_index(op.f("ix_captures_household_id"), table_name="captures")
    op.drop_table("captures")
