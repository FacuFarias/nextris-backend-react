# API Admissions Documentation

## Overview
Este documento describe todos los endpoints disponibles para la gestión de admisiones y worklist DICOM en el sistema NextRIS.

**Base URL:** `/api`
**Authentication:** Requerido JWT Token

---

## Endpoints

### 0. GET /admissions
Obtiene lista paginada de admisiones del usuario filtradas por ubicaciones asignadas.

#### Description
Retrieves a paginated list of admissions (worklist orders) for the authenticated user's assigned locations. Includes filters for status, date, and pagination support.

#### Query Parameters
- `status` (optional): Filtrar por estado (A, P, etc)
- `date` (optional): Filtrar por fecha en formato YYYY-MM-DD
- `page` (optional): Número de página (default: 1)
- `per_page` (optional): Items por página (default: 20, máximo: 100)

#### Request
```http
GET /api/admissions?page=1&per_page=20&status=A
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": [
    {
      "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
      "admission_number": "ADM001",
      "accession_number": "ACC001",
      "patient_surname": "Díaz",
      "patient_name": "Lucia",
      "study_type": "ANGIOGRAFÍA PELVIANA O VASOS ILÍACOS",
      "status": "A",
      "created_on": "2025-12-30T10:30:00",
      "is_executed": false,
      "is_admitted": true
    },
    {
      "guid": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
      "admission_number": "ADM002",
      "accession_number": "ACC002",
      "patient_surname": "García",
      "patient_name": "Juan",
      "study_type": "TOMOGRAFÍA COMPUTARIZADA",
      "status": "A",
      "created_on": "2025-12-30T11:15:00",
      "is_executed": true,
      "is_admitted": true
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20
}
```

#### Errors
```json
{
  "success": false,
  "message": "Error de configuración de base de datos"
}
```

---

### 1. GET /admissions/{admission_guid}
Obtiene detalles completos de una admisión específica.

#### Description
Retrieves complete details of an admission including patient information, study type, equipment, location, and execution status.

#### Path Parameters
- `admission_guid` (required): UUID of the admission

#### Request
```http
GET /api/admissions/f39710b4-7914-44ba-ab72-ad4ed5e22e98
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": {
    "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "patient_surname": "Díaz",
    "patient_name": "Lucia",
    "patient_id": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6",
    "study_type": "ANGIOGRAFÍA PELVIANA O VASOS ILÍACOS",
    "status": "A",
    "created_on": "2025-12-30T10:30:00",
    "is_executed": false,
    "is_admitted": true,
    "is_reported": false,
    "equipment": "CT Diagnóstico por Imag",
    "location": "Centro de Diagnóstico"
  }
}
```

#### Errors
```json
{
  "success": false,
  "message": "Admisión no encontrada"
}
```

---

### 2. POST /admissions/appointment/{appointment_guid}/admit
Admisiona una cita existente creando números de admisión y accession.

#### Description
Admits an appointment by marking it as admitted (IsAdmitted = 1) and generating unique admission and accession numbers. This creates a worklist entry.

#### Path Parameters
- `appointment_guid` (required): UUID of the appointment/examination to admit

#### Request Body (optional)
```json
{
  "notes": "notas adicionales o comentarios"
}
```

#### Request
```http
POST /api/admissions/appointment/f39710b4-7914-44ba-ab72-ad4ed5e22e98/admit
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "notes": "Paciente requiere monitoreo especial"
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
    "examination_guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98"
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

### 3. DELETE /admissions/{admission_guid}
Cancela una admisión (la marca como no admitida).

#### Description
Cancels an admission by marking IsAdmitted = 0. This removes the order from the worklist while keeping the appointment record.

#### Path Parameters
- `admission_guid` (required): UUID of the admission to cancel

#### Request
```http
DELETE /api/admissions/f39710b4-7914-44ba-ab72-ad4ed5e22e98
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Admisión cancelada exitosamente"
}
```

#### Errors
```json
{
  "success": false,
  "message": "Admisión no encontrada"
}
```

---

### 4. POST /admission/create-order
Crea una nueva orden de admisión directamente desde datos de paciente y equipo.

#### Description
Creates a new admission order (worklist entry) with an examination directly from patient, location, and equipment data. Generates unique ADM and ACC numbers automatically. Useful for creating worklist entries without a pre-existing appointment.

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
    "severity": "normal|urgent (opcional, default: normal)"
  }
}
```

#### Request
```http
POST /api/admission/create-order
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "patient_id": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
  "location_id": "a1234567-8901-2345-6789-012345678901",
  "exam": {
    "study_type_id": "b1234567-8901-2345-6789-012345678901",
    "equipment_id": "c1234567-8901-2345-6789-012345678901",
    "severity": "normal"
  }
}
```

#### Response
**Status Code:** 201 Created

