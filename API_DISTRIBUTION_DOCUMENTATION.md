# API de Distribución de Informes - Documentación Completa

Esta documentación describe las APIs de distribución de informes médicos del sistema NEXTRIS disponibles en `/apps/api/distribution.py`.

**Base URL**: `/api`

**Autenticación**: Todas las APIs requieren autenticación JWT mediante el header `Authorization: Bearer <token>`

---

## Tabla de Contenidos

1. [Obtener Exámenes para Distribución](#obtener-exámenes-para-distribución)
2. [Enviar Informe por Email](#enviar-informe-por-email)
3. [Actualizar Email de Examen](#actualizar-email-de-examen)
4. [Visualizar Informe PDF](#visualizar-informe-pdf)
5. [Obtener Información del Visor DICOM](#obtener-información-del-visor-dicom)
6. [Enviar Informe por WhatsApp](#enviar-informe-por-whatsapp)
7. [Actualizar Teléfono de Examen](#actualizar-teléfono-de-examen)
8. [Configuración de WhatsApp por Facility](#configuración-de-whatsapp-por-facility)

---

## Obtener Exámenes para Distribución

### GET /examinations/distribution

Obtiene la lista de exámenes que tienen informes finalizados y están listos para ser distribuidos vía email.

**Permisos**: El usuario solo verá exámenes de las ubicaciones (locations) a las que tiene acceso.

**Query Parameters:**

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `all_reported` | boolean | No | `false` | `true`: incluye todos los exámenes reportados. `false`: solo muestra los que no han sido enviados por email |
| `page` | integer | No | `1` | Número de página para paginación |
| `per_page` | integer | No | `50` | Cantidad de items por página (máximo: 100) |

**Ejemplo Request:**
```bash
GET /api/examinations/distribution?all_reported=false&page=1&per_page=50
Authorization: Bearer <jwt_token>
```

**Response 200 - Success:**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "guid": "123e4567-e89b-12d3-a456-426614174000",
        "fecha": "07/01/2025 14:30",
        "examen": "ANGIOTOMOGRAFIA DE TORAX",
        "paciente": "García Pérez, Ana María",
        "mail": "ana.garcia@email.com",
        "estado": "R",
        "medico_autor": "Dr. Juan Carlos Smith",
        "medico_solicitante": "Dr. Roberto Jones",
        "urgencia": false,
        "phone": "+54111573653752"
      }
    ],
    "page": 1,
    "per_page": 50,
    "total": 25
  }
}
```

**Campos de Respuesta:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `guid` | string (UUID) | Identificador único del examen |
| `fecha` | string | Fecha de creación del examen (formato DD/MM/YYYY) |
| `examen` | string | Descripción del tipo de estudio |
| `paciente` | string | Nombre completo del paciente |
| `mail` | string | Email del paciente (de `patient_email` en orden, o email del paciente) |
| `phone` | string | Teléfono del paciente con código de país (para envío por WhatsApp) |
| `estado` | string | Estado de distribución: `"R"` = Reportado (pendiente), `"E"` = Enviado |
| `medico_autor` | string | Nombre del médico que realizó el informe |
| `medico_solicitante` | string | Nombre del médico que solicitó el estudio |
| `urgencia` | string | Indica si es urgente: `"S"` = Sí, `"N"` = No |

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Error: descripción del error"
}
```

**Notas Importantes:**
- Los exámenes deben tener `isreported = 1` para aparecer en la lista
- El estado `"E"` (Enviado) se determina si existe un registro en `tbemailqueue` con `status = 'sent'`
- Si `all_reported=false`, solo se muestran exámenes que NO han sido enviados
- La paginación es obligatoria, con un máximo de 100 items por página

---

## Enviar Informe por Email

### POST /examinations/{exam_id}/send-report

Envía el informe médico en formato PDF al email especificado, utilizando la configuración SMTP de la instalación (facility).

**Path Parameters:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `exam_id` | string (UUID) | Sí | GUID del examen |

**Request Body (JSON):**
```json
{
  "email": "paciente@email.com"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `email` | string | Sí | Dirección de email destino |

**Ejemplo Request:**
```bash
POST /api/examinations/123e4567-e89b-12d3-a456-426614174000/send-report
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "email": "paciente@example.com"
}
```

**Response 200 - Success:**
```json
{
  "success": true,
  "message": "Informe enviado correctamente"
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "El email es requerido"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```
o
```json
{
  "success": false,
  "message": "PDF del informe no encontrado"
}
```

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Configuración SMTP incompleta"
}
```
o
```json
{
  "success": false,
  "message": "Error al enviar email: descripción del error"
}
```

**Configuración SMTP Utilizada:**

El endpoint utiliza la configuración SMTP de la tabla `tbfacility` asociada a la ubicación del examen:

| Campo | Default | Descripción |
|-------|---------|-------------|
| `smtp_server` | smtp.gmail.com | Servidor SMTP |
| `smtp_port` | 587 | Puerto SMTP |
| `smtp_user` | - | Usuario SMTP (requerido) |
| `smtp_password` | - | Contraseña SMTP (requerida) |
| `smtp_from` | valor de smtp_user | Email remitente |
| `smtp_from_name` | NextRIS | Nombre del remitente |
| `use_tls` | true | Usar TLS/STARTTLS |

**Contenido del Email:**

- **Asunto**: `Informe Médico - {tipo_de_estudio}`
- **Cuerpo**: Mensaje personalizado con nombre del paciente, tipo de estudio y número de acceso
- **Adjunto**: PDF del informe con nombre `informe_{accession_number}.pdf`

**Registro de Envío:**

Cada envío exitoso se registra en la tabla `tbemailqueue`:
- `guid`: UUID único del registro
- `examination_id`: GUID del examen
- `recipient_email`: Email destinatario
- `status`: 'sent'
- `sent_at`: Timestamp del envío

**Notas Importantes:**
- El PDF debe existir en el servidor en la ruta especificada en `tbreport.pdfpath`
- La configuración SMTP debe estar completa en la instalación
- El email se envía de forma síncrona (bloqueante)
- Si falla el envío, no se registra en la cola de emails

---

## Actualizar Email de Examen

### PATCH/PUT /examinations/{exam_id}/update-email

Actualiza el email asociado a un examen/orden específico.

**Path Parameters:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `exam_id` | string (UUID) | Sí | GUID del examen |

**Request Body (JSON):**
```json
{
  "email": "nuevo@email.com"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `email` | string | Sí | Nueva dirección de email |

**Ejemplo Request:**
```bash
PATCH /api/examinations/123e4567-e89b-12d3-a456-426614174000/update-email
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "email": "nuevo.email@example.com"
}
```

**Response 200 - Success:**
```json
{
  "success": true,
  "message": "Email actualizado correctamente"
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "El email es requerido"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Error: descripción del error"
}
```

**Base de Datos:**

El email se actualiza en el campo `patient_email` de la tabla `tborder` (asociada al examen a través de `tbexamination.order_id`).

**Notas Importantes:**
- El email se actualiza a nivel de orden, no de examen
- Una orden puede tener múltiples exámenes
- El email actualizado se usará en futuros envíos desde el endpoint de distribución
- No se valida el formato del email (debe validarse en frontend)

---

## Flujo de Trabajo Típico

1. **Listar exámenes pendientes de distribución:**
   ```bash
   GET /api/examinations/distribution?all_reported=false
   ```

2. **Actualizar email si es necesario:**
   ```bash
   PATCH /api/examinations/{exam_id}/update-email
   {
     "email": "email.correcto@example.com"
   }
   ```

3. **Enviar el informe:**
   ```bash
   POST /api/examinations/{exam_id}/send-report
   {
     "email": "email.correcto@example.com"
   }
   ```

4. **Verificar envío:**
   ```bash
   GET /api/examinations/distribution?all_reported=true
   ```
   El examen ahora tendrá `estado: "E"` (Enviado)

---

## Códigos de Error Comunes

| Código | Descripción | Causa |
|--------|-------------|-------|
| 400 | Bad Request | Falta el email en el body o body JSON inválido |
| 404 | Not Found | Examen no existe o PDF no encontrado |
| 500 | Internal Server Error | Error de configuración SMTP, error de BD, error al enviar email |

---

## Consideraciones de Seguridad

- **Autenticación JWT**: Todas las APIs requieren token válido
- **Filtrado por ubicación**: Los usuarios solo ven exámenes de sus ubicaciones asignadas
- **Validación de existencia**: Se verifica que el examen y el PDF existan antes de enviar
- **Credenciales SMTP**: Las contraseñas SMTP se almacenan en la base de datos (considerar encriptación)

---

---

## 4. Visualizar Informe PDF

Permite visualizar el informe PDF de un examen en el navegador.

**Endpoint:** `GET /examinations/<exam_id>/report/view`

**Autenticación:** Requerida (JWT Token)

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| exam_id | UUID | ID único del examen |

**Ejemplo de Request:**
```bash
GET /api/examinations/123e4567-e89b-12d3-a456-426614174000/report/view
Authorization: Bearer <token>
```

**Response 200 - Success:**
- Retorna el archivo PDF directamente
- Content-Type: `application/pdf`
- El navegador abrirá el PDF en una nueva pestaña para visualización

**Response 404 - No encontrado:**
```json
{
  "success": false,
  "error": "Informe no encontrado para este examen"
}
```

**Response 500 - Error del servidor:**
```json
{
  "success": false,
  "error": "Error al obtener el informe"
}
```

**Códigos de Error:**
| Código | Descripción |
|--------|-------------|
| 404 | El examen no tiene un informe PDF asociado o el archivo no existe en el sistema |
| 500 | Error al acceder al archivo o error de base de datos |

**Notas:**
- El archivo PDF debe existir en la ruta especificada en `tbreport.pdfpath`
- El PDF se abre directamente en el navegador, no se descarga
- Si el archivo no existe físicamente aunque esté registrado en la BD, retorna 404

---

## 5. Obtener Información del Visor DICOM

Obtiene la información necesaria para abrir el visor DICOM de un examen.

**Endpoint:** `GET /examinations/<exam_id>/dicom-viewer`

**Autenticación:** Requerida (JWT Token)

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| exam_id | UUID | ID único del examen |

**Ejemplo de Request:**
```bash
GET /api/examinations/123e4567-e89b-12d3-a456-426614174000/dicom-viewer
Authorization: Bearer <token>
```

**Response 200 - Success:**
```json
{
  "success": true,
  "data": {
    "study_uid": "1.2.840.113619.2.55.3.2831869264.123.1234567890.1",
    "viewer_url": "http://localhost/weasis-pacs-connector/viewer?studyUID=1.2.840.113619.2.55.3.2831869264.123.1234567890.1",
    "patient_name": "García Pérez^Ana María",
    "study_description": "ANGIOTOMOGRAFIA DE TORAX",
    "study_date": "20250107"
  }
}
```

**Response 404 - No encontrado:**
```json
{
  "success": false,
  "error": "Examen no encontrado o sin imágenes DICOM"
}
```

**Response 500 - Error del servidor:**
```json
{
  "success": false,
  "error": "Error al obtener información del visor DICOM"
}
```

**Códigos de Error:**
| Código | Descripción |
|--------|-------------|
| 404 | El examen no existe o no tiene studyinstanceuid asociado |
| 500 | Error de base de datos o error interno del servidor |

**Campos del Response:**
| Campo | Tipo | Descripción |
|-------|------|-------------|
| study_uid | string | UID del estudio DICOM (studyinstanceuid) |
| viewer_url | string | URL completa para abrir en el visor Weasis |
| patient_name | string | Nombre del paciente en formato DICOM |
| study_description | string | Descripción del estudio |
| study_date | string | Fecha del estudio en formato YYYYMMDD |

**Notas:**
- El `study_uid` es el campo `studyinstanceuid` de la tabla `tbexamination`
- La URL del visor se construye automáticamente con el patrón: `http://localhost/weasis-pacs-connector/viewer?studyUID=<study_uid>`
- Si el examen no tiene `studyinstanceuid`, retorna 404
- El visor DICOM debe estar configurado y accesible en el servidor

---

---

## 6. Enviar Informe por WhatsApp

### POST /examinations/{exam_id}/send-report-whatsapp

Envía el informe médico en formato PDF por WhatsApp al número especificado, utilizando la **Meta Cloud API** con la configuración WhatsApp de la facility asociada al examen.

**Path Parameters:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `exam_id` | string (UUID) | Sí | GUID del examen |

**Request Body (JSON):**
```json
{
  "phone": "+54111573653752"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `phone` | string | Sí | Número de teléfono del destinatario con código de país |

**Formato del Número de Teléfono:**

El número debe incluir el código de país. Para Argentina, el formato correcto es **con el prefijo 15** (no con 9):

| Formato | Ejemplo | Válido |
|---------|---------|--------|
| Con 15 (correcto para Argentina) | `+54111573653752` | Sí |
| Con 9 (formato E.164) | `+5491173653752` | No funciona con Meta API en modo dev |
| Sin código de país | `1173653752` | No (se rechaza por longitud) |

> **Nota**: El endpoint limpia automáticamente el número eliminando el `+` y caracteres no numéricos, y valida que tenga al menos 10 dígitos.

**Ejemplo Request:**
```bash
POST /api/examinations/123e4567-e89b-12d3-a456-426614174000/send-report-whatsapp
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "phone": "+54111573653752"
}
```

**Response 200 - Success:**
```json
{
  "success": true,
  "message": "Informe enviado por WhatsApp correctamente"
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "El número de teléfono es requerido"
}
```
o
```json
{
  "success": false,
  "message": "WhatsApp no está activo para esta facility. Active la configuración de WhatsApp en la configuración de la facility."
}
```
o
```json
{
  "success": false,
  "message": "Número de teléfono inválido. Debe incluir código de país (ej: +521234567890)"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```
o
```json
{
  "success": false,
  "message": "PDF del informe no encontrado"
}
```

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Configuración de WhatsApp incompleta. Verifique API URL, Token y Phone Number ID en la configuración de la facility.",
  "data": {
    "whatsapp_configured": false,
    "api_url_exists": true,
    "api_token_exists": true,
    "phone_number_id_exists": false
  }
}
```
o
```json
{
  "success": false,
  "message": "Error al enviar por WhatsApp: Error al subir media: 400 - ..."
}
```

**Flujo Interno del Envío:**

1. Valida el número de teléfono (formato y longitud)
2. Obtiene datos del examen, paciente, reporte PDF y configuración WhatsApp de la facility
3. Valida que WhatsApp esté activo (`whatsapp_is_active = true`) y la configuración esté completa
4. Verifica que el PDF del informe exista en disco
5. **Sube el PDF como media** a la API de Meta (`POST /{phone_number_id}/media`)
6. **Envía el documento** con caption informativo al destinatario (`POST /{phone_number_id}/messages`)
7. Si el examen tiene **imágenes DICOM** (`isimage = 1` y `studyinstanceuid` presente), envía un **segundo mensaje de texto** con el link al visor DICOM
8. Marca el examen como publicado (`ispublicated = 1`)

**Contenido del Mensaje WhatsApp:**

El documento PDF se envía con el siguiente caption:
```
Estimado/a {nombre_paciente},

Adjunto el informe médico correspondiente al estudio: {tipo_estudio}
Número de acceso: {accession_number}

Este es un mensaje automático.
- {nombre_facility}
```

**Mensaje del Visor DICOM** (solo si hay imágenes):
```
Para visualizar las imágenes médicas de su estudio ({tipo_estudio}),
acceda al siguiente enlace:

https://viewer.nextris.cloud/viewer?StudyInstanceUIDs={study_uid}
```

**Cadena de Relación Facility → WhatsApp Config:**
```
tbexamination → isequipment (idequipment) → tblocation (location_id) → tbfacility (facility_id)
```

---

## 7. Actualizar Teléfono de Examen

### PATCH/PUT /examinations/{exam_id}/update-phone

Actualiza el número de teléfono del paciente asociado a un examen. Útil para corregir o agregar el teléfono desde la vista de distribución antes de enviar por WhatsApp.

**Path Parameters:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `exam_id` | string (UUID) | Sí | GUID del examen |

**Request Body (JSON):**
```json
{
  "phone": "+54111573653752"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `phone` | string | Sí | Nuevo número de teléfono con código de país |

**Ejemplo Request:**
```bash
PATCH /api/examinations/123e4567-e89b-12d3-a456-426614174000/update-phone
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "phone": "+54111573653752"
}
```

**Response 200 - Success:**
```json
{
  "success": true,
  "message": "Teléfono actualizado correctamente"
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "El teléfono es requerido"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```

**Base de Datos:**

El teléfono se actualiza en el campo `phone` de la tabla `datapatient` (asociada al examen a través de `tbexamination.idpatient`).

**Notas:**
- El teléfono se actualiza a nivel de paciente, no de examen
- Todos los exámenes del mismo paciente se verán afectados
- Se recomienda almacenar el número con código de país (ej: `+54111573653752`)

---

## 8. Configuración de WhatsApp por Facility

La configuración de WhatsApp se almacena en la tabla `nextris.tbfacility`. Cada facility tiene su propia configuración independiente, lo que permite que diferentes centros médicos usen distintas cuentas de WhatsApp Business.

### Campos de Configuración

| Campo en BD | Tipo | Descripción |
|-------------|------|-------------|
| `whatsapp_api_url` | VARCHAR(500) | URL base de la API de Meta. Valor estándar: `https://graph.facebook.com/v22.0` |
| `whatsapp_api_token` | VARCHAR(500) | Token de acceso permanente generado en Meta Developers |
| `whatsapp_phone_number_id` | VARCHAR(100) | Identificador del número de teléfono de WhatsApp Business |
| `whatsapp_business_account_id` | VARCHAR(100) | Identificador de la cuenta de WhatsApp Business |
| `whatsapp_webhook_verify_token` | VARCHAR(255) | Token de verificación para webhooks (opcional, para recepción de mensajes) |
| `whatsapp_is_active` | BOOLEAN | Indica si WhatsApp está activo para esta facility |

### Obtener Configuración

La configuración se obtiene automáticamente al listar facilities:

```bash
GET /api/config/facilities
Authorization: Bearer <jwt_token>
```

La respuesta incluye `whatsapp_config` en cada facility:
```json
{
  "success": true,
  "data": [
    {
      "guid": "af4b2512-...",
      "name": "Clinica Facundo Farias",
      "whatsapp_config": {
        "api_url": "https://graph.facebook.com/v22.0",
        "api_token": "EAAZAk...",
        "phone_number_id": "946885088516257",
        "business_account_id": "1621354785823653",
        "webhook_verify_token": null,
        "is_active": true
      }
    }
  ]
}
```

### Actualizar Configuración

```bash
PUT /api/config/facilities/{facility_id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "whatsapp_api_url": "https://graph.facebook.com/v22.0",
  "whatsapp_api_token": "EAAZAk...",
  "whatsapp_phone_number_id": "946885088516257",
  "whatsapp_business_account_id": "1621354785823653",
  "whatsapp_is_active": true
}
```

### Requisitos Previos para Configurar WhatsApp

Para utilizar el envío de informes por WhatsApp, el cliente debe tener:

1. **Meta Business Account** verificada en [business.facebook.com](https://business.facebook.com)
2. **App de WhatsApp Business** creada en [developers.facebook.com](https://developers.facebook.com)
3. **Número de teléfono dedicado** registrado en WhatsApp Business (no puede estar en uso con WhatsApp personal)
4. **Método de pago** configurado en Meta Business (costo por conversación: ~$0.02-0.08 USD según país)

### Dónde Obtener los Datos

| Campo | Ubicación en Meta Developers |
|-------|------------------------------|
| `whatsapp_api_url` | Siempre `https://graph.facebook.com/v22.0` (actualizar versión según corresponda) |
| `whatsapp_api_token` | Meta Developers → App → WhatsApp → Configuración de la API → "Identificador de acceso" → Copiar |
| `whatsapp_phone_number_id` | Meta Developers → App → WhatsApp → Configuración de la API → "Identificador del número de teléfono" |
| `whatsapp_business_account_id` | Meta Developers → App → WhatsApp → Configuración de la API → "Identificador de la cuenta de WhatsApp Business" |

### Modo Desarrollo vs Producción

| Aspecto | Modo Desarrollo | Modo Producción |
|---------|-----------------|-----------------|
| Destinatarios | Solo números agregados manualmente (máx. 5) | Cualquier número de WhatsApp |
| Ventana de conversación | Destinatario debe escribir primero al número de negocio | Se pueden usar templates para iniciar conversación |
| Tokens | Temporales (90 días) | Permanentes (System User Token) |
| Verificación | No requiere verificación del negocio | Requiere verificación del negocio |

### Consideraciones para Producción

1. **Templates de Mensaje**: Para enviar mensajes fuera de la ventana de 24 horas sin que el paciente haya escrito primero, se deben crear **plantillas de mensaje aprobadas** por Meta
2. **Token Permanente**: Generar un System User Token en Meta Business → Configuración del negocio → Usuarios del sistema
3. **Verificación del Negocio**: Completar la verificación en Meta Business (puede tardar 2-5 días)
4. **Número Propio**: Registrar un número de teléfono propio del centro médico (reemplaza el número de prueba)

---

## Flujo de Trabajo con WhatsApp

1. **Listar exámenes pendientes de distribución:**
   ```bash
   GET /api/examinations/distribution?all_reported=false
   ```
   La respuesta incluye el campo `phone` del paciente.

2. **Actualizar teléfono si es necesario:**
   ```bash
   PATCH /api/examinations/{exam_id}/update-phone
   {
     "phone": "+54111573653752"
   }
   ```

3. **Enviar el informe por WhatsApp:**
   ```bash
   POST /api/examinations/{exam_id}/send-report-whatsapp
   {
     "phone": "+54111573653752"
   }
   ```

4. **Verificar envío:**
   ```bash
   GET /api/examinations/distribution?all_reported=true
   ```
   El examen tendrá `estado: "E"` (Enviado).

---

## Funciones Auxiliares Internas

### `send_whatsapp_document()`

Sube un PDF como media a la API de Meta y lo envía como documento con caption.

**Flujo:**
1. `POST {api_url}/{phone_number_id}/media` — Sube el archivo PDF
2. `POST {api_url}/{phone_number_id}/messages` — Envía el documento con el `media_id` obtenido

**Retorna:** `(success: bool, message: str)`

### `send_whatsapp_text()`

Envía un mensaje de texto simple por WhatsApp.

**Flujo:**
1. `POST {api_url}/{phone_number_id}/messages` — Envía mensaje tipo `text`

**Retorna:** `(success: bool, message: str)`

---

## Dependencias Técnicas (Actualizado)

- **Python**: smtplib, email.mime para envío de emails
- **Python**: requests para llamadas a la Meta Cloud API (WhatsApp)
- **PostgreSQL**: Tablas `tbexamination`, `tbreport`, `datapatient`, `tbfacility`, `tblocation`, `isequipment`
- **Archivos**: PDFs almacenados en sistema de archivos local
- **Servicios Externos**: Meta Cloud API (graph.facebook.com) para envío de WhatsApp

---

## Registro de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2025-01-10 | 1.0 | Creación inicial. APIs de distribución por email |
| 2026-02-14 | 2.0 | Integración WhatsApp: endpoint send-report-whatsapp, update-phone, funciones auxiliares send_whatsapp_document/text. Campo phone agregado al listado de distribución |

---

Para preguntas o issues relacionados con estas APIs, contactar al equipo de desarrollo de NextRIS.
