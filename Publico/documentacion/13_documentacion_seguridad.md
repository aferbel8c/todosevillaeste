# Documentación de Seguridad - TodoSevillaEste

## 1. Superficie de ataque

Componentes expuestos:

- Web pública.
- API pública.
- Login/registro.
- OAuth.
- Captcha/antibot.
- Panel admin.
- API admin.
- Terminal SSH vía WebSocket.
- Subida de archivos.
- Mensajería.
- Soporte.
- Reseñas.
- API de IA.
- Apps Android WebView.

## 2. Autenticación

### Usuarios

- Cookie `tsev_session`.
- Login con usuario/email y contraseña.
- Verificación por código en flujos concretos.
- Recuperación de contraseña por email/código.
- OAuth opcional Google/Microsoft.

### Admin

- Cookie `tsev_admin_session`.
- Login con usuario, email, contraseña y modo/duración.
- Restauración controlada.
- Verificación de contraseña para acciones críticas.

## 3. Autorización

Controles:

- Usuario autenticado para perfil, mensajes, soporte y reseñas.
- Rol negocio para `/business/me`.
- Sesión admin para `/admin/*`.
- Validación de propiedad antes de editar negocio propio.
- Validación de participante antes de leer o modificar chats.
- Validación de autor antes de editar/eliminar mensajes o reseñas.

## 4. Protección contra abuso

Medidas:

- Captcha propio.
- hCaptcha/reCAPTCHA/Turnstile según configuración.
- Antibot con token, tiempo y honeypot.
- Moderación de reseñas.
- Reportes de usuarios.
- Bloqueo de chats/tickets.
- Logs de IP.

## 5. Subida de archivos

Riesgos:

- Malware.
- Ficheros demasiado grandes.
- Extensiones peligrosas.
- Nombres con path traversal.
- Contenido ofensivo.

Controles recomendados:

- Validar extensión/MIME.
- Renombrar archivos.
- Limitar tamaño.
- Servir como estático sin ejecución.
- Separar permisos de escritura/ejecución.
- Revisar imágenes reportadas.

## 6. Cookies

Recomendaciones:

- `HttpOnly` para cookies de sesión cuando sea posible.
- `Secure=1` en producción HTTPS.
- `SameSite=Lax` o más restrictivo salvo necesidad.
- Dominio controlado con `SESSION_COOKIE_DOMAIN`.
- Expiración coherente.

## 7. HTTPS

En producción debe usarse HTTPS. Las apps Android permiten cleartext para desarrollo; no debe usarse en producción salvo caso controlado.

## 8. Panel admin

Riesgos altos:

- Eliminación de usuarios/negocios.
- Cambio de roles.
- Activación de versiones.
- Build APK.
- Terminal SSH.
- Reinicio de servicios.
- Correo admin.

Controles:

- Acceso solo con sesión admin.
- Contraseña fuerte.
- Verificación extra para borrados.
- Auditoría/log de acciones recomendada.
- No compartir sesión admin.
- Cerrar sesión en equipos ajenos.

## 9. Terminal SSH

La terminal web debe tratarse como acceso crítico.

Recomendaciones:

- Limitar a usuarios admin autorizados.
- Usar claves SSH seguras.
- Registrar accesos.
- Evitar comandos destructivos.
- Separar usuario de servicio sin privilegios excesivos.
- Revisar `ADMIN_SSH_STRICT_HOST_KEY`.

## 10. IA

Riesgos:

- Filtración de datos privados.
- Respuestas inventadas.
- Prompt injection.
- Exposición de información técnica.

Controles:

- Usar solo contexto público.
- Prompt de sistema restrictivo.
- No pasar cookies/tokens.
- Limitar caracteres.
- Cache controlada.
- Mensajes de no disponibilidad cuando no exista dato.

## 11. Dependencias externas

Riesgos:

- Caída de OAuth/captcha/correo/FCM/LLM.
- Cambio de API.
- Exposición de claves.

Controles:

- Variables de entorno.
- No subir secretos a repositorio.
- Timeouts.
- Fallbacks.
- Rotación de claves.

## 12. Copias de seguridad

Debe incluir:

- Base de datos.
- JSON de configuración.
- Imágenes y adjuntos.
- APKs publicadas.
- Snapshots web activos.
- `.env` o inventario seguro de configuración.

## 13. Respuesta ante incidente

1. Identificar alcance.
2. Aislar servicio afectado.
3. Revocar sesiones/tokens si procede.
4. Cambiar contraseñas/secretos.
5. Restaurar backup limpio si es necesario.
6. Revisar logs.
7. Documentar causa raíz.
8. Aplicar parche.
9. Comunicar a afectados si procede.

## 14. Checklist de hardening

- HTTPS activo.
- Cookies seguras.
- Secrets fuera del repositorio.
- Admin con contraseña fuerte.
- Captcha activo en formularios críticos.
- DB con permisos mínimos.
- Backups automáticos.
- Logs revisables.
- Terminal restringida.
- Builds Android solo por admin.
- IA sin datos privados.

