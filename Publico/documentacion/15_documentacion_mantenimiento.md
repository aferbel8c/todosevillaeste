# Documentación de Mantenimiento - TodoSevillaEste

## 1. Objetivo

Definir tareas recurrentes para mantener TodoSevillaEste estable, seguro, actualizado y recuperable.

## 2. Tareas diarias

- Comprobar que `/frontend.html` carga.
- Comprobar que `/places` responde.
- Revisar estado del stack en admin.
- Revisar tickets nuevos.
- Revisar reportes de reseñas.
- Revisar logs de errores.
- Confirmar que la API de agentes responde si IA está activa.

## 3. Tareas semanales

- Revisar usuarios nuevos y posibles abusos.
- Revisar negocios pendientes o inactivos.
- Revisar feedback.
- Revisar almacenamiento de imágenes y adjuntos.
- Revisar espacio en disco.
- Revisar backups.
- Revisar versiones APK activas.
- Comprobar que las rutas de prueba no apuntan a snapshots obsoletos.

## 4. Tareas mensuales

- Probar restauración de backup.
- Revisar secretos y credenciales.
- Revisar dependencias npm/Python/Gradle.
- Revisar política de cookies y privacidad si hubo cambios.
- Limpiar memoria IA incorrecta.
- Revisar logs antiguos.
- Revisar permisos de archivos.
- Probar build Android si se mantiene publicación APK.

## 5. Backups

Debe copiarse:

- Base de datos completa.
- `web_versions.json`.
- `android_versions.json`.
- `visibility_config.json`.
- `admin_auth_config.json`.
- `admin_sessions.json` si se requiere continuidad.
- `data/learning_memory.json`.
- `web/img`.
- `web/downloads`.
- Snapshots activos de `web/versions_web`.
- Configuración `.env` guardada de forma segura.

Frecuencia recomendada:

- DB: diaria.
- Archivos subidos: diaria o incremental.
- Configuración: tras cada cambio.
- Snapshots/versiones: antes de publicar.

## 6. Publicación de nueva web

Flujo:

1. Hacer backup.
2. Crear o sincronizar snapshot desde admin.
3. Probar en ruta de pruebas.
4. Validar home, login, registro, negocio, soporte y admin.
5. Revisar consola del navegador.
6. Revisar UTF-8.
7. Revisar modales personalizados.
8. Activar versión live.
9. Confirmar `/web/versions/public`.
10. Monitorizar errores.

## 7. Publicación de APK

Flujo:

1. Verificar JDK/Android SDK.
2. Lanzar build desde admin o Gradle.
3. Comprobar APK generado.
4. Activar versión.
5. Verificar `android_versions.json`.
6. Descargar desde página pública.
7. Probar instalación.

## 8. Cambios de base de datos

Antes:

- Backup.
- Revisar `ensure_*`.
- Revisar índices.
- Probar en entorno de pruebas.

Después:

- Verificar logs.
- Probar endpoints afectados.
- Revisar permisos read/write.
- Documentar cambios en modelo de datos.

## 9. Mantenimiento de IA

- Refrescar cache tras cambios masivos de negocios.
- Verificar proveedor LLM.
- Revisar timeouts.
- Limpiar aprendizaje erróneo.
- Validar que no se filtra información privada.
- Probar preguntas típicas.

## 10. Mantenimiento de seguridad

- Rotar contraseñas admin periódicamente.
- Revisar sesiones admin.
- Revisar accesos SSH.
- Mantener HTTPS.
- Revisar secretos en entorno.
- Comprobar que no hay archivos sensibles servidos en `/web`.
- Revisar subida de archivos.
- Actualizar dependencias con pruebas.

## 11. Monitorización

Indicadores:

- Estado systemd.
- Uso CPU/RAM.
- Espacio en disco.
- Errores 5xx.
- Latencia `/places`.
- Latencia IA.
- Fallos correo.
- Fallos FCM/Web Push.
- Tickets sin responder.

## 12. Recuperación rápida

Si backend falla:

1. Ver logs.
2. Revisar variables DB.
3. Reiniciar `todosevillaeste-frontend.service`.
4. Probar `/`.
5. Si persiste, restaurar versión/snapshot anterior.

Si IA falla:

1. Ver `/health`.
2. Revisar proveedor LLM.
3. Reiniciar `todosevillaeste-agents.service`.
4. Desactivar IA temporalmente si afecta UX.

Si una versión web rompe producción:

1. Entrar admin.
2. Activar snapshot anterior.
3. Limpiar cache del navegador si es necesario.
4. Revisar service worker.
5. Corregir en snapshot de pruebas.

Si DB falla:

1. No publicar cambios.
2. Revisar conectividad.
3. Revisar credenciales.
4. Restaurar backup si hay corrupción.
5. Validar integridad.

## 13. Registro de cambios recomendado

Cada cambio debe documentar:

- Fecha.
- Autor.
- Archivos tocados.
- Antes.
- Después.
- Motivo.
- Pruebas realizadas.
- Riesgos.
- Plan de rollback.

## 14. Checklist final de mantenimiento

- Backups verificados.
- Servicios activos.
- Web pública operativa.
- Admin operativo.
- IA controlada.
- Logs revisados.
- Versiones coherentes.
- Documentación actualizada.
- Sin mojibake.
- Sin modales nativos nuevos.

