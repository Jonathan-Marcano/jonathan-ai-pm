# Evening Close

P1-08 provides a deterministic end-of-day reconciliation built only from Jonathan AI PM records.
It does not call a calendar, WhatsApp, Google Drive, an LLM, or another external service.

## Endpoint

```http
GET /api/v1/briefs/evening?date=2026-09-14
```

- `date` is optional and defaults to the current date in `APP_TIMEZONE`.
- Stored timestamps are interpreted as UTC before selecting records for the local day.
- The endpoint is read-only and repeatable. The user applies corrections through the existing
  task, capture, action-item, deliverable, and project endpoints, then runs the close again.

## Sections

| Section | Selection rule |
|---|---|
| Completed tasks | Tasks currently `done` whose last update occurred on the close date |
| Work logs | Sessions whose `started_at` falls on the close date, plus total logged minutes |
| Untriaged captures | Inbox captures created on or before the close date |
| Triaged captures | Captures triaged on the close date |
| Open action items | All action items currently `captured` or `accepted` |
| Unfinished tasks | Inbox, in-progress, blocked, overdue, or due-today tasks |
| Blocked tasks | All tasks currently `blocked` |
| Touched deliverables | Deliverables linked to work logged or tasks completed that day |
| Projects to review | Projects touched that day plus non-terminal projects at risk or off track |
| Tomorrow's first action | Highest-ranked ready or in-progress task using Morning Brief ranking |

The counts object gives the size of every section and the day's total logged minutes.

## Reconciliation loop

Before accepting the close, the user should:

1. triage or explicitly dismiss every listed capture;
2. convert or close open action items;
3. complete, reschedule, block, cancel, or leave a clear next step for unfinished tasks;
4. confirm current deliverable status and project health;
5. verify that tomorrow's first action is realistic.

Rerunning the endpoint reflects those updates immediately. This produces a dated operational
summary without storing a second, potentially inconsistent copy of the same state.

## Current limitations

- Tasks do not yet store a dedicated completion timestamp. Until audit history is implemented in
  P1-12, completed-today selection uses the task's `updated_at` value.
- Historical project-status changes are not inferred. The close shows current touched and at-risk
  projects for explicit user confirmation.
- Planned minutes and capacity comparison require task estimates and remain part of the later
  measurement increment.

The existing schema already contains every field required by this report, so P1-08 adds no new
migration.
