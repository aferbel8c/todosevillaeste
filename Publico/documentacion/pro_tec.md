# Proyecto técnico - TodoSevillaEste

## 1. Introducción

TodoSevillaEste es una plataforma web y móvil para centralizar información de negocios, usuarios, reseñas, soporte, mensajería, gestión administrativa, versiones de despliegue y asistencia mediante IA. El proyecto combina un backend principal en Python/FastAPI, una API específica para agentes de inteligencia artificial, una web pública legacy versionada, una SPA Vue/Vite en migración progresiva, un panel de administración y dos aplicaciones Android basadas en WebView.

Desde el punto de vista técnico, el sistema está diseñado como una arquitectura modular con un núcleo backend que coordina autenticación, base de datos, archivos, versiones, notificaciones, correo, administración del servidor y comunicación con servicios externos.

## 2. Objetivo técnico del proyecto

El objetivo principal es construir un sistema completo de publicación, gestión y consulta de negocios locales con:

- Web pública para clientes y visitantes.
- Panel de administración para gestionar usuarios, negocios, reseñas, soporte, versiones y servicios.
- Área de negocio para propietarios.
- Sistema de cuentas, sesiones y roles.
- Mensajería entre usuarios y negocios.
- Reseñas, votos y reportes.
- Soporte técnico con tickets.
- Versionado web mediante snapshots.
- Distribución de APKs Android.
- Notificaciones web y móviles.
- Integración de IA con contexto público.
- Herramientas adicionales de manuales, planos, checklists y rack.

El proyecto permite relacionar contenidos de varios módulos del ciclo porque incluye desarrollo backend, frontend, redes, seguridad, administración de servicios, despliegue en Linux, base de datos y programación en Python.

## 3. Estructura general del proyecto

La estructura principal observada es:

```text
agents/
├── frontend_backend.py
├── agents_main.py
├── web/
│   ├── versions_web/
│   │   ├── public/4.3/
│   │   └── admin/2.4/
│   ├── app/
│   ├── img/
│   └── downloads/
├── android/
├── android_admin/
├── scripts/
├── sql/
├── data/
├── web_versions.json
├── android_versions.json
├── admin_auth_config.json
└── admin_sessions.json
```

Los archivos y carpetas principales tienen estas responsabilidades:

- `frontend_backend.py`: backend principal FastAPI. Sirve la web pública, panel admin, APIs de negocio, autenticación, subida de archivos, correo, notificaciones, versiones, herramientas y administración técnica.
- `agents_main.py`: API FastAPI de agentes IA. Gestiona chat, contexto público de negocios, memoria de aprendizaje y conexión con Ollama u OpenRouter.
- `web/versions_web/public/4.3`: snapshot público activo de la versión 4.3.
- `web/versions_web/admin/2.4`: snapshot activo del panel administrativo.
- `web/app`: SPA moderna con Vue 3, Vue Router, Pinia y Vite.
- `android`: aplicación Android de usuario basada en WebView.
- `android_admin`: aplicación Android para administración.
- `scripts`: scripts de instalación y desinstalación systemd.
- `sql`: esquemas auxiliares de base de datos.
- `data`: datos persistentes de agentes y memoria IA.
- `web_versions.json`: catálogo de versiones web públicas y administrativas.
- `android_versions.json`: catálogo de versiones APK.

## 4. Arquitectura lógica

La arquitectura se puede dividir en capas:

```text
Cliente web / Android WebView
        │
        ▼
Frontend legacy HTML/CSS/JS y SPA Vue
        │
        ▼
Backend principal FastAPI
        │
        ├── Base de datos MariaDB/MySQL
        ├── Sistema de archivos
        ├── API de agentes IA
        ├── Correo / Gmail API / SMTP / IMAP
        ├── Web Push / Firebase FCM
        ├── Proxmox / SSH / systemd
        └── Servicios externos OAuth y captcha
```

