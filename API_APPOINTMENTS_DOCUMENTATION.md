# API Appointments Documentation

## Overview
Este documento describe todos los endpoints disponibles para la gestión de citas/turnos en el sistema NextRIS.

**Base URL:** `/api`
**Authentication:** Requerido JWT Token

---

## Endpoints

### 0. GET /doctors
Obtiene la lista de médicos disponibles en el sistema.

#### Description
Retrieves a list of all users with the role "Medico" (Physician) for assignment in appointments.

#### Parameters
**Query Parameters:**
- `active_only` (optional): true/false para obtener solo médicos activos (default: false)

#### Request
```http
GET /api/doctors
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": [
    {
      "guid": "584f6b5b-9eb6-438d-a63f-920a12adbfe9",
      "name": "Paredes Armando"
    },
    {
      "guid": "7cbdd185-2efc-4a61-bff8-0eac3f715b20",
      "name": "Test Usuario Actualizado"
    }
  ]
}
```

#### Errors
```json
{
  "success": false,
  "message": "Error: {error_details}"
}
```

---

### 1. GET /appointments
Obtiene una lista de citas con filtros y paginación.

#### Description
Retrieves a paginated list of appointments with optional filters by date, doctor, equipment, and admission status.

#### Parameters
**Query Parameters:**
- `date` (optional): Fecha específica en formato YYYY-MM-DD
- `doctor_id` (optional): UUID del médico para filtrar
- `equipment_id` (optional): UUID del equipo para filtrar
- `admitted` (optional): true/false para filtrar por estado de admisión
- `today` (optional): true para obtener solo citas del día actual
- `page` (optional): Número de página (default: 1)
- `per_page` (optional): Items por página (default: 20, máximo: 100)

