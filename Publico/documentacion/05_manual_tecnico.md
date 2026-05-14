# Manual Técnico - TodoSevillaEste

## 1. Requisitos

- Python 3 compatible con FastAPI/Uvicorn.
- MariaDB/MySQL accesible.
- Node.js y npm para `web/app`.
- JDK y Android SDK para compilar APKs.
- Servicio SMTP/IMAP o Gmail API para correo admin.
- Firebase Service Account para FCM si se usan notificaciones Android.
- Claves VAPID para Web Push si se usan notificaciones web.
- Ollama u OpenRouter para IA.

## 2. Estructura principal

- `frontend_backend.py`: backend principal.
- `agents_main.py`: API de IA.
- `web/versions_web/public/4.3`: web pública activa.
- `web/versions_web/admin/2.4`: admin activo.
- `web/app`: SPA Vue/Vite.
- `android`: APK cliente.
- `android_admin`: APK admin.
- `scripts`: instalación systemd.
- `data`: memoria IA.

## 3. Variables de entorno

### Base de datos

- `DB_READ_HOST`
- `DB_READ_PORT`
- `DB_READ_USER`
- `DB_READ_PASSWORD`
- `DB_READ_DATABASE`
- `DB_WRITE_HOST`
- `DB_WRITE_PORT`
- `DB_WRITE_USER`
- `DB_WRITE_PASSWORD`
- `DB_WRITE_DATABASE`

### Servicios

- `TSE_WORKDIR`
- `TSE_START_CMD`
- `TSE_STOP_CMD`
- `TSE_RESTART_CMD`
- `AGENTS_RESTART_CMD`
- `TSE_SERVICE_CANDIDATES`
- `TSE_PROCESS_PATTERN`

### Admin/terminal

- `ADMIN_SSH_HOST`
- `ADMIN_SSH_PORT`
- `ADMIN_SSH_USER`
- `ADMIN_SSH_STRICT_HOST_KEY`
- `ADMIN_TERMINAL_MODE`
- `PVE_BASE_URL`
- `PVE_NODE`
- `PVE_VMID`
- `PVE_VMNAME`
- `PVE_USER`
- `PVE_PASSWORD`
- `PVE_VERIFY_TLS`

### Autenticación y captcha

- `SESSION_COOKIE_DOMAIN`
- `SESSION_COOKIE_SECURE`
- `CF_TURNSTILE_SECRET`
- `HCAPTCHA_SECRET`
- `HCAPTCHA_SITE_KEY`
- `RECAPTCHA_SECRET`
- `RECAPTCHA_SITE_KEY`
- `ANTI_BOT_SECRET`
- `FIRST_PARTY_CAPTCHA_SECRET`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `MICROSOFT_OAUTH_CLIENT_ID`
- `MICROSOFT_OAUTH_CLIENT_SECRET`
- `MICROSOFT_OAUTH_TENANT`
- `OAUTH_STATE_TTL_SECONDS`

### Correo

- `ADMIN_MAIL_FROM`
- `ADMIN_MAIL_LOGIN`
- `ADMIN_MAIL_PASSWORD`
- `ADMIN_IMAP_HOST`
- `ADMIN_IMAP_PORT`
- `ADMIN_IMAP_LOGIN`
- `ADMIN_IMAP_PASSWORD`
- `GMAIL_API_CLIENT_ID`
- `GMAIL_API_CLIENT_SECRET`
- `GMAIL_API_REFRESH_TOKEN`
- `GMAIL_API_USER_EMAIL`
- `GMAIL_API_TIMEOUT_SECONDS`

### Notificaciones

- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`
- `FIREBASE_SERVICE_ACCOUNT_FILE`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `FIREBASE_PROJECT_ID`
- `FCM_ANDROID_PACKAGE`

### IA

- `AGENTS_API_BASE`
- `AGENTS_PUBLIC_CHAT_TIMEOUT_SECONDS`
- `AGENTS_PUBLIC_STREAM_TIMEOUT_SECONDS`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`
- `OLLAMA_API_BASE`
- `LLM_PROVIDER`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_API_BASE`
- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_APP_NAME`
- `PLACES_REFRESH_SECONDS`
- `MAX_DOC_CHARS`
- `MAX_PLACES_CONTEXT_CHARS`
- `MAX_CONTEXT_ROWS`
- `MAX_CATEGORY_CONTEXT_ROWS`
- `CHAT_MEMORY_MAX_ITEMS`
- `ENABLE_REPLY_CACHE`

