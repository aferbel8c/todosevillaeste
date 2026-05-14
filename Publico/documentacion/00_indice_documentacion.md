# TodoSevillaEste - Índice de documentación 4.3 Public / 2.4 Admin

## Alcance

Esta carpeta documenta el estado funcional, técnico, legal, operativo y de mantenimiento del proyecto TodoSevillaEste tomando como base:

- Web pública activa: `web/versions_web/public/4.3`.
- Panel de administración activo: `web/versions_web/admin/2.4`.
- Backend principal: `frontend_backend.py`.
- API auxiliar de IA: `agents_main.py`.
- SPA Vue/Vite progresiva: `web/app`.
- Apps Android WebView: `android/` y `android_admin/`.
- Versionado web y APK: `web_versions.json` y `android_versions.json`.

## Documentos incluidos

- `01_documento_requisitos.md`: requisitos funcionales, no funcionales, roles, permisos y criterios de aceptación.
- `02_documento_arquitectura.md`: arquitectura lógica, física, despliegue, flujo de navegación, versiones y dependencias.
- `03_modelo_datos.md`: entidades, tablas, JSON de configuración, relaciones y reglas de integridad.
- `04_documentacion_api.md`: catálogo de endpoints por módulo, autenticación, payloads principales y errores esperables.
- `05_manual_tecnico.md`: instalación, arranque, configuración, desarrollo, builds, rutas y operación técnica.
- `06_manual_usuario_clientes.md`: uso de la plataforma por visitantes y clientes registrados.
- `07_manual_negocios.md`: uso del alta y panel de gestión para negocios.
- `08_manual_administrador.md`: uso del panel administrativo y tareas de gestión.
- `09_proteccion_datos.md`: inventario de datos personales, bases de tratamiento, derechos y medidas.
- `10_aviso_legal.md`: aviso legal base del servicio.
- `11_politica_cookies.md`: cookies, almacenamiento local, finalidades y configuración.
- `12_terminos_condiciones_servicio.md`: condiciones de uso de la plataforma.
- `13_documentacion_seguridad.md`: controles técnicos, riesgos, hardening y respuesta ante incidentes.
- `14_documentacion_ia.md`: integración de IA, límites, datos usados, cache y mantenimiento del asistente.
- `15_documentacion_mantenimiento.md`: rutinas, checklist, copias, despliegues, monitorización y recuperación.

## Nota de mantenimiento

Estos documentos amplían el `release.md`. El `release.md` explica el funcionamiento observado de la release; esta documentación lo convierte en material formal para requisitos, operación, usuarios, administradores, cumplimiento y seguridad.

Cuando se publique una nueva versión pública, admin o APK, se debe revisar como mínimo:

- Endpoints añadidos o modificados.
- Cambios de tablas o columnas.
- Nuevos tratamientos de datos personales.
- Nuevas cookies, `localStorage` o integraciones externas.
- Nuevas variables de entorno.
- Nuevos permisos Android.
- Cambios en flujos de login, soporte, reseñas, mensajes, IA o administración.

