# Google Calendar read-only

P2-08 connects personal Google Calendar events to the same meeting model, deduplication rules,
and bounded-window contracts already in place for Microsoft 365.

## Read-only boundary

The calendar adapter (`integrations/google_calendar.py`) uses the delegated scope
`https://www.googleapis.com/auth/calendar.readonly` and declares `READ_ONLY_CAPABILITIES`. It
fetches only `id, summary, start, end, status, htmlLink, updated` for events in one bounded UTC
window via the `events.list` endpoint with `singleEvents=true`. It can never create, update,
cancel, invite, or delete an event.

Tenant authorization is not configured yet. `POST /api/v1/integrations/calendar/sync` returns
HTTP 503 with `Calendar integration is not configured` until credentials are supplied.

## Syncing a window

`POST /api/v1/integrations/calendar/sync?starts_at=...&ends_at=...` requires both bounds with a
timezone and `ends_at` after `starts_at` (HTTP 422 otherwise). An optional `project_id` query
parameter projects all imported meetings onto one deliverable; when omitted, unmatched events
enter the review queue exactly like Microsoft 365 events.

The request is routed through `reconcile_calendar_events`, which reuses the same contracts
(`CalendarWindow`, `ExternalCalendarEvent`), persistence, and idempotency rules as P2-03/P2-04:

- repeated syncs update one meeting per source key and never duplicate records;
- cancelled events are marked cancelled without deleting the operational record;
- a failed provider read keeps existing meeting data and records a redacted entry.

## Safety notes

- Sync windows are bounded and every timestamp includes a timezone.
- The adapter exposes no write capability and requests no write scope.
- Errors are redacted before persistence, and no credentials are stored.
- The integration never changes, invites, or deletes an external calendar event.