# Phase 1 HTTP API

The manual-first API is served under `/api/v1`. Interactive OpenAPI documentation is available
at `/docs` while the application is running. `GET /` serves the branded dashboard documented in
[Web dashboard](web-dashboard.md).

`GET /api/v1/briefs/morning` generates the dated operational brief. Its selection and ranking
rules are documented in [Morning Brief](morning-brief.md).

`GET /api/v1/briefs/evening` generates the read-only daily reconciliation. Its sections and
completion loop are documented in [Evening Close](evening-close.md).

`GET /api/v1/reports/progress` aggregates workload, completion, deliverable state, and logged
minutes at every hierarchy level. See [Workload and progress summary](progress-summary.md).

`GET /api/v1/snapshots/export` returns a versioned portable JSON snapshot. `POST
/api/v1/snapshots/import` validates and restores that document only into an empty datastore.
`GET /api/v1/audit-events` exposes immutable change history. See
[Snapshots and audit history](snapshots-and-audit.md).

Manual translations are managed through `/api/v1/translations`. Each translation targets one
supported display field while the source record remains unchanged. See
[Manual translations](translations.md).

Imported meetings that arrive without a confirmed project enter a review queue. `GET
/api/v1/integrations/meetings/unmatched` lists them, and `POST
/api/v1/integrations/meetings/{id}/project` with `{"project_id": ...}` confirms the association
and records a reusable mapping. `GET /api/v1/integrations/meeting-project-mappings` lists confirmed
mappings and `DELETE /api/v1/integrations/meeting-project-mappings/{mapping_id}` removes one
without touching operational meeting data. See [Meeting project association](phase-2-integration-state.md).

Drive file links attach read-only artifact metadata to deliverables. `POST
/api/v1/deliverables/{id}/drive-link` registers a link, `DELETE
/api/v1/deliverables/{id}/drive-link` removes it, and `GET /api/v1/integrations/drive-links`
lists them. `POST /api/v1/integrations/drive/refresh` refreshes name, URL, MIME type, version
marker, and modification time idempotently, returning the document sync run; it returns HTTP 503
until Drive authorization is configured. See [Google Drive artifacts](google-drive-artifacts.md).

`POST /api/v1/integrations/calendar/sync?starts_at=...&ends_at=...` imports a bounded,
timezone-aware Google Calendar window into meetings using the same deduplication rules as
Microsoft 365. Both bounds are required (`ends_at` after `starts_at`) and an optional `project_id`
projects every event onto one deliverable. It returns the calendar sync run, HTTP 422 on an
invalid window, and HTTP 503 until Calendar authorization is configured. See
[Google Calendar read-only](google-calendar.md).

`GET /api/v1/meetings/{id}/preparation` returns the dated read-only preparation view for a meeting:
the linked project and client, open action items, task and deliverable deadlines, and relevant
artifact links. It returns HTTP 404 for an unknown meeting. See
[Meeting preparation](meeting-preparation.md).

Completed meetings enter a post-meeting review queue. `POST /api/v1/meetings/{id}/complete` moves a
scheduled meeting to `completed`, `GET /api/v1/integrations/meetings/completed` lists completed
meetings awaiting acknowledgment, and `POST /api/v1/meetings/{id}/review` with
`{"decision": "reviewed"}` acknowledges one so it leaves the queue. See
[Meeting review](meeting-review.md).

Synchronization status is exposed read-only. `GET /api/v1/integrations/sync-runs` lists runs with
optional `source_system`, `resource_kind`, and `status` filters; `GET
/api/v1/integrations/sync-runs/{id}` and `GET /api/v1/integrations/sync-runs/{id}/errors` return one
run and its redacted errors. `POST /api/v1/integrations/sync-runs/{id}/retry` safely re-runs the
original bounded window and returns HTTP 503 until authorization is configured. See
[Synchronization status](integration-status.md).

Integration security is enforced at startup and per run (read-only capabilities and scopes only),
with retention and disconnection behavior documented in
[Integration permissions and retention](integration-retention.md).

## Resources

