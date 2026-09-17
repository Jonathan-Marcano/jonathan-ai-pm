# Meeting review — post-meeting queue

Completed meetings enter a manual review queue so follow-up work and confirmation decisions stay
explicit instead of automatic. The queue is read-only: acknowledging a meeting never changes action
items, deliverables, or external provider state.

## Endpoints

- `POST /api/v1/meetings/{id}/complete` — move a `scheduled` meeting to `completed`. The meeting
  immediately appears in the post-meeting review queue. A meeting already `completed` or `cancelled`
  returns HTTP 422.
- `GET /api/v1/integrations/meetings/completed` — list completed meetings that have not been
  acknowledged (`reviewed_at` is null), newest first, with the usual `limit`/`offset` pagination.
- `POST /api/v1/meetings/{id}/review` with `{"decision": "reviewed"}` — acknowledge a completed
  meeting so it leaves the queue. Repeating the same review is idempotent; reviewing a meeting that
  is not `completed` returns HTTP 422.

Marking a meeting completed through the normal patch endpoint `PATCH /api/v1/meetings/{id}`
(`{"status": "completed"}`) also places it in the queue, so the review loop applies regardless of how
completion happened.

## Lifecycle

- `scheduled` → `completed` via completion (queue entry) or manual patch.
- `completed` → `reviewed_at` set via review (leaves queue).
- Completion always clears `reviewed_at`; a reopened meeting must be acknowledged again.
- Re-synchronizing an imported calendar meeting never reopens settled `completed` or `cancelled`
  records, so provider changes cannot silently re-enter the review queue.

Prerequisites for review (action capture, deadlines, evidence) remain unchanged and are documented in
[Meeting preparation](meeting-preparation.md) and [Domain validation](domain-validation.md).