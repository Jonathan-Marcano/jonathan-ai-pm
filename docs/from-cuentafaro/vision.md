# Visión de CuentaFaro

Documento de referencia: CF0-05.

## Problema

Administrar ingresos, gastos y deudas conjuntas de una familia sin herramientas
claras genera incertidumbre: no se sabe qué pagos vienen, hacia dónde va el
dinero ni cuál es la mejor ruta para salir de deudas.

## Propuesta

CuentaFaro es una aplicación personal y familiar de finanzas que orienta,
aclara y alerta. El nombre "Faro" refleja su función: ayudar a entender dónde
estamos financieramente, qué pagos vienen y cuál es la mejor ruta para alcanzar
las metas.

## Usuario principal

Jonathan y su esposa, para sus finanzas conjuntas, administradas principalmente
por Jonathan. El diseño (múltiples integrantes del hogar, roles) contempla la
futura conversión en producto comercial sin rediseñar el dominio.

## Ciclo funcional esperado

```text
Plan financiero mensual
  → captura/importación de movimientos
  → clasificación
  → actualización de deudas y presupuesto
  → dashboard
  → cierre mensual
  → nueva proyección
```

## Capacidades objetivo

- Consolidar ingresos, gastos, cuentas, tarjetas, créditos y otras deudas.
- Manejar finanzas conjuntas dentro de un hogar.
- Registrar pagos ordinarios y extraordinarios.
- Presupuestos mensuales por categoría.
- Proyectar estrategias de pago: bola de nieve, avalancha, personalizada,
  escenarios con bonos o ingresos extraordinarios.
- Mostrar próximos vencimientos y compromisos.
- Comparar presupuesto contra gasto real.
- Calcular deuda total, patrimonio neto y evolución mensual.
- Dashboards y resúmenes claros.
- Conservar referencias a comprobantes.
- En el futuro: entradas por WhatsApp (texto, audio, foto), clasificación
  asistida con confirmación humana, y sincronización con la base de datos.
- Funcionar desde teléfono y computadora: aplicación web responsive/PWA.

## Lo que CuentaFaro NO es

- No es un banco: no mueve dinero, ni ejecuta transferencias o pagos.
- No es asesoría financiera profesional garantizada.
- No conecta cuentas bancarias en las primeras fases.
- No es una herramienta de contabilidad formal ni genera informes fiscales.
- No elimina el criterio humano: la IA propone, la persona confirma.

## Fases

1. **Fase 0**: fundación (producto, modelo, seguridad, roadmap).
2. **Fase 1**: MVP manual utilizable con interfaz web responsive.
3. **Fase 2**: importación de CSV/Excel y preparación de PDF.
4. **Fase 3**: asistencia con IA con confirmación humana.
5. **Fase 4**: entrada por WhatsApp y captura rápida.
6. **Fase 5**: producto comercial (múltiples hogares, usuarios, suscripciones).

Las conexiones bancarias reales se evaluarán como una fase posterior
independiente debido a permisos, regulación, seguridad y disponibilidad por país.

## Éxito

CuentaFaro es exitoso cuando Jonathan administra un mes financiero completo de
principio a fin desde el móvil y el computador, sin depender de `curl` ni de la
documentación de la API, con claridad sobre deudas, presupuesto y camino hacia
las metas.