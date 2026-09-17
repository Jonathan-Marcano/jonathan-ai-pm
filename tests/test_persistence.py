from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from faroflow.services import DomainRuleError, DomainStore


def build_hierarchy(store: DomainStore) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo Project")
    store.create(
        "deliverable",
        id="del_demo",
        project_id="prj_demo",
        title="Demo plan",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "task",
        id="tsk_demo",
        project_id="prj_demo",
        deliverable_id="del_demo",
        title="Write plan",
    )


def test_core_hierarchy_crud(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    assert store.get("task", "tsk_demo").deliverable_id == "del_demo"
    assert [project.id for project in store.list("project")] == ["prj_demo"]
    assert store.update("project", "prj_demo", health="on_track").health == "on_track"
    store.delete("task", "tsk_demo")
    assert store.get("task", "tsk_demo") is None


def test_orphan_client_is_rejected(session) -> None:
    store = DomainStore(session)
    with pytest.raises(IntegrityError):
        store.create("client", id="cli_orphan", workspace_id="wrk_missing", name="Orphan")
    session.rollback()


def test_action_item_retains_meeting_and_links_one_task(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Review",
        starts_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
    )
    action = store.create(
        "action_item",
        id="act_demo",
        meeting_id="mtg_demo",
        task_id="tsk_demo",
        title="Confirm plan",
        owner="Demo Engineer",
    )
    assert action.meeting_id == "mtg_demo"
    assert action.task_id == "tsk_demo"


def test_action_item_creates_task_in_meeting_project(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Review",
        starts_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
    )
    store.create(
        "action_item",
        id="act_demo",
        meeting_id="mtg_demo",
        title="Prepare validation",
        owner="Demo Engineer",
    )
    task = store.create_task_from_action(
        "act_demo", "tsk_from_action", priority="high", due_at=date(2026, 9, 16)
    )
    assert task.project_id == "prj_demo"
    assert task.status == "ready"
    assert store.get("action_item", "act_demo").task_id == "tsk_from_action"


def test_task_cannot_link_deliverable_from_another_project(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.create("project", id="prj_other", client_id="cli_demo", name="Other Project")
    with pytest.raises(DomainRuleError):
        store.create(
            "task",
            id="tsk_invalid",
            project_id="prj_other",
            deliverable_id="del_demo",
            title="Invalid link",
        )
    session.rollback()


def test_task_completion_requires_evidence(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError):
        store.complete_task("tsk_demo")
    assert store.complete_task("tsk_demo", completion_note="Reviewed locally").status == "done"


def test_incremental_work_starts_task_and_tracks_evidence(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.update("task", "tsk_demo", status="ready")

    task = store.start_task("tsk_demo")
    assert task.status == "in_progress"
    assert store.get("project", "prj_demo").status == "active"
    assert store.get("deliverable", "del_demo").status == "in_progress"

    first = store.add_work_log(
        "tsk_demo",
        minutes=25,
        summary="  Drafted the validation section.  ",
        started_at=datetime(2026, 9, 14, 14, 0, tzinfo=UTC),
    )
    second = store.add_work_log(
        "tsk_demo",
        minutes=15,
        summary="Reviewed the draft.",
        started_at=datetime(2026, 9, 14, 15, 0, tzinfo=UTC),
    )
    assert first.summary == "Drafted the validation section."
    assert [log.id for log in store.list_task_work_logs("tsk_demo")] == [first.id, second.id]
    assert store.complete_task("tsk_demo").status == "done"


def test_work_log_requires_started_task(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError, match="in-progress"):
        store.add_work_log("tsk_demo", minutes=10, summary="Drafted notes")


def test_task_start_uses_guarded_lifecycle(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError, match="ready or blocked"):
        store.start_task("tsk_demo")
    store.update("task", "tsk_demo", status="ready")
    assert store.start_task("tsk_demo").status == "in_progress"
    assert store.start_task("tsk_demo").status == "in_progress"


def test_generic_updates_cannot_bypass_guarded_transitions(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError, match="complete_task"):
        store.update("task", "tsk_demo", status="done")
    with pytest.raises(DomainRuleError, match="move_deliverable_to_review"):
        store.update("deliverable", "del_demo", status="in_review")
    with pytest.raises(DomainRuleError, match="start_task"):
        store.update("task", "tsk_demo", status="in_progress")
    with pytest.raises(DomainRuleError, match="complete_task"):
        store.create(
            "task",
            id="tsk_precompleted",
            project_id="prj_demo",
            title="Precompleted task",
            status="done",
        )


def test_deliverable_review_requires_criteria_and_evidence(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    with pytest.raises(DomainRuleError):
        store.move_deliverable_to_review("del_demo")
    store.update(
        "deliverable",
        "del_demo",
        acceptance_criteria="Approved by reviewer",
        evidence_url="https://drive.google.com/example",
    )
    assert store.move_deliverable_to_review("del_demo").status == "in_review"
