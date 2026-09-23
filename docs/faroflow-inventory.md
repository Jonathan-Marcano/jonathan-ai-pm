# Faro Flow — Inventario verificable (Fase 0)

Este inventario se contrastó contra el código de ambos repositorios, no solo contra
los README o backlogs. Fuentes:

- Faro Flow (base, ex Jonathan AI PM): `src/faroflow`, rama `main`, head `7457ac3`.
- CuentaFaro: `src/cuentafaro`, head `3169694` (integrado en este repositorio, ver ADR 0004).

Estado del entorno al momento del inventario: rama `main`, árbol de trabajo limpio,
241 pruebas de faroflow y 309 de cuentafaro en verde (mentiras no; verificadas).

---

## 1. Pantallas y rutas de Faro Flow (área Trabajo / shell)

SPA vanilla en `static/web` con router por hash. Rutas de aplicación:

| Ruta | Pantalla |
|---|---|
| `/inicio` | Resumen (workload, briefs, pendientes) |
| `/mi-dia` | Mañana / cierre / pendientes |
| `/inbox` | Bandeja de capturas (tareas/acciones/referencias) |
| `/proyectos` y `/proyectos/:id` | Proyectos y detalle |
| `/tareas` | Tareas |
| `/calendario` | Agenda |
| `/reuniones` y `/reuniones/:id` | Reuniones y detalle |
| `/asistente` | Asistente / clasificación |
| `/integraciones` | Estado de integraciones |
| `/configuracion` | Configuración |

API (FastAPI, prefijo `/api/v1`), routers en `src/faroflow/api`:

- `routes_catalog`: workspaces, clients, projects, deliverables (+ `/review`).
- `routes_work`: tasks (start/work-logs/complete), work logs.
- `routes_meetings`: meetings (complete/review/preparation), action items (→task).
- `routes_captures`: captures (suggest/apply/triage).
- `routes_integrations`: drive-links, drive/refresh, calendar/sync, sync-runs, retry,
  meetings unmatched/project mapping.
- `routes_system`: health, briefs morning/evening, reports/progress, audit-events,
  snapshots export/import.
- `routes_translations`: traducciones manuales por entidad/campo/idioma.
- `routes_web`: `GET /` → SPA.

## 2. Entidades y relaciones de Faro Flow

Modelos en `src/faroflow/models.py` (12 tablas + 5 de integración):

`Workspace → Client → Project → {Deliverable → Task; Meeting → ActionItem}`
también `WorkLog (→Task)`, `Capture`, `Translation`, `AuditEvent`, y tablas de
integración `ExternalIdentity`, `SyncRun(+Error)`, `MeetingProjectMapping`.

Reglas de dominio clave (`domain_rules.py`, `services.py`):
- Estado de proyecto (`planned/active/paused/completed/cancelled`) y salud
  (`unknown/on_track/at_risk/off_track`) son conceptos distintos.
- Tareas `done` exigen evidencia (nota de cierre o work log); `in_progress` exige
  `start_task`. Estados protegidos en PATCH.
- Entregables `in_review` exigen criterios de aceptación + `evidence_url`.
- Action items solo se convierten en tarea desde `captured` y con proyecto de reunión.
- Cierre de reunión → cola de revisión posterior; asociación de reunión a proyecto idempotente.
- Capturas inmutables tras crear el registro; `apply_capture` idempotente.
- Work logs append-only, minutos > 0, con fecha aware UTC.
- Clasificación: proposals de solo lectura, confirmación humana aplica.

Integraciones (`src/faroflow/integrations`): microsoft365, google_calendar,
google_drive (todos de solo lectura, autorización NO configurada), reconciliation
(dedup por source+external_id), persistence (SyncRun + external identities),
safety (rechaza scopes de escritura al arranque), messaging (contratos inbound/outbound
con puerta `OutboundPolicy` — sin proveedor en vivo). Sin webhook/getUpdates desde el PC.

## 3. Importaciones y exportaciones de Faro Flow

- `faroflow backup` → snapshot JSON versionado (`schema_version 1.1`) con entidades
  + audit, sin IDs renumerados.
- `faroflow seed-demo` → carga `data/seed/demo-workspace.json` (ficticio).
- Snapshots export/import vía API (`/api/v1/snapshots/export|import`); import solo en
  almacén vacío, transaccional, sin fabricar audit.
- Traducciones manuales por entidad. Sin import de CSV/Excel/PDF.

