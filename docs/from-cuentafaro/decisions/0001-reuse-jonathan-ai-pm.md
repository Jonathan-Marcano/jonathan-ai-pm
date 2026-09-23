# ADR 0001: Reutilización de componentes de Jonathan AI PM

- Estado: Aceptado
- Fecha: 2026-09-15

## Contexto

CuentaFaro nace como aplicación independiente de finanzas personales. Existe
una referencia técnica madura, Jonathan AI PM, con patrones de arquitectura,
documentación y calidad probados. Antes de modelar el dominio financiero hay
que decidir qué se reutiliza y qué se excluye para no contaminar CuentaFaro
con lógica de gestión de proyectos ni acoplar ambos repositorios.

Jonathan AI PM se mantiene intacto: no se modifica, ramifica ni se usa su
repositorio o Drive como destino.

## Decisión

Se reutilizan como **patrón de referencia** (reimplementación adaptada, no
copia de código dependiente), los siguientes componentes:

### Reutilizados como patrón

| Componente | Reutilización |
|---|---|
| Estructura del repositorio | Mismo esqueleto: `src/`, `docs/`, `migrations/`, `schemas/`, `data/seed/`, `tests/` |
| Stack base | Python ≥3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings, SQLite (dev), pytest, Ruff, `uv` |
| `pyproject.toml` | Misma filosofía de dependencias y configuración de calidad |
| Configuración con `.env` | Mismo patrón de Pydantic Settings y `.env.example` |
| Redacción de secretos en logs | Mismo filtro de logging |
| Auditoría inmutable | Auditoría en la misma transacción que el cambio de dominio |
| Snapshots de exportación/restauración | Mismo contrato portátil validado |
| Datos seed sintéticos | Misma disciplina de fixtures completamente ficticios |
| Contratos neutrales respecto al proveedor | Mismo principio de adaptadores (para IA y WhatsApp en fases posteriores) |
| Integraciones con confirmación humana | Mismo principio: la máquina propone, la persona confirma |
| Historial de sincronizaciones | Mismo registro auditable (definido hasta Fase 2) |
| Documentación (arquitectura, workflows, roadmap, ADR) | Misma estructura y convenciones de numeración |
| CI | Mismo pipeline: ruff → pytest → migraciones ascendente/descendente |
| Numeración de historias | `CF0-xx`, `CF1-xx` con criterios de aceptación |

### Excluidos (no se trasladan)

| Componente | Razón |
|---|---|
| Workspaces / Jobs, Clients, Projects, Deliverables | Dominio de gestión de proyectos |
| Meetings, Action Items | Reuniones e seguimientos |
| Work Logs, Captures | Registro de trabajo y captura de tareas |
| Morning Brief, Evening Close | Ciclo diario de trabajo |
| Rule-specific tareas (prioridad, completar con nota, etc.) | Reglas de dominio de proyectos |
| Integraciones de calendario (Microsoft 365 adapter, reconciliation, associations) | Integración propia de trabajo |
| Translations | Traducciones no requeridas en el alcance inicial financiero |
| ExternalIdentity / SyncRun / SyncRunError | Contratos de calendario; se rediseñan para importaciones en Fase 2 |
| Carpeta `src/jonathan_ai_pm/` como destino | CuentaFaro es un paquete independiente `src/cuentafaro/` |

## Consecuencias

- CuentaFaro comparte convenciones, no código compartido ni dependencia de build.
- Cada proyecto evoluciona con git history independiente.
- Los patrones genéricos (stack, auditoría, snapshots, seguridad) se reimplementan
  en el contexto financiero de CuentaFaro.
- Revisar una decisión posterior en un ADR no requiere cambios en el otro proyecto.