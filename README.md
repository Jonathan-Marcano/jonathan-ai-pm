# FaroFlow

AI-powered personal project management assistant for coordinating multiple jobs, clients, projects, tasks, meetings, action items, and deliverables.

## Purpose

FaroFlow is intended to support a simple daily operating loop:

1. **Morning Brief:** surface meetings, priorities, deadlines, and risks.
2. **Day capture:** record work, decisions, and action items as they appear.
3. **Incremental delivery:** turn tasks into visible progress on deliverables.
4. **Evening Close:** review completed and pending work, update projects, and measure effort.

Phase 0 established the product definition and repository conventions. Phase 1 delivered the tested manual-first application. Phase 2 is underway; Slice B links and refreshes read-only Google Drive artifacts, Microsoft 365 calendar sync is complete, and Google Calendar is now available through the same read-only contracts without a live provider connection. WhatsApp and AI integrations remain deferred.

## Repository map

```text
.
├── data/seed/              # Synthetic development data only
├── docs/                   # Product and operating documentation
│   ├── decisions/          # Architecture decision records
│   └── backlog/            # Phase backlogs
├── migrations/             # Versioned database migrations
├── schemas/                # Machine-readable domain contracts
├── src/faroflow/     # Application, persistence, and domain services
├── static/                 # Brand kit, PWA manifest, and web dashboard
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
- [Phase 2 backlog](docs/backlog/phase-2.md)
- [Phase 3 backlog](docs/backlog/phase-3.md)
- [Phase 4 backlog](docs/backlog/phase-4.md)
- [Phase 2 integration contracts](docs/phase-2-integration-contracts.md)
- [Phase 2 integration state](docs/phase-2-integration-state.md)
- [Microsoft 365 calendar adapter](docs/microsoft-365-calendar.md)
- [Google Calendar read-only](docs/google-calendar.md)
- [Google Drive artifacts](docs/google-drive-artifacts.md)
- [Meeting preparation](docs/meeting-preparation.md)
- [Meeting review](docs/meeting-review.md)
- [Synchronization status](docs/integration-status.md)
- [Integration permissions and retention](docs/integration-retention.md)
- [Phase 1 HTTP API](docs/api.md)
- [Morning Brief](docs/morning-brief.md)
- [Incremental work](docs/incremental-work.md)
- [Evening Close](docs/evening-close.md)
- [Domain validation](docs/domain-validation.md)
- [Workload and progress summary](docs/progress-summary.md)
- [Snapshots and audit history](docs/snapshots-and-audit.md)
- [Local data protection](docs/local-data-protection.md)
- [Manual translations](docs/translations.md)
- [Web dashboard](docs/web-dashboard.md)
- [Source-of-truth decision](docs/decisions/0001-systems-of-record.md)
- [Phase 1 stack decision](docs/decisions/0002-phase-1-stack.md)
- [Phase 2 integration boundary](docs/decisions/0003-phase-2-integrations.md)

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
uv run faroflow seed-demo
uv run faroflow backup
uv run uvicorn faroflow.api:app --reload
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
- Phase 1 / Slice A: core CRUD, migrations, relationships, lifecycle rules, and automated domain validation are complete.
- Phase 1 / Slice B: the manual daily loop from capture and Morning Brief through incremental work
  and Evening Close is implemented.
- Phase 1 / Slice C: workload summaries, portable snapshots, audit history, local-data
  protection, and manual translations are implemented.
- Phase 1: complete.
- Phase 2: complete — contracts, calendar/document synchronization, meeting preparation and
  review, integration permission/retention controls, and synchronization status are implemented.
- Meeting review (P2-10): completed meetings enter a post-meeting review queue; completion and
  acknowledgment endpoints are implemented.
- Permissions and retention (P2-11): startup and sync checks reject write scopes and capabilities,
  provider errors are redacted, deliverable deletion requires unlinking Drive files first, and
  retention/disconnection behavior is documented.
- Synchronization status (P2-12): read-only run list/detail/error endpoints and safe retry are
  implemented.
- Microsoft 365 calendar: read-only adapter complete; tenant authorization is not configured.
- Google Calendar: read-only adapter complete using the same contracts and deduplication rules;
  authorization is not configured.
- Google Drive artifacts: read-only file links and idempotent metadata refresh are implemented;
  Drive authorization is not configured.
- Web: `GET /` serves the branded dashboard under the `static/` kit (design tokens, Inter,
  favicon, app icons, and an installable PWA manifest).

## Working agreements

- GitHub is the source of truth for code, schemas, and versioned technical documentation.
- Google Drive is the shared workspace for collaborative documentation and project-management artifacts.
- Every action item must be converted into a task or explicitly closed as informational.
- Every task should contribute to a project outcome and, where applicable, a deliverable.
- Real customer data, credentials, meeting transcripts, and confidential attachments must never enter seed fixtures.

## License

No license has been selected yet. Until one is added, all rights are reserved.
