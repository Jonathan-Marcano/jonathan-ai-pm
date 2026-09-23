# Backlog Fase 2 — Importación de información

Documento de referencia: CF0-11 (nuevo; seguir el esquema de CF0-10).

## Priorización

Las historias se agrupan en franjas de entrega. Cada franja es funcionalmente
útil y verificable al cerrar. Todo CSV/Excel proviene de estados de cuenta
exportados por el usuario (sin conexión con cuentas bancarias reales).

### Franja A — Parser y registro del lote (CF2-01 a CF2-05)

Modelo `ImportBatch`, parser de CSV (stdlib) y Excel (`openpyxl`), y registro
de cada ejecución de importación.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF2-01 | Definir esquema de columnas para importar (contrato de mapeo) | CF0-06 | 1 d |
| CF2-02 | Modelo ImportBatch + migración (estado, archivo, filas, errores) | CF1-02 | 1 d |
| CF2-03 | Parser de CSV con tipos y validación por fila | CF2-02 | 1.5 d |
| CF2-04 | Parser de Excel con `openpyxl` + nueva dependencia | CF2-03 | 1 d |
| CF2-05 | Asociación manual de columnas del archivo al contrato | CF2-03 | 1 d |

Total franja: ~5.5 días. Criterio de salida: subir un CSV/Excel y obtener un
`ImportBatch` con conteo de filas válidas e inválidas, sin afectar el mes.

### Franja B — Idempotencia y vista previa (CF2-06 a CF2-09)

Identidades externas estables, detección de duplicados y preview antes de
confirmar.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF2-06 | Identidad externa de movimientos (external_id + fuente) | CF2-02, CF1-08 | 1 d |
| CF2-07 | Detección de duplicados por identidad y por heurística (saldo/monto/fecha) | CF2-06 | 1.5 d |
| CF2-08 | Vista previa de movimientos y reglas de conciliación (saldo calculado) | CF2-07, CF1-08 | 1.5 d |
| CF2-09 | Confirmar lote → crea Transactions (solo filas válidas) | CF2-08 | 1 d |

Total franja: ~5 días. Criterio de salida: importar el mismo archivo dos veces
sin duplicar movimientos, y confirmar con vista previa.

**Estado: ✅ entregada (commit `72ffedf`)**.

### Franja C — Cola de revisión y categorías (CF2-10 a CF2-12)

Movimientos que requieren revisión y asociación manual de columnas/categorías.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF2-10 | Cola de movimientos pendientes de revisión | CF2-09 | 1.5 d |
| CF2-11 | Resolver fila en revisión (confirmar, corregir o descartar) | CF2-10 | 1.5 d |
| CF2-12 | Asociación manual de categorías en columnas importadas | CF2-11, CF1-06 | 1 d |

Total franja: ~4 días. Criterio de salida: las filas ambiguas quedan en cola y
se resuelven antes de tocar el presupuesto.

**Estado: ✅ entregada.** Confirmar un lote encola las filas
inválidas y los duplicados heurísticos en `import_reviews`; se resuelven con
`POST /import-reviews/{id}/resolve` (confirmar, corregir o descartar). Las
reglas `import_category_rules` asocian texto de columnas a categorías y
sugieren categoría en preview/confirm bajo el hogar.

### Franja D — Frontend de importación (CF2-13 a CF2-15)

Subida, vista previa y confirmación desde la interfaz web responsive.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF2-13 | Pantalla de importación con upload CSV/Excel | CF2-05 | 1.5 d |
| CF2-14 | Listado de lotes y vista previa en frontend | CF2-08 | 1.5 d |
| CF2-15 | Confirmación del lote y revisión desde frontend | CF2-09, CF2-11 | 1.5 d |

Total franja: ~4.5 días.

**Estado: ✅ entregada.** `#/imports` sube CSV/Excel con mapeo de columnas
(CSV lee el encabezado en el navegador y precarga la asociación), lista los
lotes, muestra el preview (validación, duplicados, saldo y categoría sugerida),
confirma el lote y `#/imports/review` resuelve la cola (confirmar/corregir/
descartar) desde el frontend.

## Estimación total de Fase 2

- Esfuerzo nominal: ~19 días de trabajo.
- Con holgura por integración, revisión y QA: **~3-4 semanas calendario**.
- La importación de PDF queda fuera de esta fase: aquí solo se prepara el
  contrato de parser (CF2-01) que reutilizará Fase 3 para OCR.

## Reglas de calidad en Fase 2

- Todo parser es determinista: mismo archivo → mismo resultado.
- Sin conexión con cuentas bancarias reales; los archivos son locales.
- Ninguna fila entra a Transactions sin pasar por validación y preview.
- Cambios de esquema requieren migración reversible.
- CI: `ruff check .` → `pytest` → `alembic upgrade/downgrade`.