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
- Web CRUD: project detail, tasks, deliverables, meetings, inbox items, captures, and the
  finance modules (transactions, accounts, debts, budgets, goals) can be edited or deleted
  from the interface. Destructive operations follow the domain semantics: transactions are
  voided rather than deleted, and debts and budgets are closed rather than erased.
- Web deletion guards: a record with dependents is refused with HTTP 409 and a reason the
  interface shows in Spanish, instead of the foreign-key failure the API used to return.
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

### Sistema visual compartido

La composición se apoya en una única fuente de verdad en `static/tokens.css` y
`static/web/app.css`, para que ninguna pantalla vuelva a inventar su propia
escala:

- **Escala tipográfica por rol** (`--ff-size-page-title`, `--ff-size-card-title`,
  `--ff-size-value`, `--ff-size-body`, `--ff-size-secondary`). Los equivalentes
  comparten token y se adaptan por rol en los breakpoints, no por componente.
- **Un único componente de indicador**: `.kpi` = `.kpi-icon` (izquierda) +
  `.kpi-body` (derecha, vertical) con `.kpi-label` arriba, `.kpi-value` debajo y
  `.kpi-note` (subtítulo) bajo el valor en tono secundario. Se construye siempre
  con `kpiTile()` en `static/web/js/ui.js`; la clase `kpi-meta` se eliminó por
  ser ambigua (contenedor y texto a la vez).
- **Ritmo**: márgenes de contenido 20–28 px, separación 16 px entre tarjetas,
  radios de 12 px, borde de 1 px y sombra mínima.
- **Cabecera compacta** de 130–150 px con el faro como ilustración horizontal
  suave y secundaria, nunca como panel dominante ni imagen de fondo.
- **Sin reglas contradictorias**: los selectores duplicados se fusionaron en su
  definición única y se eliminaron las sobrescrituras acumuladas al final del
  archivo.

### Resumen semanal de hábitos (calculado en el servidor)

`HabitService.week_summary()` resuelve la semana natural (lunes a domingo) que
contiene hoy y la expone en `HabitSeriesRead.week`:

- Solo cuenta días ya transcurridos: un día futuro nunca es un incumplimiento.
- Los hábitos `weekdays` excluyen fin de semana; los `specific_days` solo sus días.
- Los hábitos `weekly` no se fijan en un día, así que se resuelven a nivel de
  semana con `goal_met` y `total_quantity`.
- `rate` = días cumplidos / días programados transcurridos.

Esto corrigió el indicador que mostraba `X / 0` y `0 %` por un denominador vacío,
y reemplazó la ventana móvil de 7 días corridos por la semana real en la matriz y
en la tira de cada hábito.

### Bloque "Disponible"

Componente único (`disponibleCard()`) con un único origen
(`availableBalance()` en `api.js`): la suma del saldo de las cuentas activas del
hogar. **Solo aparece en Finanzas** (Resumen y Egresos), a ancho completo y
arriba del todo.

- No depende del mes: es saldo actual, no un total del período.
- Se cachea por hogar, así que las dos vistas no multiplican llamadas. La
  invalidación por prefijo `fin` de `invalidate()` lo cubre al registrar o dar de
  baja un movimiento.
- Usa `balance_calculated` y cae a `balance_reported` si una cuenta no tiene
  saldo calculado.
- La nota dice cuántas cuentas activas suman y, si hay, el total de líneas de
  crédito. El número va en negativo a `--ff-danger-500`.
- Se quitó de Mi Día, Trabajo, Hábitos y Bandeja: un saldo en euros no pertenece
  a un tablero de trabajo, hábitos o capturas, y competía con el contenido de
  cada área.

### Egresos: orden de la vista

1. **Disponible** a ancho completo.
2. **Este mes** (indicadores de total, resultado y movimientos) junto a
   **Distribución** (donut + barras por categoría) en un 60/40.
3. **Política de gastos**: el presupuesto real del mes, planificado contra real
   por categoría con su % de desviación.
4. Movimientos y recurrentes en pestañas, con próximos pagos y capturas
   pendientes al lado.

