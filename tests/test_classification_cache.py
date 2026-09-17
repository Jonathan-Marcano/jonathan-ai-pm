from datetime import date

import pytest

from faroflow.api import app
from faroflow.api.deps import capture_classifier
from faroflow.classification import (
    CachingClassifier,
    CaptureCandidate,
    CaptureDispositionSuggestion,
    CaptureSuggestionCache,
    ClassifierConfig,
    ClassifierError,
    prompt_brief,
    suggest_capture_disposition,
)


class FictionalClassifier:
    source_system = "fictional-classifier"

    def __init__(self, suggestion, recorder=None, source_system=None):
        self.suggestion = suggestion
        self.recorder = recorder if recorder is not None else []
        if source_system is not None:
            self.source_system = source_system

    def suggest(self, text, candidates):
        self.recorder.append((text, [item.id for item in candidates]))
        return self.suggestion


def candidate(candidate_id="prj_demo", name="Demo project", client="Demo client"):
    return CaptureCandidate(id=candidate_id, name=name, client=client)


def task_suggestion(project_id="prj_demo", confidence=0.82):
    return CaptureDispositionSuggestion(
        kind="task",
        confidence=confidence,
        project_id=project_id,
        priority="high",
        due_at=date(2026, 9, 18),
        reasons=("demo plan",),
        source="fictional-classifier",
    )


def test_cache_replays_same_text_without_recalling_the_provider() -> None:
    recorder: list = []
    inner = FictionalClassifier(task_suggestion(), recorder=recorder)
    cached = CachingClassifier(inner)

    first = suggest_capture_disposition("Prepare the demo plan", [candidate()], classifier=cached)
    second = suggest_capture_disposition("Prepare the demo plan", [candidate()], classifier=cached)

    assert first == second
    assert len(recorder) == 1
    assert cached.cache.hits == 1
    assert cached.cache.misses == 1


def test_cache_misses_when_the_text_changes() -> None:
    recorder: list = []
    cached = CachingClassifier(FictionalClassifier(task_suggestion(), recorder=recorder))

    suggest_capture_disposition("Prepare the first demo plan", [candidate()], classifier=cached)
    suggest_capture_disposition("Prepare the second demo plan", [candidate()], classifier=cached)

    assert len(recorder) == 2
    assert cached.cache.size == 2


def test_cache_misses_when_the_candidate_set_changes() -> None:
    recorder: list = []
    inner = FictionalClassifier(task_suggestion(), recorder=recorder)
    cached = CachingClassifier(inner)

    suggest_capture_disposition(
        "Prepare the demo plan",
        [candidate(), candidate("prj_other", "Other project")],
        classifier=cached,
    )
    suggest_capture_disposition(
        "Prepare the demo plan",
        [candidate(), candidate("prj_new", "New project")],
        classifier=cached,
    )

    assert len(recorder) == 2
    assert cached.cache.size == 2


def test_cache_revalidates_against_the_current_candidate_set() -> None:
    recorder: list = []
    cached = CachingClassifier(
        FictionalClassifier(
            task_suggestion(project_id="prj_demo"),
            recorder=recorder,
        )
    )

    suggest_capture_disposition("Prepare the demo plan", [candidate()], classifier=cached)
    assert [item[1] for item in recorder] == [["prj_demo"]]

    with pytest.raises(ClassifierError, match="supplied candidates"):
        suggest_capture_disposition(
            "Prepare the demo plan",
            [candidate("prj_other", "Other project")],
            classifier=cached,
        )


def test_cache_evicts_the_oldest_entry_when_full() -> None:
    cache = CaptureSuggestionCache(max_entries=2)
    cached = CachingClassifier(
        FictionalClassifier(task_suggestion()),
        cache=cache,
    )

    suggest_capture_disposition("Prepare the first demo plan", [candidate()], classifier=cached)
    suggest_capture_disposition("Prepare the second demo plan", [candidate()], classifier=cached)
    suggest_capture_disposition("Prepare the third demo plan", [candidate()], classifier=cached)

    assert cache.size == 2
    assert cache.lookup("any-key") is None
    assert cache.misses == 4
    assert cache.hits == 0


def test_cache_limits_are_validated() -> None:
    with pytest.raises(ClassifierError, match="max_entries"):
        CaptureSuggestionCache(max_entries=0)


def test_wrapper_rejects_double_caching() -> None:
    cached = CachingClassifier(FictionalClassifier(task_suggestion()))

    with pytest.raises(ClassifierError, match="already wrapped"):
        CachingClassifier(cached)


def test_wrapper_requires_a_source_system() -> None:
    class AnonymousClassifier:
        def suggest(self, text, candidates):
            return task_suggestion()

    with pytest.raises(ClassifierError, match="source_system"):
        CachingClassifier(AnonymousClassifier())


def test_prompt_brief_never_contains_the_capture_text() -> None:
    confidential = "Send the quarterly P&L to the board before the 9am meeting"

    brief = prompt_brief(confidential, [candidate()])

    rendered = str(brief)
    assert confidential not in rendered
    assert "P&L" not in rendered
    assert len(brief.text_digest) == 64
    assert brief.text_chars == len(confidential)
    assert brief.max_text_chars == 2000
    assert brief.candidate_ids == ("prj_demo",)
    assert brief.source_system == "classifier"


def test_prompt_brief_bounds_long_text_for_logging() -> None:
    brief = prompt_brief(
        "Secret payload " + "x" * 5000,
        [candidate()],
        config=ClassifierConfig(max_text_chars=120),
    )

    assert brief.text_chars == 120
    assert len(brief.text_digest) == 64


def test_prompt_brief_validates_shape() -> None:
    with pytest.raises(ClassifierError, match="cache_state"):
        prompt_brief("Some text", [candidate()], cache_state="stale")


def test_caching_classifier_reports_hit_and_miss_through_the_brief() -> None:
    recorder: list = []
    cached = CachingClassifier(FictionalClassifier(task_suggestion(), recorder=recorder))

    suggest_capture_disposition("Prepare the demo plan", [candidate()], classifier=cached)
    hits_after_miss = cached.cache.hits
    suggest_capture_disposition("Prepare the demo plan", [candidate()], classifier=cached)

    assert hits_after_miss == 0
    assert cached.cache.hits == 1
    assert cached.cache.size == 1


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


def test_api_suggest_is_cached_and_never_recalls_the_provider(api_client) -> None:
    create_core_hierarchy(api_client)
    capture_id = api_client.post(
        "/api/v1/captures", json={"text": "Prepare the demo plan"}
    ).json()["id"]
    recorder: list = []
    cached = CachingClassifier(
        FictionalClassifier(task_suggestion(), recorder=recorder)
    )
    app.dependency_overrides[capture_classifier] = lambda: cached

    first = api_client.post(f"/api/v1/captures/{capture_id}/suggest")
    second = api_client.post(f"/api/v1/captures/{capture_id}/suggest")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["proposal_kind"] == "task"
    assert second.json()["proposal_reasons"] == ["demo plan"]
    assert len(recorder) == 1