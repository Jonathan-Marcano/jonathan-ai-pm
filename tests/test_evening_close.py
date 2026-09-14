from datetime import UTC, date, datetime

from jonathan_ai_pm.services import DomainStore


def seed_evening_scenario(store: DomainStore, session) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create(
        "project",
        id="prj_demo",
        client_id="cli_demo",
        name="Demo Project",
        status="active",
        health="on_track",
    )
    store.create(
        "project",
        id="prj_risk",
        client_id="cli_demo",
        name="Project needing review",
        status="active",
        health="off_track",
    )
    store.create(
        "deliverable",
        id="del_demo",
        project_id="prj_demo",
        title="Demo plan",
        status="in_progress",
        due_at=date(2026, 9, 18),
    )

    task_data = (
        ("tsk_done", "ready", "high", date(2026, 9, 14), "del_demo"),
        ("tsk_doing", "ready", "critical", date(2026, 9, 16), "del_demo"),
        ("tsk_blocked", "blocked", "high", date(2026, 9, 20), None),
        ("tsk_overdue", "ready", "medium", date(2026, 9, 13), None),
        ("tsk_inbox", "inbox", "low", None, None),
        ("tsk_future", "ready", "low", date(2026, 9, 20), None),
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

    completed = store.complete_task("tsk_done", "Reviewed locally")
    completed.updated_at = datetime(2026, 9, 14, 16, tzinfo=UTC)
    store.start_task("tsk_doing")
    store.add_work_log(
        "tsk_doing",
        minutes=20,
        summary="Previous local day session.",
        started_at=datetime(2026, 9, 14, 2, tzinfo=UTC),
    )
    store.add_work_log(
        "tsk_doing",
        minutes=30,
        summary="Drafted and reviewed a section.",
        started_at=datetime(2026, 9, 14, 14, tzinfo=UTC),
    )

    old_capture = store.capture("Older open note")
    old_capture.captured_at = datetime(2026, 9, 13, 12, tzinfo=UTC)
    today_capture = store.capture("Today's open note")
    today_capture.captured_at = datetime(2026, 9, 14, 12, tzinfo=UTC)
    future_capture = store.capture("Future note")
    future_capture.captured_at = datetime(2026, 9, 15, 12, tzinfo=UTC)
    triaged_capture = store.capture("Reviewed note")
    store.triage_capture(triaged_capture.id, "reference", project_id="prj_demo")
    triaged_capture.captured_at = datetime(2026, 9, 14, 13, tzinfo=UTC)
    triaged_capture.triaged_at = datetime(2026, 9, 14, 15, tzinfo=UTC)

    store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Review",
        starts_at=datetime(2026, 9, 14, 13, tzinfo=UTC),
    )
    store.create(
        "action_item",
        id="act_open",
        meeting_id="mtg_demo",
        title="Confirm dependencies",
        owner="Demo Engineer",
    )
    store.create(
        "action_item",
        id="act_done",
        meeting_id="mtg_demo",
        title="Already closed",
        status="done",
        owner="Demo Engineer",
    )
    session.commit()


def ids(records) -> list[str]:
    return [record.id for record in records]


def test_evening_close_reconciles_daily_work(session) -> None:
    store = DomainStore(session)
    seed_evening_scenario(store, session)

    close = store.evening_close(
        "America/Santiago",
        close_date=date(2026, 9, 14),
        now=datetime(2026, 9, 14, 22, tzinfo=UTC),
    )

    assert ids(close["completed_tasks"]) == ["tsk_done"]
    assert len(close["work_logs"]) == 1
    assert close["work_logs"][0].minutes == 30
    assert [capture.text for capture in close["untriaged_captures"]] == [
        "Older open note",
        "Today's open note",
    ]
    assert [capture.text for capture in close["triaged_captures"]] == ["Reviewed note"]
    assert ids(close["open_action_items"]) == ["act_open"]
    assert ids(close["unfinished_tasks"]) == [
        "tsk_doing",
        "tsk_blocked",
        "tsk_overdue",
        "tsk_inbox",
    ]
    assert ids(close["blocked_tasks"]) == ["tsk_blocked"]
    assert ids(close["touched_deliverables"]) == ["del_demo"]
    assert ids(close["projects_to_review"]) == ["prj_risk", "prj_demo"]
    assert close["tomorrow_first_action"].id == "tsk_doing"
    assert close["counts"] == {
        "completed_tasks": 1,
        "work_logs": 1,
        "logged_minutes": 30,
        "untriaged_captures": 2,
        "triaged_captures": 1,
        "open_action_items": 1,
        "unfinished_tasks": 4,
        "blocked_tasks": 1,
        "touched_deliverables": 1,
        "projects_to_review": 2,
    }


def test_evening_close_endpoint(api_client, session) -> None:
    store = DomainStore(session)
    seed_evening_scenario(store, session)

    response = api_client.get("/api/v1/briefs/evening?date=2026-09-14")

    assert response.status_code == 200
    payload = response.json()
    assert payload["close_date"] == "2026-09-14"
    assert payload["timezone"] == "America/Santiago"
    assert payload["counts"]["logged_minutes"] == 30
    assert payload["tomorrow_first_action"]["id"] == "tsk_doing"
