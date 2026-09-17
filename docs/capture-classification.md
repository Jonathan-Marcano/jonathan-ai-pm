# Capture classification — assisted triage proposals

Free-text captures can receive a read-only, provider-neutral classification proposal that suggests
the structured destination (kind, candidate project, priority, due date) with a confidence and
reasons quoted from the original text. The human always decides: a proposal never assigns a record
to a project on its own, and manual triage keeps working exactly as before.

Until a provider is authorized, the classification service answers HTTP 503 and the inbox continues
to work with manual triage only.

## Endpoint

- `POST /api/v1/captures/{id}/suggest` — attach a pending proposal to an **inbox** capture. The
  capture stays `inbox`; `disposition`, `project_id`, `task_id`, and `triaged_at` are untouched.
  Re-suggesting replaces the previous pending proposal. Suggesting a capture that is already
  `triaged` returns HTTP 422, an unknown capture returns HTTP 404, and an unconfigured provider
  returns HTTP 503.

The proposal is returned on the capture as read-only fields:

| Field | Meaning |
|---|---|
| `proposal_kind` | `task`, `action`, or `reference` |
| `proposal_project_id` | Candidate project, chosen only from the supplied candidates |
| `proposal_owner` | Suggested owner for an action item |
| `proposal_priority` | `low`, `medium`, `high`, or `critical` |
| `proposal_due_at` | Suggested due date |
| `proposal_confidence` | Value between `0` and `1` |
| `proposal_reasons` | Quoted fragments of the capture text that support the proposal |
| `proposal_source` | Provider identifier that produced the proposal |
| `proposed_at` | When the proposal was recorded |
| `applied_at` | When the proposal was explicitly confirmed (P3-03) |

## Provider-neutral contract

`suggest_capture_disposition(text, candidates)` is the neutral service boundary:

1. It bounds the request: text is capped by `max_text_chars` and candidates by `max_candidates`
   before any provider is called, capping token cost and data exposure.
2. It calls a `ClassifierAdapter` that returns a `CaptureDispositionSuggestion`.
3. It re-validates the suggestion before persistence: the kind, priority, and confidence are within
   their allowed ranges; a suggested project must be one of the supplied candidates; and every
   reason must literally quote the bounded capture text, so a provider cannot fabricate evidence or
   inject content that was never written by the user.

The project candidates expose only `id`, `name`, and the client name — never confidential event or
document bodies. No credential lives in the repository; the runtime factory raises
`ClassifierNotConfigured` until a provider is authorized, and the endpoint exposes that state as
HTTP 503.

## Explicit confirmation

`POST /api/v1/captures/{id}/apply` confirms a pending proposal and creates the operational record
exactly from it — the human always decides. Confirmation only works on an **inbox** capture that has
`proposed_at` set; an unconfirmed capture is never bound to a project.

- A `task` proposal creates one ready task titled with the captured text in the proposed project,
  with the proposed priority and due date.
- An `action` proposal creates one captured action item; it requires `{"meeting_id": ...}` in the
  request body because an action item always belongs to a meeting, and the meeting's project must
  match the proposed project.
- A `reference` proposal marks the capture as a `reference` and, when a project was proposed, links
  it to that project.

Applying is idempotent: repeating `apply` returns the same confirmed capture and never creates a
second record. Applying a capture without a pending proposal returns HTTP 422, an unknown capture
returns HTTP 404, and a capture triaged through manual triage cannot be applied.

### Decision trail

The confirmation does not discard the proposal. The capture keeps its original `text` and every
immutable `proposal_*` field together with `applied_at`, so the read of the capture always
references the exact proposal and source wording that were confirmed. The audit history records the
full trail: the capture creation event holds the original text, the proposal event (the `suggest`
update) holds the exact suggestion, the applied-record creation event holds the source wording as
its title, and the apply event on the capture links `task_id`/`action_item_id`, `project_id`,
`disposition`, `status`, `triaged_at`, and `applied_at`. Applied captures round-trip through
portable snapshots unchanged.

## Bounded cost and data exposure

`CachingClassifier` wraps any provider adapter so per-text suggestions are never re-charged:
repeating `suggest` for the same text and candidate set replays the stored suggestion without
calling the model again. The cache key is content-addressed from the provider, the bounded text,
and the candidate set, so a changed candidate set still reaches the provider, and a bounded
`CaptureSuggestionCache` (FIFO, default 100 entries) caps memory use. The wrapper validates the
provider result like any adapter and re-validation against the *current* candidates still runs on
every call.

Nothing that leaves the process for logging carries the captured text: `prompt_brief` renders a
redacted summary (sha256 digest of the bounded text, character count, candidate ids, provider, and
cache hit/miss state) and every classifier log line uses it, so a full-text capture never appears in
logs. Request bounds (`max_text_chars`) cap token cost and exposure on every call, and no test or
default path ever calls a live model.

## Out of scope

Provider accounts and token limits for live providers are tracked separately in the
[Phase 3 backlog](backlog/phase-3.md).
