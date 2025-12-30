# API Execution Documentation

## Overview
Este documento describe todos los endpoints disponibles para la gestión de ejecución de órdenes de examen en el sistema NextRIS.

**Base URL:** `/api`
**Authentication:** Requerido JWT Token

---

## Endpoints

### 0. GET /executions/orders
Obtiene órdenes de exámenes pendientes de ejecución filtradas por ubicaciones del usuario.

#### Description
Retrieves a list of pending examination orders (not yet executed) filtered by the user's assigned locations. Only shows non-executed examinations.

#### Query Parameters
None

#### Request
```http
GET /api/executions/orders
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
      "created_on": "2025-12-30T10:30:00",
      "patient_surname": "Díaz",
      "patient_name": "Lucia",
      "study_type": "ANGIOGRAFÍA PELVIANA O VASOS ILÍACOS",
      "status": "A",
      "equipment": "CT Diagnóstico por Imag",
      "admission_number": "ADM001",
      "accession_number": "ACC001"
    },
    {
      "guid": "a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o7",
      "created_on": "2025-12-30T11:15:00",
      "patient_surname": "García",
      "patient_name": "Juan",
      "study_type": "TOMOGRAFÍA COMPUTARIZADA",
      "status": "A",
      "equipment": "CT Ecocardiografía",
      "admission_number": "ADM002",
      "accession_number": "ACC002"
    }
  ]
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

### 1. GET /executions/examination/{exam_guid}/details
Obtiene detalles completos de un examen para ejecutar.

#### Description
Retrieves complete details of an examination including clinical information, patient data, and existing order details for execution.

#### Path Parameters
- `exam_guid` (required): UUID of the examination

#### Request
```http
GET /api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/details
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "data": {
    "guid": "f39710b4-7914-44ba-ab72-ad4ed5e22e98",
    "study_type": "ANGIOGRAFÍA PELVIANA O VASOS ILÍACOS",
    "patient_name": "Díaz Lucia",
    "status": "A",
    "created_on": "2025-12-30T10:30:00",
    "is_reported": false,
    "study_instance_uid": "1.2.840.113619.1234567890.1",
    "history": "Historia clínica del paciente",
    "clinical_question": "¿Presencia de trombosis?",
    "laterality": "Bilateral",
    "stat": true,
    "number_of_views": 3,
    "other_details": "Requiere contraste"
  }
}
```

#### Errors
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```

---

### 2. POST /executions/examination/{exam_guid}/execute
Ejecuta un examen actualizando su estado y detalles clínicos.

#### Description
Marks an examination as executed and updates its clinical details. Converts "no clasifica" values to NULL in the database.

#### Path Parameters
- `exam_guid` (required): UUID of the examination

#### Request Body
```json
{
  "history": "Historia clínica (opcional)",
  "clinical_question": "Pregunta clínica (opcional)",
  "laterality": "Lateralidad (opcional)",
  "stat": true,
  "number_of_views": 2,
  "other_details": "Otros detalles técnicos (opcional)"
}
```

**Notes:**
- All fields are optional
- Use value `"no clasifica"` if field is not applicable (will be stored as NULL)
- `stat` expects boolean value (true/false)
- `number_of_views` expects integer

#### Request
```http
POST /api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/execute
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>

{
  "history": "Paciente con antecedentes de trombosis venosa",
  "clinical_question": "Descartar trombosis aguda",
  "laterality": "Bilateral",
  "stat": true,
  "number_of_views": 3,
  "other_details": "Protocolo estándar con contraste IV"
}
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Examen ejecutado exitosamente"
}
```

