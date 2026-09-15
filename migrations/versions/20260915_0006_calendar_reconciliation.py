"""Track external identities missing from a calendar window.

Revision ID: 20260915_0006
Revises: 20260914_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0006"
down_revision: str | None = "20260914_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "external_identities",
        sa.Column("missing_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_external_identities_missing_since",
        "external_identities",
        ["missing_since"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_identities_missing_since", table_name="external_identities")
    op.drop_column("external_identities", "missing_since")
