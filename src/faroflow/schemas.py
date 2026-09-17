import json
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from faroflow.classification import ProposalKind
from faroflow.domain_rules import (
    action_item_link_error,
    deliverable_review_evidence_error,
    task_completion_evidence_error,
)

EntityId = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]+$")]
Name = Annotated[str, Field(min_length=1, max_length=300)]
Url = Annotated[str, Field(max_length=500, pattern=r"^https?://")]

RecordStatus = Literal["active", "paused", "archived"]
ProjectStatus = Literal["planned", "active", "paused", "completed", "cancelled"]
ProjectHealth = Literal["unknown", "on_track", "at_risk", "off_track"]
DeliverableStatus = Literal[
    "planned", "in_progress", "in_review", "accepted", "blocked", "cancelled"
]
TaskStatus = Literal["inbox", "ready", "in_progress", "blocked", "done", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "critical"]
MeetingStatus = Literal["scheduled", "completed", "cancelled"]
ActionItemStatus = Literal["captured", "accepted", "done", "dismissed"]
CaptureStatus = Literal["inbox", "triaged"]
CaptureDisposition = Literal["task", "action", "reference", "dismissed"]
TranslatableEntityKind = Literal[
    "project", "deliverable", "task", "meeting", "action_item", "capture"
]
TranslationField = Literal["name", "title", "text"]
LanguageCode = Annotated[
    str,
    Field(min_length=2, max_length=20, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"),
]
EntityKind = Literal[
    "workspace",
    "client",
    "project",
    "deliverable",
    "task",
    "meeting",
    "action_item",
    "work_log",
    "capture",
    "translation",
]
AuditAction = Literal["create", "update", "delete"]
SnapshotVersion = Literal["1.0", "1.1"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Timestamps(ResponseModel):
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(StrictModel):
    id: EntityId
    name: Name
    status: RecordStatus = "active"
    timezone: Annotated[str, Field(min_length=1, max_length=80)]


class WorkspaceUpdate(StrictModel):
    name: Name | None = None
    status: RecordStatus | None = None
    timezone: Annotated[str, Field(min_length=1, max_length=80)] | None = None


class WorkspaceRead(Timestamps, WorkspaceCreate):
    pass


class ClientCreate(StrictModel):
    id: EntityId
    workspace_id: EntityId
    name: Name
    status: RecordStatus = "active"


class ClientUpdate(StrictModel):
    workspace_id: EntityId | None = None
    name: Name | None = None
    status: RecordStatus | None = None


class ClientRead(Timestamps, ClientCreate):
    pass


class ProjectCreate(StrictModel):
    id: EntityId
    client_id: EntityId
    name: Name
    status: ProjectStatus = "planned"
    health: ProjectHealth = "unknown"


class ProjectUpdate(StrictModel):
    client_id: EntityId | None = None
    name: Name | None = None
    status: ProjectStatus | None = None
    health: ProjectHealth | None = None


class ProjectRead(Timestamps, ProjectCreate):
    pass


class DeliverableCreate(StrictModel):
    id: EntityId
    project_id: EntityId
    title: Name
    status: DeliverableStatus = "planned"
    due_at: date
    drive_url: Url | None = None
    acceptance_criteria: Annotated[str, Field(min_length=1)] | None = None
    evidence_url: Url | None = None


class DeliverableUpdate(StrictModel):
    project_id: EntityId | None = None
    title: Name | None = None
    status: DeliverableStatus | None = None
    due_at: date | None = None
    drive_url: Url | None = None
    acceptance_criteria: Annotated[str, Field(min_length=1)] | None = None
    evidence_url: Url | None = None


class DeliverableRead(Timestamps, DeliverableCreate):
    pass


class TaskCreate(StrictModel):
    id: EntityId
    project_id: EntityId
    deliverable_id: EntityId | None = None
    title: Name
    status: TaskStatus = "inbox"
    priority: TaskPriority = "medium"
    due_at: date | None = None
    completion_note: str | None = None


class TaskUpdate(StrictModel):
    project_id: EntityId | None = None
    deliverable_id: EntityId | None = None
    title: Name | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: date | None = None
    completion_note: str | None = None


class TaskRead(Timestamps, TaskCreate):
    pass


class TaskComplete(StrictModel):
    completion_note: Annotated[str, Field(min_length=1)] | None = None


class WorkLogCreate(StrictModel):
    started_at: datetime | None = None
    minutes: Annotated[int, Field(ge=1)]
    summary: Annotated[str, Field(min_length=1, max_length=5000)]


class WorkLogRead(Timestamps):
    id: EntityId
    task_id: EntityId
    started_at: datetime
    minutes: int
    summary: str


class MeetingCreate(StrictModel):
    id: EntityId
    project_id: EntityId
    title: Name
    starts_at: datetime
    status: MeetingStatus = "scheduled"


class MeetingUpdate(StrictModel):
    project_id: EntityId | None = None
    title: Name | None = None
    starts_at: datetime | None = None
    status: MeetingStatus | None = None


class MeetingRead(Timestamps, MeetingCreate):
    project_id: EntityId | None
    reviewed_at: datetime | None = None


class MeetingReview(StrictModel):
    decision: Literal["reviewed"] = "reviewed"


class MeetingProjectAssociate(StrictModel):
    project_id: EntityId


class MeetingProjectMappingRead(ResponseModel):
    id: EntityId
    source_system: str
    external_scope: str
    external_id: str
    project_id: EntityId
    created_at: datetime
    updated_at: datetime


class DriveFileLinkCreate(StrictModel):
    source_system: Annotated[str, Field(min_length=1, max_length=80)]
    external_id: Annotated[str, Field(min_length=1, max_length=500)]
    name: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    web_url: Url | None = None
    mime_type: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class DriveLinkRead(ResponseModel):
    id: EntityId
    deliverable_id: EntityId
    deliverable_title: Name
    source_system: str
    external_id: str
    external_name: str | None
    web_url: str | None
    mime_type: str | None
    external_version: str | None
    external_modified_at: datetime | None
    last_synced_at: datetime
    created_at: datetime
    updated_at: datetime


class SyncRunRead(ResponseModel):
    id: EntityId
    source_system: str
    resource_kind: str
    external_scope: str | None
    status: str
    window_starts_at: datetime | None
    window_ends_at: datetime | None
    started_at: datetime
    completed_at: datetime | None
    seen_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    skipped_count: int
    error_count: int


class SyncRunErrorRead(ResponseModel):
    id: EntityId
    sync_run_id: EntityId
    external_identity_id: EntityId | None
    code: str
    message: str
    occurred_at: datetime


class ActionItemCreate(StrictModel):
    id: EntityId
    meeting_id: EntityId
    task_id: EntityId | None = None
    deliverable_id: EntityId | None = None
    title: Name
    status: ActionItemStatus = "captured"
    owner: Name


class ActionItemUpdate(StrictModel):
    meeting_id: EntityId | None = None
    task_id: EntityId | None = None
    deliverable_id: EntityId | None = None
    title: Name | None = None
    status: ActionItemStatus | None = None
    owner: Name | None = None


class ActionItemRead(Timestamps, ActionItemCreate):
    pass


class ActionItemToTask(StrictModel):
    task_id: EntityId
    priority: TaskPriority = "medium"
    due_at: date | None = None
    deliverable_id: EntityId | None = None


class CaptureCreate(StrictModel):
    text: Annotated[str, Field(min_length=1, max_length=5000)]


class CaptureRead(Timestamps):
    id: EntityId
    text: str
    status: CaptureStatus
    captured_at: datetime
    disposition: CaptureDisposition | None = None
    project_id: EntityId | None = None
    task_id: EntityId | None = None
    action_item_id: EntityId | None = None
    disposition_note: str | None = None
    triaged_at: datetime | None = None
    proposal_kind: ProposalKind | None = None
    proposal_source: str | None = None
    proposal_confidence: float | None = None
    proposal_project_id: EntityId | None = None
    proposal_owner: str | None = None
    proposal_priority: TaskPriority | None = None
    proposal_due_at: date | None = None
    proposal_reasons: list[str] | None = None
    proposed_at: datetime | None = None
    applied_at: datetime | None = None

    @field_validator("proposal_reasons", mode="before")
    @classmethod
    def parse_proposal_reasons(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except ValueError:
                return []
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, str)]
        return value


class CaptureTriage(StrictModel):
    disposition: CaptureDisposition
    project_id: EntityId | None = None
    task_id: EntityId | None = None
    action_item_id: EntityId | None = None
    meeting_id: EntityId | None = None
    deliverable_id: EntityId | None = None
    owner: Name | None = None
    priority: TaskPriority = "medium"
    due_at: date | None = None
    note: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_destination(self) -> Self:
        if self.disposition == "task" and (not self.project_id or not self.task_id):
            raise ValueError("Task triage requires project_id and task_id")
        if self.disposition == "task" and (self.meeting_id or self.action_item_id or self.owner):
            raise ValueError("Task triage cannot include action-item fields")
        if self.disposition == "action" and (
            not self.meeting_id or not self.action_item_id or not self.owner
        ):
            raise ValueError("Action triage requires meeting_id, action_item_id, and owner")
        if self.disposition == "action" and self.task_id:
            raise ValueError("Action triage cannot include task_id")
        if self.disposition in {"reference", "dismissed"} and any(
            (self.task_id, self.action_item_id, self.meeting_id, self.deliverable_id, self.owner)
        ):
            raise ValueError("Reference and dismissed triage cannot include work-item fields")
        if self.disposition == "dismissed" and not self.note:
            raise ValueError("Dismissed triage requires a note")
        return self


class CaptureApply(StrictModel):
    """Explicit confirmation payload for a pending capture proposal."""

    meeting_id: EntityId | None = None


class TranslationCreate(StrictModel):
    id: EntityId
    entity_kind: TranslatableEntityKind
    entity_id: EntityId
    field_name: TranslationField
    language: LanguageCode
    translated_text: Annotated[str, Field(min_length=1, max_length=10000)]


class TranslationUpdate(StrictModel):
    translated_text: Annotated[str, Field(min_length=1, max_length=10000)]


class TranslationRead(Timestamps, TranslationCreate):
    pass


class MorningBriefCounts(StrictModel):
    meetings: int
    overdue_tasks: int
    due_soon_tasks: int
    focus_tasks: int
    blocked_tasks: int
    blocked_deliverables: int
    deliverable_opportunities: int
    at_risk_projects: int


class MorningBrief(ResponseModel):
    brief_date: date
    timezone: str
    due_soon_through: date
    generated_at: datetime
    counts: MorningBriefCounts
    meetings: list[MeetingRead]
    overdue_tasks: list[TaskRead]
    due_soon_tasks: list[TaskRead]
    focus_tasks: list[TaskRead]
    blocked_tasks: list[TaskRead]
    blocked_deliverables: list[DeliverableRead]
    deliverable_opportunities: list[DeliverableRead]
    at_risk_projects: list[ProjectRead]


class EveningCloseCounts(StrictModel):
    completed_tasks: int
    work_logs: int
    logged_minutes: int
    untriaged_captures: int
    triaged_captures: int
    open_action_items: int
    unfinished_tasks: int
    blocked_tasks: int
    touched_deliverables: int
    projects_to_review: int


class EveningClose(ResponseModel):
    close_date: date
    timezone: str
    generated_at: datetime
    counts: EveningCloseCounts
    completed_tasks: list[TaskRead]
    work_logs: list[WorkLogRead]
    untriaged_captures: list[CaptureRead]
    triaged_captures: list[CaptureRead]
    open_action_items: list[ActionItemRead]
    unfinished_tasks: list[TaskRead]
    blocked_tasks: list[TaskRead]
    touched_deliverables: list[DeliverableRead]
    projects_to_review: list[ProjectRead]
    tomorrow_first_action: TaskRead | None


class MeetingPreparation(ResponseModel):
    meeting: MeetingRead
    project: ProjectRead | None = None
    client: ClientRead | None = None
    open_action_items: list[ActionItemRead]
    task_deadlines: list[TaskRead]
    deliverable_deadlines: list[DeliverableRead]
    artifact_links: list[DriveLinkRead]
    prepared_at: datetime


ProgressLevel = Literal["workspace", "client", "project", "deliverable"]


class TaskProgressCounts(StrictModel):
    total: int
    open: int
    overdue: int
    completion_percent: float
    inbox: int
    ready: int
    in_progress: int
    blocked: int
    done: int
    cancelled: int


class DeliverableProgressCounts(StrictModel):
    total: int
    planned: int
    in_progress: int
    in_review: int
    accepted: int
    blocked: int
    cancelled: int


class ProgressMetrics(StrictModel):
    tasks: TaskProgressCounts
    deliverables: DeliverableProgressCounts
    logged_minutes: int


class ProgressRow(StrictModel):
    level: ProgressLevel
    id: EntityId
    parent_id: EntityId | None = None
    name: str
    metrics: ProgressMetrics


class ProgressSummary(StrictModel):
    as_of: date
    work_from: date | None
    work_to: date | None
    timezone: str
    generated_at: datetime
    totals: ProgressMetrics
    workspaces: list[ProgressRow]
    clients: list[ProgressRow]
    projects: list[ProgressRow]
    deliverables: list[ProgressRow]


class AuditEventRead(ResponseModel):
    id: EntityId
    entity_kind: EntityKind
    entity_id: EntityId
    action: AuditAction
    actor: Annotated[str, Field(min_length=1, max_length=200)]
    occurred_at: datetime
    changes: dict[str, Any]


class SnapshotEntities(StrictModel):
    workspaces: list[WorkspaceRead]
    clients: list[ClientRead]
    projects: list[ProjectRead]
    deliverables: list[DeliverableRead]
    tasks: list[TaskRead]
    meetings: list[MeetingRead]
    action_items: list[ActionItemRead]
    work_logs: list[WorkLogRead]
    captures: list[CaptureRead]
    translations: list[TranslationRead] = Field(default_factory=list)
    audit_events: list[AuditEventRead]

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        collections = (
            self.workspaces,
            self.clients,
            self.projects,
            self.deliverables,
            self.tasks,
            self.meetings,
            self.action_items,
            self.work_logs,
            self.captures,
            self.translations,
            self.audit_events,
        )
        for records in collections:
            record_ids = [record.id for record in records]
            if len(record_ids) != len(set(record_ids)):
                raise ValueError("Snapshot collections cannot contain duplicate IDs")

        workspace_ids = {record.id for record in self.workspaces}
        clients = {record.id: record for record in self.clients}
        projects = {record.id: record for record in self.projects}
        deliverables = {record.id: record for record in self.deliverables}
        tasks = {record.id: record for record in self.tasks}
        meetings = {record.id: record for record in self.meetings}
        actions = {record.id: record for record in self.action_items}

        if any(record.workspace_id not in workspace_ids for record in self.clients):
            raise ValueError("Snapshot client references an unknown workspace")
        if any(record.client_id not in clients for record in self.projects):
            raise ValueError("Snapshot project references an unknown client")
        if any(record.project_id not in projects for record in self.deliverables):
            raise ValueError("Snapshot deliverable references an unknown project")

        for task in self.tasks:
            if task.project_id not in projects:
                raise ValueError("Snapshot task references an unknown project")
            if task.deliverable_id:
                deliverable = deliverables.get(task.deliverable_id)
                if not deliverable or deliverable.project_id != task.project_id:
                    raise ValueError("Snapshot task and deliverable must share a project")

        for meeting in self.meetings:
            if meeting.project_id is not None and meeting.project_id not in projects:
                raise ValueError("Snapshot meeting references an unknown project")

        for action in self.action_items:
            meeting = meetings.get(action.meeting_id)
            if not meeting:
                raise ValueError("Snapshot action item references an unknown meeting")
            if action.task_id:
                task = tasks.get(action.task_id)
                if not task or task.project_id != meeting.project_id:
                    raise ValueError("Snapshot action item and task must share a project")
            if action.deliverable_id:
                deliverable = deliverables.get(action.deliverable_id)
                if not deliverable or deliverable.project_id != meeting.project_id:
                    raise ValueError("Snapshot action item and deliverable must share a project")
            link_error = action_item_link_error(action.status, action.task_id)
            if link_error:
                raise ValueError(link_error)

        if any(record.task_id not in tasks for record in self.work_logs):
            raise ValueError("Snapshot work log references an unknown task")
        logged_task_ids = {record.task_id for record in self.work_logs}
        if any(
            task_completion_evidence_error(
                task.completion_note, task.id in logged_task_ids, status=task.status
            )
            for task in self.tasks
        ):
            raise ValueError("Snapshot completed task requires completion evidence")
        if any(
            deliverable_review_evidence_error(
                item.status, item.acceptance_criteria, item.evidence_url
            )
            for item in self.deliverables
        ):
            raise ValueError("Snapshot reviewed deliverable requires acceptance evidence")

        for capture in self.captures:
            if capture.project_id and capture.project_id not in projects:
                raise ValueError("Snapshot capture references an unknown project")
            if capture.task_id and capture.task_id not in tasks:
                raise ValueError("Snapshot capture references an unknown task")
            if capture.action_item_id and capture.action_item_id not in actions:
                raise ValueError("Snapshot capture references an unknown action item")
            if capture.status == "inbox" and (
                capture.disposition
                or capture.triaged_at
                or capture.task_id
                or capture.action_item_id
            ):
                raise ValueError("Snapshot inbox capture cannot contain triage output")
            if capture.status == "triaged" and not (capture.disposition and capture.triaged_at):
                raise ValueError("Snapshot triaged capture requires disposition and timestamp")

        targets = {
            "project": projects,
            "deliverable": deliverables,
            "task": tasks,
            "meeting": meetings,
            "action_item": actions,
            "capture": {record.id: record for record in self.captures},
        }
        expected_fields = {
            "project": "name",
            "deliverable": "title",
            "task": "title",
            "meeting": "title",
            "action_item": "title",
            "capture": "text",
        }
        translation_keys = set()
        for translation in self.translations:
            if translation.entity_id not in targets[translation.entity_kind]:
                raise ValueError("Snapshot translation references an unknown entity")
            if translation.field_name != expected_fields[translation.entity_kind]:
                raise ValueError("Snapshot translation uses an invalid display field")
            key = (
                translation.entity_kind,
                translation.entity_id,
                translation.field_name,
                translation.language,
            )
            if key in translation_keys:
                raise ValueError("Snapshot contains a duplicate translation")
            translation_keys.add(key)

        return self


class SnapshotDocument(StrictModel):
    schema_version: SnapshotVersion
    exported_at: datetime
    entities: SnapshotEntities


class SnapshotCounts(StrictModel):
    workspaces: int
    clients: int
    projects: int
    deliverables: int
    tasks: int
    meetings: int
    action_items: int
    work_logs: int
    captures: int
    translations: int = 0
    audit_events: int


class SnapshotImportResult(StrictModel):
    schema_version: SnapshotVersion
    imported: SnapshotCounts