Cambios frente a la versión anterior:
- Se eliminó la pestaña *Por categoría*: mostraba el mismo donut que ya está en
  el bloque de Distribución.
- Se añadió el filtro de **estado** (vigentes / anuladas), que antes se mostraba
  como etiqueta en la fila pero no se podía filtrar.
- *Política de gastos* es una tarjeta única con el presupuesto real. **No
  existe** una entidad "política de gastos" en el modelo de datos: se decidió no
  inventar la tabla y mostrar `Budget` + `BudgetCategory` (planificado, real y
  desviación) con ese rótulo.
- Los filtros *tipo* y *método* de la referencia **no se implementaron**: en
  Egresos todas las filas son `type=expense`, así que el filtro tendría una sola
  opción, y el modelo `Transaction` no tiene ningún campo de método de pago.
  Quedan los tres con backing real: mes, estado y búsqueda.

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
- El bloque de KPIs del detalle de proyecto mantiene 4 tarjetas (aceptados,
  completadas, tiempo, bloqueos); la referencia muestra 5 y no queda claro cuál
  es la quinta, así que no se inventó una.
- La edición en la UI no cubre todavía la lista independiente de tareas, los
  action-items dentro del detalle de reunión, la edición de cuenta más allá del
  saldo y el estado, ni las categorías, instituciones, miembros y fuentes de
  ingreso. La API sí expone los cuatro últimos; es la interfaz la que quedó
  pendiente.
- Las 16 clases que el JS usaba sin regla en CSS se resolvieron en la Fase 11.
  Quedan 3 sin regla a propósito, porque son ganchos de `querySelector` y no
  estilo: `f-status`, `f-prio` y `task-list`.


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

### Estado de las fases web (ciclo de adaptación a referencias)
- F1 (`f80a3b3`) shell y tokens. F2 (`fbc7408`) Mi Día. F3 (`25e1e01` + checklist
  persistente en `b70dfbc`) detalle de proyecto 70/30 con checklist de
  aceptación. F4 (`615d2b7` + `70eb13b`) egresos 72/28 con búsqueda, filtro por
  cuenta y nombres legibles. F5 (`19b9668` + `00d6208`) hábitos con detalle del
  seleccionado sin salir. F6 (`d377248` + `da6261d` + `70a22b6`) bandeja
  master-detail con búsqueda y filtro por tipo + documentación del circuito
  Telegram→Drive. F7 capturas 1536×1024 (escritorio) y 390×844 (móvil).
  F8 este informe.
- Verificación: `pytest` 594 pruebas verdes; endpoints reales responden 200 y
  los adaptadores sin autorización responden 503 por diseño.



### Fase 9 — sistema visual unificado y corrección de indicadores
- **Un componente de indicador** (`kpiTile`) en las cinco áreas, con la clase
  ambigua `kpi-meta` eliminada y sus dos papeles separados en `.kpi-body` y
  `.kpi-note`.
- **Escala por rol**: página 42 px, tarjeta 24 px, valor 30 px en escritorio;
  26 / 20 / 23 px a 520 px. Los breakpoints ajustan tokens, no selectores.
- **Precedencia de `.menu-btn` corregida** (`.icon-btn.menu-btn`, especificidad
  0-2-0): antes ganaba `.icon-btn` y el botón de menú aparecía en escritorio.
- **`.detail-head` unificado** en una sola definición; el título ya no se
  encoge a 24 px. Los entregables del detalle de proyecto pasan de tarjetas a
  **tabla** con el detalle del seleccionado debajo.
- **Faro** rediseñado a 240×96 horizontal y suave, dentro de una cabecera de
  130–150 px, sin el rectángulo dominante anterior.
- **Hábitos**: `week_summary()` en el servidor corrigió el `X / 0` y el `0 %`, y
  la matriz dejó de usar la ventana móvil de 7 días por la semana real lun–dom.
- **Reuniones**: "próxima" ahora exige estado programado **y** fecha no vencida;
  antes una reunión ya pasada seguía apareciendo como próxima.
- **Deuda CSS resuelta**: 0 selectores duplicados, llaves balanceadas, sin
  reglas huérfanas por variables de token.
