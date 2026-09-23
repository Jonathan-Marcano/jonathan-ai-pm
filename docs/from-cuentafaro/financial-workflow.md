# Workflow financiero

Documento de referencia: CF0-08.

## Ciclo mensual

```text
Plan financiero mensual
  → captura/importación de movimientos
  → clasificación
  → actualización de deudas y presupuesto
  → dashboard
  → cierre mensual
  → nueva proyección
```

## Detalle por etapas

### 1. Plan financiero mensual

- Se define el presupuesto del mes (estado `draft` → `active`).
- Se registran fuentes de ingreso esperadas y su monto.
- Se identifican pagos programados del mes (cuotas de deudas).

### 2. Captura de movimientos

- Ingresos, gastos, transferencias y pagos se registran manualmente (MVP).
- En fases posteriores: importación CSV/Excel (F2), captura WhatsApp (F4).
- Toda captura conserva la referencia a su fuente (batch de importación).

### 3. Clasificación

- Cada movimiento se asigna a una categoría del tipo correcto
  (ingreso/gasto/transferencia).
- Con IA (fase 3): la clasificación es una propuesta que la persona confirma
  antes de persistir.

### 4. Actualización de deudas y presupuesto

- Los gastos actualizan `actual_amount` del presupuesto por categoría.
- Los pagos de deuda actualizan `current_balance` de la deuda y el
  `balance_calculated` de la cuenta; nunca el saldo informado.
- Las transferencias entre cuentas propias se registran sin afectar ingreso/gasto.

### 5. Dashboard

- Resumen del mes: ingresos, gastos, balance, deuda total, patrimonio neto.
- Comparación presupuesto vs real.
- Próximos vencimientos.
- Evolución y métricas.

### 6. Cierre mensual

- Se verifica que los pagos del mes estén registrados.
- Se calcula el balance final.
- El presupuesto pasa a `closed`; las cuotas se marcan pagadas o impagas.
- Se genera el resumen del cierre para la proyección siguiente.

### 7. Nueva proyección

- Con base en saldos y deudas actuales se proyectan estrategias
  (bola de nieve, avalancha, personalizada, con bonos).
- La simulación muestra supuestos y nunca reemplaza el plan activo sin confirmación.

## Reglas transversales

- La aplicación no ejecuta transferencias, pagos ni movimientos bancarios.
- Toda modificación relevante queda auditada (actores están registrados).
- Las eliminaciones son recuperables o usan estados de anulación.
- Los timestamps son UTC; la presentación usa `APP_TIMEZONE`.

Ver [Modelo de datos](data-model.md) para estados de cada entidad y
[Política de privacidad](privacy-and-data-policy.md).