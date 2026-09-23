# ADR 0002: Dinero, monedas y precisión

- Estado: Aceptado
- Fecha: 2026-09-15

## Contexto

CuentaFaro maneja montos de dinero en múltiples contextos: saldos de cuentas,
movimientos, deudas, cuotas, presupuestos y proyecciones. Los errores de
redondeo o la pérdida de precisión en dinero son inaceptables. La moneda base
confirmada es el peso chileno (CLP), sin decimales en circulación.

## Decisión

### Representación interna

- Todo monto se almacena como **entero** (`int`) en **unidades monetarias menores**:
  centavos de CLP. Como CLP no tiene centavos en circulación, `1` unidad
  representa `1` peso, `1000` representa `$1.000`.
- Está **prohibido el uso de `float`** para dinero en cualquier capa (modelos,
  servicios, API, frontend).
- No se usa `DECIMAL`/`NUMERIC` de SQLite para montos: enteros de 64 bits
  (`BigInteger`/`Integer` con margen) dan precisión exacta y comparaciones simples.
- El límite práctico (CLP) es 9·10^15 centavos, muy por encima de cualquier
  monto real de un hogar.

### Frontera de la API

- En los contratos JSON, los montos viajan como **números enteros**.
- Los montos **no** se convierten a `float` en ningún punto del contrato.
- El campo se documenta con `"type": "integer"` y unidad `"CLP"`.

### Frontera de UI

- El formateo de moneda es exclusivamente de presentación y ocurre en el frontend.
- `$1.234.567` se renderiza a partir del entero `1234567` con
  `Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' })` o equivalente.
- El usuario ingresa montos en pesos; la conversión a unidades se hace al límite
  del formulario y se valida como entero.

### Cómputo

- Sumas, restas y comparaciones se hacen con enteros. Resultados parciales que
  puedan fraccionar (intereses, prórratas) se **redondean hacia el monto más
  cercano al final de cada paso** y el redondeo se documenta en la proyección.
- Tablas de equivalencia: una tarjeta o préstamo en USD se representará con su
  monto en CLP convertido al momento del registro, conservando la referencia
  original. La conversión de divisas se aplaza a una fase posterior.

## Consecuencias

- Los tests usan montos enteros; las expectativas nunca dependen de precisión flotante.
- Las migraciones de base de datos definen montos como enteros, nunca como `REAL`.
- Cualquier cálculo que requiera división documenta su redondeo.
- La moneda base es configurable vía `.env` (`BASE_CURRENCY`), pero el modelo
  asume una única moneda por hogar en esta fase.