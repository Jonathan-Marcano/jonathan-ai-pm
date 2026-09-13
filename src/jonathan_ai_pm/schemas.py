from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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
