"""UI-6: modelo de metas de ahorro (financial_goals)

Revision ID: b7a2e9813c40
Revises: c1af45366829
Create Date: 2026-09-20 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7a2e9813c40"
down_revision = "f7e3d2c1b4a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_goals",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column("current_amount", sa.Integer(), nullable=False),
        sa.Column("monthly_contribution", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_amount > 0", name="ck_financial_goal_target_positive"
        ),
        sa.CheckConstraint(
            "current_amount >= 0", name="ck_financial_goal_current_nonnegative"
        ),
        sa.CheckConstraint(
            "monthly_contribution >= 0", name="ck_financial_goal_contribution_nonnegative"
        ),
        sa.CheckConstraint(
            "status IN ('active','achieved','archived')", name="ck_financial_goal_status"
        ),
        sa.CheckConstraint(
            "category IN ('fondo','security','travel','purchase','debt','other')",
            name="ck_financial_goal_category",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_financial_goals_household_id"),
        "financial_goals",
        ["household_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_financial_goals_household_id"), table_name="financial_goals")
    op.drop_table("financial_goals")