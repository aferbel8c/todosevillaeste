# Release 4.3 Public / 2.4 Admin - Funcionamiento del proyecto TodoSevillaEste

## Alcance de este documento

Este documento describe el funcionamiento global del proyecto TodoSevillaEste tomando como referencia principal:

- Web publica activa: `web/versions_web/public/4.3`.
- Panel de administracion activo: `web/versions_web/admin/2.4`.
- Backend principal: `frontend_backend.py`.
- API auxiliar de agentes: `agents_main.py`, solo a nivel de integracion. Se omite la explicacion interna del chatbot propio por indicacion expresa.
- SPA Vue/Vite en migracion progresiva: `web/app`.
- Apps Android WebView: `android/` y `android_admin/`.
- Scripts de servicio y datos de versionado.

La idea de esta release es que cualquier agente o desarrollador pueda entender que parte toca cada archivo, que rutas existen, como fluye la informacion y donde mirar si algo falla.

## Resumen ejecutivo

TodoSevillaEste es una plataforma web y movil para consultar negocios de Sevilla Este, registrar usuarios, dar de alta negocios, gestionar fichas, enviar mensajes, publicar resenas, tramitar soporte, administrar usuarios y controlar versiones web/APK.

La arquitectura real combina tres capas:

- `frontend_backend.py`: backend FastAPI principal. Sirve las paginas publicas, el panel admin, assets, endpoints de usuarios, negocios, mensajes, resenas, soporte, versiones, notificaciones y administracion del sistema.
- `web/versions_web/public/4.3`: snapshot de la web publica que el backend sirve cuando la version activa de `web_versions.json` apunta a `public/4.3`.
- `web/versions_web/admin/2.4`: snapshot del panel de administracion que el backend sirve cuando la version activa de admin apunta a `admin/2.4`.

La SPA Vue de `web/app` existe como migracion progresiva, pero gran parte del producto en produccion sigue siendo HTML/JS legacy servido directamente por FastAPI.

## Versionado activo

El archivo `web_versions.json` controla que snapshot web se sirve en vivo y cual se usa para pruebas.

Estado observado:

- Public activo: version `4.3`, snapshot `public/4.3`, notas `Cambios generales`.
- Public de pruebas: version `3.9`, snapshot `public/3.9`.
- Admin activo: version `2.4`, snapshot `admin/2.4`, notas `Mejoras`.
- Admin de pruebas: version `2.4`, snapshot `admin/2.4`.

El backend no sirve simplemente `web/frontend` o `web/administracion` de forma fija. Para muchas rutas llama a resolutores como:

- `resolve_web_public_file_for_request(request, rel_path)`.
- `resolve_web_public_file_with_mode(rel_path, mode)`.
- `resolve_web_admin_file(rel_path)`.
- `resolve_web_admin_file_with_mode(rel_path, mode)`.

Estos resolutores miran `web_versions.json` y deciden desde que snapshot entregar el archivo.

Rutas de prueba:

- Public test: `/pruebas` y `/pruebas/{path}`.
- Admin test: `/administracion/pruebas` y `/administracion/pruebas/{path}`.

## Backend principal: `frontend_backend.py`

### Responsabilidad general

`frontend_backend.py` es el corazon del proyecto. Expone una app FastAPI titulada `Backend de gestion de negocios` y concentra:

- Servicio de HTML publico y administracion.
- API CRUD de negocios.
- Registro, login, sesiones, recuperacion de contrasena y OAuth.
- Gestion de usuarios y roles.
- Mensajeria privada y global.
- Resenas, votos, reportes y moderacion.
- Soporte/tickets y feedback.
- Gestion de versiones web y Android.
- Push web y FCM Android.
- Panel admin del servidor, terminal SSH, logs y reinicio de servicios.
- Configuracion de visibilidad publica.
- Herramientas estaticas como manuales, planos, checklists y rack.

### Middlewares y control de acceso

El backend incluye middlewares para:

- Registrar IPs y pais aproximado de visitantes.
- Redirigir rutas antiguas a rutas nuevas.
- Proteger accesos externos fuera de zonas permitidas.
- Servir `/frontend.html`, `/administracion`, assets y aliases limpios.
- Devolver redireccion a `/frontend.html` para rutas desconocidas publicas que no sean API.

Hay dos modelos principales de sesion:

- Usuario normal: cookie `tsev_session`.
- Administrador: cookie `tsev_admin_session`.