#### Request
```http
GET /api/appointments?page=1&per_page=20&today=true
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": {
    "timezone": "America/Argentina/Buenos_Aires",
    "data": [
      {
        "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
        "patient_name": "Juan García",
        "start": "2025-12-18T14:00:00-03:00",
        "end": "2025-12-18T15:00:00-03:00",
        "exam": "Tomografía Computarizada",
        "exam_id": "b1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
        "doctor": "Dr. Carlos López",
        "equipment": "CT-01",
        "is_admitted": false,
        "location_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
        "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8",
        "modality": "Tomografía Computarizada"
      }
    ],
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

**Nota:** Los campos `start` y `end` se devuelven en formato ISO 8601 con la zona horaria de la location. La zona horaria se especifica en el campo `timezone` al nivel de `data`. El campo `exam_id` contiene el UUID del tipo de examen (isstudytype.guid).

#### Errors
```json
{
  "success": false,
  "message": "Error: {error_details}"
}
```

---

### 2. POST /appointments
Crea una nueva cita o múltiples citas.

#### Description
Creates one or multiple appointments in the system. Supports both equipment-based and doctor-based appointments.

#### Request Body
```json
{
  "patient_id": "uuid-del-paciente",
  "appointment_type": "doctor o equipment",
  "location_id": "uuid-de-la-ubicacion (opcional)",
  "calendar_events": [
    {
      "exam_id": "uuid-del-examen",
      "start_datetime": "2025-12-05 10:00:00",
      "end_datetime": "2025-12-05 11:00:00",
      "physician_id": "uuid-del-medico",
      "obra_social_id": "uuid-de-la-obra-social",
      "equipment_id": "uuid-del-equipo (REQUERIDO - se usa para obtener la zona horaria)"
    }
  ]
}
```

**Importante:**
- `start_datetime` y `end_datetime` deben estar en **hora local** de la location (ej: Argentina)
- El `equipment_id` es **obligatorio** porque se usa para:
  1. Obtener la `location_id` del equipo
  2. Obtener el `timezone` de esa location
  3. Convertir automáticamente la hora local → UTC para almacenar en la BD
- Formato de fecha: `YYYY-MM-DD HH:MM:SS`

#### Request
```http
POST /api/appointments
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "patient_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "appointment_type": "equipment",
  "location_id": "d1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o9",
  "calendar_events": [
    {
      "exam_id": "b1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
      "start_datetime": "2025-12-05 10:00:00",
      "end_datetime": "2025-12-05 11:00:00",
      "physician_id": "e1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5f1",
      "obra_social_id": "f1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5f2",
      "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8"
    }
  ]
}
```

#### Response
**Status Code:** 201 Created

```json
{
  "success": true,
  "data": {
    "appointment_ids": ["f39710b4-7914-44ba-ab72-ad4ed5e22e98"],
    "created_count": 1
  },
  "message": "1 cita(s) creada(s) exitosamente"
}
```

#### Errors
```json
{
  "success": false,
  "message": "Los campos requeridos no fueron proporcionados"
}
```

---

### 3. PATCH /appointments/:id/reschedule
Actualiza las fechas y/o equipo de una cita (reprogramación).

#### Description
Reschedules an appointment by updating its start/end times and optionally changing the equipment.

#### Path Parameters
- `id` (required): GUID de la cita

#### Request Body
```json
{
  "start_datetime": "2025-12-05 10:00:00",
  "end_datetime": "2025-12-05 11:00:00",
  "equipment_id": "uuid-del-nuevo-equipo (opcional)"
}
```

**Importante:**
- `start_datetime` y `end_datetime` deben estar en **hora local** de la location
- Si no se proporciona `equipment_id`, se usa el equipo actual de la cita
- El backend obtiene automáticamente la zona horaria del equipo y convierte local → UTC
- Formato de fecha: `YYYY-MM-DD HH:MM:SS`

#### Request
```http
PATCH /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/reschedule
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "start_datetime": "2025-12-20 14:00:00",
  "end_datetime": "2025-12-20 15:00:00",
  "equipment_id": "new-equipment-uuid"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Cita reprogramada exitosamente (1 registro(s) actualizado(s))",
  "rows_affected": 1
}
```

#### Errors
```json
{
  "success": false,
  "message": "Cita no encontrada"
}
```

**Status Code:** 404 Not Found

---

### 4. PATCH /appointments/:id
Actualiza datos específicos de una cita.

#### Description
Updates specific fields of an existing appointment (doctor, requesting physician, exam).

#### Path Parameters
- `id` (required): GUID de la cita

#### Request Body
```json
{
  "doctor_id": "uuid-del-nuevo-medico (opcional)",
  "requesting_physician_id": "uuid-del-nuevo-medico-solicitante (opcional)",
  "exam_id": "uuid-del-nuevo-examen (opcional)"
}
```

#### Request
```http
PATCH /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "doctor_id": "new-doctor-uuid",
  "exam_id": "new-exam-uuid"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Cita actualizada exitosamente",
  "rows_affected": 1
}
```

#### Errors
```json
{
  "success": false,
  "message": "Cita no encontrada"
}
```

---

### 5. DELETE /appointments/:id
Elimina/cancela una cita.

#### Description
Deletes an appointment from the system.

#### Path Parameters
- `id` (required): GUID de la cita

#### Request
```http
DELETE /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Cita eliminada exitosamente",
  "rows_affected": 1
}
```

#### Errors
```json
{
  "success": false,
  "message": "Cita no encontrada"
}
```

**Status Code:** 404 Not Found

---

### 6. POST /appointments/:id/admit
Admisiona una cita y crea la orden de examen en worklist.

#### Description
Admits an appointment and creates an examination order in the DICOM worklist.

#### Path Parameters
- `id` (required): GUID de la cita

#### Request Body (opcional)
```json
{
  "equipment_id": "uuid-del-equipo (opcional, si no viene en la cita)"
}
```

#### Request
```http
POST /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/admit
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Cita admisionada exitosamente",
  "data": {
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "exam_id": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
    "study_instance_uid": "1.2.840.113619.1234567890.1",
    "timezone": "America/Argentina/Buenos_Aires"
  }
}
```

#### Errors
```json
{
  "success": false,
  "message": "Cita no encontrada"
}
```

**Status Code:** 404 Not Found

---

### 7. POST /appointments/calendar-events
Obtiene eventos de calendario para editar una cita específica.

#### Description
Retrieves calendar events for a specific equipment, marking one event as editable if provided.

#### Request Body
```json
{
  "guid": "uuid-del-evento-a-editar (opcional)",
  "equipment_aetitle": "aetitle-del-equipo (requerido)"
}
```

#### Request
```http
POST /api/appointments/calendar-events
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "equipment_aetitle": "CT-01",
  "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": {
    "timezone": "America/Argentina/Buenos_Aires",
    "events": [
      {
        "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
        "start": "2025-12-05T10:00:00",
        "end": "2025-12-05T11:00:00",
        "title": "Juan García - Tomografía",
        "patient_name": "Juan García",
        "exam": "Tomografía Computarizada",
        "editable": true
      }
    ],
    "work_hours": [
      {
        "day": 1,
        "start": "08:00:00",
        "end": "17:00:00"
      },
      {
        "day": 2,
        "start": "08:00:00",
        "end": "17:00:00"
      }
    ]
  }
}
```

#### Errors
```json
{
  "success": false,
  "message": "El campo equipment_aetitle es requerido"
}
```

---

### 8. GET /appointments/availability
Obtiene disponibilidad de un equipo para agendar citas.

#### Description
Checks availability of a specific equipment for scheduling appointments.

#### Query Parameters
- `equipment_id` (required): UUID del equipo
- `date` (required): Fecha a consultar (YYYY-MM-DD)

#### Request
```http
GET /api/appointments/availability?equipment_id=c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8&date=2025-12-05
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": {
    "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8",
    "date": "2025-12-05",
    "available_slots": [
      {
        "start": "08:00",
        "end": "09:00",
        "available": true
      },
      {
        "start": "09:00",
        "end": "10:00",
        "available": false
      },
      {
        "start": "10:00",
        "end": "11:00",
        "available": true
      }
    ]
  }
}
```

#### Errors
```json
{
  "success": false,
  "message": "Los parámetros equipment_id y date son requeridos"
}
```

---

## Common Response Codes

| Code | Description |
|------|-------------|
| 200  | OK - Operación exitosa |
| 201  | Created - Recurso creado exitosamente |
| 400  | Bad Request - Parámetros inválidos o incompletos |
| 401  | Unauthorized - Token JWT inválido o expirado |
| 404  | Not Found - Recurso no encontrado |
| 500  | Internal Server Error - Error del servidor |

---

## Authentication

Todos los endpoints requieren autenticación mediante JWT token. El token debe incluirse en el header `Authorization`:

```http
Authorization: Bearer <JWT_TOKEN>
```

**Token Acquisition:**
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

---

### 9. POST /admission/create-order
Crea una orden de admisión (worklist) con un examen.

#### Description
Creates an admission order (examination) in the system and sends it to the DICOM worklist.

#### Request Body
```json
{
  "patient_id": "uuid-del-paciente",
  "location_id": "uuid-de-la-ubicacion",
  "exam": {
    "study_type_id": "uuid-del-tipo-de-estudio",
    "equipment_id": "uuid-del-equipo",
    "physician_id": "uuid-del-medico-solicitante (opcional)",
    "insurance_id": "uuid-de-la-obra-social (opcional)",
    "severity": "normal | urgent (opcional, default: normal)"
  }
}
```

#### Request
```http
POST /api/admission/create-order
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "patient_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "location_id": "d1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o9",
  "exam": {
    "study_type_id": "b1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
    "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8",
    "physician_id": "e1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5f1",
    "insurance_id": "f1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5f2",
    "severity": "urgent"
  }
}
```

#### Response
**Status Code:** 201 Created

```json
{
  "success": true,
  "data": {
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "exam_id": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
    "study_instance_uid": "1.2.840.113619.1234567890.1",
    "timezone": "America/Argentina/Buenos_Aires"
  },
  "message": "Orden creada exitosamente"
}
```

#### Errors
```json
{
  "success": false,
  "message": "patient_id es obligatorio"
}
```

---

## Data Types

### Appointment Object
```json
{
  "guid": "string (UUID)",
  "patient_name": "string",
  "start": "string (ISO 8601 datetime)",
  "end": "string (ISO 8601 datetime)",
  "exam": "string",
  "doctor": "string",
  "equipment": "string",
  "is_admitted": "boolean",
  "location_id": "string (UUID)",
  "equipment_id": "string (UUID)",
  "modality": "string",
  "timezone": "string (e.g., America/Argentina/Buenos_Aires)"
}
```

### DateTime Format

**Para enviar (POST, PATCH):**
- Formato: `YYYY-MM-DD HH:MM:SS` (hora **local**)
- Ejemplo: `2025-12-05 10:00:00` (hora Argentina)
- El backend obtiene el timezone del `equipment_id` y convierte automáticamente a UTC

**Para recibir (GET):**
- Formato: ISO 8601 con zona horaria
- Ejemplo: `2025-12-05T10:00:00-03:00` (hora local + offset)
- El campo `timezone` en la respuesta indica la zona horaria de la location

**Conversión automática:**
```
Frontend envía: "2025-12-05 14:00:00" (Argentina)
    ↓
