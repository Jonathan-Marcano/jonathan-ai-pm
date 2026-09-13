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
