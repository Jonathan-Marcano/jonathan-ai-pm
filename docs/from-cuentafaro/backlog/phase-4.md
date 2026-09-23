# Backlog Fase 4 — WhatsApp y captura rápida

Documento de referencia: CF0-11 (mismo esquema que CF0-10/CF2/CF3).

## Alcance y postura de costos

La Fase 4 integra mensajería para capturar gastos e ingresos con texto, audio
o imagen y para enviar recordatorios y resúmenes. Al igual que Fase 3, se
construye por tramos y **solo el tramo que hoy no genera costos**:

- Contrato de mensajería neutral e independiente del proveedor (ADR 0001).
- Capturas que entran al dominio y quedan **pendientes de confirmación humana**.
- Extracción de texto de imágenes con **OCR local** (reutiliza Fase 3) y
  transcripción de audio solo con herramientas **locales opcionales**.
- Entrega simulada de recordatorios/resúmenes (consola/log), sin enviar nada
  a una red real.

El tramo concreto (WhatsApp Business Platform / **Cloud API oficial**,
autenticación con token, plantillas aprobadas y webhooks) queda **fuera** de
este backlog y se conectará como **un adaptador `MessagingProvider` más**,
sin rediseñar el dominio. No se usan librerías no oficiales de WhatsApp.

Regla transversal (heredada de Fase 3): **la máquina propone, la persona
confirma**. Ninguna captura crea, modifica ni anula movimientos sin confirmación
humana explícita. Toda captura queda registrada de forma auditable.

## Priorización

### Franja A — Capturas pendientes y contrato neutral (CF4-01 a CF4-03) ✅

Entrada de capturas (simulando WhatsApp por API local), almacenadas como
pendientes, bajo un contrato de mensajería neutral.

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF4-01 | Contrato `MessagingProvider` (enviar mensaje/plantilla) + registro por `settings` y adaptador simulado local | ADR 0001 | 1 d |
| CF4-02 | Modelo `Capture` (hilo/canal, tipo texto/audio/imagen, contenido, estado pendiente/confirmado/rechazado/descartado, transacción ligada) + migración | CF4-01, CF1-25 | 1.5 d |
| CF4-03 | API para ingresar capturas pendientes y listarlas (bandeja), con canal `simulated` | CF4-02 | 1 d |

### Franja B — Extracción local y propuesta de movimiento (CF4-04 a CF4-05) ✅

La captura se convierte en **propuesta** que la persona confirma, corrige o
descarta. Reutiliza OCR (Fase 3) y clasificación por reglas (CF2-12).

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF4-04 | Extracción: texto directo, OCR local (Tesseract) para imágenes y transcripción local opcional para audio; contenido sin transcribir pasa a revisión manual | CF4-02, CF3-04 | 1.5 d |
| CF4-05 | Captura → propuesta de movimiento (fecha/monto/descripción + categoría por `RuleBasedProvider`) → confirmar/corregir/descartar persistiendo la transacción | CF4-03, CF2-12 | 1.5 d |

### Franja C — Recordatorios y resumen (CF4-06 a CF4-08) ✅

Generación programada de recordatorios de pagos, resumen semanal, aviso de
desviación y solicitud de cierre de mes, entregados por el adaptador (simulado
en este tramo).

| ID | Historia | Dependencias | Esfuerzo |
|---|---|---|---|
| CF4-06 | Plantillas de notificación en el dominio (pago próximo por vencer, resumen semanal, desviación vs presupuesto, solicitud de cierre) | CF4-01, CF1-26 | 1.5 d |
| CF4-07 | Programador de notificaciones (colas de salida + ejecución por fecha) y registro auditable de envíos | CF4-06 | 1.5 d |
| CF4-08 | Frontend: bandeja de capturas (confirmar/corregir/descartar) e historial + gestión de recordatorios | CF4-05, CF4-07 | 1.5 d |

### Franja D — WhatsApp Cloud API oficial (fuera de este tramo)

Con credenciales operativas: webhook de recepción firmado, envío por Cloud API
con plantillas aprobadas, verificación de firma y reenvío a la bandeja. Es
**un adaptador `MessagingProvider`**; el dominio no cambia. No se planifica
hasta decidir activar WhatsApp real (costos y aprobación Meta).

## Estimación total (tramo sin costo)

- Esfuerzo nominal: ~11.5 días de trabajo.
- Con holgura por integración, revisión y QA: **~3 semanas calendario**.

## Reglas de calidad en Fase 4

- Contrato `MessagingProvider` neutral: el dominio no importa ningún SDK externo.
- Sin auto-confirmación: las capturas requieren confirmación humana.
- OCR/transcripción local y determinista; mismo insumo → mismo resultado.
- Cambios de esquema requieren migración reversible.
- Privacidad: nada sale del proceso local mientras el proveedor sea simulado.
- CI: `ruff check .` → `pytest` → `alembic upgrade/downgrade`.