- **Verificación**: `pytest` 599 pruebas verdes (5 nuevas para la semana
  natural), `ruff check` limpio, 0 desbordamiento horizontal en 8 rutas a
  1440 px y 500 px, y capturas en `capturas_fases/revision_visual/`.
- **Pendiente de persona**: comparación visual pixel a pixel de las capturas
  desktop (1440×1000) y móvil (430×932) de las cinco áreas, y (si se desea)
  autorizar credenciales reales para Telegram/Drive.

### Fase 10 — bloque "Disponible" y reordenación de Egresos
- **Disponible** añadido a seis dashboards y después reducido a los dos de
  Finanzas (ver Fase 11). Componente `disponibleCard()` y fuente cacheada
  `availableBalance()`: suma de `balance_calculated` de las cuentas activas, con
  `balance_reported` como respaldo. 52 px en escritorio, 38 px a 820 px y 32 px
  a 520 px.
- **Egresos reordenado**: Disponible a ancho completo → *Este mes* (60) junto a
  *Distribución* (40) → *Política de gastos* → movimientos y recurrentes con
  próximos pagos al lado.
- **Política de gastos** = presupuesto real del mes (planificado, real y
  desviación por categoría). No se creó la tabla "política de gastos": no existe
  en el modelo y se decidió no inventarla.
- **Filtro de estado** nuevo (vigentes / anuladas) con contador sincronizado; la
  etiqueta `voided` ya se mostraba en la fila pero no se podía filtrar.
- Se quitó la pestaña *Por categoría*, que duplicaba el donut de Distribución.
- Se quitaron los filtros *tipo* y *método*: sin backing real. Quedan mes, estado y
  búsqueda.
- **`.stack` definido** (flex column, hueco 16 px). Existía como clase usada en
  tres vistas sin regla, y dejaba las tarjetas pegadas con hueco 0.
- **Verificación**: 599 pruebas verdes, `ruff check` limpio, sin desbordamiento
  horizontal a 1440 px ni 500 px, filtro de estado probado con filas inyectadas
  (vigentes 2/3, anuladas 1/3, todas 3/3, contador correcto), 0 selectores
  duplicados en el CSS.
- **Nota**: la base local no tiene transacciones de finanzas, así que Egresos se
  valida sobre estados vacíos.

### Fase 11 — "Disponible" solo en Finanzas y limpieza de clases muertas
- **"Disponible" se queda únicamente en Finanzas** (Resumen y Egresos). Se
  retiró de Mi Día, Trabajo, Hábitos y Bandeja: un saldo en euros no pertenece a
  un tablero de trabajo, hábitos o capturas, y competía con el contenido de cada
  área. El componente y la fuente cacheada se conservan porque Finanzas los usa
  en sus dos vistas.
- **7 clases que el JS usaba sin ninguna regla CSS**, resueltas con estilo real:
  - `alert` + `alert-warn`: el bloque "Revisión pendiente" del dashboard de
    Trabajo salía como texto pelado. Ahora es una caja de aviso ámbar
    (`--ff-warning-100` sobre `--ff-warm-200`, radio 12 px) con icono de 20 px,
    siguiendo la estructura que ya tenía `.advice`.
  - `alert-cta`: empuja el botón a la derecha con `margin-left: auto`.
  - `date-line` (8 usos): la fecha o el contexto en la línea del `h1` iba con el
    mismo peso y color que el título; ahora secundario, 13,5 px y apagado.
  - `workload-bar` y `workload-note`: las filas del gráfico de carga no tenían
    layout (nombre, barra y número se apilaban como bloques) ni el pie tenía
    estilo. Ahora es una rejilla `1fr 2fr auto` centrada y el pie queda en
    secundario.
  - `quick-row`: los `.chip` de sugerencias rápidas son inline y se tocaban entre
    sí; ahora `flex` con `gap: 8px`.
- **5 clases muertas retiradas del markup** en vez de inventarles estilo:
  - `btn-safe` → se usó la variante existente `.btn-accent` (mismo botón sólido).
  - `brief-body` → se quitó; los hijos `.brief-*` ya llevan su propio margen
    vertical y un contenedor con `gap` duplicaría la separación.
  - `md-grid`, `btn-ghost-view`, `inbox-item` y `chat-card` → el estilo ya lo
    dan `dash-grid`, `.view-toggle .icon-btn`, `.item` y `.card`.
