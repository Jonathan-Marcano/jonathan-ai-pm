# Integration operations

P2-12 exposes the existing read-only calendar synchronization and association services as a
small operational HTTP surface. It does not add OAuth, scheduled execution, provider writes, or
credential persistence.

## Safety boundary

Operations are disabled by default. To enable them locally, set:

```dotenv
INTEGRATION_OPERATIONS_ENABLED=true
INTEGRATION_OPERATION_KEY=<random value containing at least 32 characters>
INTEGRATION_MAX_SYNC_WINDOW_DAYS=31
```

Every endpoint below requires the key in `X-Integration-Key`. This key protects only the
integration-operation surface; it is not general application authentication. Do not expose the
application outside a trusted local environment before Phase 2.5 adds user authentication,
session protection, origin restrictions, and secure transport.

Calendar adapters are registered in memory by deployment code. The registry contains an adapter
reference and its source/scope coordinates, never an access token. A configured connection is
`ready` only when it is enabled, has a registered adapter, and declares read-only capabilities.
No live adapter is registered by the default application startup.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/v1/integrations/status` | Show configured connections, adapter readiness, approved permissions, and the latest run |
| `POST /api/v1/integrations/calendar/sync` | Fetch and reconcile one explicit, bounded calendar window |
| `GET /api/v1/integrations/sync-runs` | List run history with source, scope, status, and safe retry eligibility |
| `GET /api/v1/integrations/sync-runs/{id}` | Read one run and its counters |
| `GET /api/v1/integrations/sync-runs/{id}/errors` | Read redacted errors for one run |
| `POST /api/v1/integrations/sync-runs/{id}/retry` | Retry a failed or partial calendar run with the same source, scope, and time window |
| `GET /api/v1/integrations/calendar/reviews` | List unmatched calendar events awaiting a decision |
| `POST /api/v1/integrations/calendar/reviews/{id}/confirm` | Associate an event with an explicitly selected project |
| `POST /api/v1/integrations/calendar/reviews/{id}/dismiss` | Close an unmatched event without importing it |

Run lists accept `source_system`, `external_scope`, `status`, and a bounded `limit`. Review lists
accept `source_system` and `external_scope`.

## Execution and retry behavior

- The caller supplies timezone-aware `starts_at` and `ends_at` timestamps.
- Windows larger than `INTEGRATION_MAX_SYNC_WINDOW_DAYS` are rejected before provider access.
- Provider failures create a failed run, store only a redacted error, and return the `run_id` for
  diagnosis.
- Reconciliation failures produce a partial run and do not erase existing meetings.
- A retry creates a new run and preserves the original run. It reuses exactly the original
  provider, scope, and window.
- Successful or running runs cannot be retried.
- A disconnected run whose scope was anonymized by P2-11 is not retryable.
- Unmatched events are never assigned by title or other confidential content; they remain in the
  review queue until confirmed or dismissed.

## Example

This fictional request assumes deployment code has already registered the matching adapter:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/integrations/calendar/sync \
  -H 'Content-Type: application/json' \
  -H 'X-Integration-Key: fictional-local-operation-key-123' \
  -d '{
    "source_system":"microsoft-365",
    "external_scope":"work-a:default",
    "starts_at":"2026-09-15T00:00:00Z",
    "ends_at":"2026-09-22T00:00:00Z"
  }'
```

Microsoft 365 token acquisition remains deliberately unimplemented. Tenant consent and a safe
delegated OAuth flow must be confirmed before any real adapter is registered.
