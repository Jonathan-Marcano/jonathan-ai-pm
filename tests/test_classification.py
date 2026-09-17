import math
from datetime import date

import pytest

from faroflow.classification import (
    CaptureCandidate,
    CaptureDispositionSuggestion,
    ClassifierConfig,
    ClassifierError,
    ClassifierNotConfigured,
    build_capture_classifier,
    suggest_capture_disposition,
)


class FakeClassifier:
    source_system = "fictional-classifier"

    def __init__(self, suggestion):
        self.suggestion = suggestion
        self.calls = []

    def suggest(self, text, candidates):
        self.calls.append((text, list(candidates)))
        return self.suggestion


def candidate(candidate_id="prj_demo", name="Demo project", client="Demo client"):
    return CaptureCandidate(id=candidate_id, name=name, client=client)


def test_default_config_is_bounded() -> None:
    config = ClassifierConfig()

    assert config.max_text_chars == 2000
    assert config.max_candidates == 60
    assert config.max_reasons == 5
    assert config.timeout_seconds > 0


def test_config_rejects_unsafe_limits() -> None:
    with pytest.raises(ClassifierError, match="max_text_chars"):
        ClassifierConfig(max_text_chars=10)
    with pytest.raises(ClassifierError, match="max_candidates"):
        ClassifierConfig(max_candidates=0)
    with pytest.raises(ClassifierError, match="max_reasons"):
        ClassifierConfig(max_reasons=0)
    with pytest.raises(ClassifierError, match="max_reason_chars"):
        ClassifierConfig(max_reason_chars=5)
    with pytest.raises(ClassifierError, match="timeout_seconds"):
        ClassifierConfig(timeout_seconds=0)


def test_candidate_requires_identity_and_project_kind() -> None:
    with pytest.raises(ClassifierError, match="id cannot be empty"):
        CaptureCandidate(id="  ", name="Demo")
    with pytest.raises(ClassifierError, match="name cannot be empty"):
        CaptureCandidate(id="prj_demo", name="  ")
    with pytest.raises(ClassifierError, match="unsupported candidate kind"):
        CaptureCandidate(id="prj_demo", name="Demo", kind="client")


def test_suggestion_dataclass_validates_its_shape() -> None:
    with pytest.raises(ClassifierError, match="kind"):
        CaptureDispositionSuggestion(kind="sprint", confidence=0.5)
    with pytest.raises(ClassifierError, match="priority"):
        CaptureDispositionSuggestion(kind="task", confidence=0.5, priority="whenever")
    with pytest.raises(ClassifierError, match="confidence"):
        CaptureDispositionSuggestion(kind="task", confidence=1.5)
    with pytest.raises(ClassifierError, match="confidence"):
        CaptureDispositionSuggestion(kind="task", confidence=math.nan)
    with pytest.raises(ClassifierError, match="confidence"):
        CaptureDispositionSuggestion(kind="task", confidence=True)
    with pytest.raises(ClassifierError, match="reasons"):
        CaptureDispositionSuggestion(kind="task", confidence=0.5, reasons=("   ",))


def test_suggestion_normalizes_text_fields() -> None:
    suggestion = CaptureDispositionSuggestion(
        kind="action",
        confidence=0.9,
        project_id="  prj_demo  ",
        owner="  Demo Engineer  ",
        reasons=(" Confirm dependencies ",),
        source="  ",
    )

    assert suggestion.project_id == "prj_demo"
    assert suggestion.owner == "Demo Engineer"
    assert suggestion.reasons == ("Confirm dependencies",)
    assert suggestion.source == "classifier"


def test_unconfigured_provider_raises_not_configured() -> None:
    with pytest.raises(ClassifierNotConfigured, match="not configured"):
        build_capture_classifier()


def test_service_bounds_text_and_candidates_before_calling_provider() -> None:
    long_text = "Prepare the demo plan " + "x" * 5000
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="task",
            confidence=0.7,
            project_id="prj_demo",
            reasons=("Prepare",),
        )
    )
    config = ClassifierConfig(max_text_chars=120, max_candidates=1)

    suggest_capture_disposition(
        long_text,
        [candidate(), candidate("prj_other", "Other")],
        classifier=classifier,
        config=config,
    )

    supplied_text, supplied_candidates = classifier.calls[0]
    assert len(supplied_text) == 120
    assert [item.id for item in supplied_candidates] == ["prj_demo"]


def test_service_bounds_reasons_and_keeps_only_quotes() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="task",
            confidence=0.5,
            reasons=tuple(["Prepare"] * 9),
        )
    )

    suggestion = suggest_capture_disposition(
        "Prepare the demo plan",
        [candidate()],
        classifier=classifier,
        config=ClassifierConfig(max_reasons=3, max_reason_chars=20),
    )

    assert suggestion.reasons == ("Prepare", "Prepare", "Prepare")


def test_service_rejects_reason_that_does_not_quote_the_text() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="task",
            confidence=0.5,
            reasons=("A sentence the user never wrote",),
        )
    )

    with pytest.raises(ClassifierError, match="quote the captured text"):
        suggest_capture_disposition(
            "Prepare the demo plan", [candidate()], classifier=classifier
        )


def test_service_rejects_project_outside_candidates() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="task",
            confidence=0.5,
            project_id="prj_invented",
        )
    )

    with pytest.raises(ClassifierError, match="supplied candidates"):
        suggest_capture_disposition(
            "Prepare the demo plan", [candidate()], classifier=classifier
        )


def test_service_accepts_a_suggestion_without_a_candidate() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="reference",
            confidence=0.2,
            project_id=None,
            priority="low",
            due_at=None,
            reasons=("Architecture note",),
            source="fictional-classifier",
        )
    )

    suggestion = suggest_capture_disposition(
        "Architecture note for the migration",
        [],
        classifier=classifier,
    )

    assert suggestion.kind == "reference"
    assert suggestion.project_id is None
    assert suggestion.source == "fictional-classifier"
    assert suggestion.reasons == ("Architecture note",)


def test_service_rejects_empty_text() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(kind="task", confidence=0.5)
    )

    with pytest.raises(ClassifierError, match="empty"):
        suggest_capture_disposition("   ", [candidate()], classifier=classifier)


def test_service_normalizes_due_date_and_priority() -> None:
    classifier = FakeClassifier(
        CaptureDispositionSuggestion(
            kind="task",
            confidence=0.88,
            project_id="prj_demo",
            priority="high",
            due_at=date(2026, 9, 18),
            reasons=("demo plan",),
        )
    )

    suggestion = suggest_capture_disposition(
        "Prepare the demo plan", [candidate()], classifier=classifier
    )

    assert suggestion.due_at == date(2026, 9, 18)
    assert suggestion.priority == "high"
    assert suggestion.confidence == 0.88
