from datetime import UTC, date, datetime

from faroflow.services import DomainStore


def seed_progress_scenario(store: DomainStore) -> None:
    store.create("workspace", id="wrk_consulting", name="Consulting", timezone="America/Santiago")
    store.create(
        "client",
        id="cli_bank",
        workspace_id="wrk_consulting",
        name="Demo Bank",
    )
    store.create(
        "project",
        id="prj_aci",
        client_id="cli_bank",
        name="Demo ACI",
        status="active",
    )
    store.create(
        "project",
        id="prj_assessment",
        client_id="cli_bank",
        name="Demo Assessment",
        status="active",
    )
    store.create(
        "deliverable",
        id="del_plan",
        project_id="prj_aci",
        title="Demo plan",
        status="in_progress",
        due_at=date(2026, 9, 18),
    )

    store.create(
        "task",
        id="tsk_done",
        project_id="prj_aci",
        deliverable_id="del_plan",
        title="Completed section",
        status="ready",
        priority="high",
    )
    store.start_task("tsk_done")
    store.add_work_log(
        "tsk_done",
        minutes=60,
        summary="Completed and reviewed the section.",
        started_at=datetime(2026, 9, 14, 14, tzinfo=UTC),
    )
    store.complete_task("tsk_done")

    store.create(
        "task",
        id="tsk_active",
        project_id="prj_aci",
        deliverable_id="del_plan",
        title="Active section",
        status="ready",
        priority="critical",
    )
    store.start_task("tsk_active")
    store.add_work_log(
        "tsk_active",
        minutes=30,
        summary="Previous-day session.",
        started_at=datetime(2026, 9, 13, 14, tzinfo=UTC),
    )
    store.add_work_log(
        "tsk_active",
        minutes=20,
        summary="Current-day session.",
        started_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )
    store.create(
        "task",
        id="tsk_blocked",
        project_id="prj_aci",
        title="Blocked dependency",
        status="blocked",
        priority="high",
        due_at=date(2026, 9, 13),
    )
    store.create(
        "task",
        id="tsk_ready",
        project_id="prj_assessment",
        title="Ready assessment",
        status="ready",
        priority="medium",
        due_at=date(2026, 9, 13),
    )

    store.create("workspace", id="wrk_personal", name="Personal", timezone="America/Santiago")
    store.create(
        "client",
        id="cli_personal",
        workspace_id="wrk_personal",
        name="Personal",
    )
    store.create(
        "project",
        id="prj_personal",
        client_id="cli_personal",
        name="Personal project",
    )
    store.create(
        "task",
        id="tsk_cancelled",
        project_id="prj_personal",
        title="Cancelled task",
        status="cancelled",
    )


def rows_by_id(rows) -> dict:
    return {row["id"]: row for row in rows}


def test_progress_summary_rolls_up_every_hierarchy_level(session) -> None:
    store = DomainStore(session)
    seed_progress_scenario(store)

    report = store.progress_summary(
        "America/Santiago",
        as_of=date(2026, 9, 14),
        work_from=date(2026, 9, 14),
        work_to=date(2026, 9, 14),
        now=datetime(2026, 9, 14, 22, tzinfo=UTC),
    )

    assert report["totals"]["tasks"] == {
        "total": 5,
        "open": 3,
        "overdue": 2,
        "completion_percent": 25.0,
        "inbox": 0,
        "ready": 1,
        "in_progress": 1,
        "blocked": 1,
        "done": 1,
        "cancelled": 1,
    }
    assert report["totals"]["logged_minutes"] == 80

    workspaces = rows_by_id(report["workspaces"])
    assert workspaces["wrk_consulting"]["metrics"]["tasks"]["total"] == 4
    assert workspaces["wrk_consulting"]["metrics"]["logged_minutes"] == 80
    assert workspaces["wrk_personal"]["metrics"]["tasks"]["cancelled"] == 1

    projects = rows_by_id(report["projects"])
    assert projects["prj_aci"]["metrics"]["tasks"]["completion_percent"] == 33.3
    assert projects["prj_aci"]["metrics"]["deliverables"]["in_progress"] == 1
    assert projects["prj_assessment"]["metrics"]["tasks"]["overdue"] == 1

    deliverables = rows_by_id(report["deliverables"])
    assert deliverables["del_plan"]["metrics"]["tasks"]["total"] == 2
    assert deliverables["del_plan"]["metrics"]["tasks"]["completion_percent"] == 50.0
    assert deliverables["del_plan"]["metrics"]["logged_minutes"] == 80


def test_progress_summary_endpoint_and_date_validation(api_client, session) -> None:
    seed_progress_scenario(DomainStore(session))

    response = api_client.get(
        "/api/v1/reports/progress"
        "?as_of=2026-09-14&work_from=2026-09-14&work_to=2026-09-14"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["logged_minutes"] == 80
    assert len(payload["workspaces"]) == 2
    assert len(payload["clients"]) == 2
    assert len(payload["projects"]) == 3
    assert len(payload["deliverables"]) == 1

    invalid = api_client.get(
        "/api/v1/reports/progress?work_from=2026-09-15&work_to=2026-09-14"
    )
    assert invalid.status_code == 422