El backend principal actúa como punto de entrada técnico. Centraliza peticiones públicas, autenticación, administración, persistencia y entrega de archivos. La API de IA queda separada para aislar la lógica de agentes, prompts, caché de negocios y llamadas al modelo.

## 5. Backend principal: `frontend_backend.py`

El backend principal está construido con FastAPI y Uvicorn. Sus responsabilidades técnicas son amplias:

- Servir páginas públicas como `frontend.html`, `login.html`, `register.html`, `negocio.html`, `perfil.html`, `support.html` y `scan_qr.html`.
- Servir snapshots según la versión activa definida en `web_versions.json`.
- Servir el panel admin bajo `/administracion`.
- Exponer endpoints REST para usuarios, negocios, reseñas, mensajes, soporte, feedback, versiones y configuración pública.
- Gestionar sesiones públicas mediante cookie `tsev_session`.
- Gestionar sesiones de administración mediante cookie `tsev_admin_session`.
- Conectar con MariaDB/MySQL usando configuración de lectura y escritura.
- Inicializar o ampliar tablas mediante funciones `ensure_*`.
- Guardar y servir imágenes, avatares, adjuntos y APKs.
- Enviar correo mediante SMTP/IMAP o Gmail API.
- Gestionar notificaciones Web Push y FCM.
- Integrar OAuth de Google/Microsoft si está configurado.
- Validar captcha, antibot, límites de abuso y formularios críticos.
- Exponer estado técnico, logs, reinicio de servicios y terminal SSH para administración.
- Montar recursos estáticos de `web`, `img`, `downloads`, `manuales`, `planos`, `checklists`, `rack2` y SPA Vue.

El archivo concentra gran parte de la lógica del sistema, por lo que representa el núcleo de programación Python y de servicios en red.

## 6. API de agentes IA: `agents_main.py`

La API de IA está separada del backend principal. Sus funciones principales son:

- Crear agentes personalizados.
- Añadir documentos a agentes.
- Atender chat contra agentes concretos.
- Atender chat público sobre TodoSevillaEste.
- Mantener caché de negocios activos.
- Construir contexto público desde base de datos.
- Responder consultas frecuentes mediante reglas, SQL controlado o modelo LLM.
- Usar historial reciente de conversación.
- Guardar aprendizaje en `data/learning_memory.json`.
- Conectar con Ollama o con OpenRouter según variables de entorno.
- Ofrecer streaming de respuesta.

Esta separación ayuda a que la IA no tenga acceso directo a datos privados del usuario. El flujo recomendado consiste en pasarle únicamente información pública o filtrada por reglas del backend.

## 7. Frontend público legacy

La versión pública activa está en:

```text
web/versions_web/public/4.3
```

Incluye páginas HTML, CSS y JavaScript que forman la interfaz pública:

- `frontend.html`: página principal.
- `login.html` y `register.html`: autenticación.
- `negocio.html`: ficha de negocio.
- `alta_negocio.html`: alta pública de negocio.
- `negocios_gestion.html`: gestión para propietarios.
- `perfil.html`: perfil de usuario.
- `support.html`: soporte.
- `scan_qr.html`: escaneo QR.
- `versiones.html` y `versiones_cliente.html`: consulta de versiones.
- `ui_public.js` y `ui_public.css`: lógica y estilos compartidos.
- `header_shared.css`: cabecera común.
- `sw.js` y `manifest.webmanifest`: PWA y service worker.
- Documentos legales y técnicos en `documentacion/`.

La web legacy se comunica con el backend usando `fetch` contra endpoints REST. El backend decide qué snapshot entregar, de modo que producción no depende de editar directamente una única carpeta global.

## 8. Panel de administración

El panel admin activo está versionado en:

```text
web/versions_web/admin/2.4
```

Sus funciones técnicas incluyen:

