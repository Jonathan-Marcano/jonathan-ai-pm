# Sistemas de registro

Documento de referencia: CF0-14.

## Propietarios de la información

| Información | Sistema de registro |
|---|---|
| Código, esquemas y decisiones técnicas versionadas | GitHub (`Jonathan-Marcano/cuentafaro`) |
| Documentación colaborativa y planificación | Google Drive (carpeta `CuentaFaro`) |
| Estado operativo financiero (movimientos, deudas, presupuestos) | Datastore de CuentaFaro (base local) |
| Documentos y comprobantes originales | Fuente original; CuentaFaro guarda solo referencias |
| Mensajes originales (futuro, WhatsApp) | Canal de origen; no permanecen en la base |

## Principio

GitHub es la fuente de verdad para el código y la documentación técnica
versionada (incluidos los ADR). Google Drive es el espacio de trabajo
colaborativo y de planificación (narrativa de producto, análisis de deudas,
minutas). Un artefacto vive en un solo lugar: los enlaces en el otro sistema
solo referencian, no duplican.

## Convenios

- Las decisiones de arquitectura se registran como ADR en
  `docs/decisions/` y se versionan en GitHub.
- Los backlogs priorizados viven en `docs/backlog/` en GitHub.
- Los documentos colaborativos alineados con el producto viven en Drive.
- Los datos sensibles (estado de cuentas, movimientos reales) nunca entran a
  GitHub ni a Drive compartido.
- La base de datos local es el único lugar donde el estado financiero operativo
  se escribe y se lee.

## Carpetas sugeridas en Drive (carpeta `CuentaFaro`)

```
CuentaFaro/
├── 01 - Vision y Estrategia     # Visión, análisis de producto
├── 02 - Planificacion           # Planes, minutas, decisiones operativas
├── 03 - Analisis de deudas      # Simulaciones y hojas de trabajo
├── 04 - Documentos de referencia
└── 05 - Backups                 # Copias de respaldo (uso privado)
```