- **`.stack` definido** (flex column, hueco 16 px) en la fase anterior: la clase
  se usaba en tres vistas sin regla y dejaba las tarjetas pegadas con hueco 0.
- Quedan 3 clases sin regla de forma intencionada: `f-status`, `f-prio` y
  `task-list` son ganchos de `querySelector`, no estilo.
- **Verificación**: 599 pruebas verdes, `ruff check` limpio, sin desbordamiento
  horizontal en 8 vistas, llaves CSS balanceadas y 0 selectores duplicados. El
  aviso y el gráfico de carga se midieron inyectados en el navegador, porque con
  los datos locales no hay nada que revisar ni filas de carga que los rendereen:
  aviso de 62 px de alto con fondo `rgb(255, 241, 214)`, icono de 20 px, CTA a
  480 px del texto, y filas de carga en rejilla 353/705/13 px.

### Fase 12 — el nombre de la persona en toda la app
- La barra lateral decía `Usuario local` fijo en el HTML y el saludo de Mi Día
  salía sin nombre. La causa era que `ff.user` ya era la fuente del nombre, la
  barra lateral y el saludo, pero **nada lo escribía nunca**: la clave quedaba
  vacía y ambos caían al texto de arranque.
- `ui.js` concentra el perfil en una sola fuente: `displayName()`,
  `firstName()`, `userInitials()` y `setDisplayName()`. El valor por defecto es
  `Jonathan Marcano` y se puede cambiar; `ff.user` ya no se lee fuera de `ui.js`.
- El saludo es una función sola, `greeting()`, con la misma regla de hora en
  toda la app: antes de las 6 y desde las 20 `Buenas noches`, hasta las 12
  `Buenos días`, el resto `Buenas tardes`, siempre con el primer nombre.
- Se wiring en `main.js` con `paintProfile()`: la barra lateral se repinta con
  el evento `ff:profile-changed`, así que cambiar el nombre se ve al instante
  sin recargar.
- **Configuración** tiene ahora una tarjeta *Tu perfil* con el campo de nombre.
  Un nombre vacío o solo espacios se rechaza y el campo vuelve al valor
  guardado, y guardar no vuelve a renderizar la vista entera para no perder el
  foco ni volver a pedir salud, progreso, auditoría y respaldo.
- De paso, `Buenos días` estaba escrito a mano en tres lugares (el briefing y
  dos veces en Inicio), así que a las 23:00 saludaba con "Buenos días". Ahora
  los tres usan `greeting()`.
- Verificado en Chrome real sobre la app servida, en cinco vistas: Mi Día,
  Inicio y Trabajo muestran `Buenas noches, Jonathan` a las 21:00, la barra
  lateral `Jonathan Marcano` con avatar `JM`, el campo precargado, sin
  desbordamiento y sin errores de consola. Los cortes de hora se revisaron
  uno por uno: 05:00 noches, 06:00 días, 11:00 días, 12:00 tardes, 19:00 tardes,
  20:00 noches.

### Fase 13 — edición y borrado de registros
- Los registros se podían crear y, en el mejor de los casos, cambiar de estado, pero no
  corregir ni borrar. Un movimiento mal cargado, una meta que ya no interesa o una reunión
  con el título mal escrito no tenían arreglo, y borrar reventaba con un 500 y el error de
  clave foránea de Postgres, que no dice qué hacer.
- **Proyectos**: edición del detalle completo y eliminación. El formulario se precarga con
  los valores guardados y el borrado informa cuántas tareas, entregables y reuniones hay
  colgando, en vez de fallar con el error de la FK.
- **Tareas, entregables y reuniones** de un proyecto: editar y eliminar desde la fila,
  reutilizando el mismo formulario. En la lista de reuniones los botones estaban dentro de
  un `<a>`, así que el HTML no era válido; se sacaron del enlace. Para el `datetime-local`
  se agregó `toLocalInput()`, que convierte el UTC del servidor a la zona local, porque
  antes se mostraban horas corridas.