- Login de administración.
- Gestión de negocios.
- Gestión de usuarios y roles.
- Moderación de reseñas y reportes.
- Gestión de soporte.
- Gestión de versiones web.
- Gestión de versiones Android.
- Correo administrativo.
- Visualización de IPs, logs y estado del sistema.
- Acciones técnicas como reinicios, consulta de servicios y terminal SSH.

El acceso se protege mediante sesión admin y dependencias del backend. Las operaciones críticas deben considerarse de alto riesgo porque pueden modificar datos, versiones publicadas o estado del servidor.

## 9. SPA Vue/Vite

La carpeta `web/app` contiene una SPA moderna con:

- Vue 3.
- Vue Router.
- Pinia.
- Vite.

Sus comandos son:

```bash
npm run dev
npm run build
npm run preview
npm run lint:routes
```

La SPA funciona como migración progresiva desde el frontend legacy. Incluye vistas modernas como:

- `HomeView.vue`
- `PublicBusinessesView.vue`
- `BusinessDetailView.vue`
- `ProfileView.vue`
- `MessagesView.vue`
- `SupportView.vue`
- `AdminBusinessesView.vue`
- `AdminUsersView.vue`
- `AdminReviewsView.vue`
- `AdminSupportView.vue`
- `AdminVersionsView.vue`
- `LegacyFrameView.vue`

`LegacyFrameView` permite integrar páginas antiguas dentro de la navegación moderna, reduciendo el riesgo de una migración completa de golpe.

## 10. Aplicaciones Android

El proyecto tiene dos apps Android:

- `android`: app para usuarios.
- `android_admin`: app para administración.

La app de usuario usa:

- Kotlin.
- Gradle Kotlin DSL.
- WebView.
- Firebase Cloud Messaging.
- WorkManager.
- ZXing para QR.
- Permisos de internet, estado de red, cámara y notificaciones.

La app carga por defecto la web de TodoSevillaEste. Esto reduce duplicación de lógica, porque la experiencia principal vive en la web y Android actúa como contenedor móvil con capacidades nativas puntuales.

## 11. Persistencia de datos

El proyecto combina persistencia relacional y persistencia en archivos.

### Base de datos relacional

La base principal usa MariaDB/MySQL. Las tablas principales observadas o documentadas son:

- `users`: usuarios.
- `sessions`: sesiones públicas.
- `auth_codes`: códigos de verificación.
- `places`: negocios.
- `place_user_assignments`: relación entre usuarios y negocios.
- `reviews`: reseñas.
- `review_votes`: votos de reseñas.
- `review_reports`: reportes de reseñas.
- `chat_threads`: conversaciones.
- `chat_messages`: mensajes.
- `global_chat_messages`: chat global.
- `support_tickets`: tickets de soporte.
- `support_ticket_messages`: mensajes de soporte.
- `feedback_submissions`: feedback.
- `feedback_messages`: mensajes de feedback.
- `push_subscriptions`: suscripciones Web Push.
- `fcm_device_tokens`: tokens FCM Android.

El backend diferencia configuración de lectura y escritura mediante variables `DB_READ_*` y `DB_WRITE_*`, lo que permite separar permisos o destinos si el despliegue lo requiere.

### Archivos JSON y almacenamiento local

Los JSON relevantes son:

- `web_versions.json`: versiones web.
- `android_versions.json`: versiones Android.
- `visibility_config.json`: visibilidad pública e IA.
- `admin_auth_config.json`: credenciales y configuración admin.
- `admin_sessions.json`: sesiones admin.
- `manuales_sessions.json`: sesiones de manuales.
- `data/learning_memory.json`: aprendizaje de IA.

Los archivos subidos se almacenan en:

- `web/img/businesses`
- `web/img/reviews`
- `web/img/messages`
- `web/img/support`
- `user_avatars`
- `web/downloads/android`

## 12. Versionado y despliegue

El versionado web se gestiona mediante snapshots. En `web_versions.json` hay dos bloques:

- `public`: versiones de la web pública.
- `admin`: versiones del panel administrativo.