Tambien existen sesiones especificas para herramientas internas, por ejemplo manuales, con `manuales_session`.

### Base de datos

El backend usa MariaDB/MySQL mediante `mysql.connector`.

Variables relevantes:

- `DB_READ_HOST`, `DB_READ_PORT`, `DB_READ_USER`, `DB_READ_PASSWORD`, `DB_READ_DATABASE`.
- Tambien hay configuracion de escritura en el backend, derivada de las variables del entorno definidas en el archivo.

En arranque se ejecutan funciones de preparacion de esquema que crean o amplian tablas si faltan columnas. Las familias de tablas principales son:

- `users`: usuarios, email, password hash, roles, avatar, fecha de nacimiento, verificacion email, flags de cuenta.
- `sessions`: sesiones de usuario.
- `places`: negocios, datos visibles, propietario, email de negocio, coordenadas, horarios especiales.
- `place_user_assignments`: asignaciones usuario-negocio.
- `reviews`, `review_votes`, `review_reports`: sistema de resenas, votos y denuncias.
- `chat_threads`, `chat_messages`, `global_chat_messages`: mensajeria.
- `push_subscriptions`, `fcm_device_tokens`: notificaciones web push y Android FCM.
- `support_tickets`, `support_ticket_messages`: soporte.
- `feedback_submissions`, `feedback_messages`: feedback/mejoras y conversaciones asociadas.

### Archivos y directorios de datos

Rutas relevantes:

- `web/img/businesses`: imagenes principales y extra de negocios.
- `web/img/reviews`: imagenes de resenas.
- `web/img/messages`: adjuntos de mensajes.
- `web/img/support`: adjuntos de soporte.
- `web/downloads/android`: APKs publicadas.
- `web_versions.json`: versiones web public/admin.
- `android_versions.json`: versiones APK client/admin.
- `visibility_config.json`: visibilidad de frontend publico e IA.
- `admin_auth_config.json`: configuracion de autenticacion admin.
- `admin_sessions.json`: sesiones admin persistidas.
- `manuales_sessions.json`: sesiones de herramientas manuales.

## Web publica 4.3

La version publica 4.3 esta en `web/versions_web/public/4.3`. Es un snapshot completo de la web publica legacy.

### `frontend.html`

Es la pagina principal publica.

Funciones principales:

- Muestra la portada de TodoSevillaEste.
- Carga listado de negocios desde `/places`.
- Consulta configuracion realtime desde `/meta/realtime`.
- Consulta visibilidad desde `/public/visibility`.
- Detecta sesion con `/auth/me`.
- Permite logout mediante `/auth/logout`.
- Carga mensajes del usuario desde `/messages/chats`.
- Comprueba si el usuario tiene negocio vinculado con `/business/me`.
- Gestiona QR/camara usando `/qr/settings/public`.
- Gestiona notificaciones push con `/notifications/vapid_public_key` y `/notifications/subscribe`.
- Usa `localStorage` para recordar estado de permisos, hints iOS PWA, version publica aceptada y conversacion del asistente externo.
- Escucha cambios de version con `/web/versions/public` y muestra aviso de actualizacion.

La parte del asistente/chatbot se omite en este documento. A nivel de producto, solo hay que saber que la pagina puede cargar un widget que llama a la API auxiliar de agentes cuando la visibilidad lo permite.

### `ui_public.js`

Script compartido publico.

Responsabilidades:

- Aviso de nueva version publica.
- Polling a `/web/versions/public`.
- Stream SSE con `EventSource('/web/versions/stream?target=public')`.
- Banner y configuracion de cookies con `localStorage`.
- Buscador global de negocios.
- Sugerencias locales y remotas.
- Normalizacion de textos, escape HTML y control de clicks/foco/teclado.

Este archivo da comportamiento comun a paginas publicas sin duplicar toda la logica en cada HTML.

### `ui_public.css` y `header_shared.css`

Estilos compartidos de la web publica.

Cubren:

- Cabecera comun.
- Buscador.
- Botones.
- Layout responsive.
- Estilos auxiliares reutilizados por varias pantallas.

### `alta_negocio.html`

Pagina publica para crear un negocio.

Flujo:

1. Comprueba sesion con `/auth/me`.
2. Presenta un wizard por pasos.
3. Recoge nombre, categoria, descripcion, datos de contacto, horarios, coordenadas y fotografia.
4. Permite escoger categoria desde un modal personalizado.
5. Permite ubicar el negocio en mapa con Leaflet y reverse geocoding de Nominatim.
6. Construye el payload del negocio.
7. Envia el alta a `POST /places`.
8. Si hay foto principal, la sube a `POST /places/{id}/main_photo`.
9. Muestra modal de exito y vuelve a la principal.

