# Política de privacidad y datos

Documento de referencia: CF0-04.

CuentaFaro gestiona información financiera sensible. Estas reglas aplican desde
la Fase 0 y son condición para cualquier desarrollo posterior.

## Prohibiciones en cualquier fase

- No guardar datos financieros reales en seeds, fixtures, ejemplos, commits ni CI.
- No guardar números completos de tarjetas o cuentas bancarias.
- No guardar contraseñas, PIN, tokens bancarios ni credenciales.
- No guardar secretos de API en el repositorio; solo viajan en `.env` local.
- No ejecutar transferencias, pagos ni movimientos bancarios desde la aplicación.
- No conectar bancos, WhatsApp o proveedores de IA sin gate de decisión explícito.
- No enviar información financiera a un proveedor externo sin confirmación explícita del usuario.

## Tratamiento de datos

| Tipo de dato | Tratamiento |
|---|---|
| Movimientos, deudas, presupuestos | Se guardan localmente en la base de datos de la aplicación |
| Saldos informados por instituciones | Se guardan como dato informado, diferenciado del saldo calculado |
| Comprobantes y estados de cuenta | Solo referencias/enlaces; el contenido no se copia al operativo |
| Credenciales de proveedores (futuro) | Solo variables de entorno o adminrador de secretos aprobado; jamás en BD o logs |
| Mensajes de WhatsApp (futuro) | No permanecen en la base; se descartan tras el procesamiento confirmado |
| Propuestas de IA (futuro) | Son propuestas; requieren confirmación humana antes de persistir |

## Redacción y logs

- Un filtro de logging redacta tokens, contraseñas, PIN, secretos, API keys y
  credenciales bearer de todos los handlers configurados.
- Los errores de sincronización se persisten redactados; el cuerpo de la
  respuesta del proveedor nunca entra en logs persistentes.
- Los montos pequeños y categorías son sensibles por contexto: los logs no
  deben incluir valores de movimientos salvo que sea estrictamente necesario
  para depuración autorizada.

## Retención y eliminación

- La base de datos local se conserva mientras el hogar esté activo.
- Las eliminaciones de registros operativos deben ser recuperables o usar
  estados de anulación (las eliminaciones fuertes solo por procedimiento
  específico y documentado).
- La eliminación completa de datos requiere procedimiento OS-level aprobado
  (borrado de la base local y todos los snapshots exportados), no solo una
  llamada a la API.
- Política de retención de propuestas de IA y de sincronizaciones se define
  en la fase correspondiente antes de activar la integración.

## Registro de quién modifica

- Toda modificación relevante queda auditada con actor, instante y valores
  antes/después (AuditEvent inmutable, misma transacción que el cambio).

## Backups

- Los snapshots y backups contienen información confidencial.
- Viven fuera del repositorio (`backups/` ignorado por Git), con permisos
  restringidos (0600/0700 donde el SO lo soporte).
- Backup y restore usan el contrato validado de exportación/importación.
- Se prueba la restauración periódicamente; un backup nunca restaurado no es verificado.

## Advertencia

CuentaFaro ofrece cálculos y escenarios de apoyo. No constituye asesoría
financiera profesional garantizada. Las proyecciones muestran sus supuestos y
simulan posibilidades, no prometen resultados.

## Regla de oro

La IA y las automatizaciones pueden **proponer**, nunca **confirmar**.
La confirmación de movimientos, clasificaciones y decisiones es siempre humana.