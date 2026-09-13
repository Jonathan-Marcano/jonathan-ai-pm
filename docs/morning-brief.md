# Morning Brief

The Morning Brief is a deterministic daily view built only from Jonathan AI PM records. Phase 1
does not read calendars, messages, Google Drive content, or an LLM.

## Endpoint

```http
GET /api/v1/briefs/morning?date=2026-09-14&due_soon_days=3
```

- `date` is optional and defaults to the current date in `APP_TIMEZONE`.
- `due_soon_days` is inclusive, defaults to 3, and accepts values from 0 through 30.
- Timestamps are stored in UTC and meetings are selected after conversion to `APP_TIMEZONE`.

## Sections

| Section | Selection rule |
|---|---|
| Meetings | Scheduled meetings occurring on the local brief date |
| Overdue tasks | Open tasks due before the brief date |
| Due-soon tasks | Open tasks due from the brief date through the configured horizon |
| Focus tasks | Top three ready or in-progress tasks, ranked by priority and due date |
| Task blockers | Tasks currently marked `blocked` |
| Deliverable blockers | Deliverables currently marked `blocked` |
| Deliverable opportunities | First five planned or active deliverables without a task in progress |
| At-risk projects | Active projects whose health is `at_risk` or `off_track` |

The sections may overlap intentionally. For example, a blocked task can also be due soon. This
keeps both deadline pressure and the reason work cannot advance visible.

## Current limitations

- Meeting entries are manual until a later calendar-integration phase.
- Capacity comparison requires task estimates and is deferred to the measurement increment.
- The API proposes focus tasks; the user remains responsible for confirming the day's plan.
