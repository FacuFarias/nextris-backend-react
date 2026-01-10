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
        "urgencia": false
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

## Dependencias Técnicas

- **Python**: smtplib, email.mime para envío de emails
- **PostgreSQL**: Tablas `tborder`, `tbexamination`, `tbreport`, `tbemailqueue`, `tbfacility`, `tblocation`
- **Archivos**: PDFs almacenados en sistema de archivos local

---

## Registro de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2025-01-10 | 1.0 | Creación inicial de la documentación. APIs implementadas en archivo separado `/apps/api/distribution.py` |

---

## Soporte

---

## 4. Visualizar Informe PDF

Permite visualizar o descargar el informe PDF de un examen.

**Endpoint:** `GET /examinations/<exam_id>/report/view`

**Autenticación:** Requerida (JWT Token)

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| exam_id | UUID | ID único del examen |

**Parámetros de Query:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| download | boolean | No | Si es `true`, descarga el PDF. Si es `false` o no está presente, lo visualiza en el navegador |

**Ejemplo de Request:**
```bash
# Visualizar en navegador
GET /api/examinations/123e4567-e89b-12d3-a456-426614174000/report/view
Authorization: Bearer <token>

# Descargar archivo
GET /api/examinations/123e4567-e89b-12d3-a456-426614174000/report/view?download=true
Authorization: Bearer <token>
```

**Response 200 - Success:**
- Retorna el archivo PDF directamente
- Content-Type: `application/pdf`
- Si `download=true`: incluye header `Content-Disposition: attachment; filename="informe_<exam_id>.pdf"`
- Si `download=false` o no especificado: el navegador intenta visualizar el PDF inline

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
- El parámetro `download` es opcional y por defecto es `false`
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

Para preguntas o issues relacionados con estas APIs, contactar al equipo de desarrollo de NextRIS.