| Resource | Create | List/filter | Read | Update | Delete |
|---|---:|---:|---:|---:|---:|
| Workspaces | Yes | `status` | Yes | Yes | Yes |
| Clients | Yes | `workspace_id`, `status` | Yes | Yes | Yes |
| Projects | Yes | `client_id`, `status`, `health` | Yes | Yes | Yes |
| Deliverables | Yes | `project_id`, `status`, `due_from`, `due_to` | Yes | Yes | Yes |
| Tasks | Yes | `project_id`, `deliverable_id`, `status`, `priority`, dates | Yes | Yes | Yes |
| Task work logs | Through task | Chronological by task | Yes | Append only | Preserved |
| Meetings | Yes | `project_id`, `status`, `starts_from`, `starts_to` | Yes | Yes | Yes |
| Action items | Yes | `meeting_id`, `status` | Yes | Yes | Yes |
| Captures | Text only | `capture_status`, `disposition`, `project_id` | Yes | Triage / apply endpoints | Preserved |
| Translations | Yes | `entity_kind`, `entity_id`, `field_name`, `language` | Yes | Text only | Yes |
| Audit events | Automatic | `entity_kind`, `entity_id`, `actor` | Through list | Immutable | Preserved |

## Pagination

Every list endpoint (`workspaces`, `clients`, `projects`, `deliverables`, `tasks`, `meetings`,
`action-items`, `captures`, `translations`, `audit-events`) accepts optional `limit` (`1..500`,
default: all results) and `offset` (`>= 0`). When `limit` is provided the response adds a `Link`
header with `rel="next"` and `rel="prev"` URLs that preserve the current filters:

```bash
curl 'http://127.0.0.1:8000/api/v1/tasks?status=ready&limit=20' \
  -H 'Accept: application/json'
```

```http
Link: <http://127.0.0.1:8000/api/v1/tasks?status=ready&limit=20&offset=20>; rel="next"
```

Listings are ordered by record id. Single-item detail reads are unaffected.

## Protected transitions

- `POST /api/v1/tasks/{id}/complete` requires a completion note or an existing work log.
- `POST /api/v1/tasks/{id}/start` starts a `ready` task or resumes a `blocked` task. It also marks
  its planned project active and its linked planned deliverable in progress.
- `POST /api/v1/tasks/{id}/work-logs` accepts positive `minutes`, a non-empty evidence `summary`,
  and an optional `started_at`. The task must be in progress.
- `GET /api/v1/tasks/{id}/work-logs` returns that task's evidence history chronologically.
- `POST /api/v1/deliverables/{id}/review` requires acceptance criteria and an evidence URL.
- `POST /api/v1/action-items/{id}/task` creates one ready task in the meeting's project and links
  it to the source action item.
- Cross-project task, deliverable, meeting, and action-item links are rejected.
- `POST /api/v1/captures` requires only `text`.
- `POST /api/v1/captures/{id}/triage` records one immutable disposition and optionally creates a
  task or meeting action in the same transaction.
- A dismissed capture requires a reason in `note`.
- `POST /api/v1/captures/{id}/suggest` attaches a read-only classification proposal
  (`proposal_kind`, `proposal_project_id`, `proposal_priority`, `proposal_due_at`,
  `proposal_confidence`, `proposal_reasons`, `proposed_at`) to an inbox capture. It never changes
  the capture status and never binds a project; manual triage keeps working unchanged. An
  unconfigured classifier provider answers HTTP 503. See
  [Capture classification](capture-classification.md).
- `POST /api/v1/captures/{id}/apply` explicitly confirms a pending proposal and creates the
  operational record exactly from it (one ready task, one meeting action item, or a reference).
  An action proposal requires `{"meeting_id": ...}` in the body. Applying is idempotent, keeps the
  immutable proposal and original text on the capture as the decision trail, and never binds an
  unconfirmed capture to a project. See [Capture classification](capture-classification.md).

## Example

All IDs use lowercase snake case. This example contains fictional data.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"id":"wrk_demo","name":"Demo","timezone":"America/Santiago"}'

curl 'http://127.0.0.1:8000/api/v1/tasks?status=ready&priority=high'
```

Constraint conflicts return HTTP 409, missing records return HTTP 404, and rejected domain rules
return HTTP 422. The same rules are enforced below the HTTP layer so service and future ingestion
channels cannot bypass them. See [Domain validation](domain-validation.md).

The full P1-07 lifecycle and safe evidence guidance are documented in
[Incremental work](incremental-work.md).