Validaciones destacadas:

- Nombre y categoria obligatorios.
- Consentimiento si se publican datos de contacto.
- Horarios en estructura por dia.
- Coordenadas normalizadas.

### `negocio.html`

Pagina de detalle de un negocio.

Funciones:

- Carga ficha con `GET /places/{place_id}`.
- Muestra banner, categoria, estado abierto/cerrado, contacto, descripcion, fotos y ubicacion.
- Calcula estado horario en cliente segun horarios recibidos.
- Carga resumen de resenas con `GET /places/{place_id}/reviews?sample=true&limit=3`.
- Carga listado completo de resenas con sort y limite.
- Permite crear resena con `POST /places/{place_id}/reviews`.
- Permite reportar resenas con `POST /reviews/{review_id}/report`.
- Abre chat con el negocio mediante `POST /messages/chats/from_place/{place_id}`.
- Consulta usuario actual con `/users/me`.
- Gestiona suscripcion push igual que otras pantallas autenticadas.
- Usa el listado de negocios para cabecera/busqueda.

Si el negocio no existe o esta desactivado, presenta un estado 404 visual.

### `negocios_gestion.html`

Panel publico para propietarios de negocios.

Aunque tambien aparece en admin 2.4, en public 4.3 sirve como panel de acceso del propietario.

Funciones:

- Login de negocio con `/auth/login`.
- Verificacion de login con `/auth/login/verify`.
- Cambio obligatorio de contrasena con `/users/change_password`.
- Recuperacion de contrasena con `/auth/forgot_password` y `/auth/reset_password/verify`.
- Consulta de configuracion publica con `/meta/public-config`.
- Carga negocio vinculado con `/business/me`.
- Actualiza datos del negocio con `PUT /business/me`.
- Sube foto principal con `POST /business/me/main_photo`.
- Sube fotos extra con `POST /business/me/photos`.
- Borra fotos extra con `DELETE /business/me/photos`.
- Permite horarios normales, dias especiales, descripcion, contacto, web, email, mapa y categoria.
- Usa `sessionStorage` para recordar logout local y usuario del panel.

Este panel depende de que el usuario tenga rol `business` y negocio vinculado.

### `login.html`

Pantalla publica de inicio de sesion.

Funciones:

- Login por usuario/email y contrasena con `POST /auth/login`.
- Segundo paso de verificacion con `POST /auth/login/verify` si aplica.
- Antibot mediante `/public/antibot/challenge`.
- Captcha propio mediante `/public/captcha/challenge` y `/public/captcha/verify`.
- OAuth usando `/auth/oauth/providers` y redireccion al proveedor configurado.
- Cambio de contrasena si el backend marca `must_change_password`.
- Recuperacion de contrasena con `/auth/forgot_password` y `/auth/reset_password/verify`.
- Redireccion posterior mediante parametro `redirect`.

### `register.html`

Pantalla de creacion de cuenta.

Funciones:

- Comprueba disponibilidad con `POST /auth/register/check`.
- Usa antibot y captcha igual que login.
- Envia codigo de email con `POST /auth/register/email_code/send`.
- Verifica codigo con `POST /auth/register/email_code/verify`.
- Registra cuenta con `POST /auth/register`.
- Ofrece OAuth si hay proveedores configurados.

### `perfil.html`

Perfil publico de usuario.

Funciones:

- Consulta sesion con `/auth/me`.
- Carga perfil publico con `/profiles/{user_id}`.
- Carga resenas del usuario con `/profiles/{user_id}/reviews?limit=20`.
- Permite iniciar chat privado con `POST /messages/chats/with_user/{user_id}`.

### `support.html`

Formulario publico de soporte.

Funciones:

- Requiere sesion con `/users/me`.
- Permite elegir asunto, asunto personalizado y cuerpo.
- Permite adjuntos.
- Envia ticket con `POST /support/tickets`.
- Muestra feedback visual de envio.

### `scan_qr.html`

Pantalla de escaneo QR.

Funciones:

- Consulta reglas publicas de QR con `/qr/settings/public?app_mode=...`.
- Usa camara del dispositivo si el navegador/WebView lo permite.
- Aplica reglas segun modo cliente o admin.