```json
{
  "success": true,
  "data": {
    "admission_number": "ADM019",
    "accession_number": "ACC019",
    "exam_id": "d1234567-8901-2345-6789-012345678901",
    "study_instance_uid": "1.2.840.1767057345518.NR00000001",
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

```json
{
  "success": false,
  "message": "Paciente no encontrado"
}
```

```json
{
  "success": false,
  "message": "Equipo no encontrado"
}
```

```json
{
  "success": false,
  "message": "Tipo de estudio no encontrado"
}
```

---

## Data Types

### Admission Object (List)
```json
{
  "guid": "string (UUID)",
  "admission_number": "string (ADM001)",
  "accession_number": "string (ACC001)",
  "patient_surname": "string",
  "patient_name": "string",
  "study_type": "string",
  "status": "string (A, P, etc)",
  "created_on": "string (ISO 8601 datetime)",
  "is_executed": "boolean",
  "is_admitted": "boolean"
}
```

### Admission Details Object
```json
{
  "guid": "string (UUID)",
  "admission_number": "string",
  "accession_number": "string",
  "patient_surname": "string",
  "patient_name": "string",
  "patient_id": "string (UUID)",
  "study_type": "string",
  "status": "string",
  "created_on": "string (ISO 8601 datetime)",
  "is_executed": "boolean",
  "is_admitted": "boolean",
  "is_reported": "boolean",
  "equipment": "string",
  "location": "string"
}
```

---

## Filtering & Location-Based Access

### Location Filtering
All GET endpoints respect user location assignments:
- Returns only admissions for equipment assigned to user's locations
- Automatic filtering based on `rel_user_location` table
- Users cannot access admissions outside their assigned locations

### Status Values
- `A` - Active/Aprobado
- `P` - Pendiente
- `C` - Cancelled/Cancelado
- `R` - Reported/Reportado

---

## Pagination

### Response Format
```json
{
  "success": true,
  "data": [...],
  "total": 150,
  "page": 1,
  "per_page": 20
}
```

### Parameters
- `page`: página actual (comienza en 1)
- `per_page`: items por página (máximo 100)
- `total`: cantidad total de registros

---

## Error Handling

All errors follow a consistent format:

```json
{
  "success": false,
  "message": "Descripción del error"
}
```

**Common Errors:**
- `Admisión no encontrada` - The admission GUID doesn't exist
- `Cita no encontrada` - The appointment/examination doesn't exist
- `Error de configuración de base de datos` - Database connection error
- `Usuario no autenticado` - Invalid or missing JWT token

---

## Examples

### Listar admisiones
```bash
curl -X GET "http://localhost:5000/api/admissions?page=1&per_page=20&status=A" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Obtener detalles de una admisión
```bash
curl -X GET http://localhost:5000/api/admissions/f39710b4-7914-44ba-ab72-ad4ed5e22e98 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Admisionar una cita
```bash
curl -X POST http://localhost:5000/api/admissions/appointment/f39710b4-7914-44ba-ab72-ad4ed5e22e98/admit \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Paciente requiere inyección de contraste IV"
  }'
```

### Cancelar admisión
```bash
curl -X DELETE http://localhost:5000/api/admissions/f39710b4-7914-44ba-ab72-ad4ed5e22e98 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Database Schema Reference

### Tables Used
- `nextris.tbexamination` - Examination/admission records
- `nextris.datapatient` - Patient demographic data
- `nextris.isstudytype` - Study type descriptions
- `nextris.isequipment` - Equipment information
- `nextris.tblocation` - Location information
- `nextris.rel_user_location` - User location assignments

### Key Columns
- `AdmisionNumber` - Unique admission identifier (ADM001, ADM002, etc)
- `LocalAcc` - Local accession number (ACC001, ACC002, etc)
- `IsAdmitted` - Flag indicating if examination is in worklist (0 or 1)
- `IsExecuted` - Flag indicating if examination has been executed (0 or 1)
- `isreported` - Flag indicating if examination has been reported (0 or 1)
- `Status` - Current status of the examination

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Successful GET or DELETE request |
| 201 | Admission created successfully |
| 400 | Bad request (missing required fields) |
| 401 | Unauthorized (invalid JWT token) |
| 404 | Resource not found |
| 500 | Internal server error |

---

## Workflow Example

### Complete Admission Flow
```
1. User creates appointment
   POST /api/appointments
   
2. Appointment created with IsAdmitted = 0

3. User admits appointment
   POST /api/admissions/appointment/{id}/admit
   
4. System generates ADM and ACC numbers
   Admission is created in worklist
   
5. Worklist is sent to DICOM equipment
   Technician executes order
   
6. After execution, order appears in ejecución
   POST /api/executions/examination/{id}/execute
   
7. Can cancel admission if needed
   DELETE /api/admissions/{id}
```

---

## Version History

### Version 1.0.0 (2025-12-30) ✨ **Initial Release - Admissions API**
- ✅ Agregado endpoint GET /admissions para listar admisiones con paginación
- ✅ Agregado endpoint GET /admissions/{id} para detalles de admisión
- ✅ Agregado endpoint POST /admissions/appointment/{id}/admit para admisionar citas
- ✅ Agregado endpoint DELETE /admissions/{id} para cancelar admisiones
- ✅ Agregado endpoint POST /admission/create-order para crear órdenes directas
- ✅ Implementado filtrado automático por ubicaciones del usuario
- ✅ Soporte para filtros por status y fecha
- ✅ Paginación configurable
- ✅ Documentación completa con ejemplos

---

## Contact & Support

Para reportar issues o solicitar features, contactar al equipo de desarrollo.

**Repository:** https://github.com/FacuFarias/nextris-backend-react
