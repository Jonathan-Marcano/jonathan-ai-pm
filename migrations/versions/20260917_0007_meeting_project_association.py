"""Allow unmatched meetings and persist confirmed project associations.

Revision ID: 20260917_0007
Revises: 20260916_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0007"
down_revision: str | None = "20260916_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _meetings_table(project_nullable: bool) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "meetings",
        metadata,
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=project_nullable),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('scheduled','completed','cancelled')"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_meetings_project_id", "project_id"),
    )


def upgrade() -> None:
    op.create_table(
        "meeting_project_mappings",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_scope", sa.String(length=240), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_meeting_project_mapping_source_key",
        ),
    )
    op.create_index(
        "ix_meeting_project_mappings_source_system",
        "meeting_project_mappings",
        ["source_system"],
    )
    op.create_index(
        "ix_meeting_project_mappings_project_id",
        "meeting_project_mappings",
        ["project_id"],
    )

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "meetings", copy_from=_meetings_table(project_nullable=True)
        ) as batch_op:
            batch_op.alter_column("project_id", nullable=True, existing_type=sa.String(length=80))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "meetings", copy_from=_meetings_table(project_nullable=False)
        ) as batch_op:
            batch_op.alter_column("project_id", nullable=False, existing_type=sa.String(length=80))

    op.drop_index("ix_meeting_project_mappings_project_id", table_name="meeting_project_mappings")
    op.drop_index(
        "ix_meeting_project_mappings_source_system", table_name="meeting_project_mappings"
    )
    op.drop_table("meeting_project_mappings")