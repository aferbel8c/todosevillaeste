# Documentación de API - TodoSevillaEste

## 1. Base

Backend principal:

- Desarrollo: `http://127.0.0.1:8001`.
- Producción: dominio público configurado.
- Archivo: `frontend_backend.py`.

API de agentes:

- Desarrollo: `http://127.0.0.1:8000`.
- Archivo: `agents_main.py`.
- Proxy desde backend para chat público.

Todas las llamadas de usuario usan `credentials: include` desde frontend para enviar cookies.

## 2. Autenticación

### Cookie pública

- Nombre: `tsev_session`.
- Se crea en login/registro/verificación.
- Protege `/users/me`, mensajería, reseñas, soporte y negocio propietario.

### Cookie admin

- Nombre: `tsev_admin_session`.
- Se crea en `/admin/auth/login`.
- Protege endpoints `/admin/*` y herramientas técnicas.

### Respuestas de error comunes

- `400`: payload inválido o validación fallida.
- `401`: no autenticado.
- `403`: sin permisos.
- `404`: recurso no encontrado.
- `409`: conflicto, duplicado o estado incompatible.
- `422`: validación Pydantic.
- `503`: dependencia no inicializada o servicio externo no disponible.

## 3. Endpoints públicos de negocios

### `GET /places`

Lista negocios. Puede incluir negocios activos y datos públicos.

Respuesta típica:

```json
[
  {
    "public_id": 1,
    "name": "Negocio",
    "category": "Comercio",
    "address": "Sevilla Este",
    "phone": "600000000",
    "website": "https://...",
    "description": "...",
    "active": true,
    "photos": [],
    "map_latitude": 37.0,
    "map_longitude": -5.0
  }
]
```

### `GET /places/{place_id}`

Devuelve detalle de negocio por `public_id`.

### `POST /places`

Crea negocio. Requiere sesión de usuario o admin según contexto.

Payload principal:

```json
{
  "name": "Nombre",
  "address": "Dirección",
  "phone": "Teléfono",
  "website": "https://...",
  "business_email": "negocio@example.com",
  "contact_email": "publico@example.com",
  "opening_hours": {
    "lunes": [{"inicio": "09:00", "fin": "14:00"}]
  },
  "category": "Categoría",
  "description": "Descripción",
  "initial_phrase": "Frase",
  "active": true,
  "map_latitude": 37.0,
  "map_longitude": -5.0
}
```

### `PUT /places/{place_id}`

Actualiza negocio completo. Uso admin.

### `PUT /places/{place_id}/active`

Activa o desactiva negocio. Uso admin.

### `DELETE /places/{place_id}`

Elimina negocio. Uso admin.

### `POST /places/{place_id}/main_photo`

Sube foto principal. `multipart/form-data`.

## 4. Endpoints de negocio propietario

### `GET /business/me`

Devuelve el negocio vinculado al usuario autenticado con rol negocio.

### `PUT /business/me`

Actualiza negocio propio.

### `POST /business/me/main_photo`

Sube foto principal del negocio propio.

### `POST /business/me/photos`

Sube fotos extra.

### `DELETE /business/me/photos`

Elimina foto extra.

Payload:

```json
{ "photo_url": "/img/businesses/..." }
```

## 5. Endpoints de autenticación pública

### `POST /auth/register`

Registra usuario.

Payload:

```json
{
  "username": "usuario",
  "email": "correo@example.com",
  "password": "secreta",
  "birthdate": "2000-01-01",
  "captcha_token": "...",
  "captcha_answer": "...",
  "antibot_token": "..."
}
```

### `POST /auth/register/check`

Comprueba disponibilidad de usuario/email.

### `POST /auth/register/email_code/send`

Envía código de verificación de email.

### `POST /auth/register/email_code/verify`

Valida código de email.

### `POST /auth/login`

Inicia sesión.

Payload:

```json
{
  "login": "usuario-o-email",
  "password": "secreta",
  "remember": true,
  "captcha_token": "...",
  "antibot_token": "..."
}
```

### `POST /auth/login/verify`

Segundo paso de login por código si aplica.

### `POST /auth/logout`

Cierra sesión pública.

### `GET /auth/me` y `GET /users/me`

Devuelve usuario autenticado.

### `POST /auth/forgot_password`

Solicita recuperación.

