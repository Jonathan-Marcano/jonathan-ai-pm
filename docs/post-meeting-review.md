# Post-meeting review

P2-10 closes the operational loop after a meeting without transcription, content inference, or
autonomous task creation. The user remains responsible for confirming the result and each action.

## Queue

`GET /api/v1/briefs/meeting-reviews?date=YYYY-MM-DD` returns meetings that:

- have started by the time the response is generated;
- fall on or before the requested date in `APP_TIMEZONE`;
- are not cancelled; and
- do not yet have a completed review.

The queue is oldest first so missed days remain visible. Each item includes its client and project.
An imported meeting also exposes only its provider name and optional source URL; attendee lists,
email addresses, descriptions, bodies, and attachments are not copied into this flow.

## Closing a review

`POST /api/v1/meetings/{meeting_id}/review` accepts one of two explicit outcomes:

- `actions_captured`: requires at least one action with an ID, title, owner, and optional
  deliverable from the same project;
- `no_follow_up`: requires an empty action list.

Example with fictional data:

```json
{
  "decision": "actions_captured",
  "summary": "The client confirmed the next implementation window.",
  "actions": [
    {
      "id": "act_confirm_window",
      "title": "Confirm the maintenance window",
      "owner": "Jonathan",
      "deliverable_id": "del_demo_plan"
    }
  ]
}
```

The server records the actor from `X-Actor` (default `local-user`) and the UTC review timestamp.
It marks the meeting completed and creates all requested actions in one transaction. A validation
failure writes none of those changes. A closed review cannot be submitted again, preventing retry
duplicates.

Actions begin as `captured`. The existing action-to-task transition remains a separate human
decision, so P2-10 does not silently add work to the execution plan.

## Boundaries

- No audio, transcript, meeting body, or attendee data is processed.
- No LLM generates the summary or actions.
- No provider event is edited and no outbound notification is sent.
- The result is included in portable snapshots and immutable audit history.
