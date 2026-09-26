from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, inspect, select
from sqlalchemy.orm import Session

import faroflow.audit  # noqa: F401
from faroflow.classification import (
    CaptureCandidate,
    ClassifierAdapter,
    ClassifierConfig,
    suggest_capture_disposition,
)
from faroflow.domain_rules import (
    DELIVERABLE_PROTECTED_STATUSES,
    DomainConflictError,
    DomainNotFoundError,
    DomainRuleError,
    action_item_link_error,
    create_status_error,
    deliverable_review_evidence_error,
    task_completion_evidence_error,
    task_status_error,
    timezone_aware_error,
)
from faroflow.integrations.persistence import IntegrationStateError, IntegrationStateStore
from faroflow.models import (
    MODEL_BY_KIND,
    ActionItem,
    Capture,
    Client,
    Deliverable,
    ExternalIdentity,
    Habit,
    HabitCompletion,
    Meeting,
    Project,
    Task,
    Translation,
    WorkLog,
    utc_now,
)


class DomainStore:
    """Small transaction boundary for Phase 1 manual-first CRUD."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, kind: str, **attributes: Any):
        model = self._model(kind)
        entity = model(**attributes)
        status_error = create_status_error(kind, attributes.get("status"))
        if status_error:
            raise DomainRuleError(status_error)
        self.session.add(entity)
        self._validate_links(entity)
        self._validate_entity(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, kind: str, entity_id: str):
        return self.session.get(self._model(kind), entity_id)

    def list(self, kind: str, **filters: Any):
        items, _has_more = self.list_page(kind, **filters)
        return items

    def list_page(
        self,
        kind: str,
        limit: int | None = None,
        offset: int = 0,
        **filters: Any,
    ) -> tuple[list, bool]:
        """Return (items, has_more) honoring limit/offset for API pagination."""
        model = self._model(kind)
        statement = select(model)
        statement = self._apply_filters(statement, model, filters)
        statement = statement.order_by(model.id).offset(offset)
        if limit is None:
            return list(self.session.scalars(statement)), False
        rows = list(self.session.scalars(statement.limit(limit + 1)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def list_meetings_without_project(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Meeting], bool]:
        """Return the imported-meeting review queue as (items, has_more)."""
        statement = (
            select(Meeting)
            .where(Meeting.project_id.is_(None))
            .order_by(Meeting.starts_at, Meeting.id)
            .offset(offset)
        )
        if limit is None:
            return list(self.session.scalars(statement)), False
        rows = list(self.session.scalars(statement.limit(limit + 1)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def complete_meeting(self, meeting_id: str) -> Meeting:
        """Mark a scheduled meeting completed and enter it in the post-meeting review queue."""
        meeting = self._required("meeting", meeting_id)
        if meeting.status != "scheduled":
            raise DomainRuleError("Only scheduled meetings can be completed")
        meeting.status = "completed"
        meeting.reviewed_at = None
        self.session.commit()
        self.session.refresh(meeting)
        return meeting

    def review_meeting(self, meeting_id: str, reviewed_at: datetime | None = None) -> Meeting:
        """Acknowledge a completed meeting so it leaves the post-meeting queue."""
        meeting = self._required("meeting", meeting_id)
        if meeting.status != "completed":
            raise DomainRuleError("Only completed meetings can be reviewed")
        if meeting.reviewed_at is None:
            meeting.reviewed_at = reviewed_at or utc_now()
            self.session.commit()
            self.session.refresh(meeting)
        return meeting

    def list_completed_meetings(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Meeting], bool]:
        """Return the completed-meeting review queue as (items, has_more)."""
        statement = (
            select(Meeting)
            .where(Meeting.status == "completed", Meeting.reviewed_at.is_(None))
            .order_by(Meeting.starts_at.desc(), Meeting.id)
            .offset(offset)
        )
        if limit is None:
            return list(self.session.scalars(statement)), False
        rows = list(self.session.scalars(statement.limit(limit + 1)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def update(self, kind: str, entity_id: str, **changes: Any):
        entity = self._required(kind, entity_id)
        if isinstance(entity, Capture):
            # Una captura solo se puede corregir en su texto y en la nota del
            # triaje. El resto (estado, disposicion y enlaces) sigue pasando por
            # triage_capture, que es el unico camino que valida el flujo.
            allowed = {"text", "disposition_note"}
            blocked = sorted(set(changes) - allowed)
            if blocked:
                raise DomainRuleError(
                    "Captures are immutable except for text and disposition_note; "
                    "use triage_capture for: " + ", ".join(blocked)
                )
            if "text" in changes:
                text = (changes["text"] or "").strip()
                if not text:
                    raise DomainRuleError("A capture requires non-empty text")
                changes["text"] = text
        if isinstance(entity, WorkLog):
            raise DomainRuleError("Work logs are append-only")
        if isinstance(entity, Task):
            next_status = changes.get("status", entity.status)
            status_error = task_status_error(entity.status, next_status)
            if status_error:
                raise DomainRuleError(status_error)
        if (
            isinstance(entity, Deliverable)
            and changes.get("status") in DELIVERABLE_PROTECTED_STATUSES
        ):
            status_error = create_status_error(kind, changes.get("status"))
            raise DomainRuleError(status_error)
        for name, value in changes.items():
            if name in {"id", "created_at", "updated_at"} or not hasattr(entity, name):
                raise DomainRuleError(f"Field cannot be updated: {name}")
            setattr(entity, name, value)
        self._validate_links(entity)
        self._validate_entity(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, kind: str, entity_id: str) -> None:
        entity = self._required(kind, entity_id)
        if not isinstance(entity, Translation):
            translation_id = self.session.scalar(
                select(Translation.id)
                .where(
                    Translation.entity_kind == kind,
                    Translation.entity_id == entity_id,
                )
                .limit(1)
            )
            if translation_id:
                raise DomainConflictError("Delete record translations before deleting the source")
        self._reject_references(kind, entity_id)
        self.session.delete(entity)
        self.session.commit()

    def _reject_references(self, kind: str, entity_id: str) -> None:
        if kind == "task":
            action_id = self.session.scalar(
                select(ActionItem.id).where(ActionItem.task_id == entity_id).limit(1)
            )
            if action_id:
                raise DomainRuleError("Task is still linked to an action item")
            capture_id = self.session.scalar(
                select(Capture.id).where(Capture.task_id == entity_id).limit(1)
            )
            if capture_id:
                raise DomainConflictError("Task is still referenced by a captured note")
        elif kind == "action_item":
            capture_id = self.session.scalar(
                select(Capture.id).where(Capture.action_item_id == entity_id).limit(1)
            )
            if capture_id:
                raise DomainConflictError("Action item is still referenced by a captured note")
        elif kind == "project":
            # Sin esto la respuesta seria el IntegrityError generico del FK, que
            # no dice que hay que borrar. Se listan los hijos reales del proyecto.
            for child_label, child_model, column in (
                ("task", Task, Task.project_id),
                ("deliverable", Deliverable, Deliverable.project_id),
                ("meeting", Meeting, Meeting.project_id),
            ):
                child_id = self.session.scalar(
                    select(child_model.id).where(column == entity_id).limit(1)
                )
                if child_id:
                    raise DomainConflictError(
                        f"Project still has a {child_label}; delete it first"
                    )
            capture_id = self.session.scalar(
                select(Capture.id).where(Capture.project_id == entity_id).limit(1)
            )
            if capture_id:
                raise DomainConflictError("Project is still referenced by a captured note")
        elif kind == "deliverable":
            identity_id = self.session.scalar(
                select(ExternalIdentity.id)
                .where(
                    ExternalIdentity.entity_kind == "deliverable",
                    ExternalIdentity.entity_id == entity_id,
                )
                .limit(1)
            )
            if identity_id:
                raise DomainConflictError("Unlink Drive files before deleting the deliverable")
        elif kind == "habit":
            completion_id = self.session.scalar(
                select(HabitCompletion.id)
                .where(HabitCompletion.habit_id == entity_id)
                .limit(1)
            )
            if completion_id:
                raise DomainConflictError("Habit still has recorded completions")
        elif kind == "workspace":
            client_id = self.session.scalar(
                select(Client.id).where(Client.workspace_id == entity_id).limit(1)
            )
            if client_id:
                raise DomainConflictError(
                    "Workspace still has clients; move or delete them first"
                )
        elif kind == "client":
            project_id = self.session.scalar(
                select(Project.id).where(Project.client_id == entity_id).limit(1)
            )
            if project_id:
                raise DomainConflictError(
                    "Client still has projects; move or delete them first"
                )
        elif kind == "meeting":
            action_id = self.session.scalar(
                select(ActionItem.id)
                .where(ActionItem.meeting_id == entity_id)
                .limit(1)
            )
            if action_id:
                raise DomainConflictError(
                    "Meeting still has action items; delete them first"
                )

    def associate_meeting(self, meeting_id: str, project_id: str) -> Meeting:
        """Confirm a project for an imported meeting and reuse that association later."""
        meeting = self._required("meeting", meeting_id)
        project = self._required("project", project_id)
        meeting.project_id = project.id
        self._validate_entity(meeting)
        self.session.commit()
        self.session.refresh(meeting)
        identity = self.session.scalar(
            select(ExternalIdentity)
            .where(
                ExternalIdentity.entity_kind == "meeting",
                ExternalIdentity.entity_id == meeting.id,
            )
            .limit(1)
        )
        if identity is not None:
            IntegrationStateStore(self.session).set_project_mapping(
                source_system=identity.source_system,
                external_scope=identity.external_scope,
                external_id=identity.external_id,
                project_id=project.id,
            )
        return meeting

    def link_drive_file(
        self,
        deliverable_id: str,
        *,
        source_system: str,
        external_id: str,
        name: str | None = None,
        web_url: str | None = None,
        mime_type: str | None = None,
    ) -> ExternalIdentity:
        """Register a read-only Drive file link on a deliverable without copying its body."""
        self._required("deliverable", deliverable_id)
        state = IntegrationStateStore(self.session)
        try:
            identity = state.upsert_identity(
                entity_kind="deliverable",
                entity_id=deliverable_id,
                source_system=source_system,
                external_id=external_id,
                external_name=name,
                mime_type=mime_type,
                web_url=web_url,
            )
        except IntegrationStateError as exc:
            raise DomainRuleError(str(exc)) from exc
        deliverable = self.session.get(Deliverable, deliverable_id)
        if web_url and deliverable.drive_url != web_url:
            deliverable.drive_url = web_url
            self.session.commit()
            self.session.refresh(deliverable)
        return identity

    def unlink_drive_file(self, deliverable_id: str) -> None:
        """Remove a deliverable's Drive links; the external file is never touched."""
        self._required("deliverable", deliverable_id)
        state = IntegrationStateStore(self.session)
        try:
            state.unlink_deliverable(deliverable_id)
        except IntegrationStateError as exc:
            raise DomainRuleError(str(exc)) from exc

    def complete_task(self, task_id: str, completion_note: str | None = None) -> Task:
        task = self._required("task", task_id)
        evidence_note = completion_note.strip() if completion_note else None
        has_work_log = self.session.scalar(
            select(WorkLog.id).where(WorkLog.task_id == task_id).limit(1)
        )
        if task_completion_evidence_error(completion_note, has_work_log):
            raise DomainRuleError(
                "A completed task requires a completion note or work log"
            )
        task.completion_note = evidence_note or task.completion_note
        task.status = "done"
        self.session.commit()
        self.session.refresh(task)
        return task

    def start_task(self, task_id: str) -> Task:
        task = self._required("task", task_id)
        if task.status == "in_progress":
            return task
        if task.status not in {"ready", "blocked"}:
            raise DomainRuleError("A task can start only from ready or blocked status")

        task.status = "in_progress"
        project = self._required("project", task.project_id)
        if project.status == "planned":
            project.status = "active"
        if task.deliverable_id:
            deliverable = self._required("deliverable", task.deliverable_id)
            if deliverable.status == "planned":
                deliverable.status = "in_progress"

        self.session.commit()
        self.session.refresh(task)
        return task

    def add_work_log(
        self,
        task_id: str,
        *,
        minutes: int,
        summary: str,
        started_at: datetime | None = None,
    ) -> WorkLog:
        task = self._required("task", task_id)
        if task.status != "in_progress":
            raise DomainRuleError("Work can be logged only for an in-progress task")
        evidence_summary = summary.strip()
        if not evidence_summary:
            raise DomainRuleError("A work log requires an evidence summary")
        if minutes <= 0:
            raise DomainRuleError("Work-log minutes must be greater than zero")

        session_started_at = started_at or utc_now()
        if timezone_aware_error(session_started_at, "Work-log started_at"):
            raise DomainRuleError("Work-log started_at must include a timezone")

        work_log = WorkLog(
            id=f"wlg_{uuid4().hex}",
            task_id=task.id,
            started_at=session_started_at.astimezone(UTC),
            minutes=minutes,
            summary=evidence_summary,
        )
        self.session.add(work_log)
        self.session.commit()
        self.session.refresh(work_log)
        return work_log

    def list_task_work_logs(self, task_id: str) -> list[WorkLog]:
        self._required("task", task_id)
        statement = (
            select(WorkLog)
            .where(WorkLog.task_id == task_id)
            .order_by(WorkLog.started_at, WorkLog.id)
        )
        return list(self.session.scalars(statement))

    def move_deliverable_to_review(self, deliverable_id: str) -> Deliverable:
        deliverable = self._required("deliverable", deliverable_id)
        if deliverable_review_evidence_error(
            "in_review", deliverable.acceptance_criteria, deliverable.evidence_url
        ):
            raise DomainRuleError(
                "A deliverable in review requires acceptance criteria and an evidence URL"
            )
        deliverable.acceptance_criteria = (deliverable.acceptance_criteria or "").strip()
        deliverable.evidence_url = (deliverable.evidence_url or "").strip()
        deliverable.status = "in_review"
        self.session.commit()
        self.session.refresh(deliverable)
        return deliverable

    def create_task_from_action(
        self,
        action_item_id: str,
        task_id: str,
        priority: str = "medium",
        due_at: date | None = None,
        deliverable_id: str | None = None,
    ) -> Task:
        action = self._required("action_item", action_item_id)
        if action.status != "captured":
            raise DomainRuleError("Only a captured action item can create a task")
        if action.task_id:
            raise DomainRuleError(f"Action item already links task: {action.task_id}")

        meeting = self._required("meeting", action.meeting_id)
        if meeting.project_id is None:
            raise DomainRuleError("Associate the meeting with a project before creating tasks")
        selected_deliverable_id = deliverable_id or action.deliverable_id
        if selected_deliverable_id:
            deliverable = self._required("deliverable", selected_deliverable_id)
            if deliverable.project_id != meeting.project_id:
                raise DomainRuleError("Task and deliverable must belong to the meeting project")

        task = Task(
            id=task_id,
            project_id=meeting.project_id,
            deliverable_id=selected_deliverable_id,
            title=action.title,
            status="ready",
            priority=priority,
            due_at=due_at,
        )
        self.session.add(task)
        self.session.flush()
        action.task_id = task.id
        action.deliverable_id = selected_deliverable_id
        action.status = "accepted"
        self.session.commit()
        self.session.refresh(task)
        return task

    def capture(self, text: str) -> Capture:
        normalized_text = text.strip()
        if not normalized_text:
            raise DomainRuleError("A capture requires non-empty text")
        capture = Capture(id=f"cap_{uuid4().hex}", text=normalized_text, status="inbox")
        self.session.add(capture)
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def suggest_capture(
        self,
        capture_id: str,
        *,
        classifier: ClassifierAdapter,
        config: ClassifierConfig | None = None,
        now: datetime | None = None,
    ) -> Capture:
        """Attach a read-only, bounded proposal to an inbox capture.

        The classification never binds a record to a project: the capture stays in the
        inbox and manual triage keeps working unchanged. Re-suggesting replaces the
        previous pending proposal.
        """
        capture = self._required("capture", capture_id)
        if capture.status != "inbox":
            raise DomainRuleError("Only inbox captures can receive a proposal")

        clients = {client.id: client.name for client in self.list("client")}
        candidates = [
            CaptureCandidate(
                id=project.id,
                name=project.name,
                client=clients.get(project.client_id),
            )
            for project in self.list("project")
        ]
        suggestion = suggest_capture_disposition(
            capture.text, candidates, classifier=classifier, config=config
        )

        capture.proposal_kind = suggestion.kind
        capture.proposal_source = suggestion.source
        capture.proposal_confidence = suggestion.confidence
        capture.proposal_project_id = suggestion.project_id
        capture.proposal_owner = suggestion.owner
        capture.proposal_priority = suggestion.priority
        capture.proposal_due_at = suggestion.due_at
        capture.proposal_reasons = (
            list(suggestion.reasons) if suggestion.reasons else None
        )
        capture.proposed_at = now or utc_now()
        capture.applied_at = None
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def apply_capture(
        self,
        capture_id: str,
        *,
        meeting_id: str | None = None,
        now: datetime | None = None,
    ) -> Capture:
        """Confirm a pending proposal by creating the operational record from it.

        The confirmation is idempotent: an already-applied capture is returned
        unchanged and never creates a second record. Applying requires an explicit
        proposal (``proposed_at``) and never binds an unconfirmed capture. The
        immutable proposal fields and the original text stay on the capture as the
        decision trail, and the audit events link the capture, the applied record,
        and the source wording.
        """
        capture = self._required("capture", capture_id)
        if capture.applied_at is not None:
            return capture
        if capture.status != "inbox":
            raise DomainRuleError("Only inbox captures can be confirmed")
        if capture.proposed_at is None or not capture.proposal_kind:
            raise DomainRuleError("Capture has no pending proposal to apply")

        confirmed_at = now or utc_now()
        kind = capture.proposal_kind
        if kind == "task":
            if not capture.proposal_project_id:
                raise DomainRuleError("Task proposal requires a project")
            if meeting_id:
                raise DomainRuleError("meeting_id applies only to action proposals")
            project = self._required("project", capture.proposal_project_id)
            task = Task(
                id=f"tsk_{uuid4().hex}",
                project_id=project.id,
                title=capture.text,
                status="ready",
                priority=capture.proposal_priority or "medium",
                due_at=capture.proposal_due_at,
            )
            self.session.add(task)
            self._validate_links(task)
            self.session.flush()
            capture.project_id = project.id
            capture.task_id = task.id
        elif kind == "action":
            if not meeting_id:
                raise DomainRuleError("Action proposal requires a meeting")
            meeting = self._required("meeting", meeting_id)
            if meeting.project_id is None:
                raise DomainRuleError(
                    "Associate the meeting with a project before confirming an action"
                )
            if (
                capture.proposal_project_id
                and capture.proposal_project_id != meeting.project_id
            ):
                raise DomainRuleError("Capture project must match the meeting project")
            owner = capture.proposal_owner
            if not owner:
                raise DomainRuleError("Action proposal requires an owner")
            action = ActionItem(
                id=f"act_{uuid4().hex}",
                meeting_id=meeting.id,
                title=capture.text,
                status="captured",
                owner=owner,
            )
            self.session.add(action)
            self._validate_links(action)
            self.session.flush()
            capture.project_id = meeting.project_id
            capture.action_item_id = action.id
        elif kind == "reference":
            if meeting_id:
                raise DomainRuleError("meeting_id applies only to action proposals")
            if capture.proposal_project_id:
                self._required("project", capture.proposal_project_id)
            capture.project_id = capture.proposal_project_id
        else:
            raise DomainRuleError(f"Unknown proposal kind: {kind}")

        capture.status = "triaged"
        capture.disposition = kind
        capture.triaged_at = confirmed_at
        capture.applied_at = confirmed_at
        self.session.commit()
        self.session.refresh(capture)
        return capture

    def morning_brief(
        self,
        timezone_name: str,
        brief_date: date | None = None,
        due_soon_days: int = 3,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not 0 <= due_soon_days <= 30:
            raise DomainRuleError("due_soon_days must be between 0 and 30")
        local_timezone, target_date, generated_at = self._daily_context(
            timezone_name, brief_date, now
        )
        due_soon_through = target_date + timedelta(days=due_soon_days)

        tasks = self.list("task")
        open_tasks = [task for task in tasks if task.status not in {"done", "cancelled"}]
        overdue_tasks = self._sort_tasks(
            [task for task in open_tasks if task.due_at and task.due_at < target_date]
        )
        due_soon_tasks = self._sort_tasks(
            [
                task
                for task in open_tasks
                if task.due_at and target_date <= task.due_at <= due_soon_through
            ]
        )
        executable = [task for task in open_tasks if task.status in {"ready", "in_progress"}]
        focus_tasks = self._sort_tasks(executable)[:3]
        blocked_tasks = self._sort_tasks([task for task in open_tasks if task.status == "blocked"])

        meetings: list[Meeting] = [
            meeting
            for meeting in self.list("meeting", status="scheduled")
            if self._as_utc(meeting.starts_at).astimezone(local_timezone).date() == target_date
        ]
        meetings.sort(key=lambda meeting: self._as_utc(meeting.starts_at))

        deliverables = self.list("deliverable")
        blocked_deliverables = sorted(
            [item for item in deliverables if item.status == "blocked"],
            key=lambda item: (item.due_at, item.id),
        )
        in_progress_deliverable_ids = {
            task.deliverable_id
            for task in open_tasks
            if task.status == "in_progress" and task.deliverable_id
        }
        deliverable_opportunities = sorted(
            [
                item
                for item in deliverables
                if item.status in {"planned", "in_progress"}
                and item.id not in in_progress_deliverable_ids
            ],
            key=lambda item: (item.due_at, item.id),
        )[:5]
        at_risk_projects: list[Project] = sorted(
            [
                project
                for project in self.list("project")
                if project.health in {"at_risk", "off_track"}
                and project.status not in {"completed", "cancelled"}
            ],
            key=lambda project: (project.health != "off_track", project.id),
        )

        counts = {
            "meetings": len(meetings),
            "overdue_tasks": len(overdue_tasks),
            "due_soon_tasks": len(due_soon_tasks),
            "focus_tasks": len(focus_tasks),
            "blocked_tasks": len(blocked_tasks),
            "blocked_deliverables": len(blocked_deliverables),
            "deliverable_opportunities": len(deliverable_opportunities),
            "at_risk_projects": len(at_risk_projects),
        }
        return {
            "brief_date": target_date,
            "timezone": timezone_name,
            "due_soon_through": due_soon_through,
            "generated_at": generated_at,
            "counts": counts,
            "meetings": meetings,
            "overdue_tasks": overdue_tasks,
            "due_soon_tasks": due_soon_tasks,
            "focus_tasks": focus_tasks,
            "blocked_tasks": blocked_tasks,
            "blocked_deliverables": blocked_deliverables,
            "deliverable_opportunities": deliverable_opportunities,
            "at_risk_projects": at_risk_projects,
        }

    def evening_close(
        self,
        timezone_name: str,
        close_date: date | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        local_timezone, target_date, generated_at = self._daily_context(
            timezone_name, close_date, now
        )
        tasks: list[Task] = self.list("task")
        tasks_by_id = {task.id: task for task in tasks}

        completed_tasks = self._sort_tasks(
            [
                task
                for task in tasks
                if task.status == "done"
                and self._local_date(task.updated_at, local_timezone) == target_date
            ]
        )
        work_logs: list[WorkLog] = sorted(
            [
                work_log
                for work_log in self.list("work_log")
                if self._local_date(work_log.started_at, local_timezone) == target_date
            ],
            key=lambda work_log: (self._as_utc(work_log.started_at), work_log.id),
        )
        logged_minutes = sum(work_log.minutes for work_log in work_logs)

        captures: list[Capture] = self.list("capture")
        untriaged_captures = sorted(
            [
                capture
                for capture in captures
                if capture.status == "inbox"
                and self._local_date(capture.captured_at, local_timezone) <= target_date
            ],
            key=lambda capture: (self._as_utc(capture.captured_at), capture.id),
        )
        triaged_captures = sorted(
            [
                capture
                for capture in captures
                if capture.status == "triaged"
                and capture.triaged_at
                and self._local_date(capture.triaged_at, local_timezone) == target_date
            ],
            key=lambda capture: (self._as_utc(capture.triaged_at), capture.id),
        )
        open_action_items: list[ActionItem] = self.list("action_item")
        open_action_items = [
            action for action in open_action_items if action.status in {"captured", "accepted"}
        ]

        unfinished_tasks = self._sort_tasks(
            [
                task
                for task in tasks
                if task.status not in {"done", "cancelled"}
                and (
                    task.status in {"inbox", "in_progress", "blocked"}
                    or (task.due_at is not None and task.due_at <= target_date)
                )
            ]
        )
        blocked_tasks = self._sort_tasks(
            [task for task in tasks if task.status == "blocked"]
        )

        touched_task_ids = {task.id for task in completed_tasks}
        touched_task_ids.update(work_log.task_id for work_log in work_logs)
        touched_tasks = [tasks_by_id[task_id] for task_id in touched_task_ids]
        touched_deliverable_ids = {
            task.deliverable_id for task in touched_tasks if task.deliverable_id
        }
        touched_deliverables = sorted(
            [
                deliverable
                for deliverable in self.list("deliverable")
                if deliverable.id in touched_deliverable_ids
            ],
            key=lambda deliverable: (deliverable.due_at, deliverable.id),
        )

        touched_project_ids = {task.project_id for task in touched_tasks}
        projects: list[Project] = self.list("project")
        projects_to_review = sorted(
            [
                project
                for project in projects
                if project.id in touched_project_ids
                or (
                    project.health in {"at_risk", "off_track"}
                    and project.status not in {"completed", "cancelled"}
                )
            ],
            key=lambda project: (project.health != "off_track", project.id),
        )

        executable_tasks = [
            task for task in tasks if task.status in {"ready", "in_progress"}
        ]
        tomorrow_first_action = next(iter(self._sort_tasks(executable_tasks)), None)
        counts = {
            "completed_tasks": len(completed_tasks),
            "work_logs": len(work_logs),
            "logged_minutes": logged_minutes,
            "untriaged_captures": len(untriaged_captures),
            "triaged_captures": len(triaged_captures),
            "open_action_items": len(open_action_items),
            "unfinished_tasks": len(unfinished_tasks),
            "blocked_tasks": len(blocked_tasks),
            "touched_deliverables": len(touched_deliverables),
            "projects_to_review": len(projects_to_review),
        }
        return {
            "close_date": target_date,
            "timezone": timezone_name,
            "generated_at": generated_at,
            "counts": counts,
            "completed_tasks": completed_tasks,
            "work_logs": work_logs,
            "untriaged_captures": untriaged_captures,
            "triaged_captures": triaged_captures,
            "open_action_items": open_action_items,
            "unfinished_tasks": unfinished_tasks,
            "blocked_tasks": blocked_tasks,
            "touched_deliverables": touched_deliverables,
            "projects_to_review": projects_to_review,
            "tomorrow_first_action": tomorrow_first_action,
        }

    def meeting_preparation(
        self,
        meeting_id: str,
        prepared_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Combine a meeting, its linked project, open actions, and deadlines for preparation."""
        meeting = self._required("meeting", meeting_id)
        project = self.session.get(Project, meeting.project_id) if meeting.project_id else None
        client = self.session.get(Client, project.client_id) if project else None

        open_actions = sorted(
            [
                action
                for action in self.list("action_item", meeting_id=meeting.id)
                if action.status in {"captured", "accepted"}
            ],
            key=lambda action: (self._as_utc(action.created_at), action.id),
        )

        task_deadlines: list[Task] = []
        deliverable_deadlines: list[Deliverable] = []
        artifact_identities: list[ExternalIdentity] = []
        if project is not None:
            project_deliverables = self.list("deliverable", project_id=project.id)
            deliverable_deadlines = sorted(
                [
                    item
                    for item in project_deliverables
                    if item.status not in {"accepted", "cancelled"}
                ],
                key=lambda item: (item.due_at, item.id),
            )
            task_deadlines = sorted(
                [
                    task
                    for task in self.list("task", project_id=project.id)
                    if task.status not in {"done", "cancelled"} and task.due_at is not None
                ],
                key=lambda task: (task.due_at, task.id),
            )
            deliverable_ids = [item.id for item in project_deliverables]
            if deliverable_ids:
                artifact_statement = (
                    select(ExternalIdentity)
                    .where(
                        ExternalIdentity.entity_kind == "deliverable",
                        ExternalIdentity.source_system == "google-drive",
                        ExternalIdentity.entity_id.in_(deliverable_ids),
                    )
                    .order_by(ExternalIdentity.created_at, ExternalIdentity.id)
                )
                artifact_identities = list(self.session.scalars(artifact_statement))

        return {
            "meeting": meeting,
            "project": project,
            "client": client,
            "open_action_items": open_actions,
            "task_deadlines": task_deadlines,
            "deliverable_deadlines": deliverable_deadlines,
            "artifact_links": artifact_identities,
            "prepared_at": prepared_at or utc_now(),
        }

    def progress_summary(
        self,
        timezone_name: str,
        as_of: date | None = None,
        work_from: date | None = None,
        work_to: date | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        local_timezone, target_date, generated_at = self._daily_context(
            timezone_name, as_of, now
        )
        if work_from and work_to and work_from > work_to:
            raise DomainRuleError("work_from cannot be after work_to")

        workspaces = self.list("workspace")
        clients = self.list("client")
        projects = self.list("project")
        deliverables = self.list("deliverable")
        tasks = self.list("task")
        work_logs = [
            work_log
            for work_log in self.list("work_log")
            if (not work_from or self._local_date(work_log.started_at, local_timezone) >= work_from)
            and (not work_to or self._local_date(work_log.started_at, local_timezone) <= work_to)
        ]

        def row(
            level: str,
            entity_id: str,
            parent_id: str | None,
            name: str,
            row_tasks: list[Task],
            row_deliverables: list[Deliverable],
        ) -> dict[str, Any]:
            task_ids = {task.id for task in row_tasks}
            row_logs = [work_log for work_log in work_logs if work_log.task_id in task_ids]
            return {
                "level": level,
                "id": entity_id,
                "parent_id": parent_id,
                "name": name,
                "metrics": self._progress_metrics(
                    row_tasks, row_deliverables, row_logs, target_date
                ),
            }

        workspace_rows = []
        for workspace in workspaces:
            client_ids = {
                client.id for client in clients if client.workspace_id == workspace.id
            }
            project_ids = {
                project.id for project in projects if project.client_id in client_ids
            }
            workspace_rows.append(
                row(
                    "workspace",
                    workspace.id,
                    None,
                    workspace.name,
                    [task for task in tasks if task.project_id in project_ids],
                    [
                        deliverable
                        for deliverable in deliverables
                        if deliverable.project_id in project_ids
                    ],
                )
            )

        client_rows = []
        for client in clients:
            project_ids = {
                project.id for project in projects if project.client_id == client.id
            }
            client_rows.append(
                row(
                    "client",
                    client.id,
                    client.workspace_id,
                    client.name,
                    [task for task in tasks if task.project_id in project_ids],
                    [
                        deliverable
                        for deliverable in deliverables
                        if deliverable.project_id in project_ids
                    ],
                )
            )

        project_rows = [
            row(
                "project",
                project.id,
                project.client_id,
                project.name,
                [task for task in tasks if task.project_id == project.id],
                [
                    deliverable
                    for deliverable in deliverables
                    if deliverable.project_id == project.id
                ],
            )
            for project in projects
        ]
        deliverable_rows = [
            row(
                "deliverable",
                deliverable.id,
                deliverable.project_id,
                deliverable.title,
                [task for task in tasks if task.deliverable_id == deliverable.id],
                [deliverable],
            )
            for deliverable in deliverables
        ]
        return {
            "as_of": target_date,
            "work_from": work_from,
            "work_to": work_to,
            "timezone": timezone_name,
            "generated_at": generated_at,
            "totals": self._progress_metrics(tasks, deliverables, work_logs, target_date),
            "workspaces": workspace_rows,
            "clients": client_rows,
            "projects": project_rows,
            "deliverables": deliverable_rows,
        }

    @staticmethod
    def _progress_metrics(
        tasks: list[Task],
        deliverables: list[Deliverable],
        work_logs: list[WorkLog],
        as_of: date,
    ) -> dict[str, Any]:
        task_statuses = ("inbox", "ready", "in_progress", "blocked", "done", "cancelled")
        deliverable_statuses = (
            "planned",
            "in_progress",
            "in_review",
            "accepted",
            "blocked",
            "cancelled",
        )
        task_counts = {status: 0 for status in task_statuses}
        for task in tasks:
            task_counts[task.status] += 1

        eligible_tasks = [task for task in tasks if task.status != "cancelled"]
        open_tasks = [
            task for task in eligible_tasks if task.status != "done"
        ]
        overdue_tasks = [
            task for task in open_tasks if task.due_at is not None and task.due_at < as_of
        ]
        completed_tasks = task_counts["done"]
        completion_percent = (
            round(completed_tasks / len(eligible_tasks) * 100, 1) if eligible_tasks else 0.0
        )
        task_summary = {
            "total": len(tasks),
            "open": len(open_tasks),
            "overdue": len(overdue_tasks),
            "completion_percent": completion_percent,
            **task_counts,
        }

        deliverable_counts = {status: 0 for status in deliverable_statuses}
        for deliverable in deliverables:
            deliverable_counts[deliverable.status] += 1
        deliverable_summary = {
            "total": len(deliverables),
            **deliverable_counts,
        }
        return {
            "tasks": task_summary,
            "deliverables": deliverable_summary,
            "logged_minutes": sum(work_log.minutes for work_log in work_logs),
        }

    @staticmethod
    def _daily_context(
        timezone_name: str,
        target_date: date | None,
        now: datetime | None,
    ) -> tuple[ZoneInfo, date, datetime]:
        try:
            local_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainRuleError(f"Unknown timezone: {timezone_name}") from exc

        generated_at = now or datetime.now(UTC)
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)
        else:
            generated_at = generated_at.astimezone(UTC)
        resolved_date = target_date or generated_at.astimezone(local_timezone).date()
        return local_timezone, resolved_date, generated_at

    @classmethod
    def _local_date(cls, value: datetime, timezone: ZoneInfo) -> date:
        return cls._as_utc(value).astimezone(timezone).date()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _sort_tasks(tasks: list[Task]) -> list[Task]:
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        status_rank = {"in_progress": 0, "ready": 1, "blocked": 2, "inbox": 3}
        return sorted(
            tasks,
            key=lambda task: (
                priority_rank[task.priority],
                task.due_at or date.max,
                status_rank.get(task.status, 9),
                task.id,
            ),
        )

    def triage_capture(
        self,
        capture_id: str,
        disposition: str,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        action_item_id: str | None = None,
        meeting_id: str | None = None,
        deliverable_id: str | None = None,
        owner: str | None = None,
        priority: str = "medium",
        due_at: date | None = None,
        note: str | None = None,
    ) -> Capture:
        capture = self._required("capture", capture_id)
        if capture.status != "inbox":
            raise DomainRuleError("Capture has already been triaged")

        if disposition == "task":
            if not project_id or not task_id:
                raise DomainRuleError("Task triage requires project_id and task_id")
            task = Task(
                id=task_id,
                project_id=project_id,
                deliverable_id=deliverable_id,
                title=capture.text,
                status="ready",
                priority=priority,
                due_at=due_at,
            )
            self.session.add(task)
            self._validate_links(task)
            self.session.flush()
            capture.project_id = project_id
            capture.task_id = task.id

        elif disposition == "action":
            if not meeting_id or not action_item_id or not owner:
                raise DomainRuleError(
                    "Action triage requires meeting_id, action_item_id, and owner"
                )
            meeting = self._required("meeting", meeting_id)
            if meeting.project_id is None:
                raise DomainRuleError(
                    "Associate the meeting with a project before creating action items"
                )
            if project_id and project_id != meeting.project_id:
                raise DomainRuleError("Capture project must match the meeting project")
            action = ActionItem(
                id=action_item_id,
                meeting_id=meeting_id,
                deliverable_id=deliverable_id,
                title=capture.text,
                status="captured",
                owner=owner,
            )
            self.session.add(action)
            self._validate_links(action)
            self.session.flush()
            capture.project_id = meeting.project_id
            capture.action_item_id = action.id

        elif disposition in {"reference", "dismissed"}:
            if disposition == "dismissed" and not (note or "").strip():
                raise DomainRuleError("Dismissed triage requires a note")
            if project_id:
                self._required("project", project_id)
            capture.project_id = project_id
        else:
            raise DomainRuleError(f"Unknown capture disposition: {disposition}")

        capture.status = "triaged"
        capture.disposition = disposition
        capture.disposition_note = note.strip() if note else None
        capture.triaged_at = utc_now()
        self.session.commit()
        self.session.refresh(capture)
        return capture

    @staticmethod
    def _validate_entity(entity) -> None:
        if isinstance(entity, Translation):
            entity.language = entity.language.strip()
            entity.translated_text = entity.translated_text.strip()
            if not entity.translated_text:
                raise DomainRuleError("A translation requires non-empty text")

        if isinstance(entity, Habit):
            if entity.goal_type == "binary" and entity.target_quantity != 1:
                raise DomainRuleError("Binary habits must have a target_quantity of 1")
            if entity.frequency == "weekly":
                if entity.specific_days:
                    raise DomainRuleError("Weekly habits cannot define specific_days")
                if entity.weekly_target is None:
                    entity.weekly_target = 1
            if entity.frequency == "specific_days":
                if not entity.specific_days:
                    raise DomainRuleError(
                        "specific_days frequency requires a day selection"
                    )
                if len(set(entity.specific_days)) != len(entity.specific_days):
                    raise DomainRuleError("specific_days cannot repeat weekdays")
                if any(not (1 <= day <= 7) for day in entity.specific_days):
                    raise DomainRuleError("specific_days must be ISO weekdays 1..7")
            else:
                entity.specific_days = None
            if entity.frequency not in ("weekly", "specific_days"):
                entity.weekly_target = None

        if isinstance(entity, HabitCompletion):
            if entity.quantity < 1:
                raise DomainRuleError("A completion requires quantity >= 1")

        if isinstance(entity, Meeting):
            starts_at_history = inspect(entity).attrs["starts_at"].history
            if starts_at_history.has_changes():
                if timezone_aware_error(entity.starts_at, "Meeting starts_at"):
                    raise DomainRuleError("Meeting starts_at must include a timezone")
                entity.starts_at = entity.starts_at.astimezone(UTC)

        if isinstance(entity, ActionItem):
            if action_item_link_error(entity.status, entity.task_id):
                raise DomainRuleError(
                    action_item_link_error(entity.status, entity.task_id)
                )

    @staticmethod
    def _apply_filters(statement: Select, model, filters: dict[str, Any]) -> Select:
        for name, value in filters.items():
            if value is None:
                continue
            if name.endswith("_from"):
                field_name = name.removesuffix("_from")
                statement = statement.where(getattr(model, field_name) >= value)
            elif name.endswith("_to"):
                field_name = name.removesuffix("_to")
                statement = statement.where(getattr(model, field_name) <= value)
            elif not hasattr(model, name):
                raise DomainRuleError(f"Unknown filter for {model.__tablename__}: {name}")
            else:
                statement = statement.where(getattr(model, name) == value)
        return statement

    @staticmethod
    def _model(kind: str):
        try:
            return MODEL_BY_KIND[kind]
        except KeyError as exc:
            raise DomainRuleError(f"Unknown entity kind: {kind}") from exc

    def _required(self, kind: str, entity_id: str):
        entity = self.get(kind, entity_id)
        if entity is None:
            raise DomainNotFoundError(f"{kind} not found: {entity_id}")
        return entity

    def _validate_links(self, entity) -> None:
        if isinstance(entity, Translation):
            allowed_fields = {
                "project": "name",
                "deliverable": "title",
                "task": "title",
                "meeting": "title",
                "action_item": "title",
                "capture": "text",
            }
            if entity.entity_kind not in allowed_fields:
                raise DomainRuleError("Entity kind does not support translations")
            self._required(entity.entity_kind, entity.entity_id)
            if entity.field_name != allowed_fields[entity.entity_kind]:
                raise DomainRuleError("Translation field does not match the source entity")

        if isinstance(entity, Task) and entity.deliverable_id:
            deliverable = self._required("deliverable", entity.deliverable_id)
            if deliverable.project_id != entity.project_id:
                raise DomainRuleError("Task and deliverable must belong to the same project")

        if isinstance(entity, ActionItem):
            meeting = self._required("meeting", entity.meeting_id)
            if entity.task_id:
                task = self._required("task", entity.task_id)
                if task.project_id != meeting.project_id:
                    raise DomainRuleError("Action item and task must belong to the same project")
            if entity.deliverable_id:
                deliverable = self._required("deliverable", entity.deliverable_id)
                if deliverable.project_id != meeting.project_id:
                    raise DomainRuleError(
                        "Action item and deliverable must belong to the same project"
                    )

        if isinstance(entity, HabitCompletion):
            self._required("habit", entity.habit_id)
