# Modelo de Datos - TodoSevillaEste

## 1. Fuentes de datos

El sistema usa:

- MariaDB/MySQL para datos principales.
- JSON locales para configuración, versiones, sesiones admin y memoria IA.
- Sistema de archivos para imágenes, adjuntos, APKs y snapshots.
- `localStorage`/`sessionStorage` en cliente para preferencias de UI, cookies, sesión visual y avisos.

## 2. Usuarios

### Tabla `users`

Entidad central de cuentas públicas y roles.

Campos observados por uso del backend:

- `id`: identificador interno.
- `username`: nombre visible/login.
- `email`: email de la cuenta.
- `password_hash`: contraseña hasheada.
- `must_change_password`: fuerza cambio de contraseña.
- `temp_code`: código temporal para verificación/login/reset.
- `avatar_url`: avatar.
- `birthdate`: fecha de nacimiento opcional.
- `email_verification_enabled`: indica si requiere verificación.
- `is_default_account`: cuenta creada automáticamente para negocio.
- `role_client`: permiso cliente.
- `role_business`: permiso negocio.
- `role_admin`: permiso admin.

Relaciones:

- `sessions.user_id`.
- `places.owner_user_id`.
- `place_user_assignments.user_id`.
- `reviews.user_id`.
- `chat_threads.user_a_id/user_b_id`.
- `chat_messages.sender_user_id/receiver_user_id`.
- `support_tickets.user_id`.
- `feedback_submissions.user_id`.
- `push_subscriptions.user_id`.
- `fcm_device_tokens.user_id`.

Reglas:

- Email debe ser único en operaciones de registro.
- Username debe ser único.
- Password nunca se guarda en claro.
- Si `role_business=1`, debe existir negocio vinculado cuando se usa `/business/me`.

## 3. Sesiones y códigos

### Tabla `sessions`

Guarda sesiones públicas asociadas a cookie `tsev_session`.

Campos funcionales:

- `session_id`: token de sesión.
- `user_id`: usuario.
- `expires_at` o equivalente según esquema existente.
- Fechas de creación/actualización si existen.

### Tabla `auth_codes`

Usada para verificación, reset de contraseña y códigos temporales.

Campos funcionales:

- `email`.
- `code`.
- `purpose` o uso equivalente.
- `expires_at`.

## 4. Negocios

### Tabla `places`

Entidad principal del directorio.

Campos observados:

- `id`: identificador interno.
- `public_id`: identificador público usado en URLs/API.
- `name`: nombre.
- `address`: dirección.
- `phone`: teléfono.
- `website`: web.
- `business_email`: email operativo del negocio.
- `contact_email`: email público/contacto.
- `category`: categoría.
- `description`: descripción.
- `initial_phrase`: frase inicial.
- `opening_hours`: horarios normales en JSON.
- `special_days`: días especiales en JSON.
- `photos`: fotos extra en JSON/lista.
- `main_photo`: foto principal si existe en esquema.
- `active`: visible/oculto.
- `owner_user_id`: propietario.
- `map_latitude`: latitud.
- `map_longitude`: longitud.

Reglas:

- `public_id` es la clave pública funcional.
- `active=false` debe ocultar o limitar la ficha pública.
- Coordenadas válidas: latitud `-90..90`, longitud `-180..180`.
- Fotos se almacenan bajo `web/img/businesses`.
- Horarios se estructuran por días con tramos `{inicio, fin}`.

### Tabla `place_user_assignments`

Vincula usuarios con negocios.

Campos:

- `user_id`.
- `place_public_id`.
- `assigned_at`.

Clave:

- Primaria compuesta `(user_id, place_public_id)`.

Uso:

- Compatibilidad con `owner_user_id`.
- Permite asignaciones explícitas usuario-negocio.

## 5. Reseñas

### Tabla `reviews`

Campos:

- `id`.
- `place_public_id`.
- `user_id`.
- `rating`: valoración.
- `description`: texto.
- `photos_json`: fotos.
- `is_hidden`: ocultación admin.
- `hidden_reason`: motivo.
- `pending_recheck`: pendiente de revisión tras edición.
- `previous_rating`.
- `previous_description`.
- `previous_photos_json`.
- `last_edit_requested_at`.
- `created_at`.
- `updated_at`.

Reglas:

- Solo usuarios autenticados crean reseñas.
- La moderación puede ocultar o pedir revisión.
- Las fotos se guardan bajo `web/img/reviews`.

### Tabla `review_votes`

Campos:

- `review_id`.
- `user_id`.
- `vote`: valor de voto.
- `created_at`.
- `updated_at`.

Clave:

- Primaria compuesta `(review_id, user_id)`.

### Tabla `review_reports`

Campos:

- `id`.
- `review_id`.
- `reporter_user_id`.
- `reason`.
- `status`: `pending`, resuelto u otros estados.
- `admin_action`.
- `admin_note`.
- `created_at`.
- `resolved_at`.

Uso:

- Denuncias de reseñas y moderación admin.

## 6. Mensajería

### Tabla `chat_threads`

Campos:

