# Portable snapshots and audit history

P1-11 and P1-12 provide a safe local backup boundary and traceable domain changes.

## Portable snapshot

`GET /api/v1/snapshots/export` returns one JSON document with:

- `schema_version: "1.0"` and an export timestamp;
- every workspace, client, project, deliverable, task, meeting, action item, work log, and capture;
- the immutable audit history;
- original record IDs and creation/update timestamps.

`POST /api/v1/snapshots/import` validates the full document before persistence. Validation covers
schema version, duplicate IDs, required completion/review evidence, references, and same-project
relationships. Import is transactional and only accepts an empty datastore. It never merges or
overwrites local records.

Snapshots may contain confidential work data. Store them outside the repository and do not use
production snapshots as fixtures.

## Audit history

Every create, update, and delete is recorded in the same database transaction as the domain
change. Each event contains:

- actor from the `X-Actor` HTTP header, defaulting to `local-user`;
- UTC occurrence timestamp;
- entity kind and ID;
- action;
- field-level `old` and `new` values.

Audit events are read-only through `GET /api/v1/audit-events`. Optional filters are
`entity_kind`, `entity_id`, and `actor`. Failed or rolled-back operations leave no audit event.
Snapshot restoration preserves the original history and does not fabricate import events.

## Examples

```bash
curl http://127.0.0.1:8000/api/v1/snapshots/export > backup.json

curl -X POST http://127.0.0.1:8000/api/v1/snapshots/import \
  -H 'Content-Type: application/json' \
  --data-binary @backup.json

curl 'http://127.0.0.1:8000/api/v1/audit-events?entity_kind=task&entity_id=tsk_demo'
```
