# Phase 1 HTTP API

The manual-first API is served under `/api/v1`. Interactive OpenAPI documentation is available
at `/docs` while the application is running.

`GET /api/v1/briefs/morning` generates the dated operational brief. Its selection and ranking
rules are documented in [Morning Brief](morning-brief.md).

`GET /api/v1/briefs/meetings` generates the dated preparation view for scheduled meetings. It
accepts optional `date` and `due_soon_days` parameters. See
[Meeting preparation](meeting-preparation.md).

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
| Captures | Text only | `capture_status`, `disposition`, `project_id` | Yes | Triage endpoint | Preserved |
| Translations | Yes | `entity_kind`, `entity_id`, `field_name`, `language` | Yes | Text only | Yes |
| Audit events | Automatic | `entity_kind`, `entity_id`, `actor` | Through list | Immutable | Preserved |

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