Backend: equipment → location → timezone
    ↓
Convierte: 14:00 ART → 17:00 UTC
    ↓
Almacena en BD: "2025-12-05 17:00:00" (UTC naive)
    ↓
Frontend recibe: "2025-12-05T14:00:00-03:00" (convertido de vuelta)
```

**Nota:** El frontend **no necesita hacer conversiones**. El backend maneja toda la lógica de timezone automáticamente.

---

## Pagination

Los endpoints que soportan paginación usan los siguientes parámetros:

- `page`: Número de página (comienza en 1)
- `per_page`: Cantidad de items por página (máximo 100)

**Response:**
```json
{
  "data": [...],
  "page": 1,
  "per_page": 20,
  "total": 150
}
```

---

## Error Handling

Todos los errores siguen un formato consistente:

```json
{
  "success": false,
  "message": "Descripción del error"
}
```

**Errores comunes:**
- `Se requiere un cuerpo JSON` - El request body está vacío
- `Los campos X son requeridos` - Faltan parámetros obligatorios
- `Cita no encontrada` - El ID de la cita no existe
- `Error de configuración de base de datos` - Problema de conexión a BD
- `Error en formato de fecha` - Fechas en formato inválido

---

## Examples

### Crear una nueva cita para un equipo
```bash
curl -X POST http://localhost:5000/api/appointments \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
    "appointment_type": "equipment",
    "exam_id": "b1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
    "start": "2025-12-05T10:00:00Z",
    "end": "2025-12-05T11:00:00Z",
    "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8"
  }'
