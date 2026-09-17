# Meeting preparation

P2-09 provides a dated preparation view for an upcoming meeting. `GET
/api/v1/meetings/{meeting_id}/preparation` combines everything needed before the meeting starts in
a single read-only document:

- `meeting` — the scheduled meeting record.
- `project` and `client` — the linked project and its client, when the meeting has a confirmed
  association.
- `open_action_items` — action items of this meeting still in `captured` or `accepted`.
- `task_deadlines` — open tasks (not `done`/`cancelled`) of the meeting's project that carry a due
  date, ordered by due date.
- `deliverable_deadlines` — project deliverables not yet `accepted`/`cancelled`, ordered by due
  date.
- `artifact_links` — read-only Drive links attached to the project's deliverables.
- `prepared_at` — the moment the view was generated.

A meeting without a confirmed project still returns its meeting and open action items; the project,
client, deadline, and artifact sections are empty until an association is confirmed through the
review queue.

## Boundaries

- The endpoint is read-only and never mutates the meeting, its project, or its actions.
- Deadline and artifact sections only surface operational context the user already confirmed;
  confidential provider event content is never read.
- Unmatched meetings cannot create tasks or action items, so their preparation view stays minimal.