# Estrategia de pruebas

Documento de referencia: CF0-13.

## Principios

- Los datos de prueba siempre son ficticios; nunca se usan datos financieros reales.
- El dominio, y no solo los endpoints HTTP, es el objetivo central de validación.
- Toda regla de dominio se valida donde se implementa (servicio) y se documenta
  en el mismo cambio.
- Un test que no corre en CI no existe.

## Niveles

### 1. Validación de contrato (Fase 0)

- El seed `data/seed/demo-household.json` se valida contra el JSON Schema
  `schemas/domain-model.schema.json`.
- Un cambio de contrato sin actualizar el seed rompe CI.

### 2. Persistencia e integridad referencial

- Foreign keys: huérfanos rechazados; registros referenciados no se eliminan.
- Restricciones: estados, montos no negativos, unicidad.
- Migraciones: `upgrade head` sobre BD limpia, luego `downgrade base`, luego
  `upgrade head` de nuevo (reversibilidad).

### 3. Reglas de dominio (unit tests sobre servicios)

- Montos enteros: nunca `float`; transferencias que no alteran ingreso/gasto;
  pagos que actualizan deuda y cuenta pero nunca el saldo informado.
- Reglas de ciclo: creación de presupuesto, registro de pago, cierre mensual,
  anulación de movimientos.
- Reglas de proyección: orden bola de nieve vs avalancha; supuestos visibles;
  una simulación no reemplaza el plan activo.

### 4. API (integration tests)

- Endpoints devuelven los contratos documentados.
- Errores: 404 (no existe), 409 (conflicto de relación), 422 (rechazo de dominio).
- Auditoría: cada cambio relevante emite un AuditEvent en la misma transacción.

### 5. Portabilidad

- Export → import: salida del export cumple el contrato e importa solo en datastore vacío.
- Redacción: los logs no contienen secretos ni datos sensibles.

### 6. CI

GitHub Actions valida en cada push/PR:

```bash
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

## Estructura de tests

```
tests/
├── test_schema.py              # Valida seed contra JSON Schema
├── test_persistence.py         # Integridad referencial y restricciones
├── test_domain_rules.py        # Reglas de negocio del dominio
├── test_api.py                 # Contratos HTTP y errores
├── test_audit.py               # Auditoría inmutable
├── test_portability.py         # Snapshot export/import
└── test_projection.py          # Estrategias de pago y escenarios
```

## Criterios de terminación

Una historia de Fase 1 se considera completa solo cuando:

1. La funcionalidad está implementada en API/servicio.
2. Los tests correspondientes la cubren.
3. La documentación relevante se actualizó.
4. `ruff check .` y `pytest` pasan.