### `POST /auth/reset_password/verify`

Verifica código y cambia contraseña.

### `POST /users/change_password`

Cambio obligatorio de contraseña.

## 6. Endpoints de perfil

### `PUT /users/me`

Actualiza datos del usuario autenticado.

### `POST /users/me/avatar`

Sube avatar.

### `DELETE /users/me/avatar`

Elimina avatar.

### `POST /users/me/password`

Cambia contraseña.

### `POST /users/me/email`

Cambia email tras validar contraseña.

### `POST /users/me/delete/request_code`

Solicita código para eliminar cuenta.

### `DELETE /users/me`

Elimina cuenta propia.

### `GET /profiles/{user_id}`

Perfil público de usuario.

### `GET /profiles/{user_id}/reviews`

Reseñas públicas de un usuario.

## 7. OAuth

### `GET /auth/oauth/providers`

Devuelve proveedores disponibles.

### `GET /auth/oauth/{provider}/start`

Inicia OAuth.

### `GET /auth/oauth/google/callback`

Callback Google.

### `GET /auth/oauth/microsoft/callback`

Callback Microsoft.

## 8. Captcha y antibot

### `GET /public/recaptcha/site-key`

Devuelve site key reCAPTCHA si existe.

### `GET /public/hcaptcha/site-key`

Devuelve site key hCaptcha si existe.

### `GET /public/antibot/challenge`

Devuelve desafío antibot.

### `GET /public/captcha/challenge`

Devuelve captcha propio.

### `POST /public/captcha/verify`

Verifica captcha propio.

## 9. Reseñas

### `GET /places/{place_id}/reviews`

Lista reseñas de negocio. Parámetros habituales: `limit`, `sort`, `sample`.

### `POST /places/{place_id}/reviews`

Crea reseña. Puede incluir fotos.

### `GET /users/me/reviews`

Lista reseñas propias.

### `PUT /users/me/reviews/{review_id}`

Edita reseña propia.

### `DELETE /users/me/reviews/{review_id}`

Elimina reseña propia.

### `POST /reviews/{review_id}/vote`

Vota reseña.

Payload:

```json
{ "vote": 1 }
```

### `POST /reviews/{review_id}/report`

Reporta reseña.

Payload:

```json
{ "reason": "Motivo" }
```

## 10. Mensajería

### `POST /messages/chats/from_place/{place_id}`

Abre chat con negocio.

### `POST /messages/chats/with_user/{target_user_id}`

Abre chat con usuario.

### `GET /messages/chats`

Lista chats.

### `GET /messages/chats/{chat_id}`

Detalle del chat.

### `GET /messages/chats/{chat_id}/messages`

Mensajes del chat.

### `POST /messages/chats/{chat_id}/messages`

Envía mensaje con texto y adjunto opcional.

### `PATCH /messages/chats/{chat_id}/rename`

Renombra chat.

### `PATCH /messages/chats/{chat_id}/block`

Bloquea/desbloquea chat.

### `DELETE /messages/chats/{chat_id}`

Oculta/elimina chat para el usuario.

### `PATCH /messages/chats/{chat_id}/messages/{message_id}`

Edita mensaje propio.

### `DELETE /messages/chats/{chat_id}/messages/{message_id}`

Borra mensaje propio.

### `GET /messages/global` y `POST /messages/global`

Mensajes globales.

## 11. Soporte y feedback

### `POST /support/tickets`

Crea ticket.

### `GET /support/tickets/my`

Lista tickets propios.

### `GET /support/tickets/{ticket_id}`

Detalle de ticket.

### `POST /support/tickets/{ticket_id}/messages`

Añade mensaje.

### `PATCH /support/tickets/{ticket_id}/rename`

Renombra ticket.

### `PATCH /support/tickets/{ticket_id}/block`

Bloquea conversación.

### `DELETE /support/tickets/{ticket_id}`

Oculta ticket para usuario.

### `POST /feedback/submissions` y `POST /support/feedback`

Crea feedback.

## 12. Notificaciones

### `GET /notifications/vapid_public_key`

Devuelve clave pública VAPID.

### `POST /notifications/subscribe`

Registra suscripción Web Push.

### `POST /notifications/unsubscribe`

Desactiva suscripción Web Push.

### `GET /notifications/fcm/status`

Estado FCM.

### `POST /notifications/fcm/register`

