"""UI-4: cupo de tarjetas (credit_limit) en financial_accounts.

Revision ID: 4d1c9f8a2b3e
Revises: b7a2e9813c40
Create Date: 2026-09-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4d1c9f8a2b3e"
down_revision = "b7a2e9813c40"
branch_labels = None
depends_on = None

_TMP = "financial_accounts_tmp"

_COLUMNS = (
    "id, household_id, institution_id, name, type, currency, "
    "balance_reported, balance_calculated, original_amount, status, "
    "created_at, updated_at"
)


def _recreate(with_credit_limit: bool) -> None:
    checks = [
        sa.CheckConstraint("currency = 'CLP'"),
        sa.CheckConstraint("status IN ('active','paused','closed')"),
        sa.CheckConstraint(
            "type IN ('checking','savings','credit_card','cash','wallet','loan_line')"
        ),
        sa.CheckConstraint("original_amount IS NULL OR original_amount >= 0"),
    ]
    if with_credit_limit:
        checks.append(
            sa.CheckConstraint("credit_limit IS NULL OR credit_limit >= 0")
        )
    columns = [
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("institution_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("balance_reported", sa.Integer(), nullable=False),
        sa.Column("balance_calculated", sa.Integer(), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=True),
    ]
    if with_credit_limit:
        columns.append(sa.Column("credit_limit", sa.Integer(), nullable=True))
    columns += [
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        _TMP,
        *columns,
        *checks,
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["financial_institutions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    insert_columns = _COLUMNS
    insert_tail = ""
    if with_credit_limit:
        insert_tail = ", NULL"
    op.execute(
        f"""
        INSERT INTO {_TMP} ({insert_columns}{', credit_limit' if with_credit_limit else ''})
        SELECT {insert_columns}{insert_tail}
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
    _recreate(with_credit_limit=True)


def downgrade() -> None:
    _recreate(with_credit_limit=False)