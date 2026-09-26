def test_health(api_client) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def create_core_hierarchy(api_client) -> None:
    assert (
        api_client.post(
            "/api/v1/workspaces",
            json={"id": "wrk_demo", "name": "Demo", "timezone": "America/Santiago"},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/clients",
            json={"id": "cli_demo", "workspace_id": "wrk_demo", "name": "Demo Client"},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/projects",
            json={"id": "prj_demo", "client_id": "cli_demo", "name": "Demo Project"},
        ).status_code
        == 201
    )


def test_core_crud_and_filters(api_client) -> None:
    create_core_hierarchy(api_client)
    deliverable = api_client.post(
        "/api/v1/deliverables",
        json={
            "id": "del_demo",
            "project_id": "prj_demo",
            "title": "Demo plan",
            "due_at": "2026-09-18",
        },
    )
    assert deliverable.status_code == 201
    task = api_client.post(
        "/api/v1/tasks",
        json={
            "id": "tsk_demo",
            "project_id": "prj_demo",
            "deliverable_id": "del_demo",
            "title": "Write plan",
            "priority": "high",
            "due_at": "2026-09-16",
        },
    )
    assert task.status_code == 201

    filtered = api_client.get("/api/v1/tasks?priority=high&due_to=2026-09-16")
    assert [item["id"] for item in filtered.json()] == ["tsk_demo"]
    updated = api_client.patch("/api/v1/projects/prj_demo", json={"health": "on_track"})
    assert updated.status_code == 200
    assert updated.json()["health"] == "on_track"
    assert api_client.delete("/api/v1/tasks/tsk_demo").status_code == 204
    assert api_client.get("/api/v1/tasks/tsk_demo").status_code == 404


def test_relationship_conflict_returns_409(api_client) -> None:
    response = api_client.post(
        "/api/v1/clients",
        json={"id": "cli_orphan", "workspace_id": "wrk_missing", "name": "Orphan"},
    )
    assert response.status_code == 409