### Android

- `ANDROID_SDK_ROOT`
- `ANDROID_HOME`
- `JAVA_HOME`

## 4. Arranque local

Backend principal:

```bash
python -m uvicorn frontend_backend:app --host 0.0.0.0 --port 8001
```

API de agentes:

```bash
python -m uvicorn agents_main:app --host 0.0.0.0 --port 8000
```

Frontend Vue:

```bash
cd web/app
npm install
npm run dev
```

Nota: en rutas UNC de Windows, `npm run build` puede fallar. Usar ruta local o unidad mapeada.

## 5. Instalación systemd

Instalar:

```bash
scripts/install_todosevillaeste_stack_systemd.sh
```

Desinstalar:

```bash
scripts/uninstall_todosevillaeste_stack_systemd.sh
```

Servicios creados:

- `todosevillaeste-frontend.service`.
- `todosevillaeste-agents.service`.
- `todosevillaeste-stack.target`.

## 6. Builds

### SPA Vue

```bash
cd web/app
npm run build
npm run preview
npm run lint:routes
```

### Android cliente

Windows:

```bash
cd android
gradlew.bat assembleDebug
```

Linux/macOS:

```bash
cd android
./gradlew assembleDebug
```

### Android admin

Windows:

```bash
cd android_admin
gradlew.bat assembleDebug
```

Linux/macOS:

```bash
cd android_admin
./gradlew assembleDebug
```

## 7. Versionado web

El panel admin usa `/admin/web_versions`.

Operaciones:

- Crear snapshot.
- Activar snapshot live.
- Activar snapshot test.
- Actualizar notas.
- Sincronizar snapshot.
- Eliminar snapshot.

Regla técnica:

- Editar una carpeta de snapshot no cambia producción si `web_versions.json` no apunta a ella.
- Las rutas `/pruebas` y `/administracion/pruebas` permiten validar versiones test.

## 8. Versionado APK

El panel admin usa `/admin/android_versions`.

Operaciones:

- Build APK.
- Consultar estado de build.
- Marcar APK activa.
- Publicar metadata en `android_versions.json`.
- Servir descargas desde `web/downloads/android`.

## 9. Base de datos

El backend inicializa o amplía tablas con funciones `ensure_*`.

Revisar especialmente:

- `ensure_users_optional_columns`.
- `ensure_places_optional_columns`.
- `ensure_place_user_assignments_schema`.
- `ensure_reviews_schema`.
- `ensure_messages_schema`.
- `ensure_support_schema`.
- `ensure_feedback_schema`.

Antes de desplegar cambios de modelo:

- Crear copia de seguridad.
- Probar migración en entorno de pruebas.
- Revisar permisos de usuario lectura/escritura.
- Verificar índices.

## 10. Archivos subidos

Directorios:

- Negocios: `web/img/businesses`.
- Reseñas: `web/img/reviews`.
- Mensajes: `web/img/messages`.
- Soporte: `web/img/support`.
- APKs: `web/downloads/android`.

Recomendaciones:

- Validar extensión y tamaño.
- Evitar nombres originales inseguros.
- Mantener permisos de lectura por backend.
- Hacer copia de seguridad junto con DB.

## 11. Logs y diagnóstico

Puntos de observación:

- Logs del servicio systemd.
- Log de backend configurado por `_ensure_backend_file_logging`.
- Log realtime por `_ensure_realtime_log_handler`.
- `web/administracion/ip_log.txt`.
- Panel `ip_log.html`.
- `/administracion/api/tse/state`.
- `/administracion/api/ip-log/stream`.

## 12. Checklist técnico tras despliegue

- Backend responde en `/`.
- API agentes responde en `/health`.
- `/frontend.html` carga.
- `/places` devuelve negocios.
- Login público funciona.
- Login admin funciona.
- Creación/edición de negocio funciona.
- Soporte crea ticket.
- Admin lista tickets.
- Reseñas cargan.
- Service worker no rompe navegación.
- Versiones públicas se ven.
- IA responde si está habilitada.
- Android descarga APK activa.