Cada bloque define:

- `active_id`: versión activa en producción.
- `test_active_id`: versión activa en pruebas.
- `items`: historial de snapshots.

La versión pública activa observada es `4.3`, ubicada en:

```text
web/versions_web/public/4.3
```

La versión admin activa observada es `2.4`, ubicada en:

```text
web/versions_web/admin/2.4
```

En producción se usan servicios systemd:

- `todosevillaeste-frontend.service`
- `todosevillaeste-agents.service`
- `todosevillaeste-stack.target`

Los puertos habituales son:

- Backend principal: `8001`.
- API de agentes: `8000`.
- Vite desarrollo: puerto asignado por Vite.

## 13. Flujos técnicos principales

### Flujo de carga pública

1. El usuario entra en `/` o `/frontend.html`.
2. FastAPI resuelve la versión pública activa.
3. Se entrega `web/versions_web/public/4.3/frontend.html`.
4. El navegador carga CSS, JS, manifest y service worker.
5. La interfaz consulta endpoints como `/places`, `/auth/me`, `/public/visibility` y `/meta/realtime`.
6. Si hay sesión, se habilitan acciones autenticadas.

### Flujo de login público

1. El usuario envía credenciales desde `login.html`.
2. El backend valida antibot/captcha si procede.
3. Se comprueba la contraseña contra el hash almacenado.
4. Se crea sesión en base de datos.
5. Se envía cookie `tsev_session`.
6. Las siguientes peticiones usan esa cookie para obtener el usuario actual.

### Flujo de administración

1. El administrador accede a `/administracion/index-panel.html`.
2. Envía credenciales a `/admin/auth/login`.
3. El backend valida permisos y crea sesión admin.
4. Se establece cookie `tsev_admin_session`.
5. Las páginas admin llaman endpoints `/admin/*`.
6. Las acciones críticas pueden modificar datos, snapshots, APKs o servicios.

### Flujo de IA pública

1. El usuario pregunta desde el widget o frontend.
2. El backend principal deriva la consulta hacia la API de agentes.
3. `agents_main.py` carga contexto público de negocios.
4. La API intenta responder con reglas, SQL seguro o LLM.
5. La respuesta vuelve al cliente.
6. El feedback útil puede almacenarse en memoria limitada.

### Flujo de mensajes

1. Un usuario inicia o abre un hilo con un negocio.
2. El backend valida identidad y participación en el hilo.
3. El mensaje se guarda en `chat_messages`.
4. Se actualiza el estado de lectura o entrega.
5. Si está configurado, se envían notificaciones web o Android.

## 14. Relación con Seguridad Informática

El proyecto trabaja contenidos de seguridad informática en varios niveles:

- Autenticación pública con usuario/email y contraseña.
- Hash de contraseñas en backend.
- Sesiones separadas para usuario y administrador.
- Cookies con configuración de dominio, seguridad y expiración.
- Validación de roles para distinguir usuario normal, propietario de negocio y administrador.
- Captcha, honeypot, antibot y límites contra abuso.
- Protección de endpoints `/admin/*` mediante sesión admin.
- Control de propiedad antes de editar negocios, mensajes o reseñas.
- Moderación y reporte de reseñas.
- Control de subida de archivos.
- Separación entre datos públicos y datos usados por la IA.
- Gestión de secretos mediante variables de entorno.
- Recomendación de HTTPS en producción.
- Terminal SSH tratada como componente crítico.
- Backups de base de datos, JSON, adjuntos, snapshots y configuración.

También permite estudiar riesgos reales:

- Exposición de credenciales si se suben secretos al repositorio.
- Riesgos de una WebView si se permite tráfico no cifrado.
- Riesgos de subida de ficheros.
- Riesgos de prompt injection en IA.
- Riesgos de administración remota mal protegida.
- Necesidad de auditoría y registro de acciones críticas.

