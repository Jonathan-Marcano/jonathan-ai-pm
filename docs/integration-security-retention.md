# Integration security, retention, and disconnection

P2-11 makes the read-only integration boundary enforceable before live authorization or public
operation endpoints are introduced.

## Permission enforcement

Microsoft 365 calendar configuration accepts only:

- `Calendars.ReadBasic` for calendar metadata;
- `openid`, `profile`, and `offline_access` when needed for an OAuth session.

Unknown permissions and write-enabled permissions such as `Calendars.ReadWrite` are rejected when
settings load. The Microsoft adapter validates the same policy when constructed and before every
request. Calendar reconciliation independently requires declared capabilities with read enabled
and create, update, and delete disabled. A failed check occurs before a synchronization run is
created.

OAuth acquisition is not implemented in P2-11. No access token, refresh token, password, client
secret, cookie, or authorization header has a persistence column.

## Retention

Defaults are configured in `.env`:

```text
INTEGRATION_SYNC_HISTORY_RETENTION_DAYS=90
INTEGRATION_RESOLVED_REVIEW_RETENTION_DAYS=30
```

Apply the policy explicitly:

```bash
uv run jonathan-ai-pm prune-integration-data --confirm
```

The operation deletes completed synchronization runs older than the configured history period;
their redacted errors are deleted by cascade. It also deletes resolved or dismissed calendar
import reviews older than their configured period. It never deletes a running synchronization,
a pending review, a confirmed reusable project mapping, an external identity, or an operational
meeting.

## Disconnection

Disconnect one calendar scope:

```bash
uv run jonathan-ai-pm disconnect-integration microsoft-365 \
  --scope work-a:default --confirm
```

Omit `--scope` to disconnect every local scope for that provider. The operation:

- deletes matching external identities;
- deletes matching pending/resolved import reviews;
- deletes matching project mappings;
- clears the scope from retained synchronization history;
- leaves redacted run totals and errors for the configured audit period; and
- preserves meetings, meeting reviews, actions, tasks, projects, and deliverables.

The foreign-key relationship clears any retained error-to-identity link when an identity is
removed. Provider-side consent or tokens must also be revoked using the provider's own controls;
Jonathan AI PM cannot revoke credentials it does not store.

Both maintenance commands require `--confirm`. P2-12 adds separately key-protected status, sync,
retry, and association-review endpoints, but retention and disconnection remain deliberate local
CLI operations. See [Integration operations](integration-operations.md). General application
authentication still belongs to the Phase 2.5 interface.

## Erasure boundary

Disconnecting is not complete erasure. Operational records may still contain a meeting title and
time that were previously imported, audit events preserve committed changes, and exported backups
remain independent copies. Complete local erasure requires an explicit review of those records and
snapshots using approved operating-system procedures.
