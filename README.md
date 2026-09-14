# Jonathan AI PM

AI-powered personal project management assistant for coordinating multiple jobs, clients, projects, tasks, meetings, action items, and deliverables.

## Purpose

Jonathan AI PM is intended to support a simple daily operating loop:

1. **Morning Brief:** surface meetings, priorities, deadlines, and risks.
2. **Day capture:** record work, decisions, and action items as they appear.
3. **Incremental delivery:** turn tasks into visible progress on deliverables.
4. **Evening Close:** review completed and pending work, update projects, and measure effort.

Phase 0 established the product definition and repository conventions. Phase 1 is now underway with a local relational datastore, tested domain services, migrations, and a minimal API boundary. Live WhatsApp, calendar, Google Drive, and third-party API integrations remain intentionally deferred.

## Repository map

```text
.
├── data/seed/              # Synthetic development data only
├── docs/                   # Product and operating documentation
│   ├── decisions/          # Architecture decision records
│   └── backlog/            # Phase backlogs
├── migrations/             # Versioned database migrations
├── schemas/                # Machine-readable domain contracts
├── src/jonathan_ai_pm/     # Application, persistence, and domain services
├── tests/                  # Automated domain and API checks
├── .env.example            # Safe configuration template
├── pyproject.toml          # Runtime and development dependencies
└── README.md
```

## Documentation

- [Phase 0 index](docs/phase-0-index.md)
- [Vision](docs/vision.md)
- [Architecture](docs/architecture.md)
- [Domain model](docs/data-model.md)
- [Daily workflow](docs/workflow.md)
- [Roadmap](docs/roadmap.md)
- [Phase 1 backlog](docs/backlog/phase-1.md)
- [Phase 1 HTTP API](docs/api.md)
- [Morning Brief](docs/morning-brief.md)
- [Incremental work](docs/incremental-work.md)
- [Evening Close](docs/evening-close.md)
- [Source-of-truth decision](docs/decisions/0001-systems-of-record.md)
- [Phase 1 stack decision](docs/decisions/0002-phase-1-stack.md)

## Domain at a glance

```text
Workspace / Job
└── Client
    └── Project
        ├── Deliverable
        │   └── Task
        └── Meeting
            └── Action Item
                ├── Task
                └── Deliverable (optional)
```

The complete relationship and lifecycle rules are defined in [docs/data-model.md](docs/data-model.md). A JSON Schema is available at [schemas/domain-model.schema.json](schemas/domain-model.schema.json).

## Getting started

Install [uv](https://docs.astral.sh/uv/), then prepare the local application:

```bash
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run jonathan-ai-pm seed-demo
uv run uvicorn jonathan_ai_pm.api:app --reload
```

The API health check is available at `http://127.0.0.1:8000/health` and interactive endpoint
documentation at `http://127.0.0.1:8000/docs`. Run quality checks with:

```bash
uv run ruff check .
uv run pytest
```

Keep `.env` and the generated database local. Never commit credentials or customer information.
Seed data under `data/seed/` is intentionally fictional.

## Current status

- Phase 0: complete.
- Phase 1 / Slice A: core CRUD, filters, migrations, meeting/action-item conversion, and guarded lifecycle transitions are implemented.
- Phase 1 / Slice B: the manual daily loop from capture and Morning Brief through incremental work
  and Evening Close is implemented.
- External integrations: documented for later phases; not implemented.

## Working agreements

- GitHub is the source of truth for code, schemas, and versioned technical documentation.
- Google Drive is the shared workspace for collaborative documentation and project-management artifacts.
- Every action item must be converted into a task or explicitly closed as informational.
- Every task should contribute to a project outcome and, where applicable, a deliverable.
- Real customer data, credentials, meeting transcripts, and confidential attachments must never enter seed fixtures.

## License

No license has been selected yet. Until one is added, all rights are reserved.