Registra token FCM.

### `POST /notifications/fcm/unregister`

Desregistra token.

### `GET /notifications/fcm/me`

Tokens FCM del usuario.

## 13. Administración

### Autenticación admin

- `POST /admin/auth/login`
- `GET /admin/auth/me`
- `GET /admin/auth/status`
- `POST /admin/auth/logout`
- `POST /admin/auth/restore`
- `POST /admin/auth/verify_password`
- `POST /admin/auth/forgot/request`
- `POST /admin/auth/forgot/verify`

### Configuración admin

- `GET /admin/settings/session`
- `PUT /admin/settings/session`
- `GET /admin/settings/visibility`
- `PUT /admin/settings/visibility`
- `GET /public/visibility`
- `GET /qr/settings/public`

### Usuarios admin

- `GET /users`
- `POST /users`
- `PUT /users/{user_id}`
- `DELETE /users/{user_id}`
- `POST /users/{user_id}/reset_password`
- `GET /admin/users/{user_id}/roles`
- `PUT /admin/users/{user_id}/roles`
- `GET /admin/users/{user_id}/chat`
- `POST /admin/users/{user_id}/chat/messages`
- `PATCH /admin/users/{user_id}/chat/messages/{message_id}`
- `DELETE /admin/users/{user_id}/chat/messages/{message_id}`

### Reseñas admin

- `GET /admin/reviews`
- `PATCH /admin/reviews/{review_id}/moderate`
- `PATCH /admin/reviews/{review_id}/revision`
- `GET /admin/review_reports`
- `PATCH /admin/review_reports/{report_id}`

### Soporte admin

- `GET /admin/support/metrics`
- `GET /admin/support/tickets`
- `GET /admin/support/tickets/{ticket_id}`
- `POST /admin/support/tickets/{ticket_id}/messages`
- `POST /admin/support/tickets/{ticket_id}/close`
- `POST /admin/support/tickets/{ticket_id}/email`

### Feedback admin

- `GET /admin/feedback`
- `PATCH /admin/feedback/{feedback_id}/status`
- `POST /admin/feedback/{feedback_id}/report-change`
- `GET /admin/feedback/{feedback_id}/conversation`
- `POST /admin/feedback/{feedback_id}/conversation/messages`

### Correo admin

- `GET /admin/mail/resolve`
- `GET /admin/mail/folders`
- `GET /admin/mail/inbox`
- `GET /admin/mail/inbox/{uid}`
- `PATCH /admin/mail/inbox/{uid}/flags`
- `POST /admin/mail/inbox/{uid}/trash`
- `POST /admin/mail/send`

### Versiones

- `GET /admin/android_versions`
- `POST /admin/android_versions/build`
- `GET /admin/android_versions/build_status`
- `POST /admin/android_versions/use`
- `GET /admin/web_versions`
- `POST /admin/web_versions/create`
- `POST /admin/web_versions/update`
- `POST /admin/web_versions/use`
- `POST /admin/web_versions/use_test`
- `POST /admin/web_versions/delete`
- `POST /admin/web_versions/sync`
- `GET /web/versions/public`
- `GET /web/versions/stream`
- `GET /android/versions/public`

## 14. Operación técnica

- `GET /administracion/api/tse/state`
- `GET /administracion/api/tse/terminal-action`
- `POST /administracion/api/tse/toggle`
- `POST /administracion/api/tse/restart-services`
- `POST /administracion/api/backend/restart`
- `GET /administracion/api/backend/instance`
- `POST /administracion/api/agents/restart`
- `GET /administracion/api/ssh/info`
- `WEBSOCKET /administracion/api/ssh/ws`
- `GET /administracion/api/ip-log/stream`
- `GET /administracion/api/pve-console-url`

## 15. API de agentes

- `GET /`: estado básico.
- `GET /health`: salud.
- `POST /agents/public/cache/refresh`: refresca cache pública.
- `POST /agents/create`: crea agente.
- `POST /agents/{agent_name}/documents`: añade documentos.
- `POST /agents/{agent_name}/chat`: chat con agente.
- `POST /agents/public/chat`: chat público.
- `POST /agents/public/chat/stream`: chat público streaming.
- `POST /agents/learning/feedback`: feedback de aprendizaje.
- `GET /agents/{agent_name}/embed`: iframe/widget embebible.

