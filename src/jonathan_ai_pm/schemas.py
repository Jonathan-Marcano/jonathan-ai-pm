from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    pass


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
