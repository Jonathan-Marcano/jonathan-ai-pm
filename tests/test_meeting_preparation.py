from datetime import UTC, date, datetime

from faroflow.services import DomainStore

MEETING_AT = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)


def seed_graph(session, *, link_drive: bool = True) -> str:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="del_plan",
        project_id="prj_demo",
        title="Project plan",
        status="in_progress",
        due_at=date(2026, 9, 25),
    )
    store.create(
        "deliverable",
        id="del_cancelled",
        project_id="prj_demo",
        title="Cancelled body",
        status="cancelled",
        due_at=date(2026, 9, 10),
    )
    store.create(
        "task",
        id="tsk_review",
        project_id="prj_demo",
        title="Review drafts",
        status="ready",
        due_at=date(2026, 9, 23),
    )
    store.create(
        "task",
        id="tsk_cancelled",
        project_id="prj_demo",
        title="Cancelled task",
        status="cancelled",
        due_at=date(2026, 9, 9),
    )
    store.create(
        "meeting",
        id="mtg_kickoff",
        project_id="prj_demo",
        title="Kickoff",
        starts_at=MEETING_AT,
        status="scheduled",
    )
    store.create(
        "action_item",
        id="act_open",
        meeting_id="mtg_kickoff",
        title="Confirm scope",
        status="captured",
        owner="Ana",
    )
    store.create(
        "action_item",
        id="act_closed",
        meeting_id="mtg_kickoff",
        title="Draft agenda",
        status="done",
        owner="Luis",
    )
    if link_drive:
        store.link_drive_file(
            "del_plan",
            source_system="google-drive",
            external_id="file-123",
            name="Project plan.pdf",
            web_url="https://drive.test/plan",
            mime_type="application/pdf",
        )
    return "mtg_kickoff"


def test_preparation_combines_meeting_project_and_context(session) -> None:
    meeting_id = seed_graph(session)

    preparation = DomainStore(session).meeting_preparation(meeting_id)

    assert preparation["meeting"].id == "mtg_kickoff"
    assert preparation["meeting"].project_id == "prj_demo"
    assert preparation["project"].id == "prj_demo"
    assert preparation["client"].id == "cli_demo"
    assert preparation["prepared_at"].tzinfo is not None

    assert [action.id for action in preparation["open_action_items"]] == ["act_open"]
    assert [task.id for task in preparation["task_deadlines"]] == ["tsk_review"]
    assert [item.id for item in preparation["deliverable_deadlines"]] == ["del_plan"]
    assert [link.external_id for link in preparation["artifact_links"]] == ["file-123"]


def test_preparation_excludes_closed_and_linked_out_context(session) -> None:
    meeting_id = seed_graph(session, link_drive=False)
    store = DomainStore(session)
    store.create(
        "task",
        id="tsk_other",
        project_id="prj_demo",
        title="No due date",
        status="ready",
        due_at=None,
    )

    preparation = store.meeting_preparation(meeting_id)

    assert [task.id for task in preparation["task_deadlines"]] == ["tsk_review"]
    assert [item.id for item in preparation["deliverable_deadlines"]] == ["del_plan"]
    assert preparation["artifact_links"] == []
    assert len(preparation["open_action_items"]) == 1


def test_preparation_for_unmatched_meeting_keeps_actions(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    meeting = store.create(
        "meeting",
        id="mtg_unmatched",
        project_id=None,
        title="Unmatched",
        starts_at=MEETING_AT,
        status="scheduled",
    )
    store.create(
        "action_item",
        id="act_open",
        meeting_id="mtg_unmatched",
        title="Confirm scope",
        status="captured",
        owner="Ana",
    )

    preparation = store.meeting_preparation(meeting.id)

    assert preparation["project"] is None
    assert preparation["client"] is None
    assert preparation["task_deadlines"] == []
    assert preparation["deliverable_deadlines"] == []
    assert preparation["artifact_links"] == []
    assert len(preparation["open_action_items"]) == 1


def test_preparation_missing_meeting_is_404(api_client, session) -> None:
    response = api_client.get("/api/v1/meetings/mtg_absent/preparation")

    assert response.status_code == 404
    assert response.json()["detail"] == "meeting not found: mtg_absent"


def test_preparation_endpoint_returns_full_view(api_client, session) -> None:
    meeting_id = seed_graph(session)

    response = api_client.get(f"/api/v1/meetings/{meeting_id}/preparation")

    assert response.status_code == 200
    body = response.json()
    assert body["meeting"]["id"] == "mtg_kickoff"
    assert body["project"]["id"] == "prj_demo"
    assert body["client"]["id"] == "cli_demo"
    assert [item["id"] for item in body["open_action_items"]] == ["act_open"]
    assert [item["id"] for item in body["task_deadlines"]] == ["tsk_review"]
    assert [item["id"] for item in body["deliverable_deadlines"]] == ["del_plan"]
    assert body["artifact_links"][0]["external_id"] == "file-123"
    assert body["artifact_links"][0]["deliverable_id"] == "del_plan"