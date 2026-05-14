# Documento de Arquitectura - TodoSevillaEste

## 1. Visión general

TodoSevillaEste usa una arquitectura mixta: backend FastAPI monolítico para la web pública, administración y API de negocio; API FastAPI auxiliar para IA; frontend legacy HTML/JS servido por snapshots versionados; SPA Vue/Vite en migración; y apps Android WebView que cargan la web.

## 2. Componentes

### Backend principal

Archivo: `frontend_backend.py`.

Responsabilidades:

- Servir HTML público y admin.
- Resolver snapshots activos desde `web_versions.json`.
- Exponer API de usuarios, negocios, reseñas, mensajes, soporte, feedback, versiones, correo y administración técnica.
- Gestionar cookies de sesión.
- Conectar con MariaDB/MySQL.
- Subir y servir archivos.
- Integrar Web Push, FCM, OAuth, captcha, correo, Proxmox/SSH y API de agentes.

### API de agentes

Archivo: `agents_main.py`.

Responsabilidades:

- Exponer endpoints de chat IA.
- Leer contexto público desde base de datos.
- Mantener cache de negocios.
- Gestionar agentes personalizados y documentos.
- Guardar feedback de aprendizaje en `data/learning_memory.json`.
- Conectar con Ollama u OpenRouter según configuración.

### Web pública legacy

Ruta activa: `web/versions_web/public/4.3`.

Incluye:

- `frontend.html`: home.
- `login.html`, `register.html`: autenticación.
- `negocio.html`: ficha de negocio.
- `alta_negocio.html`: alta pública.
- `negocios_gestion.html`: panel propietario.
- `perfil.html`: perfil.
- `support.html`: soporte.
- `scan_qr.html`: QR.
- `versiones.html`, `versiones_cliente.html`: APKs.
- `sw.js`, `manifest.webmanifest`: PWA.
- `ui_public.js`, `ui_public.css`, `header_shared.css`.
- Documentos legales HTML.

### Panel admin legacy

Ruta activa: `web/versions_web/admin/2.4`.

Incluye:

- `index-panel.html`: shell/login admin.
- `admin_negocios.html`: negocios.
- `admin_usuarios.html`: usuarios/roles/chat.
- `admin_reviews.html`: reseñas/reportes/feedback.
- `admin_support.html`: soporte.
- `admin_versions.html`: versiones web/APK.
- `admin_mails.html`: correo.
- `ip_log.html`: estado, terminal y logs.
- `ui_admin.js`, `ui_admin.css`.

### SPA Vue/Vite

Ruta: `web/app`.

Tecnologías:

- Vue 3.
- Vue Router.
- Pinia.
- Vite.

Funciona como migración progresiva. Tiene rutas modernas y vista `LegacyFrameView` para incrustar páginas legacy.

### Android cliente

Ruta: `android/`.

App WebView para usuarios. URL base por defecto: `https://todosevillaeste.es`. Incluye permisos de internet, red, cámara y notificaciones.

### Android admin

Ruta: `android_admin/`.

App WebView para administración. URL base por defecto: `https://todosevillaeste.es/administracion/index-panel.html?android_admin=1`.

## 3. Arquitectura lógica

Capas:

- Presentación pública: HTML/JS/CSS legacy y SPA Vue.
- Presentación admin: HTML/JS/CSS legacy.
- API principal: FastAPI `frontend_backend.py`.
- API IA: FastAPI `agents_main.py`.
- Persistencia relacional: MariaDB/MySQL.
- Persistencia JSON/archivos: versionado, sesiones admin, visibilidad, memoria IA, imágenes, APKs y adjuntos.
- Integraciones externas: OAuth, captcha, correo, Firebase, Web Push, Ollama/OpenRouter, Nominatim/Leaflet en cliente, Proxmox/SSH.

## 4. Arquitectura física

En desarrollo:

```bash
python -m uvicorn frontend_backend:app --host 0.0.0.0 --port 8001
python -m uvicorn agents_main:app --host 0.0.0.0 --port 8000
cd web/app
npm run dev
```

En producción:

- `todosevillaeste-frontend.service`: backend principal, puerto `8001`.
- `todosevillaeste-agents.service`: API de agentes, puerto `8000`.
- `todosevillaeste-stack.target`: agrupa ambos.
- Configuración en `/etc/default/todosevillaeste-stack`.

