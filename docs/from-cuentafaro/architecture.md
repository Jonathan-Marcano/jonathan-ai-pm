# Arquitectura

Documento de referencia: CF0-06.

## Arquitectura lógica

CuentaFaro sigue un modelo en capas inspirado en la referencia técnica
Jonathan AI PM, adaptado al dominio financiero.

```text
Interaction layer
  Dashboard | Captura | Reportes | Configuración
        |
Application services
  Household | Budget | Debt | Projection | Transaction | Import | Report
        |
Domain model
  Household | HouseholdMember | FinancialAccount | Transaction | Category
  IncomeSource | Budget | BudgetCategory | Debt | DebtPayment | Installment
  FinancialGoal | PaymentPlan | ProjectionScenario | DocumentReference
  ImportBatch | AuditEvent
        |
Ports/adapters
  Local DB (SQLite dev) | PostgreSQL (fase 5)
  CSV/Excel importer (fase 2) | PDF assistant (fase 2)
  LLM provider (fase 3) | WhatsApp Cloud API (fase 4)
```

## Responsabilidades por componente

| Componente | Responsabilidad | Fase |
|---|---|---|
| Domain model | Identidad, relaciones, estados y reglas de validación de entidades financieras | 1 |
| Seed fixtures | Dataset sintético repetible para desarrollo y tests | 0 |
| Household service | Creación del hogar y sus miembros | 1 |
| Account service | Cuentas, instituciones y saldos informados/calculados | 1 |
| Transaction service | Ingresos, gastos, transferencias, pagos y ajustes | 1 |
| Debt service | Deudas, cuotas y pagos ordinarios/extraordinarios | 1 |
| Budget service | Presupuesto mensual por categoría y comparación con real | 1 |
| Dashboard service | Resúmenes, deuda total, patrimonio neto, próximos pagos | 1 |
| Projection service | Estrategias de pago y escenarios | 1 |
| Report/Close service | Cierre mensual y reportes | 1 |
| Audit recorder | Registro inmutable de cambios en la misma transacción | 1 |
| Portability service | Exportación/importación de snapshots | 1 |
| Importer | Importación de CSV/Excel; identidades estables; cola de revisión | 2 |
| IA / WhatsApp adapters | Proponen/extraen; nunca confirman; gate de decisión explícito | 3-4 |

## Fronteras

- La lógica de dominio no depende de un proveedor externo (bancos, IA, WhatsApp).
- El código de integración usa adaptadores detrás de interfaces estables.
- Las identidades externas se guardan por separado con `source_system`,
  `external_id` y `last_synced_at` para sincronización idempotente.
- Toda importación tiene registro durable (`ImportBatch`), conserva referencia
  a la fuente y señala movimientos duplicados.
- Toda automatización produce una propuesta; la persistencia requiere confirmación humana.
- Una simulación nunca reemplaza el plan activo sin confirmación.
- Los timestamps se almacenan en UTC y se renderizan con `APP_TIMEZONE`.
- Un pago no puede modificar silenciosamente el saldo original informado.

## Seguridad y privacidad

- Credenciales solo en variables de entorno o secret store aprobado.
- Los logs redactan secretos y datos sensibles por defecto.
- Los fixtures son completamente ficticios.
- Los backups y snapshots viven fuera del repositorio.
- Las eliminaciones son recuperables o por anulación.

Ver [Política de privacidad y datos](privacy-and-data-policy.md).

## Dirección de despliegue

Fase 1 comienza como una aplicación modular de un solo usuario con almacenamiento
relacional (SQLite local). Un monólito modular mantiene simple el despliegue y la
observabilidad mientras el dominio se estabiliza. Servicios separados solo se
justifican por escala medible, aislamiento de seguridad o ciclo de vida independiente.
La migración a PostgreSQL se planifica para la fase comercial (Fase 5). El despliegue
local del MVP usa `uvicorn` directo.