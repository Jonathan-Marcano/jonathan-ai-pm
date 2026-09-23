"""UI-4: día de cierre (statement) y vencimiento en cuentas (tarjetas).

Revision ID: 6c1d4a8f2e9b
Revises: 4d1c9f8a2b3e
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "6c1d4a8f2e9b"
down_revision = "4d1c9f8a2b3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_accounts",
        sa.Column("statement_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "financial_accounts",
        sa.Column("due_day", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("financial_accounts", "due_day")
    op.drop_column("financial_accounts", "statement_day")