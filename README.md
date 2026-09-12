# Jonathan AI PM

AI-powered personal project management assistant for coordinating multiple jobs, clients, projects, tasks, meetings, action items, and deliverables.

## Purpose

Jonathan AI PM is intended to support a simple daily operating loop:

1. **Morning Brief:** surface meetings, priorities, deadlines, and risks.
2. **Day capture:** record work, decisions, and action items as they appear.
3. **Incremental delivery:** turn tasks into visible progress on deliverables.
4. **Evening Close:** review completed and pending work, update projects, and measure effort.

Phase 0 establishes the product definition, domain model, repository conventions, and a safe non-sensitive seed dataset. It does **not** implement live WhatsApp, calendar, Google Drive, or third-party API integrations.

## Repository map

```text
.
├── data/seed/              # Synthetic development data only
├── docs/                   # Product and operating documentation
│   ├── decisions/          # Architecture decision records
│   └── backlog/            # Phase backlogs
├── schemas/                # Machine-readable domain contracts
├── .env.example            # Safe configuration template
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
- [Source-of-truth decision](docs/decisions/0001-systems-of-record.md)

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

There is no runtime application in Phase 0. To prepare for future development:

```bash
cp .env.example .env
```

Keep `.env` local and never commit credentials or customer information. Seed data under `data/seed/` is intentionally fictional.

## Current status

- Phase 0: complete in repository structure and documentation.
- Phase 1: defined and ready for implementation planning.
- External integrations: documented for later phases; not implemented.

## Working agreements

- GitHub is the source of truth for code, schemas, and versioned technical documentation.
- Google Drive is the shared workspace for collaborative documentation and project-management artifacts.
- Every action item must be converted into a task or explicitly closed as informational.
- Every task should contribute to a project outcome and, where applicable, a deliverable.
- Real customer data, credentials, meeting transcripts, and confidential attachments must never enter seed fixtures.

## License

No license has been selected yet. Until one is added, all rights are reserved.
