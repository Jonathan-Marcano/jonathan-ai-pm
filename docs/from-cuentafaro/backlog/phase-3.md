# Backlog Fase 3 — Asistencia con IA (tramo sin costo)

> **Estado: Franjas E, F y G entregadas (2026-09-15).** Tramo sin costo completo:
> 205 tests, ruff limpio, migración reversible, CI verde. El tramo pagado sigue
> fuera del backlog y se incorporará como un adaptador `AiProvider` adicional
> sin rediseñar el dominio.

Documento de referencia: CF0-11 (mismo esquema que CF0-10/CF2).

## Alcance y postura de costos

La Fase 3 se construye por tramos. Este backlog cubre **solo el tramo que hoy
no genera costos**: OCR local (Tesseract), clasificación y explicaciones por
reglas locales, sin enviar información financiera a ningún proveedor externo
(exigencia de `privacy-and-data-policy.md`).

El tramo pagado (OpenAI/Anthropic/etc.) queda **fuera** y se incorporará a
futuro **sin rediseñar el dominio**: el ADR 0001 mandata "contratos neutrales
respecto al proveedor, principio de adaptadores". Por eso toda historia de
esta fase implementa funciones de dominio tras una interfaz `AiProvider`, y un
proveedor pagado posterior solo será **un adaptador más** detrás de ese
contrato, con su medidor de tokens y límites de costo.

Regla transversal: **la IA propone, la persona confirma**. Ninguna propuesta
crea, modifica ni anula movimientos sin confirmación humana explícita.

## Priorización

Las historias se agrupan en franjas de entrega. Cada franja es funcionalmente
útil y verificable al cerrar. Todo procesamiento es local y determinista.

### Franja E — Contrato neutral de IA y asistente local (CF3-01 a CF3-03) ✅

> Entregado: `cuentafaro/ai/base.py` (contrato), `cuentafaro/ai/__init__.py`
> (`get_provider`), `cuentafaro/ai/rule_based.py`, endpoint
> `POST /households/{id}/assistant/suggest-category` y propuestas `pending`.

Interfaz `AiProvider`, registro de proveedores por configuración y primer
adaptador local gratuito (reglas) reutilizando la lógica de categorización
importada de CF2-12.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF3-01 | Contrato `AiProvider` (métodos de dominio: sugerir categoría, extraer estado de cuenta, explicar variación, resumir) + registro por `settings` | ADR 0001 | 1 d |
| CF3-02 | Adaptador local `RuleBasedProvider`: clasificación por reglas (reutiliza motor de `import_category_rules`) para movimientos manuales | CF3-01, CF2-12 | 1.5 d |
| CF3-03 | Toda propuesta aterriza pendiente (nunca confirmada): API de sugerencia + cola de confirmación reutilizando `import_reviews` | CF3-02, CF2-10 | 1.5 d |

Total franja: ~4 días. Criterio de salida: desde la API se pide una sugerencia
de categoría para un movimiento y esta queda propuesta sin tocar el dominio.

### Franja F — OCR local y extracción de PDF (CF3-04 a CF3-05) ✅

> Entregado: `cuentafaro/ai/ocr.py` (pymupdf + Tesseract local), `source_kind 'pdf'`
> en `ImportBatch` (migración reversible), contrato `columna_N` reutilizando CF2-01,
> entidad auditable `AiProposal` con `payload`, `status` y `resolved_at`.

Importación asistida de estados de cuenta PDF preparada en CF2 con OCR
local (Tesseract): el texto extraído entra al parser mediante el contrato de
columnas CF2-01 y a la cola de revisión.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF3-04 | Extracción OCR local (PDF → imágenes → texto con Tesseract) + nuevo `ImportBatch.kind` de PDF y parser reutilizando CF2-01 | CF2-01, CF2-03 | 2 d |
| CF3-05 | Registro auditable propuesta → corrección → resultado + límites de costo/tokens y retención (0 para local; medidores listos para proveedor pagado) | CF3-04, CF2-11 | 1.5 d |

Total franja: ~3.5 días. Criterio de salida: subir un PDF escaneado de un
estado de cuenta y que sus filas queden en revisión para confirmar.

### Franja G — Resumen, variaciones y anomalías locales (CF3-06 a CF3-08) ✅

> Entregado: `GET /households/{id}/assistant/insights` (resumen + variaciones +
> anomalías deterministas), propuestas `anomaly`/`budget_adjust` que nunca se
> auto-aplican, `POST /assistant/proposals/{id}/resolve`, y frontend `#/ai`
> (analizar mes, propuestas pendientes, sugerir categoría en el modal de
> movimientos).

Explicaciones y alertas con lógica local (sin LLM), siempre como propuesta.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF3-06 | Resumen del mes y explicación de variaciones (presupuesto vs real, saltos de gasto) vía `AiProvider.explain_variation` local | CF3-01, CF1-23 | 1 d |
| CF3-07 | Detección de anomalías (gastos atípicos por categoría vs histórico) y propuestas de ajuste de presupuesto, sin auto-aplicar | CF3-06, CF1-19 | 1.5 d |
| CF3-08 | Frontend: mostrar resumen/variaciones/anomalías y confirmar propuestas | CF3-07 | 1.5 d |

Total franja: ~4 días. Criterio de salida: el dashboard informa variaciones y
anomalías con texto entendible y permite aceptarlas/rechazarlas.

## Estimación total (tramo sin costo)

- Esfuerzo nominal: ~11.5 días de trabajo.
- Con holgura por integración, revisión y QA: **~3 semanas calendario**.

## Reglas de calidad en Fase 3

- Contrato `AiProvider` neutral: el dominio no importa ningún SDK externo.
- Sin auto-confirmación: propuestas siempre requieren confirmación humana.
- Todo OCR/clasificación local es determinista: misma entrada → mismo resultado.
- Cambios de esquema requieren migración reversible.
- SI/NO de privacidad: ninguna propuesta ni texto financiero sale del proceso
  local mientras no se active un proveedor pagado.
- CI: `ruff check .` → `pytest` → `alembic upgrade/downgrade`.