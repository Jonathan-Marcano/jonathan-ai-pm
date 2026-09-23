# Roadmap

Documento de referencia: CF0-09.

## Fase 0 — Fundación (2026-09)

Objetivo: definir el producto antes de implementar funciones financieras.

- Repositorio independiente y convenciones de calidad.
- Visión, límites, arquitectura, modelo de datos y workflow.
- ADRs (reutilización, dinero/precisión).
- Política de privacidad y datos.
- JSON Schema del dominio y seed ficticio.
- Backlog priorizado de Fase 1 y estrategia de pruebas.

Salida: repositorio `cuentafaro` con documentación completa y CI verificado.

## Fase 1 — MVP manual utilizable ✅ (2026-09)

Objetivo: administrar un mes financiero completo sin usar `curl`. **Completada.**

- Hogar, miembros, cuentas e instituciones.
- Categorías, fuentes de ingreso y movimientos.
- Deudas, cuotas y pagos (ordinarios y extraordinarios).
- Presupuesto mensual y comparación con real.
- Dashboard, próximos pagos, deuda total y patrimonio neto.
- Cierre mensual.
- Proyección de pago: bola de nieve, avalancha, escenarios con bonos.
- Auditoría, backup y restore.
- Interfaz web responsive (teléfono y computadora).

Salida: MVP usable por Jonathan de extremo a extremo.
Estimación: ~6 semanas.

## Fase 2 — Importación de información

- Importar CSV y Excel.
- Importar cartolas de **tarjeta de crédito**: detección del resumen del estado de
  cuenta (Total a pagar, Pago mínimo, vencimiento, deuda total y cupo) y
  asociación automática de las compras a los gastos del mes y de la deuda
  vinculada a la cuenta de tarjeta.
- Preparar importación asistida de estados de cuenta PDF.
- Registrar cada ejecución de importación (`ImportBatch`).
- Identidades externas estables e idempotencia contra duplicados.
- Vista previa antes de confirmar y reglas de conciliación.
- Cola de movimientos que requieren revisión.
- Asociación manual de columnas y categorías.
- Sin conexión con cuentas bancarias reales.

## Fase 3 — Asistencia con IA

> **Tramo sin costo entregado (2026-09-15):** contrato `AiProvider` neutral,
> asistente local por reglas, OCR de PDF local, propuestas siempre pendientes
> con confirmación humana, resumen del mes, anomalías y ajustes de presupuesto
> como propuesta. Detalle: `docs/backlog/phase-3.md`.

- Contrato neutral para proveedores de IA.
- Clasificación sugerida, extracción y OCR con confirmación humana.
- Explicación de variaciones, resúmenes, detección de anomalías y
  propuestas de ajuste de presupuesto.
- Límites de costos, tokens y retención; registro de propuesta → corrección → resultado.
- Nunca confirmar movimientos o decisiones automáticamente.

## Fase 4 — WhatsApp y captura rápida

- Solo WhatsApp Business Platform / Cloud API oficial.
- Texto, audio o imagen → captura pendiente → extracción/transcripción →
  propuesta → confirmación → base de datos → dashboard.
- Recordatorios de pagos, resumen semanal, aviso de desviación y solicitud de cierre.
- Sin librerías no oficiales.

## Fase 5 — Producto comercial

- Múltiples hogares, usuarios, roles, aislamiento de datos y autenticación robusta.
- Cifrado, backups remotos, suscripciones y límites por plan.
- Onboarding, consentimiento, exportación/eliminación y telemetría sin datos sensibles.
- PostgreSQL y despliegue seguro con soporte y recuperación ante fallos.

## Posterior (independiente)

- Conexiones bancarias reales (evaluación por permisos, regulación, seguridad y país).

## Dependencias entre fases

- Fase 1 depende de los contratos de Fase 0.
- Fase 2 necesita el modelo transaccional de Fase 1 (movimientos y cuentas).
- Fase 3 necesita el ciclo de confirmación humana y la cola de revisión de Fase 2.
- Fase 4 necesita el contrato de propuestas de Fase 3 para confirmar entradas.
- Fase 5 necesita estabilizar el dominio (Fases 1-4) antes de multiusuario y cobros.