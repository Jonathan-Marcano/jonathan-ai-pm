from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from jonathan_ai_pm.db import build_engine
from jonathan_ai_pm.integrations import IntegrationStateStore
from jonathan_ai_pm.models import ActionItem, AuditEvent, Base
from jonathan_ai_pm.portability import export_snapshot, import_snapshot
from jonathan_ai_pm.schemas import SnapshotDocument
from jonathan_ai_pm.services import DomainRuleError, DomainStore


def seed_review_scenario(store: DomainStore) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create("project", id="prj_other", client_id="cli_demo", name="Other project")
    store.create(
        "deliverable",
        id="del_demo",
        project_id="prj_demo",
        title="Implementation plan",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "deliverable",
        id="del_other",
        project_id="prj_other",
        title="Other plan",
        due_at=date(2026, 9, 18),
    )
    store.create(
        "meeting",
        id="mtg_old",
        project_id="prj_demo",
        title="Earlier review",
        starts_at=datetime(2026, 9, 13, 16, tzinfo=UTC),
        status="completed",
    )
    store.create(
        "meeting",
        id="mtg_today",
        project_id="prj_demo",
        title="Client review",
        starts_at=datetime(2026, 9, 14, 13, tzinfo=UTC),
    )
    store.create(
        "meeting",
        id="mtg_future",
        project_id="prj_demo",
        title="Future review",
        starts_at=datetime(2026, 9, 14, 20, tzinfo=UTC),
    )
    store.create(
        "meeting",
        id="mtg_cancelled",
        project_id="prj_demo",
        title="Cancelled review",
        starts_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        status="cancelled",
    )


def test_review_queue_keeps_catch_up_and_source_reference(session) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)
    IntegrationStateStore(session).upsert_identity(
        entity_kind="meeting",
        entity_id="mtg_today",
        source_system="microsoft-365",
        external_scope="work-calendar",
        external_id="event-123",
        web_url="https://example.test/events/event-123",
        synced_at=datetime(2026, 9, 14, 14, tzinfo=UTC),
    )

    queue = store.meeting_review_queue(
        "America/Santiago",
        review_through=date(2026, 9, 14),
        now=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )

    assert queue["meeting_count"] == 2
    assert [item["meeting"].id for item in queue["meetings"]] == [
        "mtg_old",
        "mtg_today",
    ]
    assert queue["meetings"][0]["source_reference"] is None
    assert queue["meetings"][1]["source_reference"] == {
        "source_system": "microsoft-365",
        "web_url": "https://example.test/events/event-123",
    }


def test_review_meeting_closes_and_captures_actions_atomically(session) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)
    session.info["actor"] = "jonathan"

    result = store.review_meeting(
        "mtg_today",
        decision="actions_captured",
        summary="Client approved the next implementation step.",
        actions=[
            {
                "id": "act_confirm_window",
                "title": "Confirm maintenance window",
                "owner": "Jonathan",
                "deliverable_id": "del_demo",
            }
        ],
        reviewed_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )

    meeting = result["meeting"]
    assert meeting.status == "completed"
    assert meeting.review_decision == "actions_captured"
    assert meeting.reviewed_by == "jonathan"
    assert meeting.reviewed_at.replace(tzinfo=UTC) == datetime(2026, 9, 14, 15, tzinfo=UTC)
    assert [action.id for action in result["created_actions"]] == ["act_confirm_window"]
    assert session.get(ActionItem, "act_confirm_window").status == "captured"
    changes = (
        session.query(AuditEvent)
        .filter_by(entity_kind="meeting", entity_id="mtg_today", action="update")
        .one()
        .changes
    )
    assert changes["review_decision"]["new"] == "actions_captured"


