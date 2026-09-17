from datetime import date

import pytest
from sqlalchemy.orm import Session

from faroflow.api import app
from faroflow.api.deps import capture_classifier
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


def test_suggest_capture_records_a_read_only_proposal(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")

    updated = store.suggest_capture(
        capture.id, classifier=FictionalClassifier(suggestion())
    )

    assert updated.status == "inbox"
    assert updated.disposition is None
    assert updated.project_id is None
    assert updated.task_id is None
    assert updated.triaged_at is None
    assert updated.proposal_kind == "task"
    assert updated.proposal_project_id == "prj_demo"
    assert updated.proposal_confidence == 0.82
    assert updated.proposal_priority == "high"
    assert updated.proposal_due_at == date(2026, 9, 18)
    assert updated.proposal_source == "fictional-classifier"
    assert updated.proposal_reasons == ["demo plan"]
    assert updated.proposed_at is not None
    assert updated.applied_at is None


def test_manual_triage_still_works_after_a_proposal(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")
    store.suggest_capture(capture.id, classifier=FictionalClassifier(suggestion()))

    triaged = store.triage_capture(
        capture.id, "task", project_id="prj_demo", task_id="tsk_demo"
    )

    assert triaged.status == "triaged"
    assert triaged.task_id == "tsk_demo"
    assert triaged.disposition == "task"


def test_proposal_carries_project_and_client_candidates(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")
    recorded: list = []

    store.suggest_capture(
        capture.id,
        classifier=FictionalClassifier(suggestion(), recorder=recorded),
    )

    _text, candidates = recorded[0]
    assert [(item.id, item.name, item.client) for item in candidates] == [
        ("prj_demo", "Demo Project", "Demo Client")
    ]


def test_resuggesting_replaces_the_pending_proposal(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Architecture note for the demo plan")
    store.suggest_capture(capture.id, classifier=FictionalClassifier(suggestion()))

    replaced = store.suggest_capture(
        capture.id,
        classifier=FictionalClassifier(
            suggestion(
                kind="reference",
                confidence=0.3,
                project_id=None,
                priority="low",
                due_at=None,
                reasons=("Architecture note",),
            )
        ),
    )

    assert replaced.proposal_kind == "reference"
    assert replaced.proposal_project_id is None
    assert replaced.proposal_priority == "low"
    assert replaced.proposal_reasons == ["Architecture note"]


def test_only_inbox_captures_receive_proposals(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")
    store.triage_capture(capture.id, "reference", project_id="prj_demo")

    with pytest.raises(DomainRuleError, match="Only inbox captures"):
        store.suggest_capture(capture.id, classifier=FictionalClassifier(suggestion()))


def test_proposal_survives_a_snapshot_round_trip(session) -> None:
    store = DomainStore(session)
    build_hierarchy(store)
    capture = store.capture("Prepare the demo plan")
    store.suggest_capture(capture.id, classifier=FictionalClassifier(suggestion()))

    document = SnapshotDocument.model_validate(export_snapshot(session))

    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as target:
        import_snapshot(target, document)
        restored = export_snapshot(target)

    restored_capture = restored["entities"]["captures"][0]
    assert restored_capture.proposal_kind == "task"
    assert restored_capture.proposal_project_id == "prj_demo"
    assert restored_capture.proposal_reasons == ["demo plan"]
    assert restored_capture.proposal_source == "fictional-classifier"


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


def test_suggest_reports_not_configured_without_a_provider(api_client) -> None:
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]

    response = api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    assert response.status_code == 503
    assert response.json()["detail"] == "Capture classification is not configured"


def test_suggest_returns_proposal_and_keeps_capture_in_inbox(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(suggestion())

    response = api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "inbox"
    assert payload["disposition"] is None
    assert payload["proposal_kind"] == "task"
    assert payload["proposal_project_id"] == "prj_demo"
    assert payload["proposal_confidence"] == 0.82
    assert payload["proposal_priority"] == "high"
    assert payload["proposal_due_at"] == "2026-09-18"
    assert payload["proposal_reasons"] == ["demo plan"]
    assert payload["proposed_at"] is not None
    assert payload["applied_at"] is None

    persisted = api_client.get(f"/api/v1/captures/{capture_id}").json()
    assert persisted["proposal_kind"] == "task"
    assert persisted["proposal_reasons"] == ["demo plan"]

    triage = api_client.post(
        f"/api/v1/captures/{capture_id}/triage",
        json={"disposition": "task", "project_id": "prj_demo", "task_id": "tsk_demo"},
    )
    assert triage.status_code == 200
    assert triage.json()["task_id"] == "tsk_demo"


def test_suggest_returns_404_for_unknown_capture(api_client) -> None:
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(suggestion())

    response = api_client.post("/api/v1/captures/cap_missing/suggest")

    assert response.status_code == 404


def test_suggest_rejects_invalid_provider_output(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    app.dependency_overrides[capture_classifier] = lambda: FictionalClassifier(
        suggestion(project_id="prj_invented")
    )

    response = api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    assert response.status_code == 422
    assert "supplied candidates" in response.json()["detail"]
