# Backlog Fase 1 — MVP manual utilizable

Documento de referencia: CF0-10.

## Priorización

Las historias se agrupan en franjas de entrega. Cada franja es funcionalmente
útil y verificable al cerrar.

### Franja A — Núcleo configurable (CF1-01 a CF1-07)

Base de datos, hogar, miembros, instituciones, cuentas, categorías y fuentes
de ingreso.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-01 | Configuración base del proyecto (`pyproject`, config, db, cli, seed) | CF0-01 | 0.5 d |
| CF1-02 | Modelo de dominio — entidades base (models + migración) | CF1-01 | 1 d |
| CF1-03 | CRUD Household y Members | CF1-02 | 1 d |
| CF1-04 | CRUD Financial Institutions | CF1-02 | 0.5 d |
| CF1-05 | CRUD Financial Accounts | CF1-02, CF1-04 | 1 d |
| CF1-06 | Modelo y CRUD Categories | CF1-02 | 0.5 d |
| CF1-07 | Modelo y CRUD Income Sources | CF1-02 | 0.5 d |

Total franja: ~5 días. Criterio de salida: hogar configurado con miembros,
cuentas, categorías y fuentes de ingreso vía API.

### Franja B — Operación del mes (CF1-08 a CF1-12)

Movimientos, pagos de deuda, deudas, cuotas y presupuesto.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-08 | Modelo y CRUD Transactions | CF1-05, CF1-06 | 1.5 d |
| CF1-09 | Registro de pagos de deuda (ordinario/extraordinario) | CF1-08 | 1 d |
| CF1-10 | Modelo y CRUD Debts | CF1-02 | 1 d |
| CF1-11 | Modelo y CRUD Installments | CF1-10 | 1 d |
| CF1-12 | Presupuesto mensual (Budget + BudgetCategory) | CF1-06, CF1-08 | 1.5 d |

Total franja: ~6 días. Criterio de salida: registrar ingresos, gastos, deudas,
cuotas y pagos del mes por API.

### Franja C — Resúmenes e inteligencia básica (CF1-13 a CF1-17)

Dashboard, próximos pagos, resumen de deuda, patrimonio y cierre mensual.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-13 | Dashboard básico (API) | CF1-08, CF1-10, CF1-12 | 1 d |
| CF1-14 | Próximos pagos y vencimientos | CF1-10, CF1-11 | 0.5 d |
| CF1-15 | Resumen de deuda total | CF1-10 | 0.5 d |
| CF1-16 | Cálculo de patrimonio neto | CF1-05, CF1-10 | 0.5 d |
| CF1-17 | Cierre mensual | CF1-08, CF1-10, CF1-12 | 1.5 d |

Total franja: ~4 días. Criterio de salida: el mes se ve completo y se cierra.

### Franja D — Proyección (CF1-18 a CF1-19)

Estrategias de pago y escenarios con ingresos extraordinarios.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-18 | Estrategias bola de nieve y avalancha | CF1-10 | 2 d |
| CF1-19 | Escenarios con ingresos extraordinarios | CF1-18 | 1 d |

Total franja: ~3 días. Criterio de salida: simulaciones con supuestos visibles
que no modifican el plan activo.

### Franja E — Confiabilidad (CF1-20 a CF1-21)

Auditoría y backup/restore.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-20 | Auditoría inmutable | CF1-01 | 1 d |
| CF1-21 | Backup y restore (snapshots) | CF1-01 | 1 d |

Total franja: ~2 días.

### Franja F — Interfaz web responsive (CF1-22 a CF1-29)

Frontend HTML vanilla + Tailwind CDN sobre la API.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF1-22 | Layout responsive y navegación | CF1-01 | 1 d |
| CF1-23 | Dashboard en frontend | CF1-13 | 1 d |
| CF1-24 | Frontend cuentas e instituciones | CF1-05 | 1 d |
| CF1-25 | Frontend transacciones | CF1-08 | 1 d |
| CF1-26 | Frontend deudas y pagos | CF1-10, CF1-09 | 1.5 d |
| CF1-27 | Frontend presupuesto | CF1-12 | 1 d |
| CF1-28 | Frontend próximos pagos y resumen deudas | CF1-14, CF1-15 | 1 d |
| CF1-29 | Frontend proyecciones | CF1-18, CF1-19 | 1.5 d |

Total franja: ~9 días.

## Estimación total de Fase 1

- Esfuerzo nominal: ~29 días de trabajo.
- Con holgura por integración, revisión y QA: **~6 semanas calendario**.
- Cada historia incluye sus criterios de aceptación (ver CF1 en el plan y tests asociados).

## Reglas de calidad en Fase 1

- Toda regla de dominio se implementa en servicio + prueba + doc.
- Cambios de esquema requieren migración reversible.
- Los datos de prueba son ficticios.
- CI: `ruff check .` → `pytest` → `alembic upgrade/downgrade`.