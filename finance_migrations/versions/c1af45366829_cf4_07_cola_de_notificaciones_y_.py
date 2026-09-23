"""CF4-07: cola de notificaciones y registro de envios

Revision ID: c1af45366829
Revises: 5b6f6d2147c9
Create Date: 2026-09-15 21:59:16.770746
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1af45366829"
down_revision = "5b6f6d2147c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("template_kind", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "template_kind IN ('upcoming_payment','weekly_summary','budget_deviation','monthly_close')",
            name="ck_notification_preference_kind",
        ),
        sa.CheckConstraint("enabled IN (0,1)", name="ck_notification_preference_enabled"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "template_kind", name="uq_notification_preference"),
    )
    op.create_index(
        op.f("ix_notification_preferences_household_id"),
        "notification_preferences",
        ["household_id"],
        unique=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("household_id", sa.String(length=80), nullable=False),
        sa.Column("template_kind", sa.String(length=40), nullable=False),
        sa.Column("recipient", sa.String(length=120), nullable=False),
        sa.Column("external_ref", sa.String(length=120), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("send_provider", sa.String(length=40), nullable=False),
        sa.Column("message_id", sa.String(length=120), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','sent','failed')", name="ck_notification_status"),
        sa.CheckConstraint(
            "template_kind IN ('upcoming_payment','weekly_summary','budget_deviation','monthly_close')",
            name="ck_notification_kind",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_attempts_nonnegative"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id", "template_kind", "external_ref", name="uq_notification_ref"
        ),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_due_date"), ["due_date"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_notifications_household_id"), ["household_id"], unique=False
        )

    op.create_table(
        "notification_sends",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("notification_id", sa.String(length=80), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("message_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider != ''", name="ck_notification_send_provider"),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_sends_notification_id"),
        "notification_sends",
        ["notification_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_sends_notification_id"), table_name="notification_sends")
    op.drop_table("notification_sends")
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notifications_household_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_due_date"))

    op.drop_table("notifications")
    op.drop_index(
        op.f("ix_notification_preferences_household_id"), table_name="notification_preferences"
    )
    op.drop_table("notification_preferences")
