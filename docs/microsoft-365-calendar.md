# Microsoft 365 calendar adapter

P2-03 implements a real Microsoft Graph `calendarView` client behind the provider-neutral calendar
contract. Automated tests use fictional HTTP responses; the repository contains no tenant IDs,
account addresses, tokens, or customer events.

## Permission and data boundary

The required delegated Microsoft Graph permission is `Calendars.ReadBasic`. It reads event metadata
but excludes bodies, attachments, and extensions. The adapter exposes only a list operation and
declares create, update, and delete capabilities as disabled.

Each query includes an explicit UTC start and end, requests UTC response values, and accepts up to
1,000 events per page. Pagination follows the complete `@odata.nextLink` only when it remains HTTPS,
targets `graph.microsoft.com`, and stays under `/v1.0/`. Repeated links and excessive page counts are
rejected.

## Multiple work accounts

Create one adapter per authorized account and calendar. Give every one a non-sensitive
`identity_scope`, such as `work-a:default` or `work-b:operations`; do not use account email addresses
in logs or fixtures. The scope becomes part of the stable external identity.

Environment configuration supports:

```dotenv
MICROSOFT_CALENDAR_ENABLED=false
MICROSOFT_CALENDAR_IDS=default
MICROSOFT_GRAPH_TIMEOUT_SECONDS=15
```

`MICROSOFT_CALENDAR_IDS` is a comma-separated local configuration value. Access tokens are not
accepted through this setting; a token provider injects a short-lived delegated token at request
time.

## Authorization prerequisite

Before enabling a real account, an application must be registered or approved in that account's
Microsoft Entra tenant and receive delegated `Calendars.ReadBasic` consent. Some organizations may
restrict user consent and require an administrator. No secret or token should be committed, stored
in integration-state tables, or included in logs.

P2-03 retrieves and normalizes events only. P2-04 will reconcile repeated results without duplicates,
and P2-05 will handle project association and review of unmatched meetings.

## Microsoft references

- [List calendarView](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft Graph paging](https://learn.microsoft.com/en-us/graph/paging)
- [Delegated access on behalf of a user](https://learn.microsoft.com/en-us/graph/auth-v2-user?view=graph-rest-1.0)
