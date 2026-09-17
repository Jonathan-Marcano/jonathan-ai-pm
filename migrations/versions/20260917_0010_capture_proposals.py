"""Add read-only classification proposals to inbox captures.

Revision ID: 20260917_0010
Revises: 20260917_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0010"
down_revision: str | None = "20260917_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column("proposal_kind", sa.String(20), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_source", sa.String(80), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_confidence", sa.Float, nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_project_id", sa.String(80), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_owner", sa.String(120), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_priority", sa.String(20), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_due_at", sa.Date, nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposal_reasons", sa.Text, nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("captures", "applied_at")
    op.drop_column("captures", "proposed_at")
    op.drop_column("captures", "proposal_reasons")
    op.drop_column("captures", "proposal_due_at")
    op.drop_column("captures", "proposal_priority")
    op.drop_column("captures", "proposal_owner")
    op.drop_column("captures", "proposal_project_id")
    op.drop_column("captures", "proposal_confidence")
    op.drop_column("captures", "proposal_source")
    op.drop_column("captures", "proposal_kind")
