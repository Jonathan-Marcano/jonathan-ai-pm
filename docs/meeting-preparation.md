# Meeting preparation

P2-09 provides a deterministic preparation view for scheduled meetings on one local date. It uses
only records already stored in Jonathan AI PM and never invents agenda items, summarizes private
content with an LLM, records audio, or creates project documents.

## Endpoint

```http
GET /api/v1/briefs/meetings?date=2026-09-14&due_soon_days=7
```

- `date` defaults to the current date in `APP_TIMEZONE`.
- `due_soon_days` is inclusive, defaults to 7, and accepts 0 through 30.
- Only `scheduled` meetings occurring on that local date are included.
- Meetings are ordered chronologically after timezone conversion.

## Context per meeting

| Section | Selection rule |
|---|---|
| Client and project | Existing hierarchy associated with the meeting |
| Project health | Stored `unknown`, `on_track`, `at_risk`, or `off_track` value |
| Open actions | `captured` or `accepted` actions from any meeting in the same project |
| Open tasks | Project tasks not marked `done` or `cancelled`, ranked by priority and due date |
| Overdue tasks | Open tasks due before the preparation date |
| Due-soon tasks | Open tasks due from the preparation date through the configured horizon |
| Blocked tasks | Open project tasks currently marked `blocked` |
| Overdue deliverables | Active project deliverables due before the preparation date |
| Due-soon deliverables | Active project deliverables due within the configured horizon |
| Artifact links | Optional manual `drive_url` references from non-cancelled project deliverables |

Sections may overlap intentionally. A blocked task can also be overdue, preserving both deadline
pressure and the recorded blocker. Each meeting contains only its linked project's context; tasks
or actions from another client or project are never mixed into the preparation.

An empty date returns `meeting_count: 0` and an empty list. Missing information stays empty instead
of being inferred. Document creation and advanced Google Drive synchronization remain outside this
workflow.
