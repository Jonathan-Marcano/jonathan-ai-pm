"""Unified home domain: habits, habit completions, bandeja and app state.

Revision ID: 20260922_0011
Revises: 20260917_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0011"
down_revision: str | None = "20260917_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "habits",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("goal_type", sa.String(20), nullable=False),
        sa.Column("target_quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("weekly_target", sa.Integer(), nullable=True),
        sa.Column("specific_days", sa.JSON(), nullable=True),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active','paused','archived')"),
        sa.CheckConstraint("goal_type IN ('binary','quantity')"),
        sa.CheckConstraint("frequency IN ('daily','weekly','weekdays','specific_days')"),
        sa.CheckConstraint("target_quantity >= 1"),
        sa.CheckConstraint("weekly_target IS NULL OR weekly_target >= 1"),
    )
    op.create_table(
        "habit_completions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("habit_id", sa.String(80), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("external_ref", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["habit_id"], ["habits.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("quantity >= 1"),
        sa.CheckConstraint("source IN ('manual','bandeja','telegram')"),
        sa.UniqueConstraint("habit_id", "local_date", name="uq_habit_completion_day"),
    )
    op.create_index(
        "ix_habit_completions_habit_id", "habit_completions", ["habit_id"]
    )
    op.create_index(
        "ix_habit_completions_local_date", "habit_completions", ["local_date"]
    )
    op.create_table(
        "bandeja_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("author", sa.String(120), nullable=True),
        sa.Column("source_ref", sa.String(240), nullable=False),
        sa.Column("original_text", sa.String(4000), nullable=False),
        sa.Column("original_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("kind_confidence", sa.Float(), nullable=True),
        sa.Column("kind_source", sa.String(40), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.String(120), nullable=True),
        sa.Column("category_id", sa.String(120), nullable=True),
        sa.Column("project_id", sa.String(80), nullable=True),
        sa.Column("habit_id", sa.String(80), nullable=True),
        sa.Column("destination_module", sa.String(40), nullable=True),
        sa.Column("destination_ref", sa.String(120), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("drive_file_id", sa.String(240), nullable=True),
        sa.Column("drive_version", sa.String(120), nullable=True),
        sa.Column("integrity_ok", sa.Boolean(), nullable=True),
        sa.Column("drive_cleaned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('task','expense','income','habit','note','unknown')"),
        sa.CheckConstraint(
            "status IN ('received','reviewing','confirmed','applied','discarded','error')"
        ),
        sa.CheckConstraint("attempts >= 0"),
        sa.UniqueConstraint("channel", "source_ref", name="uq_bandeja_channel_source"),
    )
    op.create_index("ix_bandeja_items_channel", "bandeja_items", ["channel"])
    op.create_index("ix_bandeja_items_source_ref", "bandeja_items", ["source_ref"])
    op.create_index("ix_bandeja_items_original_at", "bandeja_items", ["original_at"])
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_state")
    op.drop_index("ix_bandeja_items_original_at", table_name="bandeja_items")
    op.drop_index("ix_bandeja_items_source_ref", table_name="bandeja_items")
    op.drop_index("ix_bandeja_items_channel", table_name="bandeja_items")
    op.drop_table("bandeja_items")
    op.drop_index("ix_habit_completions_local_date", table_name="habit_completions")
    op.drop_index("ix_habit_completions_habit_id", table_name="habit_completions")
    op.drop_table("habit_completions")
    op.drop_table("habits")