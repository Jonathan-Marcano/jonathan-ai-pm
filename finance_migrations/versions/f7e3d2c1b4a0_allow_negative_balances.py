"""allow negative balances

Revision ID: f7e3d2c1b4a0
Revises: c1af45366829
Create Date: 2026-09-16 02:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7e3d2c1b4a0"
down_revision = "c1af45366829"
branch_labels = None
depends_on = None

_TMP = "financial_accounts_tmp"


def _recreate_without_balance_checks() -> None:
    op.create_table(
        _TMP,
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("institution_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("balance_reported", sa.Integer(), nullable=False),
        sa.Column("balance_calculated", sa.Integer(), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency = 'CLP'"),
        sa.CheckConstraint("status IN ('active','paused','closed')"),
        sa.CheckConstraint(
            "type IN ('checking','savings','credit_card','cash','wallet','loan_line')"
        ),
        sa.CheckConstraint("original_amount IS NULL OR original_amount >= 0"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["financial_institutions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO financial_accounts_tmp (
            id, household_id, institution_id, name, type, currency,
            balance_reported, balance_calculated, original_amount, status,
            created_at, updated_at
        )
        SELECT
            id, household_id, institution_id, name, type, currency,
            balance_reported, balance_calculated, original_amount, status,
            created_at, updated_at
        FROM financial_accounts
        """
    )
    op.drop_table("financial_accounts")
    op.rename_table(_TMP, "financial_accounts")
    op.create_index(
        "ix_financial_accounts_household_id", "financial_accounts", ["household_id"], unique=False
    )
    op.create_index(
        "ix_financial_accounts_institution_id",
        "financial_accounts",
        ["institution_id"],
        unique=False,
    )


def _recreate_with_balance_checks() -> None:
    op.create_table(
        _TMP,
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("institution_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("balance_reported", sa.Integer(), nullable=False),
        sa.Column("balance_calculated", sa.Integer(), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("balance_reported >= 0"),
        sa.CheckConstraint("balance_calculated >= 0"),
        sa.CheckConstraint("currency = 'CLP'"),
        sa.CheckConstraint("status IN ('active','paused','closed')"),
        sa.CheckConstraint(
            "type IN ('checking','savings','credit_card','cash','wallet','loan_line')"
        ),
        sa.CheckConstraint("original_amount IS NULL OR original_amount >= 0"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["financial_institutions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO financial_accounts_tmp (
            id, household_id, institution_id, name, type, currency,
            balance_reported, balance_calculated, original_amount, status,
            created_at, updated_at
        )
        SELECT
            id, household_id, institution_id, name, type, currency,
            balance_reported, balance_calculated, original_amount, status,
            created_at, updated_at
        FROM financial_accounts
        """
    )
    op.drop_table("financial_accounts")
    op.rename_table(_TMP, "financial_accounts")
    op.create_index(
        "ix_financial_accounts_household_id", "financial_accounts", ["household_id"], unique=False
    )
    op.create_index(
        "ix_financial_accounts_institution_id",
        "financial_accounts",
        ["institution_id"],
        unique=False,
    )


def upgrade() -> None:
    _recreate_without_balance_checks()


def downgrade() -> None:
    _recreate_with_balance_checks()