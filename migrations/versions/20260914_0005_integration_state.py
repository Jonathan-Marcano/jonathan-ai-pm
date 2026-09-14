"""Add external identities and synchronization history.

Revision ID: 20260914_0005
Revises: 20260914_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0005"
down_revision: str | None = "20260914_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("entity_kind", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_scope", sa.String(length=240), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("external_version", sa.String(length=500), nullable=True),
        sa.Column("web_url", sa.String(length=1000), nullable=True),
        sa.Column("external_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entity_kind IN ('meeting','deliverable')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_external_identity_source_key",
        ),
    )
    op.create_index("ix_external_identities_entity_kind", "external_identities", ["entity_kind"])
    op.create_index("ix_external_identities_entity_id", "external_identities", ["entity_id"])
    op.create_index(
        "ix_external_identities_source_system", "external_identities", ["source_system"]
    )
    op.create_index(
        "ix_external_identities_last_synced_at", "external_identities", ["last_synced_at"]
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("resource_kind", sa.String(length=20), nullable=False),
        sa.Column("external_scope", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("window_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("resource_kind IN ('calendar','document')"),
        sa.CheckConstraint("status IN ('running','succeeded','partial','failed')"),
        sa.CheckConstraint(
            "seen_count >= 0 AND created_count >= 0 AND updated_count >= 0 "
            "AND unchanged_count >= 0 AND skipped_count >= 0 AND error_count >= 0"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_source_system", "sync_runs", ["source_system"])
    op.create_index("ix_sync_runs_resource_kind", "sync_runs", ["resource_kind"])
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"])
    op.create_index("ix_sync_runs_started_at", "sync_runs", ["started_at"])

    op.create_table(
        "sync_run_errors",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("sync_run_id", sa.String(length=80), nullable=False),
        sa.Column("external_identity_id", sa.String(length=80), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["external_identity_id"], ["external_identities.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["sync_run_id"], ["sync_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_run_errors_sync_run_id", "sync_run_errors", ["sync_run_id"])
    op.create_index(
        "ix_sync_run_errors_external_identity_id",
        "sync_run_errors",
        ["external_identity_id"],
    )
    op.create_index("ix_sync_run_errors_occurred_at", "sync_run_errors", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_sync_run_errors_occurred_at", table_name="sync_run_errors")
    op.drop_index("ix_sync_run_errors_external_identity_id", table_name="sync_run_errors")
    op.drop_index("ix_sync_run_errors_sync_run_id", table_name="sync_run_errors")
    op.drop_table("sync_run_errors")
    op.drop_index("ix_sync_runs_started_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_resource_kind", table_name="sync_runs")
    op.drop_index("ix_sync_runs_source_system", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index("ix_external_identities_last_synced_at", table_name="external_identities")
    op.drop_index("ix_external_identities_source_system", table_name="external_identities")
    op.drop_index("ix_external_identities_entity_id", table_name="external_identities")
    op.drop_index("ix_external_identities_entity_kind", table_name="external_identities")
    op.drop_table("external_identities")