### `versiones.html` y `versiones_cliente.html`

Paginas publicas de descarga de APKs.

- `versiones.html`: muestra APK activa de cliente y administracion usando `/android/versions/public`.
- `versiones_cliente.html`: muestra solo la ultima version activa de cliente.

Ambas formatean fecha, version, notas, tamano y enlace de descarga.

### Documentos legales

Archivos:

- `cookies.html`.
- `terminos.html`.
- `privacidad.html`.
- `aviso_legal.html`.

Funcion:

- Informan de cookies, privacidad, terminos, titularidad y condiciones.
- Incluyen banner/configuracion de cookies.
- En algunos textos se observan caracteres mojibake heredados en esta snapshot, por ejemplo `PolÃ­tica`; conviene corregirlos en futuras releases para cumplir UTF-8 limpio.

### `sw.js`

Service Worker publico.

Funciones:

- Instalacion y activacion.
- Estrategias de fetch con fallback seguro.
- Recepcion de mensajes desde la pagina.
- Manejo de clicks en notificaciones.
- Manejo de push.

Sirve para PWA, cache basico y notificaciones web.

### `manifest.webmanifest`

Manifest PWA.

Define nombre, iconos, colores y modo de visualizacion de la aplicacion web instalable.

### `west_widget.js` y `west_widget.css`

Widget de asistente integrado visualmente en la web publica.

Por alcance, no se documenta la logica interna del chatbot propio. Solo queda registrado que:

- Crea markup del panel flotante.
- Guarda conversacion en `localStorage`.
- Puede llamar a un endpoint externo configurado para respuesta en streaming.
- Ajusta posicion respecto al footer y al viewport.

## Panel de administracion 2.4

La version admin 2.4 esta en `web/versions_web/admin/2.4`.

El acceso principal es `/administracion/index-panel.html`. El backend protege la mayoria de paginas admin con `get_admin_session`.

### `index-panel.html`

Es el shell principal de administracion.

Funciones:

- Login admin con `/admin/auth/login`.
- Logout con `/admin/auth/logout`.
- Restauracion de sesion con `/admin/auth/restore`.
- Estado de sesion con `/admin/auth/status`.
- Datos del admin con `/admin/auth/me`.
- Recuperacion admin con `/admin/auth/forgot/request` y `/admin/auth/forgot/verify`.
- Configuracion de sesion con `/admin/settings/session`.
- Configuracion de visibilidad con `/admin/settings/visibility`.
- Consulta versiones web con `/admin/web_versions` y version publica con `/web/versions/public`.
- Recuerda ultimo panel abierto en `localStorage`.
- Usa desafio antibot y hCaptcha si esta configurado.

Actua como lanzador/navegador del resto de secciones administrativas.

### `admin_negocios.html`

Gestion administrativa de negocios.

Funciones:

- Lista negocios desde `/places`.
- Crea negocios con `POST /places`.
- Actualiza negocios con `PUT /places/{id}`.
- Elimina negocios con `DELETE /places/{id}`.
- Activa/desactiva negocios con `PUT /places/{id}/active`.
- Sube foto principal con `POST /places/{id}/main_photo`.
- Puede refrescar cache de IA/contexto con `/admin/ia/cache/refresh`.
- Usa imagen por defecto `/icono/tsev2.png` si hace falta.
- Gestiona categoria, contacto, direccion, horarios, fotos, coordenadas y estado.

El backend envia email al propietario cuando cambia estado activo/inactivo si hay correo resoluble.

### `admin_usuarios.html`

Gestion de usuarios.

Funciones:

- Lista usuarios con `/users`.
- Crea usuarios con `POST /users`.
- Edita usuarios con `PUT /users/{id}`.
- Elimina usuarios con `DELETE /users/{id}` tras verificar contrasena admin con `/admin/auth/verify_password`.
- Resetea contrasena con `POST /users/{id}/reset_password`.
- Consulta y actualiza roles con `/admin/users/{id}/roles`.
- Carga negocios para vincular rol business.
- Permite chat admin-usuario con `/admin/users/{id}/chat` y `/admin/users/{id}/chat/messages`.
- Permite editar/eliminar mensajes enviados por Administracion.

Roles soportados:

- Cliente.
- Negocio.
- Administrador.

Si se asigna rol negocio, se vincula un `place_public_id` al usuario.

### `admin_reviews.html`

Moderacion de resenas, reportes y feedback.

Funciones:

- Lista resenas con `/admin/reviews`.
- Modera resenas con `/admin/reviews/{review_id}/moderate`.
- Gestiona revisiones de resenas con `/admin/reviews/{review_id}/revision`.
- Lista reportes con `/admin/review_reports`.
- Modera reportes con `/admin/review_reports/{report_id}`.
- Lista feedback con `/admin/feedback`.
- Cambia estado de feedback con `/admin/feedback/{feedback_id}/status`.
- Abre conversacion de feedback con `/admin/feedback/{feedback_id}/conversation`.
- Envia mensajes en conversacion con `/admin/feedback/{feedback_id}/conversation/messages`.

Es el punto de control de reputacion y mejoras reportadas por usuarios.

### `admin_support.html`

Administracion de soporte.

Funciones:

- Carga metricas con `/admin/support/metrics`.
- Lista tickets con filtros usando `/admin/support/tickets`.
- Abre detalle con `/admin/support/tickets/{ticket_id}`.
- Responde tickets con `/admin/support/tickets/{ticket_id}/messages`.
- Cierra o reabre tickets con `/admin/support/tickets/{ticket_id}/close`.
- Envia email asociado a ticket con `/admin/support/tickets/{ticket_id}/email`.

Soporta adjuntos y comunicacion interna/externa con usuarios.

### `admin_mails.html`

Cliente de correo admin.

Funciones:

- Resuelve destinatarios con `/admin/mail/resolve`.
- Lista carpetas y mensajes con `/admin/mail/inbox`.
- Abre mensaje con `/admin/mail/inbox/{uid}`.
- Marca leido/no leido/destacado con `/admin/mail/inbox/{uid}/flags`.
- Mueve a papelera con `/admin/mail/inbox/{uid}/trash`.
- Envia correos con `/admin/mail/send`.
- Permite redactar, responder, reenviar, adjuntar archivos y seleccionar multiples mensajes.

El backend puede usar IMAP/SMTP o Gmail API segun variables configuradas.

### `admin_versions.html`

Control de versiones web y Android.

Funciones Android:

- Consulta versiones con `/admin/android_versions`.
- Lanza compilacion APK con `/admin/android_versions/build`.
- Consulta estado con `/admin/android_versions/build_status`.
- Marca una APK como activa con `/admin/android_versions/use`.
- Persiste job en `localStorage` para continuar polling tras recargar.

Funciones web:

- Consulta versiones con `/admin/web_versions`.
- Crea snapshot con `/admin/web_versions/create`.
- Actualiza notas/version con `/admin/web_versions/update`.
- Marca version live con `/admin/web_versions/use`.
- Marca version de pruebas con `/admin/web_versions/use_test`.
- Elimina snapshot con `/admin/web_versions/delete`.
- Sincroniza snapshot con `/admin/web_versions/sync`.

Gestiona cuatro bloques visuales:

- APK cliente.
- APK administracion.
- Web publica.
- Web administracion.

### `ip_log.html`

Panel tecnico de logs/terminal.

Funciones:

- Consulta estado del stack con `/administracion/api/tse/state`.
- Abre WebSocket SSH con `/administracion/api/ssh/ws`.
- Reinicia backend con `/administracion/api/backend/restart`.
- Reinicia API de agentes con `/administracion/api/agents/restart`.
- Consulta accion terminal sugerida con `/administracion/api/tse/terminal-action`.
- Reinicia servicios con `/administracion/api/tse/restart-services`.
- Usa xterm.js y xterm-addon-fit incluidos en `vendor/`.

El acceso esta pensado para administradores y, en algunos casos, cliente local o sesion admin valida.

### `ui_admin.js` y `ui_admin.css`

Recursos compartidos admin.

- Estilos y helpers comunes.
- Interceptores o wrappers usados por paginas admin.
- Mantienen coherencia visual y de comportamiento entre paneles.

### `main.py`

Archivo pequeno dentro del snapshot admin. No parece ser el backend principal. El backend real es `frontend_backend.py` en la raiz de `agents`.

## Autenticacion y cuentas

### Usuario publico

Flujo principal:

1. Registro en `register.html`.
2. Validacion antibot/captcha.
3. Verificacion opcional por email.
4. Login en `login.html`.
5. Cookie `tsev_session`.
6. Acceso a perfil, mensajes, soporte, resenas y panel de negocio si tiene rol adecuado.

Endpoints clave:

- `POST /auth/register`.
- `POST /auth/register/check`.
- `POST /auth/register/email_code/send`.
- `POST /auth/register/email_code/verify`.
- `POST /auth/login`.
- `POST /auth/login/verify`.
- `POST /auth/logout`.
- `GET /auth/me` y `GET /users/me`.
- `POST /auth/forgot_password`.
- `POST /auth/reset_password/verify`.
- `POST /users/change_password`.

### OAuth

El backend ofrece:

- `GET /auth/oauth/providers`.
- `GET /auth/oauth/{provider}/start`.
- `GET /auth/oauth/google/callback`.
- `GET /auth/oauth/microsoft/callback`.

La disponibilidad depende de variables de entorno configuradas.

### Administracion

Flujo:

1. Admin entra a `/administracion/index-panel.html`.
2. Login con `/admin/auth/login`.
3. Se crea cookie `tsev_admin_session`.
4. El panel puede restaurar o validar la sesion.
5. Las paginas admin protegidas dependen de `get_admin_session`.

Endpoints clave:

- `POST /admin/auth/login`.
- `GET /admin/auth/me`.
- `GET /admin/auth/status`.
- `POST /admin/auth/logout`.
- `POST /admin/auth/restore`.
- `POST /admin/auth/verify_password`.
- `GET/PUT /admin/settings/session`.
- `GET/PUT /admin/settings/visibility`.

## Negocios

### Modelo funcional

Un negocio tiene:

- `public_id` visible en URLs y APIs.
- Nombre normalizado.
- Categoria.
- Direccion.
- Telefono.
- Web.
- Email publico o email de contacto.
- Descripcion e initial phrase.
- Horarios normales.
- Dias especiales.
- Coordenadas.
- Fotos.
- Estado activo/inactivo.
- Propietario opcional (`owner_user_id`).

### Alta publica

Desde `alta_negocio.html`, cualquier usuario con sesion puede solicitar/crear un negocio con `POST /places` y subir foto principal.

### Gestion admin

Desde `admin_negocios.html`, administracion puede crear, editar, eliminar y activar/desactivar cualquier negocio.

### Gestion propietario

Desde `negocios_gestion.html`, un usuario con rol negocio puede editar su propio negocio mediante `/business/me`.

## Mensajeria

La mensajeria tiene chats privados y mensajes globales.

Endpoints principales:

- `POST /messages/chats/from_place/{place_id}`: abre chat con negocio.
- `POST /messages/chats/with_user/{target_user_id}`: abre chat privado con usuario.
- `GET /messages/chats`: lista chats del usuario.
- `GET /messages/chats/{chat_id}`: detalle de chat.
- `GET /messages/chats/{chat_id}/messages`: mensajes del chat.
- `POST /messages/chats/{chat_id}/messages`: envia mensaje con texto y adjunto opcional.
- `PATCH /messages/chats/{chat_id}/rename`: renombra chat.
- `PATCH /messages/chats/{chat_id}/block`: bloquea/desbloquea.
- `DELETE /messages/chats/{chat_id}`: elimina/oculta chat.
- `GET/POST /messages/global`: mensajes globales.

El admin tiene endpoints especiales para conversar con usuarios desde `admin_usuarios.html`.

## Resenas

### Publico

En `negocio.html` y perfiles publicos:

- Ver resenas de negocio: `GET /places/{place_id}/reviews`.
- Crear resena: `POST /places/{place_id}/reviews`.
- Editar resena propia: `PUT /users/me/reviews/{review_id}`.
- Eliminar resena propia: `DELETE /users/me/reviews/{review_id}`.
- Votar resena: `POST /reviews/{review_id}/vote`.
- Reportar resena: `POST /reviews/{review_id}/report`.
- Ver resenas de usuario: `GET /profiles/{user_id}/reviews`.

### Admin

En `admin_reviews.html`:

- Moderar resenas.
- Revisar cambios solicitados.
- Gestionar reportes.
- Gestionar feedback/mejoras.

## Soporte y feedback

### Usuario

`support.html` crea tickets con asunto, cuerpo y adjuntos.

Endpoints:

- `POST /support/tickets`.
- `GET /support/tickets/my`.
- `GET /support/tickets/{ticket_id}`.
- `POST /support/tickets/{ticket_id}/messages`.
- `PATCH /support/tickets/{ticket_id}/rename`.
- `PATCH /support/tickets/{ticket_id}/block`.
- `DELETE /support/tickets/{ticket_id}`.