## 15. Relación con Servicios en Red

El proyecto usa servicios en red de forma continua:

- Servidor HTTP/API con FastAPI y Uvicorn.
- Endpoints REST para web, administración y apps móviles.
- WebSocket para terminal SSH administrativa.
- Server-Sent Events o streaming para logs y respuestas en tiempo real.
- SMTP/IMAP o Gmail API para correo.
- OAuth con proveedores externos.
- Servicios de captcha externos.
- Firebase Cloud Messaging para notificaciones Android.
- Web Push con claves VAPID para navegador.
- API de IA local o externa mediante Ollama/OpenRouter.
- Consulta de servicios del sistema y reinicio mediante panel admin.

Los puertos principales son:

- `8001` para el backend principal.
- `8000` para la API de agentes.

Esto se relaciona directamente con configuración de servicios, protocolos, cliente-servidor, publicación de recursos y diagnóstico de conectividad.

## 16. Relación con Redes Locales

El proyecto también conecta con redes locales porque se desarrolla y administra sobre una ruta UNC:

```text
\\192.168.0.40\Chatbot\
```

Este detalle implica:

- Uso de un recurso compartido de red.
- Acceso por IP privada `192.168.0.40`.
- Dependencia de conectividad LAN.
- Posibles diferencias entre rutas locales y rutas UNC.
- Necesidad de permisos de lectura/escritura sobre el recurso compartido.
- Diagnóstico de latencia, disponibilidad y resolución de rutas.

Además, el backend puede desplegarse escuchando en `0.0.0.0`, lo que permite recibir conexiones desde otros equipos de la red. Esto requiere comprender:

- IP privada del servidor.
- Puertos abiertos.
- Firewall.
- NAT si se publica hacia internet.
- Diferencia entre `127.0.0.1`, IP local y dominio público.
- Configuración de HTTPS y proxy inverso si se usa en producción.

## 17. Relación con Aplicaciones Web

La parte de aplicaciones web es una de las más importantes del proyecto:

- HTML, CSS y JavaScript legacy para la versión pública.
- SPA moderna con Vue 3.
- Enrutado con Vue Router.
- Estado global con Pinia.
- Build con Vite.
- PWA mediante `manifest.webmanifest` y `sw.js`.
- Consumo de APIs con `fetch`.
- Formularios de login, registro, soporte, alta de negocio y reseñas.
- Componentes de administración.
- Gestión de vistas públicas y privadas.
- Integración de mapas, QR, chats y notificaciones.
- Compatibilidad con WebView Android.

El sistema muestra una transición realista entre una aplicación legacy funcional y una migración incremental a SPA moderna. Esto permite estudiar mantenimiento, refactorización, convivencia de tecnologías y despliegue progresivo.

## 18. Relación con Sistemas Operativos

El proyecto se relaciona con sistemas operativos por:

- Ejecución de servicios Python con Uvicorn.
- Instalación de servicios systemd.
- Scripts de instalación y desinstalación en `scripts/`.
- Variables de entorno para configurar producción.
- Gestión de procesos y reinicios.
- Lectura de logs.
- Permisos sobre archivos subidos y directorios.
- Uso de rutas Windows UNC en desarrollo.
- Uso de Linux en producción.
- Compilación Android con JDK y Android SDK.
- Panel admin con consulta de estado del backend.
- Terminal SSH desde el navegador para administración remota.

Los comandos base de desarrollo son:

```bash
python -m uvicorn frontend_backend:app --host 0.0.0.0 --port 8001
python -m uvicorn agents_main:app --host 0.0.0.0 --port 8000
```

En producción, los servicios systemd permiten arrancar automáticamente el backend y la API de agentes, reiniciarlos y consultar su estado con herramientas propias del sistema operativo.

## 19. Relación con Programación en Python

Python es el lenguaje central del backend. El proyecto usa:

