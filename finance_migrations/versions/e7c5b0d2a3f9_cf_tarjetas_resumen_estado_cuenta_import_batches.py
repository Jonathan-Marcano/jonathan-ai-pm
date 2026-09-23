"""Tarjeta de crédito: resumen de estado de cuenta detectado en importación.

Revision ID: e7c5b0d2a3f9
Revises: 6c1d4a8f2e9b
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "e7c5b0d2a3f9"
down_revision = "6c1d4a8f2e9b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("statement_meta", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_batches", "statement_meta")