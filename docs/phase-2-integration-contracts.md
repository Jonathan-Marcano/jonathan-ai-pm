# Phase 2 integration contracts

P2-01 introduces stable boundaries for calendar and shared-document providers. There are no live
network calls, OAuth flows, or credentials in this increment.

## Calendar contract

A calendar adapter receives a bounded, timezone-aware window and returns normalized external
events. Each event contains only provider identity, title, start/end time, status, optional web
link, and provider modification time.

The deduplication key is:

```text
source_system + calendar_id + external_id
```

A title change therefore updates the same future meeting instead of creating a duplicate.

## Document contract

A document adapter retrieves link metadata for one external file: provider identity, name, web
URL, optional MIME type, modification timestamp, and version marker. File content is deliberately
outside the contract.

The document key is:

```text
source_system + external_id
```

## Safety boundary

Both adapter protocols expose explicit read-only capabilities:

| Capability | Phase 2 |
|---|---:|
| Read | Enabled |
| Create | Disabled |
| Update | Disabled |
| Delete | Disabled |

Provider timestamps without a timezone, reversed date ranges, missing identities, and blank display
values are rejected before synchronization. P2-02 will persist external identities and sync-run
outcomes; P2-03 will implement the first live Microsoft 365 calendar adapter only after that state
and its permission checks exist.