- FastAPI para definir APIs.
- Pydantic para modelos de datos.
- Uvicorn como servidor ASGI.
- Funciones síncronas y asíncronas.
- Middleware HTTP.
- WebSocket.
- Validación de entradas.
- Manejo de ficheros.
- JSON como configuración persistente.
- Conexión a MariaDB/MySQL.
- Hash y verificación de contraseñas.
- Envío y lectura de correo.
- Integración con APIs externas.
- Procesamiento de texto para IA.
- Cachés en memoria.
- Control de errores mediante `HTTPException`.
- Rutas protegidas con dependencias.

`frontend_backend.py` representa programación backend aplicada a un producto completo. `agents_main.py` representa programación Python aplicada a IA, recuperación de contexto, reglas de negocio y conexión con modelos LLM.

## 20. Matriz de relación con los módulos del ciclo

| Módulo | Relación técnica dentro del proyecto |
|---|---|
| Seguridad Informática | Autenticación, sesiones, roles, captcha, cookies, subida de archivos, protección admin, HTTPS, secretos, backups e IA con contexto público. |
| Servicios en Red | APIs HTTP, WebSocket, streaming, correo, OAuth, captcha, FCM, Web Push, Ollama/OpenRouter, publicación con Uvicorn. |
| Redes Locales | Desarrollo sobre `\\192.168.0.40\Chatbot\`, servicios escuchando en red, puertos, firewall, IP privada, acceso LAN y despliegue. |
| Aplicaciones Web | Frontend HTML/CSS/JS, SPA Vue, PWA, consumo de APIs, formularios, panel admin, rutas públicas y privadas. |
| Sistemas Operativos | systemd, scripts, procesos, logs, permisos, variables de entorno, SSH, rutas Windows/Linux, JDK y Android SDK. |
| Programación Python | FastAPI, Pydantic, endpoints, middleware, DB, JSON, ficheros, seguridad, IA, correo, notificaciones y administración. |

## 21. Puntos fuertes técnicos

- Proyecto completo con frontend, backend, móvil, base de datos, IA y administración.
- Separación entre backend principal y API de agentes.
- Versionado por snapshots para web pública y admin.
- Panel de administración con gestión operativa real.
- Integración de notificaciones web y Android.
- Migración progresiva hacia Vue sin abandonar el sistema legacy.
- Uso de variables de entorno para configuración sensible.
- Documentación técnica ya organizada en la versión pública.
- Apps Android reutilizando la web mediante WebView.

## 22. Riesgos técnicos y mejoras recomendadas

- `frontend_backend.py` concentra muchas responsabilidades; sería recomendable dividirlo progresivamente en routers o módulos.
- Revisar que todos los documentos estén guardados en UTF-8 real y sin mojibake.
- Reforzar auditoría de acciones críticas del panel admin.
- Comprobar que cookies estén con `Secure`, `HttpOnly` y `SameSite` adecuados en producción.
- Validar tamaño, extensión y MIME en todas las subidas.
- Mantener secretos fuera del repositorio y rotarlos si han sido expuestos.
- Automatizar backups de base de datos, JSON, imágenes, APKs y snapshots.
- Revisar permisos de la terminal SSH y limitar su uso.
- Añadir pruebas automáticas para endpoints críticos.
- Separar lectura/escritura de base de datos con usuarios de mínimos privilegios.

## 23. Conclusión

TodoSevillaEste no es solo una web informativa: es un sistema técnico completo con backend, frontend, móvil, administración, IA, persistencia, servicios en red, seguridad y despliegue. Por eso encaja especialmente bien como proyecto integrador del ciclo, ya que permite demostrar competencias reales de programación en Python, desarrollo de aplicaciones web, configuración de servicios, administración de sistemas, redes locales y seguridad informática.

La versión pública 4.3 documenta una fase madura del proyecto: mantiene la web legacy productiva, incorpora documentación técnica, conserva versionado de snapshots, integra IA y prepara la evolución hacia una SPA moderna.
