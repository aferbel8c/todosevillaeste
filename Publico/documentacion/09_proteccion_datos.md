# Protección de Datos - TodoSevillaEste

## 1. Finalidad

Este documento describe los tratamientos de datos personales realizados por TodoSevillaEste. Debe ser revisado por asesoría legal antes de publicarse como texto definitivo.

## 2. Datos tratados

### Usuarios

- Nombre de usuario.
- Email.
- Contraseña hasheada.
- Fecha de nacimiento opcional.
- Avatar.
- Sesiones.
- Códigos de verificación o recuperación.
- Mensajes.
- Reseñas.
- Votos/reportes.
- Tickets de soporte.
- Feedback.
- Tokens de notificaciones.

### Negocios

- Nombre comercial.
- Dirección.
- Teléfono.
- Web.
- Email de negocio/contacto.
- Descripción.
- Fotos.
- Coordenadas.
- Horarios.
- Usuario propietario.

### Administración

- Usuario admin.
- Email admin.
- Sesiones admin.
- Acciones sobre usuarios, negocios, soporte, versiones y terminal.

### Datos técnicos

- IP.
- User-Agent.
- Logs de acceso.
- Estado de suscripciones push.
- Tokens FCM.
- Cookies y almacenamiento local.

## 3. Finalidades del tratamiento

- Prestar el servicio de directorio local.
- Gestionar cuentas de usuario.
- Publicar y mantener fichas de negocios.
- Permitir reseñas, mensajes y soporte.
- Gestionar administración, moderación y seguridad.
- Enviar notificaciones si el usuario las acepta.
- Mejorar el servicio mediante feedback.
- Cumplir obligaciones legales.
- Prevenir abuso, spam y accesos no autorizados.
- Mantener el asistente IA con contexto público.

## 4. Base jurídica

Según el caso:

- Ejecución de servicio solicitado por el usuario.
- Consentimiento para comunicaciones, cookies no necesarias y publicación de datos de contacto.
- Interés legítimo en seguridad, moderación y prevención de abuso.
- Cumplimiento de obligaciones legales.

## 5. Conservación

Criterios:

- Cuenta: mientras exista la cuenta o sea necesario por obligación legal.
- Sesiones: hasta expiración o cierre.
- Códigos temporales: tiempo limitado.
- Reseñas/mensajes/tickets: mientras sean necesarios para el servicio, moderación o trazabilidad.
- Logs/IP: plazo limitado y proporcional a seguridad.
- Tokens push/FCM: hasta baja, error persistente o revocación.
- Versiones y backups: según política de mantenimiento.

## 6. Derechos

El usuario puede ejercer:

- Acceso.
- Rectificación.
- Supresión.
- Oposición.
- Limitación.
- Portabilidad cuando aplique.
- Retirada de consentimiento.

Canales:

- Soporte desde la plataforma.
- Email de contacto indicado en aviso legal.

## 7. Encargados y terceros

Pueden intervenir:

- Proveedor de hosting/servidor.
- Proveedor de base de datos si no está autogestionada.
- Google/Firebase para FCM.
- Proveedores OAuth Google/Microsoft.
- Proveedores captcha.
- Proveedor de correo SMTP/IMAP/Gmail.
- Proveedor IA si se usa OpenRouter.
- Ollama local si se usa modelo local.

## 8. Transferencias y ubicación

La ubicación depende de la infraestructura configurada. Si se usan proveedores externos fuera del Espacio Económico Europeo, debe revisarse la base legal y garantías aplicables.

## 9. Medidas de seguridad

- Contraseñas hasheadas.
- Cookies de sesión.
- Separación de sesión pública/admin.
- Control de roles.
- Captcha/antibot.
- Validación de permisos en negocio propio.
- Restricción de rutas admin.
- Logs de actividad.
- Moderación.
- Copias de seguridad recomendadas.
- Configuración segura de HTTPS en producción.

## 10. IA y datos personales

La IA pública debe usar contexto público. No debe recibir:

- Contraseñas.
- Tokens.
- Cookies.
- Datos privados de usuarios.
- Conversaciones privadas.
- Información admin.

Si el usuario escribe datos personales en el chat, deben tratarse como contenido introducido voluntariamente y no usarse para entrenamiento externo salvo base legal y consentimiento explícito.

## 11. Cookies y almacenamiento

Se usan cookies de sesión y almacenamiento local para preferencias, banners, versión aceptada, estado de UI y conversación del asistente. La política de cookies debe detallar finalidades.

## 12. Brechas de seguridad

Ante una brecha:

1. Contener el incidente.
2. Registrar hora, alcance y sistemas afectados.
3. Identificar datos comprometidos.
4. Revocar credenciales/tokens si procede.
5. Restaurar desde backup si hace falta.
6. Notificar a autoridad y afectados si legalmente aplica.
7. Documentar medidas correctoras.

