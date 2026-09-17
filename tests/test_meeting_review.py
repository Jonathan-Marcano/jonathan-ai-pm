from datetime import UTC, datetime

from faroflow.services import DomainStore

MEETING_AT = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)


def seed_meetings(session) -> None:
    store = DomainStore(session)
    store.create(
        "meeting",
        id="mtg_old",
        title="Old review",
        starts_at=MEETING_AT,
        status="completed",
    )
    store.create(
        "meeting",
        id="mtg_new",
        title="New review",
        starts_at=MEETING_AT.replace(hour=16),
        status="completed",
    )
    store.create(
        "meeting",
        id="mtg_planned",
        title="Planned",
        starts_at=MEETING_AT.replace(hour=17),
        status="scheduled",
    )
    store.create(
        "meeting",
        id="mtg_cancelled",
        title="Cancelled",
        starts_at=MEETING_AT.replace(hour=18),
        status="cancelled",
    )


def test_complete_meeting_moves_to_completed_and_enters_queue(session) -> None:
    store = DomainStore(session)
    store.create(
        "meeting",
        id="mtg_planned",
        title="Planned",
        starts_at=MEETING_AT,
        status="scheduled",
    )

    meeting = store.complete_meeting("mtg_planned")

    assert meeting.status == "completed"
    assert meeting.reviewed_at is None
    items, _has_more = store.list_completed_meetings()
    assert [item.id for item in items] == ["mtg_planned"]


def test_review_meeting_leaves_queue_and_is_idempotent(session) -> None:
    seed_meetings(session)
    store = DomainStore(session)
    reviewed = store.review_meeting("mtg_new")

    assert reviewed.reviewed_at is not None
    items, _has_more = store.list_completed_meetings()
    assert [item.id for item in items] == ["mtg_old"]

    again = store.review_meeting("mtg_new")
    assert again.reviewed_at == reviewed.reviewed_at


def test_patch_completed_meeting_also_enters_queue(session) -> None:
    store = DomainStore(session)
    store.create(
        "meeting",
        id="mtg_direct",
        title="Direct",
        starts_at=MEETING_AT,
        status="scheduled",
    )
    store.update("meeting", "mtg_direct", status="completed")

    items, _has_more = store.list_completed_meetings()
    assert [item.id for item in items] == ["mtg_direct"]


def test_complete_meeting_rejects_invalid_statuses(session) -> None:
    seed_meetings(session)
    store = DomainStore(session)
    for meeting_id in ("mtg_new", "mtg_cancelled"):
        try:
            store.complete_meeting(meeting_id)
            raise AssertionError(f"{meeting_id} should not be completable")
        except Exception as exc:
            assert "Only scheduled meetings can be completed" in str(exc)


def test_review_meeting_rejects_uncompleted(session) -> None:
    seed_meetings(session)
    store = DomainStore(session)
    try:
        store.review_meeting("mtg_planned")
        raise AssertionError("uncompleted meeting should not be reviewable")
    except Exception as exc:
        assert "Only completed meetings can be reviewed" in str(exc)


def test_queue_ordering_and_pagination(session) -> None:
    seed_meetings(session)
    store = DomainStore(session)

    items, has_more = store.list_completed_meetings(limit=1)
    assert [item.id for item in items] == ["mtg_new"]
    assert has_more is True

    items, has_more = store.list_completed_meetings(limit=1, offset=1)
    assert [item.id for item in items] == ["mtg_old"]
    assert has_more is False


def test_complete_endpoint_returns_meeting(api_client, session) -> None:
    DomainStore(session).create(
        "meeting",
        id="mtg_planned",
        title="Planned",
        starts_at=MEETING_AT,
        status="scheduled",
    )

    response = api_client.post("/api/v1/meetings/mtg_planned/complete")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "mtg_planned"
    assert body["status"] == "completed"
    assert body["reviewed_at"] is None


def test_complete_endpoint_rejects_completed(api_client, session) -> None:
    DomainStore(session).create(
        "meeting",
        id="mtg_done",
        title="Done",
        starts_at=MEETING_AT,
        status="completed",
    )

    response = api_client.post("/api/v1/meetings/mtg_done/complete")

    assert response.status_code == 422
    assert "Only scheduled meetings can be completed" in response.json()["detail"]


def test_review_endpoint_marks_reviewed(api_client, session) -> None:
    DomainStore(session).create(
        "meeting",
        id="mtg_done",
        title="Done",
        starts_at=MEETING_AT,
        status="completed",
    )

    response = api_client.post(
        "/api/v1/meetings/mtg_done/review", json={"decision": "reviewed"}
    )

    assert response.status_code == 200
    assert response.json()["reviewed_at"] is not None


def test_completed_queue_endpoint(api_client, session) -> None:
    seed_meetings(session)

    response = api_client.get(
        "/api/v1/integrations/meetings/completed?limit=1&offset=1"
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["mtg_old"]
    assert response.headers["link"] is not None


def test_meeting_and_review_endpoints_404(api_client, session) -> None:
    assert api_client.post("/api/v1/meetings/mtg_absent/complete").status_code == 404
    review = api_client.post(
        "/api/v1/meetings/mtg_absent/review", json={"decision": "reviewed"}
    )
    assert review.status_code == 404