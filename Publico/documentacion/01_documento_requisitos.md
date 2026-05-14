# Documento de Requisitos - TodoSevillaEste

## 1. Objetivo del sistema

TodoSevillaEste es una plataforma web y móvil para descubrir negocios de Sevilla Este, consultar fichas, registrarse como usuario, valorar negocios, contactar mediante mensajería, solicitar soporte, publicar o gestionar negocios y administrar el ecosistema desde un panel interno.

El sistema debe funcionar como:

- Directorio público de negocios.
- Plataforma de cuentas de cliente.
- Panel de gestión para propietarios de negocios.
- Panel de administración para usuarios autorizados.
- Canal de soporte y feedback.
- Sistema de publicación de versiones web y APK.
- Integración con asistente de IA de alcance público controlado.

## 2. Roles

### Visitante no registrado

Puede consultar páginas públicas, negocios activos, documentos legales, versiones APK públicas, visibilidad pública, buscador y, si está habilitado, el asistente público. No puede crear reseñas, usar mensajería privada, abrir tickets autenticados ni gestionar negocios.

### Cliente registrado

Puede iniciar sesión, editar su perfil, subir avatar, cambiar contraseña y email, eliminar cuenta, crear reseñas, votar reseñas, reportar contenido, abrir chats, enviar mensajes, crear tickets de soporte y solicitar alta de negocio.

### Usuario negocio

Es un usuario con rol `business` y negocio vinculado mediante `owner_user_id` o `place_user_assignments`. Puede acceder a `negocios_gestion.html`, modificar su ficha, subir o eliminar fotos, cambiar horarios, actualizar contacto y gestionar datos públicos del negocio asignado.

### Administrador

Puede acceder a `/administracion/index-panel.html` con cookie `tsev_admin_session`. Gestiona usuarios, roles, negocios, reseñas, reportes, soporte, feedback, correo, versiones web/APK, visibilidad, sesiones admin, terminal SSH, reinicios y herramientas técnicas.

### Sistema/servicio

Incluye procesos FastAPI, service worker, WebView Android, jobs de build APK, Web Push, FCM, correo SMTP/IMAP/Gmail API, OAuth, captcha y API de IA.

## 3. Requisitos funcionales públicos

### RF-PUB-01 Página principal

La web pública debe servir `/frontend.html` desde la versión activa indicada en `web_versions.json`. Debe cargar negocios desde `GET /places`, mostrar fichas activas, permitir búsqueda, mostrar estado de sesión y respetar `/public/visibility`.

### RF-PUB-02 Búsqueda de negocios

El usuario debe poder buscar negocios por nombre, categoría, descripción y datos públicos. El buscador debe usar normalización de texto y sugerencias locales/remotas cuando estén disponibles.

### RF-PUB-03 Detalle de negocio

La página `negocio.html` debe cargar la ficha mediante `GET /places/{place_id}` y mostrar nombre, categoría, dirección, teléfono, web, email público si procede, descripción, horarios, estado abierto/cerrado, fotos, mapa y reseñas.

### RF-PUB-04 Alta de negocio

Un usuario autenticado debe poder crear un negocio desde `alta_negocio.html`, enviando datos a `POST /places` y foto principal a `POST /places/{id}/main_photo`. Debe validar nombre, categoría, consentimiento de contacto y coordenadas.

### RF-PUB-05 Registro

El sistema debe permitir registro con usuario, email, contraseña, fecha de nacimiento opcional, antibot, captcha y verificación por email cuando esté habilitada.

### RF-PUB-06 Inicio de sesión

El sistema debe permitir login con usuario/email y contraseña, verificación por código si aplica, captcha/antibot, opción recordar sesión y OAuth Google/Microsoft si está configurado.

### RF-PUB-07 Perfil

El usuario debe poder consultar su perfil, actualizar nombre/email/avatar/contraseña, revisar sus reseñas, abrir chats y eliminar su cuenta tras validación.

### RF-PUB-08 Reseñas

Los usuarios autenticados deben poder crear, editar y eliminar sus reseñas, adjuntar fotos, votar reseñas de otros usuarios y reportar contenido inadecuado.

### RF-PUB-09 Mensajería

Los usuarios autenticados deben poder crear chats con negocios o usuarios, enviar texto y adjuntos, listar conversaciones, renombrarlas, bloquearlas, borrar mensajes propios y ocultar chats.

### RF-PUB-10 Soporte

Los usuarios deben poder abrir tickets con asunto, cuerpo, email asociado y adjuntos. Deben poder listar sus tickets, responder, renombrar, bloquear u ocultar conversaciones según permisos.

### RF-PUB-11 Feedback

La plataforma debe recoger feedback de mejora con email, valoración, asunto y descripción. Administración debe poder responder y cambiar estado.

### RF-PUB-12 Versiones públicas

La web debe mostrar APKs activas de cliente y administración mediante `/android/versions/public`, incluyendo versión, notas, fecha, tamaño y enlace de descarga.

### RF-PUB-13 PWA y notificaciones

La web pública debe poder funcionar como PWA con `manifest.webmanifest` y `sw.js`. Si VAPID está configurado, debe permitir suscripción Web Push. En Android cliente debe registrar tokens FCM.

### RF-PUB-14 QR

La pantalla `scan_qr.html` debe consultar `/qr/settings/public` y aplicar permisos según modo cliente o admin.

### RF-PUB-15 Documentos legales

La web debe exponer aviso legal, privacidad, cookies y términos desde rutas públicas compatibles (`/aviso_legal.html`, `/privacidad.html`, `/cookies.html`, `/terminos.html` y aliases).

