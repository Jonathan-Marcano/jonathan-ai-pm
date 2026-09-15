from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
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
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('planned','active','paused','completed','cancelled')"),
        CheckConstraint("health IN ('unknown','on_track','at_risk','off_track')"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"))
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
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
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
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    deliverable_id: Mapped[str | None] = mapped_column(
        ForeignKey("deliverables.id", ondelete="SET NULL")
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
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")


class ActionItem(TimestampMixin, Base):
    __tablename__ = "action_items"
    __table_args__ = (CheckConstraint("status IN ('captured','accepted','done','dismissed')"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="RESTRICT"))
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), unique=True
    )
    deliverable_id: Mapped[str | None] = mapped_column(
        ForeignKey("deliverables.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="captured")
    owner: Mapped[str] = mapped_column(String(200))


class WorkLog(TimestampMixin, Base):
    __tablename__ = "work_logs"
    __table_args__ = (CheckConstraint("minutes > 0"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
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
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    action_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("action_items.id", ondelete="SET NULL")
    )
    disposition_note: Mapped[str | None] = mapped_column(Text)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    web_url: Mapped[str | None] = mapped_column(String(1000))
    external_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint("resource_kind IN ('calendar','document')"),
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
}