```

### Reprogramar una cita (cambiar fecha y equipo)
```bash
curl -X PATCH http://localhost:5000/api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/reschedule \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start": "2025-12-20T14:00:00Z",
    "end": "2025-12-20T15:00:00Z",
    "equipment_id": "new-equipment-uuid"
  }'
```

### Obtener lista de médicos disponibles
```bash
curl -X GET "http://localhost:5000/api/doctors" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Obtener solo médicos activos
```bash
curl -X GET "http://localhost:5000/api/doctors?active_only=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Obtener citas de hoy
```bash
curl -X GET "http://localhost:5000/api/appointments?today=true&per_page=50" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Admisionar una cita
```bash
curl -X POST http://localhost:5000/api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/admit \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "additional_notes": "Paciente confirmado"
  }'
```

---

## Change Log

### Version 1.3.1 (2025-12-20) ✨ **Added Doctors Endpoint**
- ✅ Nuevo endpoint GET /doctors para obtener lista de médicos
- ✅ Filtra automáticamente usuarios con rol "Medico"
- ✅ Devuelve guid y nombre completo (concatenado)
- ✅ Soporta parámetro opcional `active_only` para filtrar médicos activos
- ✅ Útil para seleccionar médicos al crear/editar citas

### Version 1.3.0 (2025-12-20) ✨ **UTC Storage & Automatic Conversion**
- ✅ POST /appointments: Convierte automáticamente hora local → UTC usando timezone del equipment
- ✅ GET /appointments: Devuelve horas en formato ISO 8601 con zona horaria (local)
- ✅ PATCH /appointments/:id/reschedule: Ahora recibe hora local y convierte a UTC
- ✅ Todos los endpoints usan `equipment_id` para obtener timezone automáticamente
- ✅ Frontend **NO necesita hacer conversiones** - el backend maneja todo
- ✅ Base de datos siempre almacena en UTC (estándar internacional)
- ⚠️ **BREAKING CHANGE**: Campos de fecha modificados:
  - POST: `start` → `start_datetime`, `end` → `end_datetime`
  - PATCH reschedule: `start` → `start_datetime`, `end` → `end_datetime`
  - GET: Ahora devuelve con zona horaria en formato ISO (ej: `2025-12-18T14:00:00-03:00`)

### Version 1.3.2 (2025-12-20) ✨ **Added exam_id to GET /appointments**
- ✅ GET /appointments ahora devuelve `exam_id` (isstudytype.guid)
- ✅ Documentación actualizada con ejemplo de respuesta
- ✅ Endpoint funcional y verificado

### Version 1.3.1 (2025-12-20) ✨ **Medical Staff Management**
- ✅ Agregado endpoint GET /doctors para listar médicos
- ✅ Filtra usuarios con rol "Medico"
- ✅ Retorna guid y nombre concatenado

### Version 1.3.0 (2025-12-20) ✨ **Timezone Support with UTC Conversion**
- ✅ Implementada conversión automática de hora local → UTC en POST /appointments
- ✅ GET /appointments ahora convierte UTC → hora local
- ✅ PATCH /appointments/:id/reschedule actualizado con conversión UTC
- ✅ Timezone obtenido automáticamente desde location del equipment

### Version 1.2.0 (2025-12-20) ✨ **Timezone Support (Primera iteración)**
- ✅ Agregado campo `timezone` a respuestas
- ✅ Configuradas todas las locations con timezone
- ⚠️ Sin conversión automática (versión mejorada en 1.3.0)

### Version 1.1.0 (2025-12-17)
- ✅ Agregado campo `location_id` a respuesta de GET /appointments
- ✅ Agregado soporte para `equipment_id` en PATCH /appointments/:id/reschedule
- ✅ Mejorado debug logging en reschedule
- ✅ Agregada verificación de filas afectadas en updates

### Version 1.0.0 (Initial Release)
- ✅ Endpoints básicos de CRUD para appointments
- ✅ Soporte para filtros y paginación
- ✅ Integración con worklist DICOM

---

## Contact & Support

Para reportar issues o solicitar features, contactar al equipo de desarrollo.

**Repository:** https://github.com/FacuFarias/nextris-backend-react
