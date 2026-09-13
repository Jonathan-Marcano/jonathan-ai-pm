# ADR 0002: Phase 1 application stack

- Status: Accepted
- Date: 2026-09-13

## Context

Phase 1 needs durable relational records, explicit domain rules, a small API surface, repeatable
local setup, and migrations. The first user is a single operator, so operational simplicity and
portability matter more than distributed scale.

## Decision

- Python 3.12 is the application runtime.
- FastAPI provides the HTTP boundary; the first endpoint is a health check and domain endpoints
  will be added incrementally.
- SQLAlchemy 2 is the persistence layer.
- SQLite is the default local database. A server database can replace it later through
  `DATABASE_URL` without changing the domain model.
- Alembic owns versioned schema migrations and rollback instructions.
- Pydantic Settings reads runtime configuration from environment variables.
- pytest verifies persistence, referential integrity, and lifecycle rules; Ruff enforces basic
  formatting and static checks.
- `uv` is the recommended local dependency workflow while standard Python packaging remains
  supported through `pyproject.toml`.

## Boundaries

- The application remains a modular monolith.
- The API does not connect to WhatsApp, calendars, Google Drive, or an LLM in Phase 1.
- Real customer and operational data stay outside GitHub. Fixtures remain fictional.
- Dates are stored as dates and timestamps as UTC; display uses `APP_TIMEZONE`.

## Consequences

- Local setup requires only Python and `uv` and stores state in an ignored SQLite file.
- SQLite foreign-key enforcement is enabled explicitly for consistent domain constraints.
- Switching databases later requires a compatibility test and migration rehearsal.
- UI decisions remain reversible because domain behavior is isolated from FastAPI.
