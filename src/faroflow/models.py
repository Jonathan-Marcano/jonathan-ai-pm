from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (CheckConstraint("status IN ('active','paused','archived')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")
    timezone: Mapped[str] = mapped_column(String(80))


class Client(TimestampMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (CheckConstraint("status IN ('active','paused','archived')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('planned','active','paused','completed','cancelled')"),
        CheckConstraint("health IN ('unknown','on_track','at_risk','off_track')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    health: Mapped[str] = mapped_column(String(20), default="unknown")


class Deliverable(TimestampMixin, Base):
    __tablename__ = "deliverables"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned','in_progress','in_review','accepted','blocked','cancelled')"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    due_at: Mapped[date] = mapped_column(Date)
    drive_url: Mapped[str | None] = mapped_column(String(500))
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(500))


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('inbox','ready','in_progress','blocked','done','cancelled')"),
        CheckConstraint("priority IN ('low','medium','high','critical')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    deliverable_id: Mapped[str | None] = mapped_column(
        ForeignKey("deliverables.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="inbox")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_at: Mapped[date | None] = mapped_column(Date)
    completion_note: Mapped[str | None] = mapped_column(Text)


class Meeting(TimestampMixin, Base):
    __tablename__ = "meetings"
    __table_args__ = (CheckConstraint("status IN ('scheduled','completed','cancelled')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionItem(TimestampMixin, Base):
    __tablename__ = "action_items"
    __table_args__ = (CheckConstraint("status IN ('captured','accepted','done','dismissed')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="RESTRICT"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), unique=True
    )
    deliverable_id: Mapped[str | None] = mapped_column(
        ForeignKey("deliverables.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="captured")
    owner: Mapped[str] = mapped_column(String(200))


class WorkLog(TimestampMixin, Base):
    __tablename__ = "work_logs"
    __table_args__ = (CheckConstraint("minutes > 0"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    minutes: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)


class Capture(TimestampMixin, Base):
    __tablename__ = "captures"
    __table_args__ = (
        CheckConstraint("status IN ('inbox','triaged')"),
        CheckConstraint(
            "disposition IS NULL OR disposition IN ('task','action','reference','dismissed')"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="inbox")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    disposition: Mapped[str | None] = mapped_column(String(20))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    action_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("action_items.id", ondelete="SET NULL"), index=True
    )
    disposition_note: Mapped[str | None] = mapped_column(Text)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    proposal_kind: Mapped[str | None] = mapped_column(String(20))
    proposal_source: Mapped[str | None] = mapped_column(String(80))
    proposal_confidence: Mapped[float | None] = mapped_column(Float)
    proposal_project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    proposal_owner: Mapped[str | None] = mapped_column(String(120))
    proposal_priority: Mapped[str | None] = mapped_column(String(20))
    proposal_due_at: Mapped[date | None] = mapped_column(Date)
    proposal_reasons: Mapped[list[str] | None] = mapped_column(JSON)
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Translation(TimestampMixin, Base):
    __tablename__ = "translations"
    __table_args__ = (
        CheckConstraint(
            "entity_kind IN ('project','deliverable','task','meeting','action_item','capture')"
        ),
        UniqueConstraint(
            "entity_kind",
            "entity_id",
            "field_name",
            "language",
            name="uq_translation_target_field_language",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    field_name: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(20), index=True)
    translated_text: Mapped[str] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint("action IN ('create','update','delete')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(200), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    changes: Mapped[dict] = mapped_column(JSON)


class ExternalIdentity(TimestampMixin, Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        CheckConstraint("entity_kind IN ('meeting','deliverable')"),
        UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_external_identity_source_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    source_system: Mapped[str] = mapped_column(String(80), index=True)
    external_scope: Mapped[str] = mapped_column(String(240), default="")
    external_id: Mapped[str] = mapped_column(String(500))
    external_version: Mapped[str | None] = mapped_column(String(500))
    external_name: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(200))
    web_url: Mapped[str | None] = mapped_column(String(1000))
    external_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint("resource_kind IN ('calendar','document','message')"),
        CheckConstraint("status IN ('running','succeeded','partial','failed')"),
        CheckConstraint(
            "seen_count >= 0 AND created_count >= 0 AND updated_count >= 0 "
            "AND unchanged_count >= 0 AND skipped_count >= 0 AND error_count >= 0"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80), index=True)
    resource_kind: Mapped[str] = mapped_column(String(20), index=True)
    external_scope: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    window_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)


class SyncRunError(Base):
    __tablename__ = "sync_run_errors"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    sync_run_id: Mapped[str] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"), index=True
    )
    external_identity_id: Mapped[str | None] = mapped_column(
        ForeignKey("external_identities.id", ondelete="SET NULL"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class Habit(TimestampMixin, Base):
    __tablename__ = "habits"
    __table_args__ = (
        CheckConstraint("status IN ('active','paused','archived')"),
        CheckConstraint("goal_type IN ('binary','quantity')"),
        CheckConstraint("frequency IN ('daily','weekly','weekdays','specific_days')"),
        CheckConstraint("target_quantity >= 1"),
        CheckConstraint("weekly_target IS NULL OR weekly_target >= 1"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    goal_type: Mapped[str] = mapped_column(String(20), default="binary")
    target_quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str | None] = mapped_column(String(40))
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    weekly_target: Mapped[int | None] = mapped_column(Integer)
    specific_days: Mapped[list[int] | None] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(80))


class HabitCompletion(TimestampMixin, Base):
    __tablename__ = "habit_completions"
    __table_args__ = (
        CheckConstraint("quantity >= 1"),
        CheckConstraint("source IN ('manual','bandeja','telegram')"),
        Index("ix_habit_completion_day", "habit_id", "local_date"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    habit_id: Mapped[str] = mapped_column(
        ForeignKey("habits.id", ondelete="RESTRICT"), index=True
    )
    local_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(20), default="manual")
    external_ref: Mapped[str | None] = mapped_column(String(240))


class BandejaItem(TimestampMixin, Base):
    __tablename__ = "bandeja_items"
    __table_args__ = (
        CheckConstraint("kind IN ('task','expense','income','habit','note','unknown')"),
        CheckConstraint(
            "status IN "
            "('received','reviewing','confirmed','applied','discarded','error')"
        ),
        UniqueConstraint(
            "channel", "source_ref", name="uq_bandeja_channel_source"
        ),
        CheckConstraint("attempts >= 0"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    channel: Mapped[str] = mapped_column(String(40), index=True)
    author: Mapped[str | None] = mapped_column(String(120))
    source_ref: Mapped[str] = mapped_column(String(240), index=True)
    original_text: Mapped[str] = mapped_column(String(4000))
    original_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="unknown")
    kind_confidence: Mapped[float | None] = mapped_column(Float)
    kind_source: Mapped[str] = mapped_column(String(40), default="manual")
    amount: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[str | None] = mapped_column(String(120))
    category_id: Mapped[str | None] = mapped_column(String(120))
    project_id: Mapped[str | None] = mapped_column(String(80))
    habit_id: Mapped[str | None] = mapped_column(String(80))
    destination_module: Mapped[str | None] = mapped_column(String(40))
    destination_ref: Mapped[str | None] = mapped_column(String(120))
    attachments: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="received")
    error: Mapped[str | None] = mapped_column(String(1000))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    drive_file_id: Mapped[str | None] = mapped_column(String(240))
    drive_version: Mapped[str | None] = mapped_column(String(120))
    integrity_ok: Mapped[bool | None] = mapped_column(Boolean)
    drive_cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(500))


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MeetingProjectMapping(TimestampMixin, Base):
    """User-confirmed provider source key to project association for reuse."""

    __tablename__ = "meeting_project_mappings"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "external_scope",
            "external_id",
            name="uq_meeting_project_mapping_source_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80), index=True)
    external_scope: Mapped[str] = mapped_column(String(240), default="")
    external_id: Mapped[str] = mapped_column(String(500))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )


MODEL_BY_KIND = {
    "workspace": Workspace,
    "client": Client,
    "project": Project,
    "deliverable": Deliverable,
    "task": Task,
    "meeting": Meeting,
    "action_item": ActionItem,
    "work_log": WorkLog,
    "capture": Capture,
    "translation": Translation,
    "habit": Habit,
    "habit_completion": HabitCompletion,
    "bandeja": BandejaItem,
}
