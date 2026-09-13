# Phase 1 HTTP API

The manual-first API is served under `/api/v1`. Interactive OpenAPI documentation is available
at `/docs` while the application is running.

## Resources

| Resource | Create | List/filter | Read | Update | Delete |
|---|---:|---:|---:|---:|---:|
| Workspaces | Yes | `status` | Yes | Yes | Yes |
| Clients | Yes | `workspace_id`, `status` | Yes | Yes | Yes |
| Projects | Yes | `client_id`, `status`, `health` | Yes | Yes | Yes |
| Deliverables | Yes | `project_id`, `status`, `due_from`, `due_to` | Yes | Yes | Yes |
| Tasks | Yes | `project_id`, `deliverable_id`, `status`, `priority`, dates | Yes | Yes | Yes |
| Meetings | Yes | `project_id`, `status`, `starts_from`, `starts_to` | Yes | Yes | Yes |
| Action items | Yes | `meeting_id`, `status` | Yes | Yes | Yes |

## Protected transitions

- `POST /api/v1/tasks/{id}/complete` requires a completion note or an existing work log.
- `POST /api/v1/deliverables/{id}/review` requires acceptance criteria and an evidence URL.
- `POST /api/v1/action-items/{id}/task` creates one ready task in the meeting's project and links
  it to the source action item.
- Cross-project task, deliverable, meeting, and action-item links are rejected.

## Example

All IDs use lowercase snake case. This example contains fictional data.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"id":"wrk_demo","name":"Demo","timezone":"America/Santiago"}'

curl 'http://127.0.0.1:8000/api/v1/tasks?status=ready&priority=high'
```

Constraint conflicts return HTTP 409, missing records return HTTP 404, and rejected lifecycle
transitions return HTTP 422.
