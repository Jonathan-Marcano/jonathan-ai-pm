"""CF2-06..CF2-08: identidad externa y vista previa de importacion

Revision ID: bc218b51ac69
Revises: 037a2c3a997e
Create Date: 2026-09-15 19:30:31.961340
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bc218b51ac69"
down_revision = "037a2c3a997e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("confirm_summary", sa.JSON(), nullable=True))

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("import_batch_id", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("external_source", sa.String(length=120), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_transactions_external_id"), ["external_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_transactions_import_batch_id"), ["import_batch_id"], unique=False
        )
        batch_op.create_index(
            "uq_transactions_external",
            ["account_id", "external_id", "external_source"],
            unique=True,
            sqlite_where=sa.text("external_id IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_transactions_external", sqlite_where=sa.text("external_id IS NOT NULL")
        )
        batch_op.drop_index(batch_op.f("ix_transactions_import_batch_id"))
        batch_op.drop_index(batch_op.f("ix_transactions_external_id"))
        batch_op.drop_column("external_source")
        batch_op.drop_column("external_id")
        batch_op.drop_column("import_batch_id")

    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_column("confirm_summary")
