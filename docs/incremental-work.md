# Incremental work

P1-07 adds a manual, auditable loop for advancing a task in focused sessions. It uses the
`work_logs` table created by the initial domain migration, so this increment requires no schema
change or additional migration.

## Task flow

1. A task is prepared in `ready`, or returned from `blocked` when work can resume.
2. `POST /api/v1/tasks/{id}/start` moves it to `in_progress`.
3. Each focused session is recorded with `POST /api/v1/tasks/{id}/work-logs`.
4. `GET /api/v1/tasks/{id}/work-logs` returns the evidence history in chronological order.
5. `POST /api/v1/tasks/{id}/complete` closes the task when a completion note or work log exists.

Starting an already in-progress task is idempotent. Starting from `inbox`, `done`, or `cancelled`
is rejected. A work log can be added only while the task is in progress.

When work starts, its planned project becomes `active` and its linked planned deliverable becomes
`in_progress`. Later deliverable review and acceptance remain explicit decisions.

## Work-log evidence

Every work log records:

- the task;
- the session start time, defaulting to the current UTC time;
- a positive number of minutes;
- a concise evidence summary describing what changed, was verified, or remains blocked.

The evidence summary is operational traceability, not a place for credentials, customer data,
meeting transcripts, or confidential file contents. A safe example is “Drafted and locally
reviewed the validation section.”

## Example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/tsk_demo/start

curl -X POST http://127.0.0.1:8000/api/v1/tasks/tsk_demo/work-logs \
  -H 'Content-Type: application/json' \
  -d '{"minutes":30,"summary":"Drafted and locally reviewed the validation section."}'

curl http://127.0.0.1:8000/api/v1/tasks/tsk_demo/work-logs

curl -X POST http://127.0.0.1:8000/api/v1/tasks/tsk_demo/complete \
  -H 'Content-Type: application/json' \
  -d '{}'
```

WhatsApp, calendar, Drive API, and LLM ingestion remain deferred. Future channels will call this
same domain boundary after explicit authorization; they will not bypass its lifecycle rules.