## 4. CuentaFaro (área Finanzas): pantallas de su SPA

`src/cuentafaro/web/static/`: hash-router con Inicio (dashboard), Cuentas, Movimientos/
Egresos, Importar (stepper + drag&drop), Deudas, Simulador (nieve/avalancha),
Presupuesto, Pagos, Tarjetas (estado de cuenta/cuotas/pagos), Metas, Asistente IA,
Avisos, Reportes (resumen/ingresos/gastos/patrimonio/deudas), Configuración.

## 5. Entidades y relaciones de CuentaFaro

Modelos en `src/cuentafaro/models.py` (24 tablas):

`Household → {Member, FinancialAccount, Category, IncomeSource, Debt, Budget,
PaymentPlan, ImportBatch(→Review), AiProposal, Capture, Notification*, FinancialGoal}`
core: `FinancialAccount → Transaction`, `Debt → {DebtPayment, Installment}`,
`Budget → BudgetCategory`, `ImportBatch → Transaction`.

Reglas clave:
- Montos enteros en CLP; nunca float en transacciones/saldos (ADR 0002).
- Transferencias propias: exigen `to_account_id`, y no cuentan como ingreso/gasto.
- Conciliación: `balance_reported` vs `balance_calculated`; duplicados por
  `(account_id, external_id, external_source)` y heurística `(fecha, monto firmado, descripción)`.
- Import: CSV/Excel(`xlrd`, `openpyxl`)/PDF(`pymupdf` + OCR tesseract local),
  pipeline parsed→validated→confirmed, revisión de inválidos/duplicados, reglas de categoría.
- Tarjetas: `statement_day`/`due_day`, cupo, resumen de estado de cuenta desde import.
- Prepuestos: única tupla (household, year, month); metas de ahorro con aportes.
- Asistente local por reglas (`RuleBasedProvider`) + OCR local; sin IA pagada por defecto.
- Capturas (CF4): kind text/audio/image, status pending/needs_input/confirmed/rejected/
  discarded; confirmación humana crea el movimiento.
- Notificaciones: cola programada (upcoming_payment, weekly_summary, budget_deviation,
  monthly_close) con proveedor simulado y `NotificationSend` auditable.
- Auditoría `AuditEvent` inmutable vía listener.
- Backup/restore CLI con verificación `PRAGMA integrity_check`.

## 6. Resultado del cruce de módulos

| Función | Origen | Destino en Faro Flow |
|---|---|---|
| Espacios de trabajo, clientes, proyectos, entregables | faroflow | Trabajo |
| Tareas, trabajo registrado, evidencia | faroflow | Trabajo |
| Agenda, reuniones, preparación, revisión, compromisos | faroflow | Trabajo |
| Brief de mañana, cierre del día, resúmenes | faroflow | Mi día > Trabajo |
| Referencias a documentos (Drive read-only) | faroflow | Trabajo |
| Traducciones manuales | faroflow | Configuración > Idioma |
| Auditoría, snapshots, portabilidad | ambos | Configuración > Datos |
| Capturas trabajo (inbox) | faroflow | Bandeja > tipo Tarea/Nota |
| Hogares, cuentas, instituciones | cuentafaro | Finanzas |
| Ingresos/egresos/transferencias/conciliación | cuentafaro | Finanzas |
| Tarjetas, deudas, cuotas, pagos, próximos pagos | cuentafaro | Finanzas |
| Presupuesto, metas de ahorro, proyecciones | cuentafaro | Finanzas |
| Import CSV/Excel/PDF + revisión | cuentafaro | Finanzas > Importar |
| Asistente por reglas + OCR local | cuentafaro | Finanzas > Asistente |
| Capturas financieras (confirmación) | cuentafaro | Bandeja > tipo Gasto/Ingreso |
| Avisos y plantillas | cuentafaro | Configuración > Avisos |
| Hábitos (nuevo) | — | Hábitos |
| Bandeja común + Telegram/Drive | — | Bandeja |
| Mi día unificado | — | Mi día |

## 7. Pruebas existentes

- faroflow: 28 archivos, 241 funciones — CRUD, dominio, briefs, reuniones,
  clasificación, integraciones, portabilidad, seguridad.
- cuentafaro: 28 archivos, 309 funciones — dominio financiero, importación,
  proyecciones, capturas, avisos, OCR, CLI, web, schema/seed.
- CI existente (faroflow): ruff → pytest → alembic upgrade/downgrade.