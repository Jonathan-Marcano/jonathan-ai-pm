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
- [Phase 4 messaging contracts and outbound policy](docs/phase-4-messaging-contracts.md)
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
- [Capture classification](docs/capture-classification.md)
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
- Phase 3: read-only capture classification proposals, the provider-neutral
  classifier contract (HTTP 503 until a provider is authorized), explicit confirmation that
  creates the operational record from the proposal with an immutable decision trail, and bounded
  cost/data exposure (per-text caching, redacted prompt logs, request bounds) are implemented.
- Phase 4 (in progress): provider-neutral messaging contracts bound inbound capture
  candidates and outbound notices, and an `OutboundPolicy` gate refuses any send without an
  explicit preview-confirmation; WhatsApp capture and notifications are next.

## Interfaz web (referencias 1536×1024)

Adaptación funcional de las seis vistas principales a las referencias de
`~/Downloads/FaroFlow_*.png`, sin datos ficticios (todo lee las APIs reales):

- **Mi Día** (`Fase 2`): grid 2 columnas, prioridades reales (`focus_tasks`),
  finanzas del mes y captura rápida al pie.
- **Trabajo — detalle de proyecto** (`Fase 3`): 70/30 con 4 indicadores, tabs
  (Resumen/Entregables/Tareas/Reuniones/Archivos/Actividad), entregables con
  avance y revisión, preparación de reunión, compromisos→tarea y registro de tiempo.
- **Finanzas — Egresos** (`Fase 4`): 72/28, 3 tarjetas del mes, tabs
  (Movimientos/Por categoría/Recurrentes), donut real por categoría, próximos
  pagos y aviso de capturas pendientes.
- **Hábitos** (`Fase 5`): 3 indicadores, semana real lun–dom, registro reciente
  con hora·hábito·origen, y detalle del hábito seleccionado en la columna
  derecha sin salir de la vista.
- **Bandeja** (`Fase 6`): master-detail 40/60 con lista seleccionable, búsqueda
  por texto y filtro por tipo, panel de revisión, "Volver" en móvil y captura
  manual como botón `data-capture-open`.
- **Entregables** (`Fase 3`): checklist de criterios de aceptación persistente por
  entregable (añadir / marcar cumplido / eliminar), creado desde el panel.

### Diferencias conocidas vs. las referencias
- Implementación funcional completa; la validación visual pixel a pixel queda
  pendiente de la persona (el agente no ve las imágenes).
- `Meetings` no exponen descripción ni lugar en la API: las tarjetas de reunión
  solo muestran título, fecha y estado.
- El donut de egresos usa proporciones reales de datos; si no hay datos en el
  mes se muestra el estado vacío en lugar de una gráfica simulada.
- Los submódulos de Finanzas *pagos*, *proyecciones*, *reportes*, *asistente* e
  *importación* no están implementados como rutas propias; el menú lateral solo
  expone los módulos realmente funcionales (resumen, ingresos, egresos, cuentas,
  deudas, presupuesto, metas) para no crear enlaces rotos.

### Circuito Telegram → Drive → importación local
La captura puede entrar por dos vías reales, ambas **solo lectura** y
pendientes de autorización:

1. **Telegram (P4-02)** — el adaptador lee actualizaciones del Bot API
   (`TELEGRAM_BOT_API_URL/bot<token>/getUpdates`) de forma acotada a los chats
   permitidos y las convierte en mensajes entrantes deduplicados. Aún no se
   autoriza el envío saliente (P4-03 exige confirmación explícita).
2. **Google Drive** — metadatos de archivos (id, nombre, enlace, mime,
   versión) bajo `drive.metadata.readonly`, enlazados a entregables; nunca se
   descarga contenido ni se escribe.

El flujo local: mensaje o archivo → bandeja pendiente → clasificación manual
(a Fase 3, Finanzas o Hábitos) → registro operacional con rastro de decisión.
La UI también ofrece **Capturar por chat**, que simula el canal Telegram
escribiendo capturas locales (`channel: telegram`) sin red ni credenciales.

**Activación (requiere credenciales personales; nunca commitearlas):**
- Las variables de entorno `.env` (ver `.env.example`): `GOOGLE_DRIVE_ENABLED`,
  `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_CALENDAR_ENABLED`, y un proveedor de token
  para el bot de Telegram (el token se inyecta por callable, no se almacena).
- El gate de mutaciones `INTEGRATION_OPERATIONS_ENABLED` + `INTEGRATION_OPERATION_KEY`
  (mín. 32 caracteres) protege los endpoints de sincronización/ingesta/reenvío.
- Hasta entonces, `POST /api/v1/integrations/messaging/inbound`,
  `/api/v1/integrations/drive/refresh` y `/api/v1/integrations/calendar/sync`
  responden **503 "integration is not configured"** por diseño; el resto de la
  app funciona con datos locales.

Capturas de verificación 1536×1024: `capturas_fases/` (fuera de git por
posible contenido personal).

## Working agreements

- GitHub is the source of truth for code, schemas, and versioned technical documentation.
- Google Drive is the shared workspace for collaborative documentation and project-management artifacts.
- Every action item must be converted into a task or explicitly closed as informational.
- Every task should contribute to a project outcome and, where applicable, a deliverable.
- Real customer data, credentials, meeting transcripts, and confidential attachments must never enter seed fixtures.

## License

No license has been selected yet. Until one is added, all rights are reserved.
