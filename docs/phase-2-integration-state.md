# Phase 2 integration state

P2-02 adds durable provider identity and synchronization history without connecting to a live
provider. The integration layer remains read-only and contains no OAuth or API credentials.

## External identities

`external_identities` maps one provider resource to an existing meeting or deliverable. Calendar
identity uses `source_system + external_scope + external_id`, where `external_scope` is the calendar
ID. Document identity uses an empty scope and the provider file ID.

Calling `upsert_identity` with the same source key refreshes version, link, modification, and sync
metadata on the same row. A source key cannot silently move to a different operational entity.

## Synchronization runs

Each execution starts as a `running` row in `sync_runs`. It records the provider, resource kind,
optional source scope, bounded UTC window, start/completion timestamps, and these outcome counts:

- seen;
- created;
- updated;
- unchanged;
- skipped;
- errors.

Completed runs are `succeeded`, `partial`, or `failed`. Classified outcome counts must add up to the
seen count, negative counts are rejected, and a completed run cannot be modified through the state
service.

## Error safety

`sync_run_errors` keeps a safe error code, redacted message, timestamp, and optional identity link.
Authorization headers, bearer values, passwords, tokens, secrets, cookies, and API keys are removed
before commit. Provider credentials and raw response payloads have no columns in these tables.

## Reconciliation

`reconcile_calendar_events` imports read-only events into meetings idempotently. The caller may
provide a `project_id`; without one, confirmed mappings or the review queue decide association.

- The stable source key (`source_system + external_scope + external_id`) prevents duplicates.
- New events create one meeting plus its external identity in a single flow.
- Repeated syncs update the linked meeting (title, start time) without duplicating records.
- External cancellations mark the meeting `cancelled`; already-settled meetings (`cancelled` or
  `completed`) are never reopened by a sync.
- Events missing from a window never delete operational data.
- A failed listing records a redacted error and completes the run as `failed`; per-event failures
  are annotated and counted as skipped.
- Explicit caller `project_id` values are authoritative for new or unmatched meetings and never
  override an already-associated meeting.

## Meeting project association

P2-05 adds review-based association for imported meetings. A meeting created without a confirmed
project keeps `project_id` null and appears in the review queue
(`GET /api/v1/integrations/meetings/unmatched`).

`meeting_project_mappings` stores one user-confirmed source key to project association. Confirming
a project (`associate_meeting` or `POST /api/v1/integrations/meetings/{id}/project`) updates the
meeting and records the mapping without guessing from event content. Later syncs reuse the mapping:

- New events with a confirmed mapping are created directly inside that project.
- Events that resolve to an existing unmatched meeting assign its project on the next sync.
- Deleting a mapping never deletes or detaches operational meetings.

Unmatched meetings cannot create tasks or action items until a project is confirmed.

## Drive file links

P2-06 and P2-07 manage read-only Google Drive links on deliverables without copying document
bodies. A link is an `external_identities` row with `entity_kind = deliverable` and
`source_system = google-drive`; it stores the file id, name, web URL, MIME type, version marker,
modification time, and last sync time.

- `link_drive_file` (or `POST /api/v1/deliverables/{id}/drive-link`) registers the link and sets
  the deliverable's `drive_url`. A source key cannot silently move to another deliverable.
- `unlink_drive_file` (or `DELETE /api/v1/deliverables/{id}/drive-link`) removes the link but
  never touches the external file.
- `reconcile_drive_files` refreshes name, URL, MIME type, version marker, and modification time
  idempotently for already-linked deliverables; a repeated refresh reports `unchanged`.
- Provider failures annotate the run and keep existing deliverable data intact; unknown or
  mismatched file ids are skipped with a redacted error.
- Authorization is not configured yet, so `POST /api/v1/integrations/drive/refresh` returns HTTP
  503 until tenant credentials are supplied.

## Google Calendar read-only

P2-08 imports personal Google Calendar events (`source_system = google-calendar`, scope
`calendar.readonly`) through the exact same contracts, identity rules, and deduplication as
Microsoft 365. `POST /api/v1/integrations/calendar/sync` accepts a bounded, timezone-aware window
and routes it through `reconcile_calendar_events`, so repeated syncs update one meeting per source
key and cancelled events are marked without deletion.

- An explicit `project_id` authority and the match-by-scope-association behavior are identical to
  the Microsoft 365 path.
- Authorization is not configured yet, so the endpoint returns HTTP 503 until tenant credentials
  are supplied.

## Synchronization status

P2-12 exposes runs read-only for monitoring and safe retries:

- `GET /api/v1/integrations/sync-runs` lists runs (optional `source_system`, `resource_kind`,
  `status` filters and pagination), `GET /api/v1/integrations/sync-runs/{id}` reads one run, and
  `GET /api/v1/integrations/sync-runs/{id}/errors` returns its redacted errors.
- `POST /api/v1/integrations/sync-runs/{id}/retry` re-runs the original bounded window from
  `window_starts_at`/`window_ends_at`, so a retry cannot expand the reconciliation scope. It returns
  HTTP 404 for unknown runs and HTTP 503 until authorization is configured.

## Permission enforcement and retention

P2-11 adds a safety layer that keeps the integration strictly read-only:

- On startup `assert_registered_providers_read_only()` audits every registered adapter class and
  prevents the process from booting if a provider declares write capability or a write scope.
- Before each reconciliation, `check_read_only_adapter()` validates the concrete adapter instance;
  a write-capable adapter fails the run with `code="unsafe_adapter"` and its message is redacted.
- Deletes that would orphan source state are rejected: a deliverable still linked to Drive files
  returns `422 "Unlink Drive files before deleting the deliverable"`. Unlinking never touches the
  external file, and disabling a provider never deletes imported records or sync history. See
  [Integration permissions and retention](integration-retention.md).

## Current boundary

The integration layer makes no network calls in tests, never writes to a provider, exposes
reconciliation state, project association, Drive link, synchronization status, and safe retry
endpoints, and implements no live provider connection yet. Drive document bodies are never copied,
and external deletions never delete operational records.