### Admin

`admin_support.html` gestiona:

- Metricas.
- Listado filtrado.
- Conversacion.
- Cierre/reapertura.
- Envio de email con adjuntos.

## Notificaciones

El sistema soporta dos vias:

- Web Push con VAPID para navegador/PWA.
- Firebase Cloud Messaging para Android cliente.

Endpoints:

- `GET /notifications/vapid_public_key`.
- `POST /notifications/subscribe`.
- `POST /notifications/unsubscribe`.
- `GET /notifications/fcm/status`.
- `POST /notifications/fcm/register`.
- `POST /notifications/fcm/unregister`.
- `GET /notifications/fcm/me`.

Archivos Android relevantes:

- Cliente: `android/app/google-services.json` si se usa Firebase.
- Backend: `FIREBASE_SERVICE_ACCOUNT_FILE` o `FIREBASE_SERVICE_ACCOUNT_JSON`.

## Versiones Android

El archivo `android_versions.json` registra APKs activas y historicas.

Estado observado:

- Cliente activo: `2.6`, notas `modificaciones Qr`.
- Admin activo: `1.5`, notas `05/03/2026`.

El backend puede compilar y publicar APKs desde el panel admin si el servidor tiene Android SDK y JDK configurados.

Directorios:

- `android/`: app cliente WebView, URL por defecto `https://todosevillaeste.es`.
- `android_admin/`: app admin WebView, URL por defecto `https://todosevillaeste.es/administracion/index-panel.html?android_admin=1`.

Permisos cliente:

- Internet.
- Estado de red.
- Camara.
- Notificaciones.

Permisos admin:

- Internet.
- Estado de red.
- Camara.

Ambas apps permiten cleartext para desarrollo local y subida de archivos desde WebView.

## SPA Vue/Vite en `web/app`

La SPA moderna existe como migracion progresiva.

Tecnologias:

- Vue 3.
- Vue Router.
- Pinia.
- Vite.

Comandos:

- `npm run dev`.
- `npm run build`.
- `npm run preview`.
- `npm run lint:routes`.

Rutas Vue declaradas:

- `/`: home.
- `/public/businesses`: negocios publicos.
- `/business`: detalle negocio.
- `/messages`: mensajes.
- `/support/new`: soporte.
- `/profile`: perfil.
- `/admin/businesses`: admin negocios.
- `/admin/users`: admin usuarios.
- `/admin/reviews`: admin resenas.
- `/admin/support`: admin soporte.
- `/admin/versions`: admin versiones.
- `/legacy/:page`: iframe/puente a paginas legacy.

`legacy-pages.js` mapea nombres a HTML legacy, por ejemplo:

- `frontend` a `/frontend.html`.
- `negocio` a `/negocio.html`.
- `admin_negocios` a `/administracion/admin_negocios.html`.
- `business` a `/administracion/negocios_gestion.html`.

La libreria `src/lib/api.js` centraliza llamadas fetch con `credentials: include` y funciones para negocios, mensajes, soporte, resenas, admin y versiones.

## Herramientas estaticas y mounts

El backend monta directorios estaticos:

- `/icono` -> `web/icono`.
- `/img` -> `web/img`.
- `/creador_qr` -> `web/creador_qr`.
- `/downloads` -> `web/downloads`.
- `/user_avatars` -> avatars.
- `/account` -> `account`.
- `/manuales` -> herramientas manuales.
- `/planos` -> herramientas planos.
- `/checklists` -> checklists.
- `/herramientas` -> herramientas generales.
- `/rack2` -> rack legacy.
- `/frontend` -> frontend legacy.
- `/administracion/assets` -> assets admin.
- `/web` -> carpeta web completa para compatibilidad.

## Servicios y despliegue

Scripts principales:

- `scripts/install_todosevillaeste_stack_systemd.sh`.
- `scripts/uninstall_todosevillaeste_stack_systemd.sh`.

El instalador crea:

- `todosevillaeste-frontend.service`: ejecuta `uvicorn frontend_backend:app` en puerto `8001`.
- `todosevillaeste-agents.service`: ejecuta `uvicorn agents_main:app` en puerto `8000`.
- `todosevillaeste-stack.target`: agrupa ambos servicios.
- `/etc/default/todosevillaeste-stack`: define `TSE_FRONTEND_PORT=8001` y `TSE_AGENTS_PORT=8000`.

Comandos de desarrollo:

