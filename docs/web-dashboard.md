# Web dashboard and PWA — Personal Work Mission Control

`GET /` serves the FaroFlow single-page application built from the same FastAPI process.

The product is a **Personal Work Mission Control**: capture → understand → organize →
prioritize → execute → review. The AI never acts alone: **Faro propone, humano confirma.**

## Assets

`static/` holds the design kit and the web app:

- `tokens.css` — design tokens (violet/indigo identity, Inter font stack, spacing, radius,
  shadow, transition).
- `fonts/Inter.ttf` — the Inter typeface under the SIL Open Font License (`fonts/OFL.txt`).
- `favicon.ico` and `brand/` — favicon, app icons (192/512/1024) and logo variants.
- `manifest.webmanifest` — PWA manifest, served at `/manifest.webmanifest`.
- `web/index.html` — the application shell (sidebar, topbar, capture modal, ⌘K palette,
  mobile nav).
- `web/app.css` — component styles.
- `web/js/` — modular ES modules:
  - `api.js` — fetch wrapper with in-memory cache and name maps.
  - `ui.js` — shared UI helpers (icons, badges, toasts, skeletons, empty states, date
    formatting, date prompt).
  - `views.js` — one view per section plus detail views.
  - `main.js` — hash router, global capture, ⌘K command palette, workspace selector,
    mobile sidebar, inbox badge.

## Navigation (App Shell)

Desktop uses a fixed sidebar; mobile collapses it into a bottom navigation with a
floating **+** capture button.

| Route                     | Sección                                    |
| ------------------------- | ------------------------------------------ |
| `#/inicio`                | Mission Control (KPIs, brief, agenda, prioridades, insights, actividad, workload) |
| `#/mi-dia`                | Línea del día, quick actions, cierre del día |
| `#/inbox`                 | Capturas sin clasificar (propuesta + confirmación) |
| `#/proyectos`             | Portfolio con filtros (workspace/cliente/estado) y vista tarjetas/lista |
| `#/proyectos/:id`         | Proyecto detalle (Resumen, Tareas, Entregables, Reuniones, Archivos, Actividad) |
| `#/tareas`                | Tareas globales con filtros de estado y prioridad |
| `#/calendario`            | Agenda de los próximos 14 días (reuniones, vencimientos, entregables) |
| `#/reuniones`             | Próximas, pasadas, sin proyecto, completadas por revisar |
| `#/reuniones/:id`         | Meeting brief (pre) y notas/decisiones/action items (post) |
| `#/asistente`             | Asistente Faro con quick actions determinísticas |
| `#/integraciones`         | Google Drive, calendarios e historial de sincronización |
| `#/configuracion`         | Catálogo y resumen del sistema |

Global actions (`⌘K` palette, `+ Capturar` in sidebar/topbar/FAB) are available from any
section.

## Data flows

- **Inicio / Mission Control** combines `GET /api/v1/briefs/morning`,
  `GET /api/v1/briefs/evening`, `GET /api/v1/reports/progress`,
  `GET /api/v1/audit-events`, captures, projects, and the meeting review queues
  (`/api/v1/integrations/meetings/unmatched`, `/api/v1/integrations/meetings/completed`).
- **Proyecto detalle** reads `GET /api/v1/projects/{id}`, deliverables/tasks/meetings
  filtered by `project_id`, Drive links, and audit events for the entity.
- **Reunión detalle** reads `GET /api/v1/meetings/{id}/preparation` (Meeting Brief) and
  action items filtered by `meeting_id`.
- **Inbox** lists captures with `capture_status=inbox`. Classification is a *proposal*
  (`POST /api/v1/captures/{id}/suggest`) that the user must **confirm**
  (`POST /api/v1/captures/{id}/apply`) or discard (`POST /api/v1/captures/{id}/triage`).

The dashboard is presentational-plus-confirmation: writes are limited to user-confirmed
actions (complete/start/reschedule task, complete/review meeting, associate meeting to
project, triage capture), exactly matching the API in [api.md](api.md).