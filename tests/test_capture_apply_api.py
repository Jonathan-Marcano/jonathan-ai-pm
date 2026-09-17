from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from faroflow.api import app
from faroflow.api.deps import capture_classifier
from faroflow.audit import list_audit_events
from faroflow.classification import CaptureDispositionSuggestion
from faroflow.db import build_engine
from faroflow.models import Base
from faroflow.portability import export_snapshot, import_snapshot
from faroflow.schemas import SnapshotDocument
from faroflow.services import DomainRuleError, DomainStore


class FictionalClassifier:
    source_system = "fictional-classifier"

    def __init__(self, suggestion, recorder=None):
        self.suggestion = suggestion
        self.recorder = recorder

    def suggest(self, text, candidates):
        if self.recorder is not None:
            self.recorder.append((text, list(candidates)))
        return self.suggestion


def build_hierarchy(store: DomainStore) -> None:
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo Client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo Project")


def build_meeting(store: DomainStore) -> None:
    store.create(
        "meeting",
        id="mtg_demo",
        project_id="prj_demo",
        title="Review",
        starts_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
    )


def suggestion(**overrides) -> CaptureDispositionSuggestion:
    values = {
        "kind": "task",
        "confidence": 0.82,
        "project_id": "prj_demo",
        "priority": "high",
        "due_at": date(2026, 9, 18),
        "reasons": ("demo plan",),
        "source": "fictional-classifier",
    }
    values.update(overrides)
    return CaptureDispositionSuggestion(**values)


def proposed_capture(
    store: DomainStore, text: str = "Prepare the demo plan", **proposal
) -> object:
    build_hierarchy(store)
    capture = store.capture(text)
    store.suggest_capture(capture.id, classifier=FictionalClassifier(suggestion(**proposal)))
    return capture


def test_apply_creates_ready_task_exactly_from_the_proposal(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)

    applied = store.apply_capture(capture.id)

    assert applied.status == "triaged"
    assert applied.disposition == "task"
    assert applied.task_id.startswith("tsk_")
    assert applied.project_id == "prj_demo"
    assert applied.applied_at is not None
    assert applied.triaged_at == applied.applied_at
    task = store.get("task", applied.task_id)
    assert task.title == capture.text
    assert task.project_id == "prj_demo"
    assert task.status == "ready"
    assert task.priority == "high"
    assert task.due_at == date(2026, 9, 18)


def test_apply_is_idempotent_and_creates_no_second_record(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)

    first = store.apply_capture(capture.id)
    again = store.apply_capture(capture.id, meeting_id="mtg_demo")

    assert again.id == capture.id
    assert again.task_id == first.task_id
    assert again.applied_at == first.applied_at
    assert len(store.list("task", project_id="prj_demo")) == 1


