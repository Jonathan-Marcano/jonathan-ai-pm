from datetime import UTC, date, datetime

import pytest

from jonathan_ai_pm.services import DomainRuleError, DomainStore


def seed_brief_scenario(store: DomainStore) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create(
        "project",
        id="prj_demo",
        client_id="cli_demo",
        name="Demo Project",
        status="active",
        health="at_risk",
    )
    store.create(
        "deliverable",
        id="del_focus",
        project_id="prj_demo",
        title="Plan without active work",
        status="planned",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "deliverable",
        id="del_active",
        project_id="prj_demo",
        title="Plan being worked",
        status="in_progress",
        due_at=date(2026, 9, 17),
    )
    store.create(
        "deliverable",
        id="del_blocked",
        project_id="prj_demo",
        title="Blocked plan",
        status="blocked",
        due_at=date(2026, 9, 16),
    )

    task_data = (
        ("tsk_overdue", "ready", "high", date(2026, 9, 13), None),
        ("tsk_today", "ready", "medium", date(2026, 9, 14), None),
        ("tsk_soon", "ready", "critical", date(2026, 9, 16), None),
        ("tsk_future", "ready", "high", date(2026, 9, 25), None),
        ("tsk_doing", "in_progress", "medium", date(2026, 9, 17), "del_active"),
        ("tsk_blocked", "blocked", "high", date(2026, 9, 15), "del_blocked"),
        ("tsk_done", "ready", "critical", date(2026, 9, 12), None),
    )
    for task_id, status, priority, due_at, deliverable_id in task_data:
        store.create(
            "task",
            id=task_id,
            project_id="prj_demo",
            deliverable_id=deliverable_id,
            title=task_id,
            status=status,
            priority=priority,
            due_at=due_at,
        )
    store.complete_task("tsk_done", "Finished")

    store.create(
        "meeting",
        id="mtg_today",
        project_id="prj_demo",
        title="Today's review",
        starts_at=datetime(2026, 9, 14, 13, tzinfo=UTC),
        status="scheduled",
    )
    store.create(
        "meeting",
        id="mtg_previous_local_day",
        project_id="prj_demo",
        title="Previous local day",
        starts_at=datetime(2026, 9, 14, 2, tzinfo=UTC),
        status="scheduled",
    )
    store.create(
        "meeting",
        id="mtg_cancelled",
        project_id="prj_demo",
        title="Cancelled",
        starts_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
        status="cancelled",
    )


def ids(records) -> list[str]:
    return [record.id for record in records]


def test_morning_brief_sections_and_ranking(session) -> None:
    store = DomainStore(session)
    seed_brief_scenario(store)
    brief = store.morning_brief(
        "America/Santiago",
        brief_date=date(2026, 9, 14),
        due_soon_days=3,
        now=datetime(2026, 9, 14, 11, tzinfo=UTC),
    )

    assert ids(brief["meetings"]) == ["mtg_today"]
    assert ids(brief["overdue_tasks"]) == ["tsk_overdue"]
    assert ids(brief["due_soon_tasks"]) == [
        "tsk_soon",
        "tsk_blocked",
        "tsk_today",
        "tsk_doing",
    ]
    assert ids(brief["focus_tasks"]) == ["tsk_soon", "tsk_overdue", "tsk_future"]
    assert ids(brief["blocked_tasks"]) == ["tsk_blocked"]
    assert ids(brief["blocked_deliverables"]) == ["del_blocked"]
    assert ids(brief["deliverable_opportunities"]) == ["del_focus"]
    assert ids(brief["at_risk_projects"]) == ["prj_demo"]
    assert brief["counts"]["due_soon_tasks"] == 4


def test_morning_brief_endpoint(api_client, session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo Project")
    store.create(
        "task",
        id="tsk_today",
        project_id="prj_demo",
        title="Today's task",
        status="ready",
        priority="critical",
        due_at=date(2026, 9, 14),
    )
    response = api_client.get("/api/v1/briefs/morning?date=2026-09-14&due_soon_days=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_date"] == "2026-09-14"
    assert payload["timezone"] == "America/Santiago"
    assert payload["focus_tasks"][0]["id"] == "tsk_today"
    assert payload["counts"]["due_soon_tasks"] == 1


def test_morning_brief_rejects_unknown_timezone(session) -> None:
    with pytest.raises(DomainRuleError, match="Unknown timezone"):
        DomainStore(session).morning_brief("Invalid/Timezone")


def test_morning_brief_rejects_invalid_horizon(session) -> None:
    with pytest.raises(DomainRuleError, match="between 0 and 30"):
        DomainStore(session).morning_brief("America/Santiago", due_soon_days=31)
