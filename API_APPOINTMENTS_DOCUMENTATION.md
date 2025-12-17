# API Appointments Documentation

## Overview
Este documento describe todos los endpoints disponibles para la gestión de citas/turnos en el sistema NextRIS.

**Base URL:** `/api`
**Authentication:** Requerido JWT Token

---

## Endpoints

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
    "data": [
      {
        "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
        "patient_name": "Juan García",
        "start": "2025-12-18T14:00:00",
        "end": "2025-12-18T15:00:00",
        "exam": "Tomografía Computarizada",
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
  "exam_id": "uuid-del-examen",
  "start": "2025-12-05T10:00:00Z",
  "end": "2025-12-05T11:00:00Z",
  "doctor_id": "uuid-del-medico (opcional si appointment_type=equipment)",
  "equipment_id": "uuid-del-equipo (obligatorio si appointment_type=equipment)",
  "requesting_physician_id": "uuid-del-medico-solicitante (opcional)",
  "location_id": "uuid-de-la-ubicacion (opcional)"
}
```

#### Request
```http
POST /api/appointments
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "patient_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
  "appointment_type": "equipment",
  "exam_id": "b1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
  "start": "2025-12-05T10:00:00Z",
  "end": "2025-12-05T11:00:00Z",
  "equipment_id": "c1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o8",
  "location_id": "d1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o9"
}
```

#### Response
**Status Code:** 201 Created

```json
{
  "success": true,
  "message": "Cita(s) creada(s) exitosamente",
  "data": {
    "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98"
  }
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
  "start": "2025-12-05T10:00:00Z",
  "end": "2025-12-05T11:00:00Z",
  "equipment_id": "uuid-del-nuevo-equipo (opcional)"
}
```

#### Request
```http
PATCH /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/reschedule
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "start": "2025-12-20T14:00:00Z",
  "end": "2025-12-20T15:00:00Z",
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
  "additional_notes": "Notas adicionales (opcional)"
}
```

#### Request
```http
POST /api/appointments/f39710b4-7914-44ba-ab72-ad4ed5e22e98/admit
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "additional_notes": "Paciente llegó temprano"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Cita admisionada exitosamente y orden creada en worklist",
  "data": {
    "appointment_id": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
    "order_status": "admitted"
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
  "modality": "string"
}
```

### DateTime Format
- **Input:** ISO 8601 with timezone (e.g., `2025-12-05T10:00:00Z`)
- **Output:** ISO 8601 without timezone (e.g., `2025-12-05T10:00:00`)
- **Timezone:** Argentina/Buenos_Aires (UTC-3)

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