def test_apply_requires_a_pending_proposal(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")

    with pytest.raises(DomainRuleError, match="no pending proposal"):
        store.apply_capture(capture.id)


def test_apply_requires_an_inbox_capture(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")
    store.triage_capture(capture.id, "reference", project_id="prj_demo")

    with pytest.raises(DomainRuleError, match="Only inbox captures"):
        store.apply_capture(capture.id)


def test_apply_task_proposal_requires_project(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store, project_id=None)

    with pytest.raises(DomainRuleError, match="requires a project"):
        store.apply_capture(capture.id)


def test_apply_rejects_meeting_id_on_task_proposal(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)
    build_meeting(store)

    with pytest.raises(DomainRuleError, match="meeting_id applies only to action"):
        store.apply_capture(capture.id, meeting_id="mtg_demo")


def test_apply_reference_links_project_and_keeps_trail(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(
        store,
        text="Architecture note",
        kind="reference",
        confidence=0.3,
        priority="low",
        due_at=None,
        reasons=("Architecture note",),
    )

    applied = store.apply_capture(capture.id)

    assert applied.status == "triaged"
    assert applied.disposition == "reference"
    assert applied.project_id == "prj_demo"
    assert applied.task_id is None
    assert applied.action_item_id is None
    assert applied.applied_at is not None
    assert applied.proposal_kind == "reference"
    assert applied.proposal_project_id == "prj_demo"
    assert applied.text == "Architecture note"


def test_apply_action_proposal_requires_a_meeting(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(
        store,
        text="Confirm dependencies",
        kind="action",
        owner="Demo Engineer",
        reasons=("Confirm dependencies",),
    )

    with pytest.raises(DomainRuleError, match="requires a meeting"):
        store.apply_capture(capture.id)


def test_apply_action_proposal_creates_action_item(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    build_meeting(store)
    capture = store.capture("Confirm dependencies")
    store.suggest_capture(
        capture.id,
        classifier=FictionalClassifier(
            suggestion(kind="action", owner="Demo Engineer", reasons=("Confirm dependencies",))
        ),
    )

    applied = store.apply_capture(capture.id, meeting_id="mtg_demo")

    assert applied.status == "triaged"
    assert applied.disposition == "action"
    assert applied.action_item_id.startswith("act_")
    assert applied.project_id == "prj_demo"
    action = store.get("action_item", applied.action_item_id)
    assert action.title == capture.text
    assert action.meeting_id == "mtg_demo"
    assert action.owner == "Demo Engineer"
    assert action.status == "captured"


def test_apply_action_requires_owner_still_unset(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    build_meeting(store)
    capture = store.capture("Confirm dependencies")
    store.suggest_capture(
        capture.id,
        classifier=FictionalClassifier(
            suggestion(kind="action", owner=None, reasons=("Confirm dependencies",))
        ),
    )

    with pytest.raises(DomainRuleError, match="requires an owner"):
        store.apply_capture(capture.id, meeting_id="mtg_demo")


def test_apply_requires_matching_meeting_project(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    store.create("project", id="prj_other", client_id="cli_demo", name="Other Project")
    store.create(
        "meeting",
        id="mtg_wrong",
        project_id="prj_other",
        title="Other",
        starts_at=datetime(2026, 9, 15, 13, 0, tzinfo=UTC),
    )
    capture = store.capture("Confirm dependencies")
    store.suggest_capture(
        capture.id,
        classifier=FictionalClassifier(
            suggestion(kind="action", owner="Demo Engineer", reasons=("Confirm dependencies",))
        ),
    )

    with pytest.raises(DomainRuleError, match="must match the meeting project"):
        store.apply_capture(capture.id, meeting_id="mtg_wrong")


def test_apply_keeps_the_immutable_proposal_and_original_text(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)

    applied = store.apply_capture(capture.id)

    assert applied.text == "Prepare the demo plan"
    assert applied.proposal_kind == "task"
    assert applied.proposal_project_id == "prj_demo"
    assert applied.proposal_priority == "high"
    assert applied.proposal_due_at == date(2026, 9, 18)
    assert applied.proposal_confidence == 0.82
    assert applied.proposal_reasons == ["demo plan"]
    assert applied.proposal_source == "fictional-classifier"
    assert applied.proposed_at is not None


def test_apply_decision_trail_links_capture_record_and_source_wording(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)

    applied = store.apply_capture(capture.id)
    task = store.get("task", applied.task_id)

    capture_events = list_audit_events(session, entity_kind="capture", entity_id=capture.id)
    task_events = list_audit_events(session, entity_kind="task", entity_id=task.id)

    assert [event.action for event in capture_events] == ["create", "update", "update"]
    suggest_changes = capture_events[1].changes
    assert suggest_changes["proposal_kind"] == {"old": None, "new": "task"}
    apply_changes = capture_events[2].changes
    assert apply_changes["status"] == {"old": "inbox", "new": "triaged"}
    assert apply_changes["disposition"] == {"old": None, "new": "task"}
    assert apply_changes["project_id"] == {"old": None, "new": "prj_demo"}
    assert apply_changes["task_id"] == {"old": None, "new": task.id}
    assert apply_changes["applied_at"]["new"] is not None

    assert [event.action for event in task_events] == ["create"]
    assert task_events[0].changes["title"] == {"old": None, "new": "Prepare the demo plan"}
    assert task.title == "Prepare the demo plan"
    assert task_events[0].entity_id == applied.task_id
    assert applied.task_id == task.id


def test_applied_capture_survives_a_snapshot_round_trip(session) -> None:
    store = DomainStore(session)
    capture = proposed_capture(store)
    applied = store.apply_capture(capture.id)

    document = SnapshotDocument.model_validate(export_snapshot(session))

    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as target:
        import_snapshot(target, document)
        restored = export_snapshot(target)

    restored_capture = restored["entities"]["captures"][0]
    assert restored_capture.id == applied.id
    assert restored_capture.status == "triaged"
    assert restored_capture.disposition == "task"
    assert restored_capture.task_id == applied.task_id
    assert restored_capture.applied_at is not None
    assert restored_capture.proposal_kind == "task"
    assert restored_capture.proposal_reasons == ["demo plan"]
    restored_task = next(
        task for task in restored["entities"]["tasks"] if task.id == applied.task_id
    )
    assert restored_task.title == "Prepare the demo plan"


def create_core_hierarchy(api_client) -> None:
    api_client.post(
        "/api/v1/workspaces",
        json={"id": "wrk_demo", "name": "Demo", "timezone": "America/Santiago"},
    )
    api_client.post(
        "/api/v1/clients",
        json={"id": "cli_demo", "workspace_id": "wrk_demo", "name": "Demo Client"},
    )
    api_client.post(
        "/api/v1/projects",
        json={"id": "prj_demo", "client_id": "cli_demo", "name": "Demo Project"},
    )
    api_client.post(
        "/api/v1/meetings",
        json={
            "id": "mtg_demo",
            "project_id": "prj_demo",
            "title": "Review",
            "starts_at": "2026-09-15T13:00:00Z",
        },
    )


def propose(api_client, capture_id: str) -> None:
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(suggestion())
    assert api_client.post(f"/api/v1/captures/{capture_id}/suggest").status_code == 200


def test_apply_returns_triaged_capture_and_creates_task(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    propose(api_client, capture_id)

    applied = api_client.post(f"/api/v1/captures/{capture_id}/apply")

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["status"] == "triaged"
    assert payload["disposition"] == "task"
    assert payload["project_id"] == "prj_demo"
    assert payload["task_id"].startswith("tsk_")
    assert payload["applied_at"] is not None
    assert payload["proposal_kind"] == "task"
    assert payload["proposal_reasons"] == ["demo plan"]
    task = api_client.get(f"/api/v1/tasks/{payload['task_id']}").json()
    assert task["title"] == "Prepare the demo plan"
    assert task["status"] == "ready"


def test_apply_is_idempotent_via_api(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    propose(api_client, capture_id)

    first = api_client.post(f"/api/v1/captures/{capture_id}/apply").json()
    again = api_client.post(
        f"/api/v1/captures/{capture_id}/apply", json={"meeting_id": "mtg_demo"}
    ).json()

    assert again["task_id"] == first["task_id"]
    assert again["applied_at"] == first["applied_at"]
    tasks = api_client.get("/api/v1/tasks").json()
    assert len(tasks) == 1


def test_apply_returns_404_for_unknown_capture(api_client) -> None:
    response = api_client.post("/api/v1/captures/cap_missing/apply")

    assert response.status_code == 404


def test_apply_without_proposal_returns_422(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]

    response = api_client.post(f"/api/v1/captures/{capture_id}/apply")

    assert response.status_code == 422
    assert "no pending proposal" in response.json()["detail"]


def test_apply_already_triaged_returns_422(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    api_client.post(
        f"/api/v1/captures/{capture_id}/triage",
        json={"disposition": "reference", "project_id": "prj_demo"},
    )

    response = api_client.post(f"/api/v1/captures/{capture_id}/apply")

    assert response.status_code == 422
    assert "Only inbox captures" in response.json()["detail"]


def test_apply_action_requires_meeting_via_api(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Confirm dependencies"}
    ).json()["id"]
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(
        suggestion(kind="action", owner="Demo Engineer", reasons=("Confirm dependencies",))
    )
    api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    response = api_client.post(f"/api/v1/captures/{capture_id}/apply")

    assert response.status_code == 422
    assert "requires a meeting" in response.json()["detail"]


def test_apply_action_creates_action_item_via_api(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Confirm dependencies"}
    ).json()["id"]
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(
        suggestion(kind="action", owner="Demo Engineer", reasons=("Confirm dependencies",))
    )
    api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    applied = api_client.post(
        f"/api/v1/captures/{capture_id}/apply", json={"meeting_id": "mtg_demo"}
    )

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["disposition"] == "action"
    assert payload["action_item_id"].startswith("act_")
    assert payload["project_id"] == "prj_demo"
    action = api_client.get(f"/api/v1/action-items/{payload['action_item_id']}").json()
    assert action["title"] == "Confirm dependencies"
    assert action["owner"] == "Demo Engineer"