## 5. Resolución de versiones web

`web_versions.json` contiene dos bloques:

- `public`: versiones de la web pública.
- `admin`: versiones del panel admin.

Cada bloque tiene:

- `active_id`: versión servida en producción.
- `test_active_id`: versión servida en rutas de prueba.
- `items`: historial con `id`, `version`, `notes`, `created_at`, `snapshot_dir`.

Rutas de producción:

- Pública: `/`, `/frontend.html`, páginas públicas.
- Admin: `/administracion`, `/administracion/index-panel.html`.

Rutas de prueba:

- Pública: `/pruebas` y `/pruebas/{path}`.
- Admin: `/administracion/pruebas` y `/administracion/pruebas/{path}`.

## 6. Flujo de petición pública

1. El navegador solicita `/`.
2. El backend redirige o sirve `/frontend.html`.
3. El resolvedor busca la versión pública activa.
4. Se entrega `web/versions_web/public/4.3/frontend.html`.
5. La página carga estilos y scripts.
6. La página llama `/places`, `/auth/me`, `/public/visibility`, `/meta/realtime`.
7. Si hay sesión, activa acciones de usuario.
8. Si hay nueva versión, `ui_public.js` avisa al usuario.

## 7. Flujo de administración

1. Admin entra en `/administracion/index-panel.html`.
2. `index-panel.html` muestra login si no hay sesión.
3. Envía credenciales a `/admin/auth/login`.
4. Backend valida y crea `tsev_admin_session`.
5. El panel consulta `/admin/auth/status` y `/admin/auth/me`.
6. Las secciones llaman endpoints admin protegidos.
7. Acciones pueden impactar DB, JSON, archivos, builds APK o servicios.

## 8. Flujo de IA

1. Widget público o frontend envía mensaje al backend.
2. Backend valida visibilidad y reenvía a `AGENTS_API_BASE`.
3. `agents_main.py` compone contexto público con negocios activos.
4. El proveedor LLM responde.
5. En modo streaming, la respuesta se entrega como stream.
6. Si hay feedback, se almacena aprendizaje limitado.

## 9. Persistencia

### Base de datos

MariaDB/MySQL con conexiones separadas:

- `DB_READ_CONFIG`: lecturas.
- `DB_WRITE_CONFIG`: escrituras.

Tablas principales:

- `users`, `sessions`, `auth_codes`.
- `places`, `place_user_assignments`.
- `reviews`, `review_votes`, `review_reports`.
- `chat_threads`, `chat_messages`, `global_chat_messages`.
- `support_tickets`, `support_ticket_messages`.
- `feedback_submissions`, `feedback_messages`.
- `push_subscriptions`, `fcm_device_tokens`.

### Archivos

- `web_versions.json`: web pública/admin.
- `android_versions.json`: APKs.
- `visibility_config.json`: visibilidad pública/IA.
- `admin_auth_config.json`: autenticación admin.
- `admin_sessions.json`: sesiones admin.
- `manuales_sessions.json`: sesiones de manuales.
- `data/learning_memory.json`: aprendizaje IA.
- `web/img/...`: imágenes y adjuntos.
- `web/downloads/android/...`: APKs.

## 10. Seguridad arquitectónica

- Separación de cookie pública y admin.
- Dependencias FastAPI para usuario/admin.
- Captcha/antibot en login y registro.
- OAuth opcional.
- Hash de contraseñas.
- Validación de rol negocio.
- Acciones admin protegidas por sesión.
- Terminal SSH y reinicios restringidos a admin/local.
- IA con contexto público y sin datos privados.

## 11. Puntos de acoplamiento

- HTML legacy contiene mucha lógica inline.
- `frontend_backend.py` concentra numerosas responsabilidades.
- Las rutas públicas dependen de `web_versions.json`.
- Android depende de que la web sea compatible con WebView.
- IA depende de disponibilidad de DB y proveedor LLM.
- Build APK depende de JDK/Android SDK.

## 12. Decisiones técnicas observadas

- FastAPI como servidor principal.
- MariaDB/MySQL como base.
- HTML/JS legacy como capa productiva.
- Vue como migración incremental.
- WebView Android en lugar de nativo completo.
- Snapshots versionados para publicar sin reemplazar carpetas base.
- JSON para configuraciones operativas simples.
- Service Worker para PWA y push.