```bash
python -m uvicorn frontend_backend:app --host 0.0.0.0 --port 8001
python -m uvicorn agents_main:app --host 0.0.0.0 --port 8000
```

## Configuracion importante

Variables y archivos que afectan al comportamiento:

- DB: `DB_READ_HOST`, `DB_READ_PORT`, `DB_READ_USER`, `DB_READ_PASSWORD`, `DB_READ_DATABASE`.
- Servicios: `TSE_START_CMD`, `TSE_STOP_CMD`, `TSE_RESTART_CMD`, `AGENTS_RESTART_CMD`.
- Admin SSH: `ADMIN_SSH_HOST`, `ADMIN_SSH_PORT`, `ADMIN_SSH_USER`.
- Firebase: `FIREBASE_SERVICE_ACCOUNT_FILE`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `FIREBASE_PROJECT_ID`.
- Gmail/IMAP/SMTP: variables de correo admin y OAuth Gmail si se usan.
- Captcha: secretos Turnstile, hCaptcha o captcha propio segun configuracion.
- Versiones: `web_versions.json`, `android_versions.json`.
- Visibilidad: `visibility_config.json`.

## Flujo de una visita publica

1. Usuario entra en `/`.
2. Backend redirige a `/frontend.html`.
3. `frontend.html` se resuelve desde `public/4.3`.
4. La pagina carga CSS/JS compartidos.
5. Consulta `/places` para pintar negocios.
6. Consulta `/auth/me` para saber si hay sesion.
7. Consulta `/public/visibility` para ocultar o mostrar funcionalidades.
8. Si hay cambios de version, `ui_public.js` detecta `/web/versions/public` o SSE y muestra aviso.
9. Si el usuario entra en un negocio, `negocio.html` carga ficha, resenas, mapa y acciones.

## Flujo de administracion

1. Admin entra en `/administracion`.
2. Backend redirige a `/administracion/index-panel.html`.
3. `index-panel.html` se resuelve desde `admin/2.4`.
4. Admin inicia sesion y obtiene cookie `tsev_admin_session`.
5. Desde el panel abre secciones:
   - Negocios.
   - Usuarios.
   - Resenas.
   - Soporte.
   - Versiones.
   - Mails.
   - Logs/terminal.
6. Cada seccion llama endpoints admin protegidos.
7. Los cambios afectan DB, JSON de versionado, archivos de imagen/APK o servicios del sistema segun la accion.

## Riesgos y puntos delicados

- Hay HTML legacy grande con mucha logica inline. Cambios pequenos pueden afectar varias rutas.
- `web_versions.json` decide que se sirve: editar snapshots sin activar la version no cambia produccion.
- `public/4.3` contiene algunos textos con mojibake heredado en documentos legales/perfil. Conviene limpiarlos en una release posterior.
- El panel admin puede reiniciar servicios y abrir terminal SSH. Hay que mantener proteccion por sesion admin/local.
- Las rutas de negocio usan `public_id`, no necesariamente `id` interno.
- La gestion de roles business depende de que el usuario tenga negocio vinculado.
- Las notificaciones requieren configuracion externa correcta: VAPID para web, Firebase para Android.
- La compilacion Android desde admin depende de SDK/JDK instalados en servidor.
- En rutas UNC de Windows, `npm run build` puede fallar; se recomienda ruta local o unidad mapeada.

## Checklist rapido para futuras releases

Antes de publicar:

- Comprobar `web_versions.json` y `android_versions.json`.
- Probar `/frontend.html`.
- Probar `/login.html` y `/register.html`.
- Probar `/negocio.html?id=...` o ruta equivalente usada por la UI.
- Probar `/alta_negocio.html` con y sin foto.
- Probar `/negocios_gestion.html` con usuario rol negocio.
- Probar `/support.html` con usuario logueado.
- Probar `/administracion/index-panel.html`.
- Probar admin negocios, usuarios, reviews, soporte y versiones.
- Verificar que los modales sean personalizados y no `alert/confirm/prompt` nativos en nuevas modificaciones.
- Revisar UTF-8 y ausencia de mojibake.
- Verificar service worker si se tocaron cache, PWA o push.
- Si se publica APK, comprobar descarga publica y version activa.

## Que queda fuera de este documento

Queda fuera la explicacion interna del chatbot propio y su razonamiento/modelos/prompts. Solo se menciona cuando una pagina publica integra visualmente el widget o llama a la API auxiliar, porque forma parte del cableado de la interfaz.
