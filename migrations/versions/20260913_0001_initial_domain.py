"""Create the Phase 1 domain tables."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260913_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The ORM metadata is the reviewed contract for this initial baseline.
    from jonathan_ai_pm.models import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    for table in (
        "work_logs",
        "action_items",
        "meetings",
        "tasks",
        "deliverables",
        "projects",
        "clients",
        "workspaces",
    ):
        op.drop_table(table)
