import pytest
from fastapi.testclient import TestClient

from faroflow.services import DomainStore


@pytest.fixture
def seeded_workspaces(session) -> list[str]:
    store = DomainStore(session)
    ids: list[str] = []
    for number in range(5):
        workspace = store.create(
            "workspace", id=f"ws_p{number}", name=f"Workspace {number}", timezone="UTC"
        )
        ids.append(workspace.id)
    return ids


def _link(response) -> dict[str, str]:
    value = response.headers.get("Link")
    if not value:
        return {}
    return {
        part.split("; rel=")[1].strip('"'): part.split(";")[0].strip("<>")
        for part in value.split(", ")
    }


def test_list_default_returns_all_without_link_header(
    api_client: TestClient, seeded_workspaces
):
    response = api_client.get("/api/v1/workspaces")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == seeded_workspaces
    assert "Link" not in response.headers


def test_list_paginates_with_next_link(api_client: TestClient, seeded_workspaces):
    response = api_client.get("/api/v1/workspaces", params={"limit": 2})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == seeded_workspaces[:2]

    links = _link(response)
    assert "next" in links
    assert "offset=2" in links["next"]
    assert "limit=2" in links["next"]
    assert "prev" not in links


def test_list_second_page_links_both_ways(api_client: TestClient, seeded_workspaces):
    response = api_client.get("/api/v1/workspaces", params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == seeded_workspaces[2:4]

    links = _link(response)
    assert "next" in links
    assert "offset=4" in links["next"]
    assert "prev" in links
    assert "offset=0" in links["prev"]


def test_list_last_page_has_no_next_link(api_client: TestClient, seeded_workspaces):
    response = api_client.get("/api/v1/workspaces", params={"limit": 3, "offset": 3})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == seeded_workspaces[3:5]
    assert "next" not in _link(response)


def test_pagination_preserves_filters_in_links(api_client: TestClient, seeded_workspaces):
    response = api_client.get(
        "/api/v1/workspaces", params={"limit": 2, "status": "active"}
    )
    links = _link(response)
    assert "status=active" in links["next"]
    assert "offset=2" in links["next"]


def test_page_limits_are_validated(api_client: TestClient):
    assert api_client.get("/api/v1/workspaces", params={"limit": 0}).status_code == 422
    assert api_client.get("/api/v1/workspaces", params={"limit": 501}).status_code == 422
    assert api_client.get("/api/v1/workspaces", params={"offset": -1}).status_code == 422


def test_list_page_service_contract(session):
    store = DomainStore(session)
    for number in range(3):
        store.create(
            "workspace", id=f"ws_s{number}", name=f"Workspace S{number}", timezone="UTC"
        )

    items, has_more = store.list_page("workspace", limit=2)
    assert len(items) == 2
    assert has_more is True

    items, has_more = store.list_page("workspace", limit=2, offset=2)
    assert len(items) == 1
    assert has_more is False