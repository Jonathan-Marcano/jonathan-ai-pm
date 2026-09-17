"""Add foreign-key indexes and guard task deletion from action items.

Revision ID: 20260916_0006
Revises: 20260914_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0006"
down_revision: str | None = "20260914_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("ix_clients_workspace_id", "clients", ["workspace_id"]),
    ("ix_projects_client_id", "projects", ["client_id"]),
    ("ix_deliverables_project_id", "deliverables", ["project_id"]),
    ("ix_tasks_project_id", "tasks", ["project_id"]),
    ("ix_tasks_deliverable_id", "tasks", ["deliverable_id"]),
    ("ix_meetings_project_id", "meetings", ["project_id"]),
    ("ix_action_items_meeting_id", "action_items", ["meeting_id"]),
    ("ix_action_items_deliverable_id", "action_items", ["deliverable_id"]),
    ("ix_work_logs_task_id", "work_logs", ["task_id"]),
    ("ix_captures_project_id", "captures", ["project_id"]),
    ("ix_captures_task_id", "captures", ["task_id"]),
    ("ix_captures_action_item_id", "captures", ["action_item_id"]),
)


def _action_items_table(task_ondelete: str) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "action_items",
        metadata,
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("meeting_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=True),
        sa.Column("deliverable_id", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('captured','accepted','done','dismissed')"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverables.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete=task_ondelete),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "action_items", copy_from=_action_items_table("RESTRICT")
        ) as batch_op:
            batch_op.alter_column("task_id", nullable=True, existing_type=sa.String(length=80))

    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "action_items", copy_from=_action_items_table("SET NULL")
        ) as batch_op:
            batch_op.alter_column("task_id", nullable=True, existing_type=sa.String(length=80))