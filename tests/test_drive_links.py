from datetime import UTC, datetime
from urllib.parse import urlencode

from faroflow.models import ExternalIdentity
from faroflow.services import DomainStore


def seed_deliverable(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="dlv_demo",
        project_id="prj_demo",
        title="Project plan",
        due_at=datetime(2026, 9, 30, tzinfo=UTC).date(),
    )


def test_link_and_list_drive_file(api_client, session) -> None:
    seed_deliverable(session)

    response = api_client.post(
        "/api/v1/deliverables/dlv_demo/drive-link",
        json={
            "source_system": "google-drive",
            "external_id": "file-1",
            "name": "Project plan.pdf",
            "web_url": "https://drive.example.test/file-1",
            "mime_type": "application/pdf",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["deliverable_id"] == "dlv_demo"
    assert body["deliverable_title"] == "Project plan"
    assert body["external_name"] == "Project plan.pdf"

    listed = api_client.get("/api/v1/integrations/drive-links")
    assert listed.status_code == 200
    assert [item["external_id"] for item in listed.json()] == ["file-1"]


def test_link_missing_deliverable_returns_404(api_client, session) -> None:
    response = api_client.post(
        "/api/v1/deliverables/dlv_nope/drive-link",
        json={"source_system": "google-drive", "external_id": "file-1"},
    )
    assert response.status_code == 404


def test_link_already_linked_file_conflicts(api_client, session) -> None:
    seed_deliverable(session)
    store = DomainStore(session)
    store.create(
        "deliverable",
        id="dlv_other",
        project_id="prj_demo",
        title="Other",
        due_at=datetime(2026, 10, 1, tzinfo=UTC).date(),
    )
    payload = {
        "source_system": "google-drive",
        "external_id": "file-1",
        "web_url": "https://drive.example.test/file-1",
    }
    assert (
        api_client.post("/api/v1/deliverables/dlv_demo/drive-link", json=payload).status_code
        == 201
    )

    response = api_client.post("/api/v1/deliverables/dlv_other/drive-link", json=payload)
    assert response.status_code == 422


def test_unlink_drive_link(api_client, session) -> None:
    seed_deliverable(session)
    DomainStore(session).link_drive_file(
        "dlv_demo",
        source_system="google-drive",
        external_id="file-1",
        web_url="https://drive.example.test/file-1",
    )

    response = api_client.delete("/api/v1/deliverables/dlv_demo/drive-link")

    assert response.status_code == 204
    assert session.query(ExternalIdentity).count() == 0


def test_unlink_without_link_returns_422(api_client, session) -> None:
    seed_deliverable(session)

    response = api_client.delete("/api/v1/deliverables/dlv_demo/drive-link")

    assert response.status_code == 422


def test_drive_links_pagination(api_client, session) -> None:
    seed_deliverable(session)
    store = DomainStore(session)
    for index in range(3):
        store.link_drive_file(
            "dlv_demo",
            source_system="google-drive",
            external_id=f"file-{index}",
            web_url=f"https://drive.example.test/file-{index}",
        )

    query = urlencode({"limit": 2})
    response = api_client.get(f"/api/v1/integrations/drive-links?{query}")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert 'rel="next"' in response.headers["Link"]


def test_drive_refresh_reports_not_configured(api_client, session) -> None:
    response = api_client.post("/api/v1/integrations/drive/refresh")

    assert response.status_code == 503
    assert response.json()["detail"] == "Drive integration is not configured"
    assert session.query(ExternalIdentity).count() == 0