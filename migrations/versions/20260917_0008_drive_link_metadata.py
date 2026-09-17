"""Add Drive file metadata columns to external identities.

Revision ID: 20260917_0008
Revises: 20260917_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0008"
down_revision: str | None = "20260917_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "external_identities",
        sa.Column("external_name", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "external_identities",
        sa.Column("mime_type", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_identities", "mime_type")
    op.drop_column("external_identities", "external_name")