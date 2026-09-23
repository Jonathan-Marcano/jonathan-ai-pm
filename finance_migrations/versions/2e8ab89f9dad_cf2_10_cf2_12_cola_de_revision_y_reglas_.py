"""CF2-10..CF2-12: cola de revision y reglas de categoria

Revision ID: 2e8ab89f9dad
Revises: bc218b51ac69
Create Date: 2026-09-15 19:43:13.375509
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2e8ab89f9dad"
down_revision = "bc218b51ac69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_category_rules",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("column", sa.String(length=80), nullable=False),
        sa.Column("pattern", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("enabled IN (0,1)", name="ck_import_category_rule_enabled"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_category_rules_category_id"),
        "import_category_rules",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_category_rules_household_id"),
        "import_category_rules",
        ["household_id"],
        unique=False,
    )

    op.create_table(
        "import_reviews",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("batch_id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("account_id", sa.String(length=80), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("transaction_id", sa.String(length=80), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('invalid','duplicate')", name="ck_import_review_kind"),
        sa.CheckConstraint(
            "status IN ('pending','resolved','discarded')", name="ck_import_review_status"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["financial_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_import_reviews_account_id"), "import_reviews", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_import_reviews_batch_id"), "import_reviews", ["batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_import_reviews_household_id"), "import_reviews", ["household_id"], unique=False
    )
    op.create_index(
        op.f("ix_import_reviews_transaction_id"),
        "import_reviews",
        ["transaction_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_reviews_transaction_id"), table_name="import_reviews")
    op.drop_index(op.f("ix_import_reviews_household_id"), table_name="import_reviews")
    op.drop_index(op.f("ix_import_reviews_batch_id"), table_name="import_reviews")
    op.drop_index(op.f("ix_import_reviews_account_id"), table_name="import_reviews")
    op.drop_table("import_reviews")

    op.drop_index(op.f("ix_import_category_rules_household_id"), table_name="import_category_rules")
    op.drop_index(op.f("ix_import_category_rules_category_id"), table_name="import_category_rules")
    op.drop_table("import_category_rules")
