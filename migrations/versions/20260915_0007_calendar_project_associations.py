"""Add calendar review queue and confirmed project mappings.

Revision ID: 20260915_0007
Revises: 20260915_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0007"
down_revision: str | None = "20260915_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_project_mappings",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_scope", sa.String(length=240), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("confirmed_by", sa.String(length=200), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_calendar_project_mapping_source_key",
        ),
    )
    op.create_index(
        "ix_calendar_project_mappings_source_system",
        "calendar_project_mappings",
        ["source_system"],
    )
    op.create_index(
        "ix_calendar_project_mappings_confirmed_at",
        "calendar_project_mappings",
        ["confirmed_at"],
    )

    op.create_table(
        "calendar_import_reviews",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_scope", sa.String(length=240), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_status", sa.String(length=20), nullable=False),
        sa.Column("web_url", sa.String(length=1000), nullable=True),
        sa.Column("external_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_project_id", sa.String(length=80), nullable=True),
        sa.Column("resolved_by", sa.String(length=200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','resolved','dismissed')"),
        sa.CheckConstraint("event_status IN ('confirmed','cancelled')"),
        sa.CheckConstraint(
            "(status = 'pending' AND resolution_project_id IS NULL "
            "AND resolved_by IS NULL AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolution_project_id IS NOT NULL "
            "AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL) OR "
            "(status = 'dismissed' AND resolution_project_id IS NULL "
            "AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_calendar_import_review_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["resolution_project_id"], ["projects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_calendar_import_review_source_key",
        ),
    )
    op.create_index(
        "ix_calendar_import_reviews_source_system",
        "calendar_import_reviews",
        ["source_system"],
    )
    op.create_index(
        "ix_calendar_import_reviews_starts_at",
        "calendar_import_reviews",
        ["starts_at"],
    )
    op.create_index(
        "ix_calendar_import_reviews_status",
        "calendar_import_reviews",
        ["status"],
    )
    op.create_index(
        "ix_calendar_import_reviews_last_seen_at",
        "calendar_import_reviews",
        ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_import_reviews_last_seen_at", table_name="calendar_import_reviews")
    op.drop_index("ix_calendar_import_reviews_status", table_name="calendar_import_reviews")
    op.drop_index("ix_calendar_import_reviews_starts_at", table_name="calendar_import_reviews")
    op.drop_index(
        "ix_calendar_import_reviews_source_system", table_name="calendar_import_reviews"
    )
    op.drop_table("calendar_import_reviews")
    op.drop_index(
        "ix_calendar_project_mappings_confirmed_at",
        table_name="calendar_project_mappings",
    )
    op.drop_index(
        "ix_calendar_project_mappings_source_system",
        table_name="calendar_project_mappings",
    )
    op.drop_table("calendar_project_mappings")