#### Errors
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```

---

### 3. POST /executions/examination/{exam_guid}/cancel
Cancela la ejecución de un examen (marca como no ejecutado).

#### Description
Cancels the execution of an examination by marking it as not executed (IsExecuted = 0). Useful for reversing an execution or removing an order from the worklist.

#### Path Parameters
- `exam_guid` (required): UUID of the examination

#### Request
```http
POST /api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/cancel
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>
```

#### Response
**Status Code:** 200 OK

```json
{
  "success": true,
  "message": "Examen cancelado exitosamente"
}
```

#### Errors
```json
{
  "success": false,
  "message": "Examen no encontrado"
}
```

---

## Data Types

### Examination Object
```json
{
  "guid": "string (UUID)",
  "study_type": "string",
  "patient_name": "string (Surname Name)",
  "status": "string",
  "created_on": "string (ISO 8601 datetime)",
  "is_reported": "boolean",
  "study_instance_uid": "string",
  "history": "string (medical history)",
  "clinical_question": "string (clinical question)",
  "laterality": "string (Izquierda, Derecha, Bilateral)",
  "stat": "boolean",
  "number_of_views": "integer",
  "other_details": "string"
}
```

### Execution Order Object
```json
{
  "guid": "string (UUID)",
  "created_on": "string (ISO 8601 datetime)",
  "patient_surname": "string",
  "patient_name": "string",
  "study_type": "string",
  "status": "string",
  "equipment": "string",
  "admission_number": "string",
  "accession_number": "string"
}
```

---

## Filtering & Location-Based Access

### Location Filtering
All endpoints in the execution API respect user location assignments:
- `GET /executions/orders` only returns orders for equipment assigned to user's locations
- Users can only see/execute orders in their assigned locations
- Location filtering is done automatically based on `rel_user_location` table

**How to assign locations to users:**
```sql
INSERT INTO nextris.rel_user_location (user_id, location_id)
VALUES ('user-guid', 'location-guid');
```

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
- `Examen no encontrado` - The examination GUID doesn't exist
- `Error de configuración de base de datos` - Database connection error
- `Usuario no autenticado` - Invalid or missing JWT token
- Missing fields in request body will use default values

---

## Examples

### Listar órdenes pendientes
```bash
curl -X GET http://localhost:5000/api/executions/orders \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Obtener detalles de un examen
```bash
curl -X GET http://localhost:5000/api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/details \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Ejecutar un examen
```bash
curl -X POST http://localhost:5000/api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/execute \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "history": "Paciente con síntomas de dolor torácico",
    "clinical_question": "Descartar infarto agudo",
    "laterality": "Bilateral",
    "stat": true,
    "number_of_views": 4,
    "other_details": "Protocolo de emergencia"
  }'
```

### Cancelar ejecución de examen
```bash
curl -X POST http://localhost:5000/api/executions/examination/f39710b4-7914-44ba-ab72-ad4ed5e22e98/cancel \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

---

## Database Schema Reference

### Tables Used
- `nextris.tbexamination` - Main examination records
- `nextris.datapatient` - Patient demographic data
- `nextris.isstudytype` - Study type descriptions
- `nextris.isequipment` - Equipment information
- `nextris.rel_user_location` - User location assignments

### Key Columns
- `IsExecuted` - Flag indicating if examination has been executed (0 or 1)
- `history` - Clinical history/medical history text
- `clinicalquestion` - Clinical question or reason for study
- `laterality_id` - Laterality information (left, right, bilateral)
- `stat` - STAT (urgent) flag
- `numberofviews` - Number of views/images acquired
- `othersdetails` - Additional technical details

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Successful GET or POST request |
| 201 | Resource created successfully |
| 400 | Bad request (missing required fields) |
| 401 | Unauthorized (invalid JWT token) |
| 404 | Resource not found |
| 500 | Internal server error |

---

## Version History

### Version 1.0.0 (2025-12-30) ✨ **Initial Release - Execution API**
- ✅ Agregado endpoint GET /executions/orders para listar órdenes pendientes
- ✅ Agregado endpoint GET /executions/examination/{id}/details para obtener detalles
- ✅ Agregado endpoint POST /executions/examination/{id}/execute para ejecutar examen
- ✅ Agregado endpoint POST /executions/examination/{id}/cancel para cancelar ejecución
- ✅ Implementado filtrado automático por ubicaciones del usuario
- ✅ Documentación completa con ejemplos

---

## Contact & Support

Para reportar issues o solicitar features, contactar al equipo de desarrollo.

**Repository:** https://github.com/FacuFarias/nextris-backend-react
