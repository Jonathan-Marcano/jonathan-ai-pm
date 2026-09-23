# ADR 0004 — Faro Flow unificado: arquitectura y separación de dominios

- Fecha: 2026-09-22
- Estado: Aceptado (Fase 0)

## Contexto

Faro Flow surge de dos productos locales: el asistente de trabajo (repositorio base,
ex Jonathan AI PM) y el gestor financiero CuentaFaro. Ambos son aplicaciones FastAPI
+ SQLAlchemy 2 + SQLite + Alembic + SPA vanilla con convenciones casi idénticas
(identificadores, auditoría, capturas, seguridad, uv/ruff/pytest). Debe construirse
un solo producto con seis áreas: Mi día, Trabajo, Finanzas, Hábitos, Bandeja y
Configuración, sin perder módulos ni datos.

## Decisión

1. **Repositorio base:** el repositorio actual (Jonathán AI PM, ya renombrado
   FaroFlow). Contiene el shell web, el dominio de trabajo completo y el contrato de
   mensajería/Drive que la Bandeja necesita.

2. **Incorporación de CuentaFaro con trazabilidad:** el paquete `src/cuentafaro`,
   sus migraciones, pruebas, seed, docs y schema se integran en este repositorio
   copiados desde el commit `3169694` de
   `https://github.com/Jonathan-Marcano/cuentafaro`. La trazabilidad se conserva en
   este ADR y en `docs/from-cuentafaro/`. No se reescribe lógica existente: se
   reutilizan servicios, reglas y pruebas tal cual.

3. **Separación interna Trabajo / Finanzas:** dos bases SQLite locales con cadenas
   de migración independientes:
   - `src/faroflow` + `migrations/` → dominio Trabajo + nuevos módulos (Hábitos,
     Bandeja, estado unificado). DB `DATABASE_URL` (default
     `sqlite:///data/local/faroflow.db`).
   - `src/cuentafaro` + `finance_migrations/` (alembic_finance.ini) → dominio
     Finanzas intacto. DB `CUENTAFARO_DATABASE_URL` (default
     `sqlite:///data/local/cuentafaro.db`).
   - La app unificada aloja los routers de finanzas bajo `/api/v1/finance`
     (rutas limpias: `/api/v1/finance/households`, ...). Los routers de CuentaFaro
     dejaron de llevar `prefix="/api/v1"`; esa versión la aporta la app standalone
     (`cuentafaro.api.create_app`), que envuelve los routers en un `APIRouter` de
     prefijo `/api/v1`. Así, la app standalone y sus pruebas se conservan intactas y
     el producto unificado expone /api/v1/finance sin prefijos duplicados. Los
     exception handlers de CuentaFaro se registran en la app unificada.
   - La separación por archivo evita unir dos historias de migración con riesgo
     destructivo e independiza respaldos por dominio.

4. **Resolución de conflictos:**
   - **Rutas:** el sub-app de finanzas vive bajo `/api/v1/finance`; las rutas de
     trabajo siguen en `/api/v1`. No hay colisión de rutas globales.
   - **Configuración:** `CUENTAFARO_DATABASE_URL` desambigua la persistencia. El
     resto de variables se comparten con nombres idénticos por diseño.
   - **Dependencias:** las de `pyproject.toml` de CuentaFaro se fusionaron en
     `pyproject.toml` de Faro Flow (pymupdf, openpyxl, xlrd, Pillow, pytesseract,
     python-multipart). CLI `cuentafaro` preservado.
   - **Migraciones:** cadenas paralelas (`migrations/` y `finance_migrations/`).
   - **Esquemas:** `schemas/domain-model.schema.json` es de trabajo;
     `schemas/cuentafaro-domain-model.schema.json` es de finanzas y es el que usan
     `cuentafaro.seed` y sus pruebas (resolución compatible con uso standalone).
   - **Pruebas:** `tests/` (trabajo) y `tests_finance/` (finanzas) con pytest
     `--import-mode=importlib`.

5. **Módulos nuevos** (Hábitos, Bandeja, Mi día, Configuración central) se
   implementan en `src/faroflow` como módulos nuevos con sus propias migraciones en
   la cadena de trabajo, y leen de la base de finanzas mediante una sesión aislada
   de CuentaFaro (bridge de solo lectura para resúmenes).

6. **No se introducen microservicios.** Una sola app FastAPI local. Telegram/Drive
   son vía Apps Script y API de Drive (ver fases 6–8), sin puertos entrantes.

## Consecuencias

- Un producto, dos archivos de datos locales y dos panoramas de respaldo.
- El sub-app de finanzas conserva todas sus rutas originales bajo `/api/v1/finance`,
  preservando las pruebas de CuentaFaro sin cambios.
- Migraciones destructivas quedan fuera: cada dominio aplica solo su cadena.
- La SPA unificada sustituye a las dos SPAs y reconstruye cada pantalla de finanzas
  contra `/api/v1/finance`. La SPA heredada de CuentaFaro sigue disponible solo en la
  app standalone (`cuentafaro.api.app`), que conserva sus pruebas.