- `id`.
- `place_public_id`: negocio asociado o `0` para chat admin/usuario.
- `user_a_id`.
- `user_b_id`.
- `initiated_by_user_id`.
- `custom_name_a`.
- `custom_name_b`.
- `is_blocked`.
- `blocked_by_user_id`.
- `created_at`.
- `updated_at`.

Clave:

- Única por `(place_public_id, user_a_id, user_b_id)`.

### Tabla `chat_messages`

Campos:

- `id`.
- `chat_id`.
- `sender_user_id`.
- `receiver_user_id`.
- `body`.
- `media_url`.
- `status`: por defecto `delivered`.
- `edited`.
- `is_deleted`.
- `deleted_at`.
- `created_at`.
- `updated_at`.
- `read_at`.

Adjuntos:

- Guardados bajo `web/img/messages`.

### Tabla `global_chat_messages`

Campos:

- `id`.
- `sender_user_id`.
- `body`.
- `created_at`.
- `updated_at`.

## 7. Soporte

### Tabla `support_tickets`

Campos:

- `id`.
- `user_id`: puede ser `NULL`.
- `place_public_id`: opcional.
- `subject`.
- `custom_subject`.
- `custom_name_user`.
- `body`.
- `email`.
- `attachments_json`.
- `status`: `open`, cerrado u otros.
- `user_visible`.
- `user_blocked`.
- `user_deleted`.
- `first_admin_response_at`.
- `created_at`.
- `updated_at`.
- `closed_at`.
- `closed_by_admin_username`.

Adjuntos:

- Guardados bajo `web/img/support`.

### Tabla `support_ticket_messages`

Campos:

- `id`.
- `ticket_id`.
- `sender_type`: usuario/admin/sistema.
- `sender_user_id`.
- `body`.
- `attachments_json`.
- `created_at`.

## 8. Feedback

### Tabla `feedback_submissions`

Campos:

- `id`.
- `user_id`.
- `email`.
- `rating`.
- `subject`.
- `body`.
- `status`.
- `created_at`.
- `updated_at`.
- `last_admin_contact_at`.

### Tabla `feedback_messages`

Campos:

- `id`.
- `feedback_id`.
- `sender_type`.
- `body`.
- `email_message_id`.
- `created_at`.

## 9. Notificaciones

### Tabla `push_subscriptions`

Campos:

- `id`.
- `user_id`.
- `endpoint`.
- `p256dh`.
- `auth`.
- `user_agent`.
- `fail_count`.
- `is_active`.
- `last_success_at`.
- `created_at`.
- `updated_at`.

Clave:

- Única por `endpoint`.

### Tabla `fcm_device_tokens`

Campos:

- `id`.
- `user_id`.
- `token`.
- `platform`: por defecto `android`.
- `app_variant`: `client` o `admin`.
- `device_id`.
- `user_agent`.
- `is_active`.
- `fail_count`.
- `last_success_at`.
- `created_at`.
- `updated_at`.

Clave:

- Única por `token`.

## 10. JSON de configuración

### `web_versions.json`

Controla snapshots públicos/admin.

Campos:

- `public.active_id`.
- `public.test_active_id`.
- `public.items[]`.
- `admin.active_id`.
- `admin.test_active_id`.
- `admin.items[]`.

Cada item contiene `id`, `target`, `version`, `notes`, `created_at`, `snapshot_ready`, `snapshot_dir` y `updated_at` cuando aplica.

### `android_versions.json`

Controla APKs cliente/admin.

Campos:

- `client.active_id`.
- `client.items[]`.
- `admin.active_id`.
- `admin.items[]`.

Cada item contiene `id`, `target`, `version`, `notes`, `download_url`, `filename`, `size_bytes`, `created_at`.

### `visibility_config.json`

Controla visibilidad pública y funcionalidades como IA. Lo consume `/public/visibility` y lo modifica `/admin/settings/visibility`.

### `admin_auth_config.json`

Controla configuración de sesión admin, duración por defecto y reglas QR.

### `admin_sessions.json`

Persistencia de sesiones admin para restauración y validación.

### `manuales_sessions.json`

Sesiones de herramientas internas de manuales.

### `data/learning_memory.json`

Memoria de aprendizaje de la API de agentes. Debe mantenerse limitada por agente para evitar crecimiento no controlado.

## 11. Archivos binarios y recursos

- `web/img/businesses`: fotos de negocios.
- `web/img/reviews`: fotos de reseñas.
- `web/img/messages`: adjuntos de mensajes.
- `web/img/support`: adjuntos soporte.
- `web/downloads/android/client`: APK cliente.
- `web/downloads/android/admin`: APK admin.
- `web/versions_web/public/*`: snapshots públicos.
- `web/versions_web/admin/*`: snapshots admin.

## 12. Integridad y limpieza

- Al eliminar usuario se limpian sesiones, auth codes, chats y relaciones asociadas según lógica del backend.
- Al eliminar negocio se deben limpiar asignaciones y, si procede, cuenta creada automáticamente.
- Al desactivar negocio no se borra la ficha: se marca inactiva.
- Los JSON deben escribirse con UTF-8.
- No se deben editar manualmente JSON de producción sin copia previa.

