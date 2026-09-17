"""Provider-neutral capture classification (Phase 3, P3-02 and P3-05).

A classifier turns free-text captures into a bounded, validated *suggestion* (kind,
candidate project, priority, due date) with confidence and reasons quoted from the
captured text. Suggestions are read-only: applying one is a separate, explicit human
confirmation. No provider credential lives in the repository, and an unconfigured
provider raises ``ClassifierNotConfigured`` so the HTTP layer can answer 503.

Cost and data exposure are kept bounded (P3-05): the request bounds cap token cost
per call, ``CachingClassifier`` replays repeated suggestions for the same text without
re-charging the model, ``prompt_brief`` renders a redacted summary that never contains
the captured text, and no test or default path ever calls a live model.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Literal, Protocol

logger = logging.getLogger("faroflow.classification")

ProposalKind = Literal["task", "action", "reference"]

PROPOSAL_KINDS: tuple[str, ...] = ("task", "action", "reference")
PROPOSAL_PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
MAX_OWNER_CHARS = 120
DEFAULT_CACHE_ENTRIES = 100


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


def _text_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _cache_key(
    source_system: str,
    text: str,
    candidates: Sequence[CaptureCandidate],
) -> str:
    candidate_signature = "|".join(
        f"{candidate.id}\u001f{candidate.name}\u001f{candidate.client or ''}"
        for candidate in candidates
    )
    return _text_digest(f"{source_system}\u001e{text}\u001e{candidate_signature}")


class CaptureSuggestionCache:
    """Bounded, content-addressed store that replays prior suggestions.

    Entries are keyed by the provider, the bounded text, and the candidate set, so a
    repeated request is replayed instead of charged again while a changed candidate
    set is still re-sent to the provider. ``max_entries`` caps the number of cached
    texts; the oldest entry is evicted first.
    """

    def __init__(self, *, max_entries: int = DEFAULT_CACHE_ENTRIES) -> None:
        if isinstance(max_entries, bool) or max_entries < 1:
            raise ClassifierError("cache max_entries must be positive")
        self._max_entries = max_entries
        self._entries: dict[str, CaptureDispositionSuggestion] = {}
        self._hit_count = 0
        self._miss_count = 0

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def hits(self) -> int:
        return self._hit_count

    @property
    def misses(self) -> int:
        return self._miss_count

    def lookup(self, key: str) -> CaptureDispositionSuggestion | None:
        suggestion = self._entries.get(key)
        if suggestion is None:
            self._miss_count += 1
            return None
        self._hit_count += 1
        return suggestion

    def store(self, key: str, suggestion: CaptureDispositionSuggestion) -> None:
        if key in self._entries:
            return
        if len(self._entries) >= self._max_entries:
            self._entries.pop(next(iter(self._entries)))
        self._entries[key] = suggestion


class PromptBrief:
    """A log-safe summary of a classifier request. It never contains the text."""

    def __init__(
        self,
        *,
        text_digest: str,
        text_chars: int,
        max_text_chars: int,
        candidate_ids: tuple[str, ...],
        source_system: str,
        cache_state: Literal["off", "hit", "miss"] = "off",
        cache_size: int = 0,
        cache_hits: int = 0,
    ) -> None:
        if len(text_digest) != 64:
            raise ClassifierError("text_digest must be a sha256 hex digest")
        if isinstance(text_chars, bool) or text_chars < 0:
            raise ClassifierError("text_chars must be non-negative")
        if cache_state not in {"off", "hit", "miss"}:
            raise ClassifierError("cache_state must be off, hit, or miss")
        self.text_digest = text_digest
        self.text_chars = text_chars
        self.max_text_chars = max_text_chars
        self.candidate_ids = candidate_ids
        self.source_system = source_system
        self.cache_state = cache_state
        self.cache_size = cache_size
        self.cache_hits = cache_hits

    def __str__(self) -> str:
        return (
            "PromptBrief("
            f"source={self.source_system} "
            f"text_digest={self.text_digest[:12]} "
            f"text_chars={self.text_chars}/{self.max_text_chars} "
            f"candidates={','.join(self.candidate_ids)} "
            f"cache={self.cache_state} "
            f"cache_size={self.cache_size} cache_hits={self.cache_hits})"
        )


def prompt_brief(
    text: str,
    candidates: Sequence[CaptureCandidate] = (),
    *,
    config: ClassifierConfig | None = None,
    cache: CaptureSuggestionCache | None = None,
    cache_state: Literal["off", "hit", "miss"] = "off",
) -> PromptBrief:
    """Render a log-safe summary for a classifier request without leaking its body."""
    resolved_config = config or ClassifierConfig()
    normalized = text.strip() if isinstance(text, str) else ""
    bounded = normalized[: resolved_config.max_text_chars]
    return PromptBrief(
        text_digest=_text_digest(bounded),
        text_chars=len(bounded),
        max_text_chars=resolved_config.max_text_chars,
        candidate_ids=tuple(candidate.id for candidate in candidates),
        source_system=resolved_config.source_system,
        cache_state=cache_state,
        cache_size=cache.size if cache is not None else 0,
        cache_hits=cache.hits if cache is not None else 0,
    )


class CachingClassifier:
    """Classifier adapter that replays per-text suggestions without re-charging.

    Wraps any ``ClassifierAdapter``: the first suggestion for a given text and
    candidate set is stored in a bounded cache, and repeated requests are replayed
    without ever calling the wrapped provider again. The wrapper stays on the
    provider side of ``suggest_capture_disposition``, so request bounds and
    candidate re-validation still run on every call.
    """

    def __init__(
        self,
        classifier: ClassifierAdapter,
        *,
        cache: CaptureSuggestionCache | None = None,
    ) -> None:
        if isinstance(classifier, CachingClassifier):
            raise ClassifierError("classifier is already wrapped in a cache")
        source_system = getattr(classifier, "source_system", None)
        if not isinstance(source_system, str) or not source_system.strip():
            raise ClassifierError("classifier must declare a source_system")
        self._classifier = classifier
        self._cache = cache or CaptureSuggestionCache()

    @property
    def source_system(self) -> str:
        return self._classifier.source_system

    @property
    def cache(self) -> CaptureSuggestionCache:
        return self._cache

    def suggest(
        self, text: str, candidates: Sequence[CaptureCandidate]
    ) -> CaptureDispositionSuggestion:
        key = _cache_key(self.source_system, text, candidates)
        cached = self._cache.lookup(key)
        if cached is not None:
            logger.info(
                "capture_classifier cache=hit %s",
                prompt_brief(
                    text,
                    candidates,
                    cache=self._cache,
                    cache_state="hit",
                ),
            )
            return cached
        logger.info(
            "capture_classifier cache=miss %s",
            prompt_brief(
                text,
                candidates,
                cache=self._cache,
                cache_state="miss",
            ),
        )
        suggestion = self._classifier.suggest(text, list(candidates))
        if not isinstance(suggestion, CaptureDispositionSuggestion):
            raise ClassifierError("classifier did not return a capture suggestion")
        self._cache.store(key, suggestion)
        return suggestion


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

    The runtime adapter will be wrapped in a ``CachingClassifier`` so repeated
    suggestions of the same text never re-charge the model. No provider account is
    configured yet, so this helper intentionally raises ``ClassifierNotConfigured``.
    The endpoint exposes that state as HTTP 503, and no test ever calls a live model.
    """
    raise ClassifierNotConfigured("Capture classification is not configured")
