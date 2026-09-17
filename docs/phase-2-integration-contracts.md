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
values are rejected before synchronization. P2-02 persists external identities and sync-run
outcomes. P2-03 implements the Microsoft 365 `calendarView` adapter, P2-04 reconciles its results
into operational meeting records idempotently, and P2-05 queues unmatched meetings for confirmed
project association without reading confidential event content.

P2-06 links Google Drive files to deliverables through the document contract (see
[Google Drive artifacts](google-drive-artifacts.md)), and P2-07 refreshes name, URL, MIME type,
version marker, and modification time idempotently without ever copying document bodies.

P2-08 adds a Google Calendar adapter (scope `calendar.readonly`) behind the same calendar contract
(see [Google Calendar read-only](google-calendar.md)); its events use the identical boundaries,
timezone rules, and deduplication as the Microsoft 365 path.

P2-11 enforces this safety boundary at runtime: `assert_registered_providers_read_only()` audits the
registered adapters at startup and `check_read_only_adapter()` guards every sync run, so an adapter
with create/update/delete capability or a write scope is rejected before any provider call. See
[Integration permissions and retention](integration-retention.md).