## 4. Requisitos funcionales de negocios

### RF-NEG-01 Acceso propietario

El propietario debe iniciar sesión y acceder a `negocios_gestion.html`. El backend debe validar sesión y rol negocio antes de permitir `/business/me`.

### RF-NEG-02 Edición de ficha

El propietario debe poder modificar nombre, categoría, dirección, teléfono, web, email, descripción, frase inicial, horarios, días especiales, coordenadas y visibilidad de contacto.

### RF-NEG-03 Gestión de fotos

El propietario debe poder subir foto principal, subir fotos extra y eliminar fotos extra de su negocio. Los archivos deben guardarse bajo `web/img/businesses`.

### RF-NEG-04 Validación de propiedad

El propietario solo puede modificar negocios asociados a su usuario. La asociación debe resolverse por `owner_user_id` o `place_user_assignments`.

## 5. Requisitos funcionales de administración

### RF-ADM-01 Login admin

El panel debe autenticar administradores con usuario, email, contraseña, modo de sesión, duración opcional, captcha/antibot y cookie `tsev_admin_session`.

### RF-ADM-02 Gestión de negocios

Administración debe listar, crear, editar, activar/desactivar, eliminar negocios, subir fotos y refrescar cache de IA.

### RF-ADM-03 Gestión de usuarios

Administración debe listar, crear, editar, eliminar usuarios, resetear contraseñas, asignar roles cliente/negocio/admin y vincular negocios.

### RF-ADM-04 Moderación

Administración debe listar reseñas, ocultar/mostrar, solicitar revisión, resolver reportes, cambiar estado de feedback y responder conversaciones.

### RF-ADM-05 Soporte

Administración debe listar tickets, filtrar por estado, ver métricas, responder, cerrar/reabrir y enviar emails vinculados.

### RF-ADM-06 Correo admin

Administración debe consultar buzón, carpetas, mensajes, marcar leído/destacado, mover a papelera, redactar, responder, reenviar y adjuntar archivos.

### RF-ADM-07 Versiones

Administración debe crear snapshots, activar versiones públicas/admin, marcar versiones de prueba, actualizar notas, sincronizar snapshots, eliminar snapshots y compilar/publicar APKs.

### RF-ADM-08 Operación técnica

Administración debe consultar estado del stack, abrir terminal SSH, reiniciar backend, reiniciar API de agentes y ejecutar acciones controladas del servicio.

### RF-ADM-09 Configuración

Administración debe cambiar duración/modo de sesión, reglas QR y visibilidad pública/IA.

## 6. Requisitos funcionales de IA

### RF-IA-01 Chat público

El frontend puede llamar a `/agents/public/chat` o `/agents/public/chat/stream` a través del backend. La IA debe responder con contexto público y no inventar datos no presentes.

### RF-IA-02 Cache pública

La API de agentes debe cachear negocios públicos y refrescarlos por tiempo o por petición admin (`/admin/ia/cache/refresh`).

### RF-IA-03 Feedback de aprendizaje

La API debe aceptar feedback en `/agents/learning/feedback`, guardarlo en `data/learning_memory.json` y usar ejemplos limitados en prompts futuros.

### RF-IA-04 Límite de privacidad

La IA no debe recibir contraseñas, sesiones, datos admin internos ni información privada no publicada. Debe usar únicamente contexto público de negocios y documentación cargada explícitamente.

## 7. Requisitos no funcionales

### RNF-01 Seguridad

Las rutas de usuario deben requerir `tsev_session`; las rutas admin deben requerir `tsev_admin_session`; las acciones críticas deben verificar contraseña o sesión admin válida.

### RNF-02 Disponibilidad

El backend principal y la API de agentes deben poder ejecutarse como servicios systemd independientes agrupados por `todosevillaeste-stack.target`.

### RNF-03 Rendimiento

Las consultas públicas deben usar endpoints simples y cache cuando aplique. La IA debe limitar caracteres de contexto y memoria para evitar latencias excesivas.

### RNF-04 Compatibilidad

La web debe funcionar en navegador móvil/escritorio, PWA y Android WebView. Las rutas legacy deben mantenerse por compatibilidad.

### RNF-05 UTF-8

Todos los documentos y cambios nuevos deben escribirse en UTF-8 limpio, sin mojibake.

### RNF-06 UX

Los modales nuevos de alerta, confirmación y prompt deben ser personalizados y coherentes, evitando diálogos nativos del navegador.

### RNF-07 Observabilidad

Debe existir logging de backend, log de IPs, estado de stack, stream de logs y métricas de soporte.

### RNF-08 Mantenibilidad

El versionado debe separar snapshots públicos/admin, permitir pruebas y evitar mezclar cambios de desarrollo con producción sin activación explícita.

## 8. Criterios de aceptación mínimos

- `/frontend.html` carga sin errores y muestra negocios.
- `/login.html` y `/register.html` completan flujos esperados.
- `/negocio.html` muestra ficha, reseñas y acciones.
- `/negocios_gestion.html` solo permite editar negocio propio.
- `/administracion/index-panel.html` protege acceso admin.
- Admin puede crear/editar/desactivar negocio.
- Admin puede gestionar usuarios y roles.
- Admin puede moderar reseñas y reportes.
- Soporte público y admin funcionan.
- Versiones web/APK se consultan y activan desde panel.
- No se introducen modales nativos en cambios nuevos.
- No se introducen textos con mojibake.

