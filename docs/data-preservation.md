# Preservación de datos (Fase 0)

Procedimiento probado sobre una copia (no destructivo). Objetivo: poder restaurar el
estado de trabajo o de finanzas tras cualquier integración o incidente local.

## Respaldo consistente

```bash
# Dominio Trabajo + módulos unificados (misma base que respalda Hábitos/Bandeja)
uv run faroflow backup [--path backups/faroflow-<ts>.snapshot.json]

# Dominio Finanzas (copie SQLite completa con sello)
uv run cuentafaro backup [--path backups/cuentafaro-<ts>.db]
```

Ambos escriben archivos privados (`0o600`), en directorio `0o700`, y respetan
`*.snapshot.json` / `*.db` en `.gitignore`: nunca se versionan datos.

## Restauración probada (dominio trabajo)

El snapshot de trabajo es un JSON versionado (`schema_version 1.1`) que conserva IDs
y timestamps originales. La restauración requiere un almacén vacío (diseño actual de
`import_snapshot`). Procedimiento verificado en este repositorio:

1. Descargar el snapshot (el nuestro: `backups/faroflow-20260923T005252Z.snapshot.json`).
2. Crear base vacía y ejecutar `alembic upgrade head`.
3. Importar: `GET/POST /api/v1/snapshots` o directamente
   `faroflow.portability.import_snapshot(session, SnapshotDocument...)`.
4. Re-exportar y comparar conteos por entidad.

Verificación ejecutada:

```text
before : {'workspaces': 1, 'clients': 1, 'projects': 1, 'deliverables': 1,
          'tasks': 1, 'meetings': 1, 'action_items': 1, 'work_logs': 0,
          'captures': 2, 'translations': 0, 'audit_events': 9}
after  : idéntico
round-trip preserved: True
```

## Restauración (dominio finanzas)

`uv run cuentafaro restore --path backups/cuentafaro-<ts>.db` valida el sello del
nombre, ejecuta `PRAGMA integrity_check` (debe ser "ok") y luego corre
`alembic upgrade head` sobre la copia restaurada. No se ejecutó aún sobre datos
reales (no existen datos reales de finanzas en este equipo); la prueba aparece en
Fase 12.

## Salvaguardas antes de migrar

- Ninguna migración es destructiva: cada dominio usa su propia cadena y aquí solo se
  añaden tablas nuevas en la cadena de trabajo.
- Antes de cualquier cambio de esquema: generar snapshot fresco y dejarlo fuera de
  Git.
- No se escriben credenciales ni datos financieros reales en seeds/commits.