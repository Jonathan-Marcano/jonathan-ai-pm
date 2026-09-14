"""Add manual display translations.

Revision ID: 20260914_0004
Revises: 20260914_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0004"
down_revision: str | None = "20260914_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "translations",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("entity_kind", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=40), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_kind IN ('project','deliverable','task','meeting','action_item','capture')"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_kind",
            "entity_id",
            "field_name",
            "language",
            name="uq_translation_target_field_language",
        ),
    )
    op.create_index("ix_translations_entity_kind", "translations", ["entity_kind"])
    op.create_index("ix_translations_entity_id", "translations", ["entity_id"])
    op.create_index("ix_translations_language", "translations", ["language"])


def downgrade() -> None:
    op.drop_index("ix_translations_language", table_name="translations")
    op.drop_index("ix_translations_entity_id", table_name="translations")
    op.drop_index("ix_translations_entity_kind", table_name="translations")
    op.drop_table("translations")
