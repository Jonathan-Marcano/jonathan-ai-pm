from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from jonathan_ai_pm.services import DomainRuleError, DomainStore


def build_hierarchy(store: DomainStore) -> None:
    store.create("workspace", id="wrk_rules", name="Rules", timezone="America/Santiago")
    store.create("client", id="cli_rules", workspace_id="wrk_rules", name="Rules Client")
    store.create("project", id="prj_rules", client_id="cli_rules", name="Rules Project")
    store.create(
        "deliverable",
        id="del_rules",
        project_id="prj_rules",
        title="Rules deliverable",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "task",
        id="tsk_rules",
        project_id="prj_rules",
        deliverable_id="del_rules",
        title="Validate rules",
        status="ready",
    )


def add_meeting(store: DomainStore) -> None:
    store.create(
        "meeting",
        id="mtg_rules",
        project_id="prj_rules",
        title="Rules review",
        starts_at=datetime(2026, 9, 14, 13, tzinfo=UTC),
    )


def test_blank_capture_and_dismissal_without_reason_are_rejected(session) -> None:
    store = DomainStore(session)
    with pytest.raises(DomainRuleError, match="non-empty"):
        store.capture("   ")

    capture = store.capture("Review note")
    with pytest.raises(DomainRuleError, match="requires a note"):
        store.triage_capture(capture.id, "dismissed", note="   ")
    session.rollback()
    assert store.get("capture", capture.id).status == "inbox"


def test_meeting_and_work_log_require_timezone_aware_timestamps(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError, match="timezone"):
        store.create(
            "meeting",
            id="mtg_naive",
            project_id="prj_rules",
            title="Naive meeting",
            starts_at=datetime(2026, 9, 14, 13),
        )
    session.rollback()

    store.start_task("tsk_rules")
    with pytest.raises(DomainRuleError, match="timezone"):
        store.add_work_log(
            "tsk_rules",
            minutes=15,
            summary="Validated a rule.",
            started_at=datetime(2026, 9, 14, 14),
        )


def test_blank_completion_and_review_evidence_are_rejected(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError, match="completion note or work log"):
        store.complete_task("tsk_rules", "   ")

    store.update(
        "deliverable",
        "del_rules",
        acceptance_criteria="   ",
        evidence_url="   ",
    )
    with pytest.raises(DomainRuleError, match="acceptance criteria"):
        store.move_deliverable_to_review("del_rules")


def test_action_item_dispositions_require_consistent_task_links(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    add_meeting(store)

    with pytest.raises(DomainRuleError, match="accepted"):
        store.create(
            "action_item",
            id="act_accepted",
            meeting_id="mtg_rules",
            title="Missing task",
            status="accepted",
            owner="Demo Engineer",
        )
    session.rollback()

    with pytest.raises(DomainRuleError, match="dismissed"):
        store.create(
            "action_item",
            id="act_dismissed",
            meeting_id="mtg_rules",
            task_id="tsk_rules",
            title="Conflicting disposition",
            status="dismissed",
            owner="Demo Engineer",
        )


def test_closed_action_item_cannot_create_task(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    add_meeting(store)
    store.create(
        "action_item",
        id="act_closed",
        meeting_id="mtg_rules",
        title="Informational",
        status="dismissed",
        owner="Demo Engineer",
    )

    with pytest.raises(DomainRuleError, match="Only a captured"):
        store.create_task_from_action("act_closed", "tsk_from_closed")


def test_cross_project_task_update_rolls_back_cleanly(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.create("project", id="prj_other", client_id="cli_rules", name="Other Project")

    with pytest.raises(DomainRuleError, match="same project"):
        store.update("task", "tsk_rules", project_id="prj_other")
    session.rollback()

    task = store.get("task", "tsk_rules")
    assert task.project_id == "prj_rules"
    assert task.deliverable_id == "del_rules"


def test_action_item_rejects_cross_project_task_and_deliverable(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    add_meeting(store)
    store.create("project", id="prj_other", client_id="cli_rules", name="Other Project")
    store.create(
        "deliverable",
        id="del_other",
        project_id="prj_other",
        title="Other deliverable",
        due_at=date(2026, 9, 20),
    )
    store.create(
        "task",
        id="tsk_other",
        project_id="prj_other",
        title="Other task",
    )

    with pytest.raises(DomainRuleError, match="task must belong"):
        store.create(
            "action_item",
            id="act_wrong_task",
            meeting_id="mtg_rules",
            task_id="tsk_other",
            title="Wrong task",
            owner="Demo Engineer",
        )
    session.rollback()

    with pytest.raises(DomainRuleError, match="deliverable must belong"):
        store.create(
            "action_item",
            id="act_wrong_deliverable",
            meeting_id="mtg_rules",
            deliverable_id="del_other",
            title="Wrong deliverable",
            owner="Demo Engineer",
        )


def test_capture_and_work_log_history_are_immutable(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Original text")
    with pytest.raises(DomainRuleError, match="immutable"):
        store.update("capture", capture.id, text="Rewritten")

    store.start_task("tsk_rules")
    work_log = store.add_work_log(
        "tsk_rules",
        minutes=20,
        summary="Validated lifecycle rules.",
        started_at=datetime(2026, 9, 14, 14, tzinfo=UTC),
    )
    with pytest.raises(DomainRuleError, match="append-only"):
        store.update("work_log", work_log.id, minutes=30)


def test_one_task_cannot_be_linked_to_two_action_items(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    add_meeting(store)
    store.create(
        "action_item",
        id="act_first",
        meeting_id="mtg_rules",
        task_id="tsk_rules",
        title="First action",
        owner="Demo Engineer",
    )
    with pytest.raises(IntegrityError):
        store.create(
            "action_item",
            id="act_second",
            meeting_id="mtg_rules",
            task_id="tsk_rules",
            title="Second action",
            owner="Demo Engineer",
        )


def test_referenced_project_cannot_be_deleted(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(IntegrityError):
        store.delete("project", "prj_rules")