def test_review_meeting_supports_explicit_no_follow_up(session) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)

    result = store.review_meeting(
        "mtg_today",
        decision="no_follow_up",
        summary="Informational review; no action required.",
        actions=[],
        reviewed_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )

    assert result["meeting"].review_decision == "no_follow_up"
    assert result["created_actions"] == []
    queue = store.meeting_review_queue(
        "America/Santiago",
        review_through=date(2026, 9, 14),
        now=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )
    assert [item["meeting"].id for item in queue["meetings"]] == ["mtg_old"]


@pytest.mark.parametrize(
    ("meeting_id", "decision", "actions", "message"),
    [
        ("mtg_today", "actions_captured", [], "at least one action"),
        (
            "mtg_today",
            "no_follow_up",
            [{"id": "act_bad", "title": "Bad", "owner": "Jonathan"}],
            "cannot include actions",
        ),
        ("mtg_future", "no_follow_up", [], "future meeting"),
        ("mtg_cancelled", "no_follow_up", [], "cancelled meeting"),
    ],
)
def test_review_meeting_rejects_invalid_closures(
    session, meeting_id, decision, actions, message
) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)

    with pytest.raises(DomainRuleError, match=message):
        store.review_meeting(
            meeting_id,
            decision=decision,
            summary="Review",
            actions=actions,
            reviewed_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
        )

    meeting = store.get("meeting", meeting_id)
    assert meeting.reviewed_at is None
    assert session.query(ActionItem).count() == 0


def test_review_meeting_rejects_cross_project_action_without_partial_write(session) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)

    with pytest.raises(DomainRuleError, match="same project"):
        store.review_meeting(
            "mtg_today",
            decision="actions_captured",
            summary="Invalid review",
            actions=[
                {
                    "id": "act_invalid",
                    "title": "Invalid action",
                    "owner": "Jonathan",
                    "deliverable_id": "del_other",
                }
            ],
            reviewed_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
        )

    assert store.get("meeting", "mtg_today").reviewed_at is None
    assert session.get(ActionItem, "act_invalid") is None


def test_review_endpoint_is_human_confirmed_and_not_repeatable(api_client, session) -> None:
    seed_review_scenario(DomainStore(session))
    payload = {
        "decision": "actions_captured",
        "summary": "Agreed next step.",
        "actions": [
            {
                "id": "act_api",
                "title": "Send agreed schedule",
                "owner": "Jonathan",
                "deliverable_id": "del_demo",
            }
        ],
    }

    response = api_client.post(
        "/api/v1/meetings/mtg_old/review",
        headers={"X-Actor": "jonathan"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["meeting"]["reviewed_by"] == "jonathan"
    assert response.json()["created_actions"][0]["id"] == "act_api"

    repeated = api_client.post("/api/v1/meetings/mtg_old/review", json=payload)
    assert repeated.status_code == 422
    assert repeated.json()["detail"] == "Meeting review is already closed"
    assert session.query(ActionItem).filter_by(meeting_id="mtg_old").count() == 1


def test_review_queue_endpoint_uses_configured_timezone(api_client, session) -> None:
    seed_review_scenario(DomainStore(session))

    response = api_client.get("/api/v1/briefs/meeting-reviews?date=2026-09-14")

    assert response.status_code == 200
    payload = response.json()
    assert payload["timezone"] == "America/Santiago"
    assert payload["review_through"] == "2026-09-14"
    assert "mtg_old" in [item["meeting"]["id"] for item in payload["meetings"]]


def test_snapshot_round_trip_preserves_meeting_review(session) -> None:
    store = DomainStore(session)
    seed_review_scenario(store)
    store.review_meeting(
        "mtg_old",
        decision="no_follow_up",
        summary="Closed without follow-up.",
        actions=[],
        reviewed_at=datetime(2026, 9, 14, 15, tzinfo=UTC),
    )
    payload = SnapshotDocument.model_validate(export_snapshot(session))

    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as target:
        import_snapshot(target, payload)
        restored = target.get(type(store.get("meeting", "mtg_old")), "mtg_old")

    assert restored.review_decision == "no_follow_up"
    assert restored.review_summary == "Closed without follow-up."
    assert restored.reviewed_by == "local-user"
