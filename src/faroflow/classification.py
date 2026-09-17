"""Provider-neutral capture classification (Phase 3, P3-02).

A classifier turns free-text captures into a bounded, validated *suggestion* (kind,
candidate project, priority, due date) with confidence and reasons quoted from the
captured text. Suggestions are read-only: applying one is a separate, explicit human
confirmation. No provider credential lives in the repository, and an unconfigured
provider raises ``ClassifierNotConfigured`` so the HTTP layer can answer 503.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

ProposalKind = Literal["task", "action", "reference"]

PROPOSAL_KINDS: tuple[str, ...] = ("task", "action", "reference")
PROPOSAL_PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
MAX_OWNER_CHARS = 120


class ClassifierError(ValueError):
    """A classifier request or a returned suggestion violates the contract."""


class ClassifierNotConfigured(ClassifierError):
    """No classifier provider is authorized; the HTTP layer reports this as 503."""


@dataclass(frozen=True, slots=True)
class ClassifierConfig:
    """Bounds that cap cost and data exposure before a provider is ever called."""

    source_system: str = "classifier"
    max_text_chars: int = 2000
    max_candidates: int = 60
    max_reasons: int = 5
    max_reason_chars: int = 200
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        source_system = self.source_system.strip()
        if not source_system:
            raise ClassifierError("source_system cannot be empty")
        if isinstance(self.max_text_chars, bool) or self.max_text_chars < 100:
            raise ClassifierError("max_text_chars must be at least 100")
        if isinstance(self.max_candidates, bool) or self.max_candidates < 1:
            raise ClassifierError("max_candidates must be positive")
        if isinstance(self.max_reasons, bool) or self.max_reasons < 1:
            raise ClassifierError("max_reasons must be positive")
        if isinstance(self.max_reason_chars, bool) or self.max_reason_chars < 20:
            raise ClassifierError("max_reason_chars must be at least 20")
        if self.timeout_seconds <= 0:
            raise ClassifierError("timeout_seconds must be positive")
        object.__setattr__(self, "source_system", source_system)


@dataclass(frozen=True, slots=True)
class CaptureCandidate:
    """A project the classifier may suggest, without any confidential content."""

    id: str
    name: str
    client: str | None = None
    kind: str = "project"

    def __post_init__(self) -> None:
        candidate_id = self.id.strip() if isinstance(self.id, str) else ""
        name = self.name.strip() if isinstance(self.name, str) else ""
        client = (
            self.client.strip()
            if isinstance(self.client, str) and self.client.strip()
            else None
        )
        kind = self.kind.strip().lower() if isinstance(self.kind, str) else ""
        if not candidate_id:
            raise ClassifierError("candidate id cannot be empty")
        if not name:
            raise ClassifierError("candidate name cannot be empty")
        if kind != "project":
            raise ClassifierError(f"unsupported candidate kind: {kind or 'unknown'}")
        object.__setattr__(self, "id", candidate_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "client", client)
        object.__setattr__(self, "kind", kind)


@dataclass(frozen=True, slots=True)
class CaptureDispositionSuggestion:
    """A read-only classification proposal. It never binds a capture on its own."""

    kind: ProposalKind
    confidence: float
    project_id: str | None = None
    owner: str | None = None
    priority: str = "medium"
    due_at: date | None = None
    reasons: tuple[str, ...] = ()
    source: str = "classifier"

    def __post_init__(self) -> None:
        if self.kind not in PROPOSAL_KINDS:
            raise ClassifierError(f"Unknown proposal kind: {self.kind}")
        if self.priority not in PROPOSAL_PRIORITIES:
            raise ClassifierError(f"Unknown proposal priority: {self.priority}")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ClassifierError("proposal confidence must be between 0 and 1")

        reasons = tuple(
            reason.strip() for reason in self.reasons if isinstance(reason, str)
        )
        if len(reasons) != len(self.reasons) or any(not reason for reason in reasons):
            raise ClassifierError("proposal reasons must be non-empty text")

        project_id = (
            self.project_id.strip()
            if isinstance(self.project_id, str) and self.project_id.strip()
            else None
        )
        owner = (
            self.owner.strip()
            if isinstance(self.owner, str) and self.owner.strip()
            else None
        )
        if owner is not None and len(owner) > MAX_OWNER_CHARS:
            raise ClassifierError("proposal owner exceeds the configured length")
        source = (
            self.source.strip()
            if isinstance(self.source, str) and self.source.strip()
            else "classifier"
        )

        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "source", source)


class ClassifierAdapter(Protocol):
    source_system: str

    def suggest(
        self, text: str, candidates: Sequence[CaptureCandidate]
    ) -> CaptureDispositionSuggestion: ...


def suggest_capture_disposition(
    text: str,
    candidates: Sequence[CaptureCandidate],
    *,
    classifier: ClassifierAdapter,
    config: ClassifierConfig | None = None,
) -> CaptureDispositionSuggestion:
    """Bound the input, ask the provider, and re-validate the returned suggestion.

    The bounded text and candidate list cap token cost and data exposure. The returned
    suggestion is rebuilt from validated primitives so an untrusted provider cannot
    smuggle oversized, out-of-candidate, or fabricated fields into the datastore.
    """
    resolved_config = config or ClassifierConfig()
    normalized_text = text.strip() if isinstance(text, str) else ""
    if not normalized_text:
        raise ClassifierError("capture text cannot be empty for classification")
    bounded_text = normalized_text[: resolved_config.max_text_chars]
    bounded_candidates = list(candidates)[: resolved_config.max_candidates]

    suggestion = classifier.suggest(bounded_text, bounded_candidates)
    if not isinstance(suggestion, CaptureDispositionSuggestion):
        raise ClassifierError("classifier did not return a capture suggestion")
    return _normalize_suggestion(
        suggestion,
        supplied_text=bounded_text,
        candidates=bounded_candidates,
        config=resolved_config,
    )


def _normalize_suggestion(
    suggestion: CaptureDispositionSuggestion,
    *,
    supplied_text: str,
    candidates: list[CaptureCandidate],
    config: ClassifierConfig,
) -> CaptureDispositionSuggestion:
    candidate_ids = {candidate.id for candidate in candidates}
    if suggestion.project_id is not None and suggestion.project_id not in candidate_ids:
        raise ClassifierError("proposal project is not among the supplied candidates")

    reasons: list[str] = []
    for fragment in suggestion.reasons[: config.max_reasons]:
        normalized = fragment.strip()
        if not normalized or normalized not in supplied_text:
            raise ClassifierError("proposal reason must quote the captured text")
        reasons.append(normalized[: config.max_reason_chars])

    return CaptureDispositionSuggestion(
        kind=suggestion.kind,
        confidence=float(suggestion.confidence),
        project_id=suggestion.project_id,
        owner=suggestion.owner,
        priority=suggestion.priority,
        due_at=suggestion.due_at,
        reasons=tuple(reasons),
        source=suggestion.source,
    )


def build_capture_classifier() -> ClassifierAdapter:
    """Build the runtime classifier once a provider is authorized.

    No provider account is configured yet, so this helper intentionally raises
    ``ClassifierNotConfigured``. The endpoint exposes that state as HTTP 503.
    """
    raise ClassifierNotConfigured("Capture classification is not configured")