def test_guarded_transitions(api_client) -> None:
    create_core_hierarchy(api_client)
    api_client.post(
        "/api/v1/deliverables",
        json={
            "id": "del_demo",
            "project_id": "prj_demo",
            "title": "Demo plan",
            "due_at": "2026-09-18",
        },
    )
    api_client.post(
        "/api/v1/tasks",
        json={"id": "tsk_demo", "project_id": "prj_demo", "title": "Write plan"},
    )

    assert api_client.patch("/api/v1/tasks/tsk_demo", json={"status": "done"}).status_code == 422
    assert api_client.post("/api/v1/tasks/tsk_demo/complete", json={}).status_code == 422
    completed = api_client.post(
        "/api/v1/tasks/tsk_demo/complete", json={"completion_note": "Reviewed"}
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"

    assert api_client.post("/api/v1/deliverables/del_demo/review").status_code == 422
    api_client.patch(
        "/api/v1/deliverables/del_demo",
        json={
            "acceptance_criteria": "Reviewer approval",
            "evidence_url": "https://drive.google.com/example",
        },
    )
    reviewed = api_client.post("/api/v1/deliverables/del_demo/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "in_review"


def test_incremental_work_flow(api_client) -> None:
    create_core_hierarchy(api_client)
    api_client.post(
        "/api/v1/deliverables",
        json={
            "id": "del_demo",
            "project_id": "prj_demo",
            "title": "Demo plan",
            "due_at": "2026-09-18",
        },
    )
    api_client.post(
        "/api/v1/tasks",
        json={
            "id": "tsk_demo",
            "project_id": "prj_demo",
            "deliverable_id": "del_demo",
            "title": "Write plan",
            "status": "ready",
        },
    )

    assert (
        api_client.patch("/api/v1/tasks/tsk_demo", json={"status": "in_progress"}).status_code
        == 422
    )
    started = api_client.post("/api/v1/tasks/tsk_demo/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    logged = api_client.post(
        "/api/v1/tasks/tsk_demo/work-logs",
        json={
            "started_at": "2026-09-14T14:00:00Z",
            "minutes": 30,
            "summary": "Drafted and locally reviewed the plan section.",
        },
    )
    assert logged.status_code == 201
    assert logged.json()["task_id"] == "tsk_demo"
    assert logged.json()["minutes"] == 30
    assert logged.json()["id"].startswith("wlg_")

    history = api_client.get("/api/v1/tasks/tsk_demo/work-logs")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [logged.json()["id"]]
    assert api_client.post("/api/v1/tasks/tsk_demo/complete", json={}).status_code == 200
    assert api_client.get("/api/v1/projects/prj_demo").json()["status"] == "active"
    assert api_client.get("/api/v1/deliverables/del_demo").json()["status"] == "in_progress"


def test_work_log_rejects_task_that_has_not_started(api_client) -> None:
    create_core_hierarchy(api_client)
    api_client.post(
        "/api/v1/tasks",
        json={"id": "tsk_demo", "project_id": "prj_demo", "title": "Write plan"},
    )
    response = api_client.post(
        "/api/v1/tasks/tsk_demo/work-logs",
        json={"minutes": 10, "summary": "Drafted notes."},
    )
    assert response.status_code == 422


def test_action_item_becomes_one_task(api_client) -> None:
    create_core_hierarchy(api_client)
    api_client.post(
        "/api/v1/meetings",
        json={
            "id": "mtg_demo",
            "project_id": "prj_demo",
            "title": "Review",
            "starts_at": "2026-09-15T13:00:00Z",
        },
    )
    api_client.post(
        "/api/v1/action-items",
        json={
            "id": "act_demo",
            "meeting_id": "mtg_demo",
            "title": "Prepare validation",
            "owner": "Demo Engineer",
        },
    )

    response = api_client.post(
        "/api/v1/action-items/act_demo/task",
        json={"task_id": "tsk_from_action", "priority": "high", "due_at": "2026-09-16"},
    )
    assert response.status_code == 201
    assert response.json()["project_id"] == "prj_demo"
    assert response.json()["status"] == "ready"
    action = api_client.get("/api/v1/action-items/act_demo").json()
    assert action["task_id"] == "tsk_from_action"
    assert action["status"] == "accepted"
    assert (
        api_client.post(
            "/api/v1/action-items/act_demo/task", json={"task_id": "tsk_duplicate"}
        ).status_code
        == 422
    )


def test_quick_capture_requires_only_text(api_client) -> None:
    response = api_client.post("/api/v1/captures", json={"text": "Prepare demo plan"})
    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("cap_")
    assert payload["status"] == "inbox"
    assert payload["disposition"] is None


def test_capture_triage_creates_task_and_audit_fields(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post("/api/v1/captures", json={"text": "Prepare demo plan"}).json()[
        "id"
    ]
    response = api_client.post(
        f"/api/v1/captures/{capture_id}/triage",
        json={
            "disposition": "task",
            "project_id": "prj_demo",
            "task_id": "tsk_from_capture",
            "priority": "high",
            "due_at": "2026-09-18",
            "note": "Confirmed during daily review",
        },
    )
    assert response.status_code == 200
    capture = response.json()
    assert capture["status"] == "triaged"
    assert capture["task_id"] == "tsk_from_capture"
    assert capture["triaged_at"] is not None
    assert api_client.get("/api/v1/tasks/tsk_from_capture").json()["status"] == "ready"
    assert (
        api_client.post(
            f"/api/v1/captures/{capture_id}/triage",
            json={
                "disposition": "task",
                "project_id": "prj_demo",
                "task_id": "tsk_second",
            },
        ).status_code
        == 422
    )


def test_capture_triage_creates_meeting_action(api_client) -> None:
    create_core_hierarchy(api_client)
    api_client.post(
        "/api/v1/meetings",
        json={
            "id": "mtg_demo",
            "project_id": "prj_demo",
            "title": "Review",
            "starts_at": "2026-09-15T13:00:00Z",
        },
    )
    capture_id = api_client.post("/api/v1/captures", json={"text": "Confirm dependencies"}).json()[
        "id"
    ]
    response = api_client.post(
        f"/api/v1/captures/{capture_id}/triage",
        json={
            "disposition": "action",
            "meeting_id": "mtg_demo",
            "action_item_id": "act_from_capture",
            "owner": "Demo Engineer",
        },
    )
    assert response.status_code == 200
    assert response.json()["action_item_id"] == "act_from_capture"
    action = api_client.get("/api/v1/action-items/act_from_capture").json()
    assert action["meeting_id"] == "mtg_demo"
    assert action["status"] == "captured"


def test_capture_triage_reference_and_dismissal(api_client) -> None:
    create_core_hierarchy(api_client)
    reference_id = api_client.post("/api/v1/captures", json={"text": "Architecture note"}).json()[
        "id"
    ]
    dismissed_id = api_client.post("/api/v1/captures", json={"text": "Duplicate reminder"}).json()[
        "id"
    ]

    reference = api_client.post(
        f"/api/v1/captures/{reference_id}/triage",
        json={"disposition": "reference", "project_id": "prj_demo"},
    )
    dismissed = api_client.post(
        f"/api/v1/captures/{dismissed_id}/triage",
        json={"disposition": "dismissed", "note": "Duplicate"},
    )
    assert reference.json()["disposition"] == "reference"
    assert dismissed.json()["disposition_note"] == "Duplicate"
    inbox = api_client.get("/api/v1/captures?capture_status=inbox")
    assert inbox.status_code == 200
    assert inbox.json() == []


def test_dismissed_capture_requires_reason(api_client) -> None:
    capture_id = api_client.post("/api/v1/captures", json={"text": "Possible duplicate"}).json()[
        "id"
    ]
    response = api_client.post(
        f"/api/v1/captures/{capture_id}/triage", json={"disposition": "dismissed"}
    )
    assert response.status_code == 422


def test_static_assets_are_not_cached(api_client) -> None:
    """El JS del cliente se revalida siempre.

    Sin Cache-Control, Chrome aplica su heurístico de frescura (10% de la
    antigüedad del Last-Modified) y puede servir un módulo viejo sin preguntar
    al servidor. Eso hizo que un arreglo en api.js no se viera en el navegador
    y el síntoma fuera "hay que recargar con F5 para que aparezca el cambio".
    """
    index = api_client.get("/")
    assert index.status_code == 200
    assert index.headers["cache-control"] == "no-cache"

    for asset in ("/static/web/js/api.js", "/static/web/js/views-habitos.js"):
        response = api_client.get(asset)
        assert response.status_code == 200, asset
        assert response.headers["cache-control"] == "no-cache", asset
