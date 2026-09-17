from __future__ import annotations

from datetime import datetime


class DomainRuleError(ValueError):
    """A business rule was violated; maps to HTTP 422 by default."""

    status_code = 422


class DomainNotFoundError(DomainRuleError):
    """A referenced entity does not exist; maps to HTTP 404."""

    status_code = 404


TASK_PROTECTED_STATUSES = frozenset({"done", "in_progress"})
DELIVERABLE_PROTECTED_STATUSES = frozenset({"in_review", "accepted"})


def create_status_error(kind: str, status: str | None) -> str | None:
    """Return a domain error message when a status cannot be written directly."""
    if kind == "task" and status == "done":
        return "Use complete_task to enforce completion evidence"
    if kind == "task" and status == "in_progress":
        return "Use start_task to enforce the work lifecycle"
    if kind == "deliverable" and status == "in_review":
        return "Use move_deliverable_to_review to enforce review evidence"
    if kind == "deliverable" and status == "accepted":
        return "A deliverable can be accepted only after it has been reviewed"
    return None


def task_status_error(current_status: str | None, next_status: str | None) -> str | None:
    """Guard tasks against transitions that bypass lifecycle evidence."""
    if next_status == "done":
        return "Use complete_task to enforce completion evidence"
    if next_status == "in_progress":
        return "Use start_task to enforce the work lifecycle"
    if current_status == "done" and next_status != "done":
        return "A completed task cannot return to an earlier status"
    return None


def action_item_link_error(status: str, task_id: str | None) -> str | None:
    if status == "accepted" and not task_id:
        return "An accepted action item requires a linked task"
    if status == "dismissed" and task_id:
        return "A dismissed action item cannot retain a linked task"
    return None


def task_completion_evidence_error(
    completion_note: str | None,
    has_work_log: bool,
    *,
    status: str = "done",
) -> str | None:
    if status != "done":
        return None
    note = completion_note.strip() if completion_note else None
    if not note and not has_work_log:
        return "A completed task requires a completion note or work log"
    return None


def deliverable_review_evidence_error(
    status: str,
    acceptance_criteria: str | None,
    evidence_url: str | None,
) -> str | None:
    if status not in {"in_review", "accepted"}:
        return None
    criteria = (acceptance_criteria or "").strip()
    evidence = (evidence_url or "").strip()
    if not criteria or not evidence:
        return "A deliverable in review requires acceptance criteria and an evidence URL"
    return None


def timezone_aware_error(value: datetime, field_name: str) -> str | None:
    if value.tzinfo is None or value.utcoffset() is None:
        return f"{field_name} must include a timezone"
    return None