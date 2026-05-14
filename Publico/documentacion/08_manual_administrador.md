# Manual de Administrador - TodoSevillaEste

## 1. Acceso

Ruta principal:

- `/administracion/index-panel.html`.

El administrador debe iniciar sesión con usuario, email y contraseña. Puede existir captcha/antibot y modo de sesión con duración configurable.

## 2. Panel principal

Desde `index-panel.html` se accede a:

- Negocios.
- Usuarios.
- Reseñas.
- Soporte.
- Versiones.
- Mails.
- Logs/terminal.
- Configuración de visibilidad y sesión.

## 3. Gestión de negocios

Pantalla: `admin_negocios.html`.

Acciones:

- Listar negocios.
- Crear negocio.
- Editar datos.
- Subir foto principal.
- Activar/desactivar.
- Eliminar.
- Refrescar cache de IA.

Campos importantes:

- `public_id`.
- Nombre.
- Categoría.
- Dirección.
- Teléfono.
- Web.
- Email.
- Horarios.
- Coordenadas.
- Propietario.
- Estado activo.

Precauciones:

- Revisar duplicados antes de crear.
- Desactivar antes de eliminar si hay dudas.
- Comprobar propietario antes de borrar cuenta asociada.
- Refrescar cache IA tras cambios relevantes.

## 4. Gestión de usuarios

Pantalla: `admin_usuarios.html`.

Acciones:

- Listar usuarios.
- Crear usuario.
- Editar usuario/email.
- Eliminar usuario.
- Resetear contraseña.
- Asignar roles.
- Vincular negocio.
- Abrir chat admin-usuario.

Roles:

- Cliente.
- Negocio.
- Administrador.

Reglas:

- No conceder rol admin sin autorización.
- Para rol negocio, vincular `business_place_public_id`.
- Verificar contraseña admin antes de eliminaciones críticas.

## 5. Moderación de reseñas

Pantalla: `admin_reviews.html`.

Acciones:

- Listar reseñas.
- Ocultar/mostrar.
- Añadir motivo.
- Solicitar revisión.
- Resolver reportes.
- Gestionar feedback.

Criterios de moderación:

- Datos personales publicados.
- Insultos o amenazas.
- Spam.
- Contenido falso evidente.
- Imágenes no permitidas.
- Conflictos legales.

## 6. Soporte

Pantalla: `admin_support.html`.

Acciones:

- Ver métricas.
- Filtrar tickets.
- Abrir detalle.
- Responder.
- Adjuntar archivos.
- Cerrar/reabrir.
- Enviar email asociado.

Buenas prácticas:

- Responder con claridad.
- No pedir contraseñas.
- Cerrar solo cuando la incidencia esté resuelta.
- Mantener trazabilidad en la conversación.

## 7. Feedback

Desde reviews/feedback:

- Ver valoraciones de mejora.
- Cambiar estado.
- Responder conversación.
- Registrar cambios reportados.

## 8. Correo admin

Pantalla: `admin_mails.html`.

Acciones:

- Ver carpetas.
- Leer mensajes.
- Marcar leído/no leído.
- Destacar.
- Enviar a papelera.
- Redactar.
- Responder.
- Reenviar.
- Adjuntar archivos.

Configuración:

- IMAP/SMTP o Gmail API mediante variables de entorno.

## 9. Versiones web

Pantalla: `admin_versions.html`.

Acciones:

- Crear snapshot.
- Actualizar notas.
- Activar versión live.
- Activar versión test.
- Eliminar snapshot.
- Sincronizar snapshot.

Flujo recomendado:

1. Crear snapshot.
2. Probar en `/pruebas`.
3. Validar login, negocios, soporte y admin.
4. Activar versión.
5. Revisar `/web/versions/public`.

## 10. Versiones Android

Acciones:

- Lanzar build APK cliente/admin.
- Consultar estado.
- Marcar APK activa.
- Revisar descarga pública.

Antes de compilar:

- Verificar `JAVA_HOME`.
- Verificar `ANDROID_SDK_ROOT` o `ANDROID_HOME`.
- Verificar permisos de escritura en `web/downloads/android`.

## 11. Logs y terminal

Pantalla: `ip_log.html`.

Acciones:

- Ver estado del stack.
- Abrir terminal SSH.
- Reiniciar backend.
- Reiniciar agentes.
- Reiniciar servicios del stack.
- Ver stream de IP/log.

Precauciones:

- No ejecutar comandos destructivos sin copia.
- No compartir credenciales.
- Verificar entorno antes de reiniciar.
- Usar terminal solo para operaciones necesarias.

## 12. Configuración de visibilidad

Desde el panel se puede controlar:

- Visibilidad pública.
- Visibilidad de IA.
- Reglas QR.
- Duración de sesión admin.

Todo cambio debe probarse en navegación pública y admin.

## 13. Checklist diario

- Comprobar estado del stack.
- Revisar tickets abiertos.
- Revisar reportes de reseñas.
- Revisar feedback nuevo.
- Confirmar que la home carga negocios.
- Revisar errores recientes.

## 14. Checklist antes de publicar

- Probar web pública.
- Probar login/registro.
- Probar negocio detalle.
- Probar panel negocio.
- Probar admin.
- Probar soporte.
- Probar versiones.
- Verificar UTF-8.
- Verificar que no hay modales nativos nuevos.

