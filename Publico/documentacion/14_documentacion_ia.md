# Documentación de IA - TodoSevillaEste

## 1. Objetivo

La IA de TodoSevillaEste sirve como asistente público para responder preguntas sobre negocios, categorías y datos públicos disponibles en la plataforma.

## 2. Componentes

### Backend principal

`frontend_backend.py` expone:

- `POST /agents/public/chat`.
- `POST /agents/public/chat/stream`.
- `POST /admin/ia/cache/refresh`.

Actúa como puente hacia `agents_main.py`.

### API de agentes

`agents_main.py` expone:

- `POST /agents/public/chat`.
- `POST /agents/public/chat/stream`.
- `POST /agents/public/cache/refresh`.
- `POST /agents/learning/feedback`.
- Endpoints para agentes personalizados.

## 3. Proveedores

Configuración:

- `LLM_PROVIDER=ollama` para modelo local.
- `LLM_PROVIDER=openrouter` para OpenRouter.

Variables:

- `OLLAMA_API_BASE`.
- `OLLAMA_MODEL`.
- `OLLAMA_TIMEOUT_SECONDS`.
- `OPENROUTER_API_KEY`.
- `OPENROUTER_MODEL`.
- `OPENROUTER_API_BASE`.
- `OPENROUTER_HTTP_REFERER`.
- `OPENROUTER_APP_NAME`.

## 4. Contexto público

La IA debe usar exclusivamente contexto público:

- Negocios activos.
- Nombre.
- Categoría.
- Dirección pública.
- Teléfono público.
- Web.
- Descripción.
- Horarios.
- Datos visibles.

No debe usar:

- Contraseñas.
- Sesiones.
- Emails privados no publicados.
- Mensajes.
- Tickets.
- Datos admin.
- Logs.
- Tokens.
- Información de base de datos no pública.

## 5. Prompt de sistema

El prompt público indica:

- Responder como asistente de Todo Sevilla Este.
- Usar tono cercano, claro y útil.
- Usar exclusivamente contexto público recibido.
- Decir explícitamente cuando algo no aparece.
- No revelar información interna, privada ni técnica.

## 6. Cache

Variables:

- `PLACES_REFRESH_SECONDS`.
- `MAX_PLACES_CONTEXT_CHARS`.
- `MAX_CONTEXT_ROWS`.
- `MAX_CATEGORY_CONTEXT_ROWS`.
- `ENABLE_REPLY_CACHE`.

La cache de negocios reduce consultas y latencia. Debe refrescarse:

- Automáticamente por tiempo.
- Manualmente desde admin tras cambios importantes.
- Con `POST /agents/public/cache/refresh`.

## 7. Streaming

Endpoint:

- `POST /agents/public/chat/stream`.

Uso:

- Mejora percepción de velocidad.
- Permite mostrar tokens progresivamente.
- Requiere manejar desconexiones.

## 8. Memoria de conversación

Variables:

- `CHAT_MEMORY_MAX_ITEMS`.

La memoria debe ser corta y contextual, no un historial indefinido. No debe usarse como fuente de verdad frente a la base pública.

## 9. Aprendizaje

Endpoint:

- `POST /agents/learning/feedback`.

Archivo:

- `data/learning_memory.json`.

Variables:

- `LEARNING_MAX_ITEMS_PER_AGENT`.
- `LEARNING_MAX_EXAMPLES_IN_PROMPT`.
- `LEARNING_MIN_ANSWER_CHARS`.

Uso:

- Guardar ejemplos útiles.
- Limitar tamaño.
- Evitar almacenar datos personales innecesarios.
- Revisar periódicamente la memoria.

## 10. Widget público

Archivos:

- `west_widget.js`.
- `west_widget.css`.

Funciones:

- Crear panel flotante.
- Guardar conversación local.
- Enviar mensajes a endpoint configurado.
- Ajustar posición respecto al footer/viewport.

## 11. Visibilidad

La disponibilidad del asistente depende de:

- `visibility_config.json`.
- `/public/visibility`.
- `/admin/settings/visibility`.

Administración puede ocultar IA sin retirar el resto de la web.

## 12. Limitaciones

La IA puede:

- No encontrar datos no publicados.
- Responder de forma incompleta si el contexto está limitado.
- Depender de disponibilidad del proveedor.
- Tardar si el modelo local o externo está lento.

Debe responder con transparencia cuando no sabe algo.

## 13. Pruebas recomendadas

- Preguntar por una categoría existente.
- Preguntar por un negocio concreto.
- Preguntar por horarios.
- Preguntar por datos no existentes y verificar que no inventa.
- Desactivar IA en visibilidad y comprobar ocultación.
- Refrescar cache tras editar negocio.
- Probar streaming y respuesta normal.

## 14. Mantenimiento

- Revisar `data/learning_memory.json`.
- Limpiar ejemplos incorrectos.
- Verificar latencia del proveedor.
- Revisar timeouts.
- Comprobar que no se envía información privada.
- Actualizar prompt si aparecen respuestas inadecuadas.

