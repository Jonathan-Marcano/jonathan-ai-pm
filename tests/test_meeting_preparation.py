from datetime import UTC, date, datetime

import pytest

from jonathan_ai_pm.services import DomainRuleError, DomainStore


def seed_preparation_scenario(store: DomainStore) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create(
        "project",
        id="prj_main",
        client_id="cli_demo",
        name="Main Project",
        status="active",
        health="at_risk",
    )
    store.create(
        "project",
        id="prj_other",
        client_id="cli_demo",
        name="Other Project",
        status="active",
    )

    store.create(
        "deliverable",
        id="del_overdue",
        project_id="prj_main",
        title="Overdue plan",
        status="in_progress",
        due_at=date(2026, 9, 13),
        drive_url="https://drive.google.com/file/d/demo-overdue/view",
    )
    store.create(
        "deliverable",
        id="del_soon",
        project_id="prj_main",
        title="Upcoming MOP",
        status="planned",
        due_at=date(2026, 9, 16),
    )
    store.create(
        "deliverable",
        id="del_future",
        project_id="prj_main",
        title="Future reference",
        status="accepted",
        due_at=date(2026, 9, 30),
        drive_url="https://drive.google.com/file/d/demo-future/view",
    )

    task_rows = (
        ("tsk_overdue", "ready", "high", date(2026, 9, 13)),
        ("tsk_soon", "ready", "critical", date(2026, 9, 16)),
        ("tsk_blocked", "blocked", "medium", None),
        ("tsk_future", "ready", "low", date(2026, 9, 30)),
        ("tsk_other", "ready", "critical", date(2026, 9, 14)),
    )
    for task_id, status, priority, due_at in task_rows:
        store.create(
            "task",
            id=task_id,
            project_id="prj_other" if task_id == "tsk_other" else "prj_main",
            title=task_id,
            status=status,
            priority=priority,
            due_at=due_at,
        )
    store.create(
        "task",
        id="tsk_done",
        project_id="prj_main",
        title="Completed task",
        status="ready",
        due_at=date(2026, 9, 12),
    )
    store.complete_task("tsk_done", "Completed before preparation")

    store.create(
        "meeting",
        id="mtg_previous",
        project_id="prj_main",
        title="Previous project meeting",
        starts_at=datetime(2026, 9, 10, 13, tzinfo=UTC),
        status="completed",
    )
    store.create(
        "meeting",
        id="mtg_today",
        project_id="prj_main",
        title="Today's project review",
        starts_at=datetime(2026, 9, 14, 13, tzinfo=UTC),
    )
    store.create(
        "meeting",
        id="mtg_other",
        project_id="prj_other",
        title="Other project review",
        starts_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )
    store.create(
        "meeting",
        id="mtg_previous_local_day",
        project_id="prj_main",
        title="Previous local day",
        starts_at=datetime(2026, 9, 14, 2, tzinfo=UTC),
    )
    store.create(
        "meeting",
        id="mtg_cancelled",
        project_id="prj_main",
        title="Cancelled meeting",
        starts_at=datetime(2026, 9, 14, 17, tzinfo=UTC),
        status="cancelled",
    )

    store.create(
        "action_item",
        id="act_open",
        meeting_id="mtg_previous",
        title="Confirm migration window",
        owner="Jonathan",
        status="captured",
    )
    store.create(
        "action_item",
        id="act_done",
        meeting_id="mtg_previous",
        title="Already resolved",
        owner="Jonathan",
        status="done",
    )


def ids(records) -> list[str]:
    return [record.id for record in records]


def item_for(preparation, meeting_id: str):
    return next(item for item in preparation["meetings"] if item["meeting"].id == meeting_id)


def test_meeting_preparation_combines_only_linked_project_context(session) -> None:
    store = DomainStore(session)
    seed_preparation_scenario(store)

    preparation = store.meeting_preparation(
        "America/Santiago",
        preparation_date=date(2026, 9, 14),
        due_soon_days=3,
        now=datetime(2026, 9, 14, 11, tzinfo=UTC),
    )

    assert preparation["meeting_count"] == 2
    assert [item["meeting"].id for item in preparation["meetings"]] == [
        "mtg_today",
        "mtg_other",
    ]
    main = item_for(preparation, "mtg_today")
    assert main["client"].id == "cli_demo"
    assert main["project"].id == "prj_main"
    assert ids(main["open_action_items"]) == ["act_open"]
    assert ids(main["open_tasks"]) == [
        "tsk_soon",
        "tsk_overdue",
        "tsk_blocked",
        "tsk_future",
    ]
    assert ids(main["overdue_tasks"]) == ["tsk_overdue"]
    assert ids(main["due_soon_tasks"]) == ["tsk_soon"]
    assert ids(main["blocked_tasks"]) == ["tsk_blocked"]
    assert ids(main["overdue_deliverables"]) == ["del_overdue"]
    assert ids(main["due_soon_deliverables"]) == ["del_soon"]
    assert [link["deliverable_id"] for link in main["artifact_links"]] == [
        "del_overdue",
        "del_future",
    ]
    assert main["counts"] == {
        "open_action_items": 1,
        "open_tasks": 4,
        "overdue_tasks": 1,
        "due_soon_tasks": 1,
        "blocked_tasks": 1,
        "overdue_deliverables": 1,
        "due_soon_deliverables": 1,
        "artifact_links": 2,
    }

    other = item_for(preparation, "mtg_other")
    assert ids(other["open_tasks"]) == ["tsk_other"]
    assert other["open_action_items"] == []
    assert other["artifact_links"] == []


def test_meeting_preparation_endpoint_returns_dated_view(api_client, session) -> None:
    seed_preparation_scenario(DomainStore(session))

    response = api_client.get("/api/v1/briefs/meetings?date=2026-09-14&due_soon_days=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["preparation_date"] == "2026-09-14"
    assert payload["timezone"] == "America/Santiago"
    assert payload["due_soon_through"] == "2026-09-17"
    assert payload["meeting_count"] == 2
    assert payload["meetings"][0]["meeting"]["id"] == "mtg_today"
    assert payload["meetings"][0]["project"]["health"] == "at_risk"


def test_meeting_preparation_empty_date_is_explicit(session) -> None:
    store = DomainStore(session)
    seed_preparation_scenario(store)

    preparation = store.meeting_preparation(
        "America/Santiago", preparation_date=date(2026, 9, 20)
    )

    assert preparation["meeting_count"] == 0
    assert preparation["meetings"] == []


def test_meeting_preparation_validates_timezone_and_horizon(session) -> None:
    store = DomainStore(session)
    with pytest.raises(DomainRuleError, match="Unknown timezone"):
        store.meeting_preparation("Invalid/Timezone")
    with pytest.raises(DomainRuleError, match="between 0 and 30"):
        store.meeting_preparation("America/Santiago", due_soon_days=31)
