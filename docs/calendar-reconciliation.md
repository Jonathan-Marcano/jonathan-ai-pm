# Idempotent calendar reconciliation

P2-04 converts normalized provider events into stable operational meetings. P2-05 supplies project
ownership through either an explicit invocation mapping or a previously confirmed persistent
mapping. Neither step calls Microsoft Graph or infers ownership from event titles, attendees,
descriptions, or other confidential text.

## Source identity

The reconciliation key remains:

```text
source_system + external_scope + external_id
```

Meeting and identity IDs are deterministic hashes of that source key. Repeating the same window
therefore updates the existing rows even if a previous process ended between attempts. Duplicate
items inside one provider response are collapsed to one event and counted as skipped.

## Outcome rules

| Provider result | Operational behavior |
|---|---|
| New event with explicit project mapping | Create one meeting and one external identity |
| New event without mapping | Upsert one review item and skip meeting creation |
| New event with a confirmed persistent mapping | Create one meeting and reuse that decision on later runs |
| Existing event unchanged | Refresh `last_synced_at` and count it as unchanged |
| Existing title, time, link, or version changed | Update the same meeting and identity |
| Explicit provider cancellation | Set a scheduled meeting to `cancelled` |
| Cancellation after local completion | Preserve the completed operational status |
| Event absent from a successful bounded window | Set `missing_since`; do not delete or cancel |
| Previously missing event reappears | Clear `missing_since` and update the same meeting |
| Invalid event or broken identity | Record a redacted run error and continue as partial |

Every run retains seen, created, updated, unchanged, skipped, and error counts. Classified outcome
counts always add up to the number of provider items received. A single event failure does not erase
successfully reconciled events from the same run.

## Safe removal policy

Absence from one calendar response is not proof of deletion: a window can change, a provider can be
temporarily inconsistent, or permissions can be reduced. For that reason, `missing_since` is a
review signal only. No meeting, task, action item, or deliverable is removed automatically.

See [Calendar project associations](calendar-project-associations.md) for the review and confirmation
workflow used by P2-05.
