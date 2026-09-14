# Workload and progress summary

P1-10 provides one dashboard-ready, read-only report for the full hierarchy:

```http
GET /api/v1/reports/progress?as_of=2026-09-14&work_from=2026-09-08&work_to=2026-09-14
```

All parameters are optional:

- `as_of` controls which open tasks count as overdue and defaults to today in `APP_TIMEZONE`;
- `work_from` and `work_to` filter work-log minutes by local calendar date, inclusively;
- without a work range, logged minutes represent all recorded work;
- `work_from` later than `work_to` is rejected.

## Response structure

The response contains overall `totals` plus ordered rows for `workspaces`, `clients`,
`projects`, and `deliverables`. Every row includes its level, stable ID, parent ID, display name,
and the same metric structure.

### Task metrics

| Metric | Definition |
|---|---|
| Total | Every task in the selected hierarchy node |
| Open | Non-cancelled tasks not marked done |
| Overdue | Open tasks whose due date is before `as_of` |
| Completion percent | Done tasks divided by all non-cancelled tasks |
| Status counts | Inbox, ready, in progress, blocked, done, and cancelled |

### Deliverable metrics

Each row reports total deliverables and counts for planned, in progress, in review, accepted,
blocked, and cancelled states. A deliverable row represents itself, so its deliverable total is one.

### Logged minutes

Minutes are summed from work logs attached to tasks in that hierarchy node. Project totals include
administrative tasks without a deliverable. Therefore, project minutes can be greater than the sum
of its deliverable rows; that difference is intentional and prevents uncategorized effort from
disappearing.

## Boundaries

The report reads the current datastore and performs no write. It contains no customer-specific
fixtures and does not connect to WhatsApp, calendars, Google Drive, or an LLM. The existing schema
already contains all required relationships and work logs, so P1-10 adds no migration.
