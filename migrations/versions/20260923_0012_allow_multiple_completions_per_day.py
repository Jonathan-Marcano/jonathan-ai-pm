"""Allow multiple habit completions per day (one row per external reference).

Revision ID: 20260923_0012
Revises: 20260922_0011
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260923_0012"
down_revision: str | None = "20260922_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_habit_completion_day", table_name="habit_completions")


def downgrade() -> None:
    op.create_index(
        "uq_habit_completion_day",
        "habit_completions",
        ["habit_id", "local_date"],
        unique=True,
    )