- **Finanzas**, con la semántica que corresponde a cada cosa:
  - Movimientos: editar y **anular**, nunca borrar. Anular mantiene el registro.
  - Cuentas: *Ajustar saldo* ahora manda `balance_reported`. Antes mandaba
    `balance_calculated`, así que ajustaba el saldo equivocado y el cambio se perdía al
    recalcular; verificado con `1000 → 123456 → 1000`.
  - Metas: editar y eliminar. Deudas: editor precargado. Presupuestos: cerrar y reabrir.
    El historial no se borra en ningún caso.
- **Capturas**: `PATCH` para corregir el texto o la nota de disposición, y `DELETE`. No
  existía ruta ni schema y el store rechazaba cualquier cambio, así que corregir una
  captura mal hecha obligaba a borrarla y volver a crearla.
- **Bandeja**: *Corregir texto* y eliminar. Corregir el texto de un item ya resuelto no lo
  reabre: `applied` y `discarded` son terminales y volverían a la cola de pendientes. Tampoco
  reclasifica, porque el destino sigue siendo el que eligió la persona. Ojo con la
  distinción: **bandeja (`bjx_`) y capturas (`cap_`) son entidades distintas**, con rutas
  propias `/api/v1/bandeja/{id}` y `/api/v1/captures/{id}`.
- **Borrados bloqueados que dicen qué hacer**: se comprueban antes de borrar y se responden
  con `409` en vez de `500`. `DomainConflictError` se separa de `DomainRuleError`
  justamente para que el cliente distinga *no lo puedo borrar todavía* de *me equivoqué en
  el payload*. Cubren proyecto con hijos, tarea y action-item referenciados por capturas,
  entregable con archivos de Drive, hábito con registro de cumplimiento, cliente y
  workspace con actividad, reunión con action-items o notas, y traducciones de un registro
  que se quiere borrar. La UI traduce el motivo al español con `confirmDelete()` y advierte
  que un item `applied` ya creó cosas en su destino que no se deshacen con el borrado.
- **De paso**: `api.js` concentra `updateRecord()`, `deleteRecord()` y `deleteEntity()`, más
  los `invalidate()` de la caché financiera —sin eso, editar un saldo dejaba la pantalla
  mostrando el valor viejo—. Se cachea el listado de cuentas para no pedirlo en cada render
  y se corrige un import duplicado de `views-bandeja` que rompía la carga de **todos** los
  módulos.
- **Verificado** en Chrome sobre la app servida: edición de proyecto con persistencia y
  vuelta al valor original, edición y anulación de movimiento en Ingresos y Egresos, ajuste
  de saldo `1000 → 123456 → 1000`, edición y borrado de meta, cierre y reapertura de
  presupuesto, corrección de texto en bandeja, y el borrado de proyecto con hijos mostrando
  *No se puede eliminar: tiene tareas; bórralas primero* y sin filtrar inglés. 604 tests
  verdes y `ruff` limpio.
- **Aparte, en su propio commit**: los saldos de Cuentas y el progreso de Metas salían
  partidos en cuatro líneas. No era falta de ancho —la tarjeta mide 977 px y cada indicador
  460—, sino que `.kpi` reserva una columna de 44 px para `.kpi-icon` y esos indicadores no
  tienen icono, así que su `.kpi-body` caía en esa columna y el texto tenía 44 px en vez de
  363. La variante `.kpi.no-icon` ya existía en el CSS desde antes y no la usaba ninguna
  vista; al aplicarla el valor pasó de 138 px de alto a 35 px, en una línea.

## Working agreements

- GitHub is the source of truth for code, schemas, and versioned technical documentation.
- Google Drive is the shared workspace for collaborative documentation and project-management artifacts.
- Every action item must be converted into a task or explicitly closed as informational.
- Every task should contribute to a project outcome and, where applicable, a deliverable.
- Real customer data, credentials, meeting transcripts, and confidential attachments must never enter seed fixtures.

## License

No license has been selected yet. Until one is added, all rights are reserved.
