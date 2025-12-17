# Documentación de APIs - Nextris

Esta documentación describe todos los endpoints REST disponibles en el sistema Nextris.

## Tabla de Contenidos

1. [Autenticación](#autenticación)
2. [Pacientes](#pacientes)
3. [Estudios](#estudios)
4. [Administración](#administración)
5. [Admisión React](#admisión-react)
6. [Turnos](#turnos)
7. [Institucional](#institucional)
8. [Médicos](#médicos)
9. [Reportes](#reportes)
10. [Configuración](#configuración)

---

## Autenticación

### Base URL
`/api/auth`

### Endpoints

#### POST /auth/login
Autenticación de usuario y obtención de tokens JWT.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Login exitoso",
  "data": {
    "access_token": "string",
    "refresh_token": "string",
    "user": {
      "id": "uuid",
      "username": "string",
      "name": "string",
      "surname": "string",
      "email": "string",
      "user_type": "string",
      "role_id": "uuid",
      "requires_password_change": false
    }
  }
}
```

#### POST /auth/refresh
Renovar token de acceso usando refresh token.

**Headers:**
```
Authorization: Bearer {refresh_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "string"
  }
}
```

#### POST /auth/logout
Cerrar sesión e invalidar tokens.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logout exitoso"
}
```

#### POST /auth/change-password
Cambiar contraseña del usuario autenticado.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Contraseña actualizada correctamente"
}
```

#### POST /auth/reset-password
Resetear contraseña de un usuario (requiere permisos admin).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "user_id": "uuid",
  "new_password": "string"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Contraseña reseteada correctamente"
}
```

#### GET /auth/verify
Verificar validez del token actual.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "valid": true,
    "user": {
      "id": "uuid",
      "username": "string",
      "user_type": "string"
    }
  }
}
```

#### GET /auth/user/:user_id/patientdomains
Obtener los patientdomains asociados a un usuario.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "patientdomain_id": "uuid",
      "patientdomain_name": "GENERAL",
      "created_at": "2024-01-01T10:00:00"
    }
  ]
}
```

---

## Pacientes

### Base URL
`/api/patients`

### Endpoints

#### GET /patients
Listar pacientes con filtros opcionales.

**Query Parameters:**
- `search` (opcional): Búsqueda por nombre, apellido o documento
- `page` (opcional): Número de página (default: 1)
- `per_page` (opcional): Items por página (default: 20)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "valid": true,
    "user": {
      "id": "uuid",
      "username": "string",
      "user_type": "string"
    }
  }
}
```

---

## Pacientes

### Base URL
`/api/patients`

### Endpoints

#### GET /patients
Listar pacientes con filtros opcionales.

**Query Parameters:**
- `search` (opcional): Búsqueda por nombre, apellido o documento
- `page` (opcional): Número de página (default: 1)
- `per_page` (opcional): Items por página (default: 20)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "patients": [
      {
        "guid": "uuid",
        "name": "string",
        "surname": "string",
        "documentnumber": "string",
        "birthdate": "date",
        "gender": "string",
        "email": "string",
        "phone": "string"
      }
    ],
    "total": 100,
    "page": 1,
    "per_page": 20,
    "total_pages": 5
  }
}
```

#### GET /patients/:id
Obtener detalles de un paciente específico.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "name": "string",
    "surname": "string",
    "documentnumber": "string",
    "birthdate": "date",
    "gender": "string",
    "email": "string",
    "phone": "string",
    "address": "string",
    "city": "string",
    "province": "string",
    "postalcode": "string",
    "country": "string",
    "socialsecuritynumber": "string",
    "healthinsurance": "string",
    "healthinsuranceplan": "string"
  }
}
```

#### POST /patients
Crear nuevo paciente.

**Request Body:**
```json
{
  "name": "string",
  "surname": "string",
  "documentnumber": "string",
  "birthdate": "date",
  "gender": "string",
  "email": "string",
  "phone": "string",
  "address": "string",
  "city": "string",
  "province": "string",
  "country": "string",
  "healthinsurance": "string"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Paciente creado exitosamente",
  "data": {
    "guid": "uuid"
  }
}
```

#### PUT /patients/:id
Actualizar información de un paciente.

**Request Body:** (mismos campos que POST, todos opcionales)

**Response (200):**
```json
{
  "success": true,
  "message": "Paciente actualizado exitosamente"
}
```

#### DELETE /patients/:id
Eliminar un paciente.

**Response (200):**
```json
{
  "success": true,
  "message": "Paciente eliminado exitosamente"
}
```

#### GET /patients/:id/studies
Obtener estudios de un paciente.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "studydate": "datetime",
      "studytype": "string",
      "modality": "string",
      "status": "string",
      "description": "string"
    }
  ]
}
```

#### GET /patients/:id/appointments
Obtener turnos de un paciente.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "appointmentdate": "datetime",
      "studytype": "string",
      "status": "string",
      "equipment": "string",
      "location": "string"
    }
  ]
}
```

#### GET /patients/:id/medical-history
Obtener historial médico del paciente.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "allergies": "string",
    "medications": "string",
    "conditions": "string",
    "surgeries": "string",
    "family_history": "string",
    "notes": "string"
  }
}
```

#### POST /patients/:id/medical-history
Actualizar historial médico del paciente.

**Request Body:**
```json
{
  "allergies": "string",
  "medications": "string",
  "conditions": "string",
  "surgeries": "string",
  "family_history": "string",
  "notes": "string"
}
```

#### GET /patients/search
Búsqueda avanzada de pacientes.

**Query Parameters:**
- `name`: Nombre
- `surname`: Apellido
- `document`: Número de documento
- `healthinsurance`: Obra social

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "surname": "string",
      "documentnumber": "string"
    }
  ]
}
```

---

## Estudios

### Base URL
`/api/studies`

### Endpoints

#### GET /studies
Listar estudios con filtros.

**Query Parameters:**
- `patient_id`: UUID del paciente
- `status`: Estado del estudio
- `date_from`: Fecha desde (YYYY-MM-DD)
- `date_to`: Fecha hasta (YYYY-MM-DD)
- `page`: Número de página
- `per_page`: Items por página

**Response (200):**
```json
{
  "success": true,
  "data": {
    "studies": [
      {
        "guid": "uuid",
        "studydate": "datetime",
        "patient_name": "string",
        "patient_surname": "string",
        "studytype": "string",
        "modality": "string",
        "status": "string",
        "referring_physician": "string"
      }
    ],
    "total": 100,
    "page": 1,
    "per_page": 20
  }
}
```

#### GET /studies/:id
Obtener detalles de un estudio.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "studydate": "datetime",
    "patient": {
      "guid": "uuid",
      "name": "string",
      "surname": "string"
    },
    "studytype": "string",
    "modality": "string",
    "status": "string",
    "description": "string",
    "indication": "string",
    "referring_physician": "string",
    "equipment": "string",
    "location": "string"
  }
}
```

#### POST /studies
Crear nuevo estudio.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "studytype_id": "uuid",
  "studydate": "datetime",
  "modality_id": "uuid",
  "description": "string",
  "indication": "string",
  "referring_physician_id": "uuid",
  "equipment_id": "uuid",
  "location_id": "uuid"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Estudio creado exitosamente",
  "data": {
    "guid": "uuid"
  }
}
```

#### PUT /studies/:id
Actualizar estudio.

**Response (200):**
```json
{
  "success": true,
  "message": "Estudio actualizado exitosamente"
}
```

#### DELETE /studies/:id
Eliminar estudio.

**Response (200):**
```json
{
  "success": true,
  "message": "Estudio eliminado exitosamente"
}
```

#### GET /studies/:id/images
Obtener imágenes del estudio.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "filename": "string",
      "series_number": "string",
      "instance_number": "string",
      "url": "string"
    }
  ]
}
```

#### POST /studies/:id/images
Subir imagen al estudio.

**Request Body:** (multipart/form-data)
- `file`: Archivo de imagen

**Response (201):**
```json
{
  "success": true,
  "message": "Imagen subida exitosamente"
}
```

#### GET /studies/:id/report
Obtener informe del estudio.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "report_text": "string",
    "findings": "string",
    "conclusion": "string",
    "radiologist": "string",
    "report_date": "datetime",
    "status": "string"
  }
}
```

#### POST /studies/:id/report
Crear o actualizar informe del estudio.

**Request Body:**
```json
{
  "report_text": "string",
  "findings": "string",
  "conclusion": "string"
}
```

#### PUT /studies/:id/status
Cambiar estado del estudio.

**Request Body:**
```json
{
  "status": "string"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Estado actualizado exitosamente"
}
```

---

## Administración

### Base URL
`/api/admin`

### Endpoints

#### GET /admin/users
Listar usuarios del sistema.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "username": "string",
      "name": "string",
      "surname": "string",
      "email": "string",
      "user_type": "string",
      "isactive": true,
      "role": "string"
    }
  ]
}
```

#### POST /admin/users
Crear nuevo usuario.

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "name": "string",
  "surname": "string",
  "email": "string",
  "user_type": "string",
  "role_id": "uuid"
}
```

#### PUT /admin/users/:id
Actualizar usuario.

**Response (200):**
```json
{
  "success": true,
  "message": "Usuario actualizado exitosamente"
}
```

#### DELETE /admin/users/:id
Desactivar usuario.

**Response (200):**
```json
{
  "success": true,
  "message": "Usuario desactivado exitosamente"
}
```

#### GET /admin/roles
Listar roles disponibles.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "description": "string",
      "permissions": ["string"]
    }
  ]
}
```

#### GET /admin/audit-logs
Obtener logs de auditoría.

**Query Parameters:**
- `user_id`: Filtrar por usuario
- `action`: Filtrar por acción
- `date_from`: Fecha desde
- `date_to`: Fecha hasta

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "user": "string",
      "action": "string",
      "entity": "string",
      "timestamp": "datetime",
      "details": "string"
    }
  ]
}
```

---

## Admisión React

### Base URL
`/api/institutional` / `/api/patients` / `/api/studies` / `/api/config`

### Descripción
Esta sección documenta las APIs utilizadas en la nueva vista React de Admisión. El flujo de admisión permite crear órdenes de trabajo (worklist) seleccionando:
1. Una ubicación (solo las que el usuario tiene asignadas)
2. Un paciente (filtrados por ubicación y dominio de paciente)
3. Un estudio/examen
4. Un equipo (filtrado por ubicación)
5. Médico solicitante y obra social (filtrados por ubicación)

### Endpoints Utilizados

#### GET /institutional/locations
Obtener ubicaciones/sedes asignadas al usuario autenticado.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Parámetros:** Ninguno (el user_id se obtiene del token JWT)

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "d290f1ee-6c54-4b01-90e6-d701748f0851",
      "name": "Sede Centro",
      "code": "SEDE-001",
      "is_default": true
    },
    {
      "guid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "name": "Sede Sur",
      "code": "SEDE-002",
      "is_default": false
    }
  ]
}
```

**Nota:** Solo retorna ubicaciones donde el usuario tiene acceso en la tabla `rel_user_location`.

---

#### POST /patients/by-location
Obtener pacientes filtrados por ubicación específica.

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "location_id": "d290f1ee-6c54-4b01-90e6-d701748f0851"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "p001",
      "name": "Juan",
      "surname": "Pérez",
      "nationalcode": "12345678",
      "sexcode": "M",
      "birthdate": "15/05/1990"
    },
    {
      "guid": "p002",
      "name": "María",
      "surname": "García",
      "nationalcode": "87654321",
      "sexcode": "F",
      "birthdate": "22/03/1985"
    }
  ]
}
```

**Nota:** Los pacientes se obtienen del `patientdomain_id` asociado a la ubicación. Retorna hasta 500 pacientes.

---

#### POST /patients
Crear nuevo paciente rápidamente desde la vista de admisión.

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Carlos",
  "surname": "López",
  "nationalcode": "11223344",
  "birthdate": "1988-07-10",
  "gender": "M"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Paciente creado exitosamente",
  "data": {
    "guid": "p003"
  }
}
```

---

#### GET /config/modalities
Obtener todas las modalidades disponibles (RX, TC, RM, ECO, etc.).

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "m001",
      "externalcode": "CT",
      "description": "Tomografía Computada"
    },
    {
      "guid": "m002",
      "externalcode": "MR",
      "description": "Resonancia Magnética"
    },
    {
      "guid": "m003",
      "externalcode": "CR",
      "description": "Radiografía Digital"
    }
  ]
}
```

---

#### GET /config/body-parts
Obtener todas las partes del cuerpo disponibles.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "bp001",
      "description": "Tórax"
    },
    {
      "guid": "bp002",
      "description": "Abdomen"
    },
    {
      "guid": "bp003",
      "description": "Extremidades"
    }
  ]
}
```

---

#### GET /study-types
Obtener todos los tipos de estudios disponibles desde la tabla `isstudytype`.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    [
      "guid-001",
      "TC-TORAX",
      "TOMOGRAFIA AXIAL COMPUTADA TORACICA",
      "CT",
      "Tórax",
      "Torax"
    ],
    [
      "guid-002",
      "RX-TORAX",
      "RADIOGRAFIA SIMPLE DE TORAX",
      "RX",
      "Tórax",
      "Torax"
    ]
  ]
}
```

**Nota:** Retorna un array de arrays con [guid, code, description, modality_code, bodypart, studygroup]. Este es el catálogo completo de tipos de estudios disponibles en el sistema.

---

#### GET /config/equipment
Obtener equipos disponibles filtrados por ubicación.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `location_id` (OBLIGATORIO): UUID de la ubicación para filtrar equipos

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "eq001",
      "description": "Tomógrafo Siemens SOMATOM",
      "aeTitle": "CT_SIEMENS_01",
      "externalcode": "TC-001",
      "modality": "CT"
    },
    {
      "guid": "eq002",
      "description": "Radiografo Digital Philips",
      "aeTitle": "CR_PHILIPS_01",
      "externalcode": "RX-001",
      "modality": "CR"
    }
  ]
}
```

**Response (400) - Sin location_id:**
```json
{
  "success": false,
  "message": "El parámetro location_id es obligatorio"
}
```

---

### Flujo de Trabajo en Admisión React

**Paso 1: Cargar Ubicaciones**
```
GET /api/institutional/locations
↓
Usuario selecciona ubicación
```

**Paso 2: Cargar Pacientes de la Ubicación**
```
POST /api/patients/by-location
Body: { "location_id": "..." }
↓
Usuario selecciona paciente o crea uno nuevo
```

**Paso 3: Cargar Catálogo de Tipos de Estudios**
```
GET /api/study-types
↓
Usuario selecciona estudio por código/descripción
```

**Paso 4: Cargar Equipos Disponibles**
```
GET /api/config/equipment?location_id=...
↓
Usuario selecciona equipo
```

**Paso 5: Cargar Médicos Solicitantes**
```
GET /api/institutional/locations/{location_id}/physicians
↓
Usuario selecciona médico solicitante
```

**Paso 6: Cargar Obras Sociales**
```
GET /api/institutional/locations/{location_id}/health-insurances
↓
Usuario selecciona obra social
```

**Paso 7: Finalizar Orden**
```
POST /api/admission/create-order
↓
Orden creada con número de admisión y acceso
```

#### POST /admission/create-order
Crear orden de admisión (worklist) con un examen. Este endpoint:
1. Valida la existencia del paciente, equipo y tipo de estudio
2. Genera números de admisión y acceso automáticamente
3. **Envía mensaje HL7 al dcm4chee (que crea el mwl_item en el worklist DICOM)**
4. Inserta el examen en tbexamination
5. Crea el registro en tbreport

**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "patient_id": "uuid-del-paciente",
  "location_id": "uuid-de-la-ubicacion",
  "exam": {
    "study_type_id": "uuid-del-tipo-de-estudio",
    "equipment_id": "uuid-del-equipo",
    "physician_id": "uuid-del-medico-solicitante",
    "insurance_id": "uuid-de-la-obra-social",
    "severity": "normal"
  }
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "exam_id": "uuid-del-examen",
    "study_instance_uid": "1.2.840..."
  },
  "message": "Orden creada exitosamente"
}
```

**Request Body:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "location_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "exam": {
    "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
    "equipment_id": "eq001-guid",
    "physician_id": "physician-guid" (opcional),
    "insurance_id": "insurance-guid" (opcional),
    "severity": "normal" | "urgent" (opcional, default: "normal")
  }
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "admission_number": "ADM008",
    "accession_number": "ACC008",
    "exam_id": "9b130f5c-e689-4b47-9488-3629a24d9cac",
    "study_instance_uid": "1.2.840.1765496198069.NR00000013"
  },
  "message": "Orden creada exitosamente"
}
```

**Response (400) - Campos obligatorios faltantes:**
```json
{
  "success": false,
  "message": "patient_id es obligatorio"
}
```

**Campos Obligatorios:**
- `patient_id`: UUID del paciente
- `location_id`: UUID de la ubicación
- `exam.study_type_id`: UUID del tipo de estudio
- `exam.equipment_id`: UUID del equipo

**Campos Opcionales:**
- `exam.physician_id`: UUID del médico solicitante
- `exam.insurance_id`: UUID de la obra social
- `exam.severity`: "normal" o "urgent"

#### GET /institutional/locations/{location_id}/physicians
Obtener médicos solicitantes filtrados por ubicación.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `location_id` (OBLIGATORIO): UUID de la ubicación

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "physician-guid-1",
      "description": "Dr. Juan Pérez"
    },
    {
      "guid": "physician-guid-2",
      "description": "Dra. María González"
    }
  ]
}
```

**Response (400) - Sin location_id:**
```json
{
  "success": false,
  "message": "El parámetro location_id es obligatorio"
}
```

#### GET /institutional/locations/{location_id}/health-insurances
Obtener obras sociales (price lists) filtradas por ubicación.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Path Parameters:**
- `location_id` (OBLIGATORIO): UUID de la ubicación

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "insurance-guid-1",
      "description": "OSDE"
    },
    {
      "guid": "insurance-guid-2",
      "description": "Swiss Medical"
    }
  ]
}
```

**Response (400) - Sin location_id:**
```json
{
  "success": false,
  "message": "El parámetro location_id es obligatorio"
}
```

---

## Turnos

### Base URL
`/api/appointments`

### Endpoints

#### POST /appointments/calendar-events
Obtener eventos del calendario para editar.

**Request Body:**
```json
{
  "guid": "optional-event-guid-to-edit",
  "equipment_aetitle": "aetitle-del-equipo"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "guid": "uuid",
        "start": "2025-12-05T10:00:00",
        "end": "2025-12-05T11:00:00",
        "title": "Paciente - Examen",
        "patient_name": "string",
        "exam": "string",
        "editable": true,
        "idmed": "uuid",
        "idmed_sol": "uuid"
      }
    ],
    "work_hours": [
      {
        "day": 1,
        "start": "08:00:00",
        "end": "17:00:00"
      }
    ]
  }
}
```

#### GET /appointments
Listar turnos con paginación.

**Query Parameters:**
- `date`: Fecha específica (YYYY-MM-DD)
- `doctor_id`: Filtrar por médico
- `equipment_id`: Filtrar por equipo
- `admitted`: true/false (filtrar por estado de admisión)
- `today`: true (obtener solo citas del día actual)
- `page`: Número de página (default: 1)
- `per_page`: Items por página (default: 20, max: 100)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "guid": "uuid",
        "patient_name": "string",
        "start": "datetime",
        "end": "datetime",
        "exam": "string",
        "doctor": "string",
        "equipment": "string",
        "is_admitted": false,
        "location_id": "uuid"
      }
    ],
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

#### POST /appointments
Crear nuevo turno.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "appointmentdate": "datetime",
  "studytype_id": "uuid",
  "equipment_id": "uuid",
  "duration": 30,
  "notes": "string"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Turno creado exitosamente",
  "data": {
    "guid": "uuid"
  }
}
```

#### PUT /appointments/:id
Actualizar turno.

**Response (200):**
```json
{
  "success": true,
  "message": "Turno actualizado exitosamente"
}
```

#### DELETE /appointments/:id
Cancelar turno.

**Response (200):**
```json
{
  "success": true,
  "message": "Turno cancelado exitosamente"
}
```

#### GET /appointments/availability
Consultar disponibilidad de turnos.

**Query Parameters:**
- `equipment_id`: UUID del equipo
- `date`: Fecha (YYYY-MM-DD)
- `studytype_id`: Tipo de estudio

**Response (200):**
```json
{
  "success": true,
  "data": {
    "available_slots": [
      {
        "start_time": "HH:MM",
        "end_time": "HH:MM",
        "available": true
      }
    ]
  }
}
```

#### POST /appointments/:id/confirm
Confirmar turno.

**Response (200):**
```json
{
  "success": true,
  "message": "Turno confirmado exitosamente"
}
```

#### POST /appointments/:id/reschedule
Reprogramar turno.

**Request Body:**
```json
{
  "new_date": "datetime"
}
```

#### PATCH /appointments/:id/reschedule
Actualizar fechas y/o equipo de una cita (reprogramar).

**Path Parameters:**
- `id`: GUID de la cita

**Request Body:**
```json
{
  "start": "2025-12-05T10:00:00Z",
  "end": "2025-12-05T11:00:00Z",
  "equipment_id": "uuid-del-nuevo-equipo (opcional)"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Cita reprogramada exitosamente (1 registro(s) actualizado(s))",
  "rows_affected": 1
}
```

**Notes:**
- `start` y `end` son requeridos
- `equipment_id` es opcional - si se proporciona, cambia el equipo de la cita
- Las fechas deben estar en formato ISO 8601 con zona horaria (Z para UTC)

#### PATCH /appointments/:id
Actualizar datos de una cita existente.

**Path Parameters:**
- `id`: GUID de la cita

**Request Body:**
```json
{
  "doctor_id": "optional-nuevo-guid-medico",
  "requesting_physician_id": "optional-guid-medico-solicitante",
  "exam_id": "optional-nuevo-guid-examen"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Cita actualizada exitosamente"
}
```

#### POST /appointments/:id/admit
Admisionar una cita y crear examen en worklist.

**Path Parameters:**
- `id`: GUID de la cita

**Request Body (opcional):**
```json
{
  "equipment_id": "guid-del-equipo"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "admission_number": "ADM123",
    "accession_number": "ACC123",
    "exam_id": "guid-del-examen-creado",
    "study_instance_uid": "1.2.840..."
  },
  "message": "Cita admisionada exitosamente"
}
```

---

## Institucional

### Base URL
`/api/institutional`

### Endpoints

#### GET /institutional/locations
Listar sedes/locaciones.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "code": "string",
      "address": "string",
      "city": "string",
      "phone": "string",
      "email": "string",
      "isactive": true
    }
  ]
}
```

#### GET /institutional/facilities
Listar establecimientos.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "code": "string",
      "address": "string",
      "city": "string",
      "country": "string",
      "phone": "string",
      "email": "string",
      "contact_person": "string",
      "status": "string"
    }
  ]
}
```

#### GET /institutional/locations/:location_id/physicians
Obtener médicos solicitantes filtrados por ubicación.

**Path Parameters:**
- `location_id`: UUID de la ubicación (OBLIGATORIO)

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Dr. Juan Pérez"
    }
  ]
}
```

#### GET /institutional/locations/:location_id/health-insurances
Obtener obras sociales (price lists) filtradas por ubicación.

**Path Parameters:**
- `location_id`: UUID de la ubicación (OBLIGATORIO)

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "OSDE"
    }
  ]
}
```

---

## Médicos

### Base URL
`/api/physicians`

### Endpoints

#### GET /physicians
Listar médicos.

**Query Parameters:**
- `specialty`: Filtrar por especialidad
- `search`: Búsqueda por nombre

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "surname": "string",
      "specialty": "string",
      "license_number": "string",
      "email": "string",
      "phone": "string"
    }
  ]
}
```

#### POST /physicians
Crear nuevo médico.

**Request Body:**
```json
{
  "name": "string",
  "surname": "string",
  "specialty": "string",
  "license_number": "string",
  "email": "string",
  "phone": "string"
}
```

#### PUT /physicians/:id
Actualizar médico.

**Response (200):**
```json
{
  "success": true,
  "message": "Médico actualizado exitosamente"
}
```

#### DELETE /physicians/:id
Eliminar médico.

**Response (200):**
```json
{
  "success": true,
  "message": "Médico eliminado exitosamente"
}
```

#### GET /physicians/:id/studies
Obtener estudios del médico.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "studydate": "datetime",
      "patient_name": "string",
      "studytype": "string",
      "status": "string"
    }
  ]
}
```

#### GET /physicians/specialties
Listar especialidades disponibles.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "description": "string"
    }
  ]
}
```

#### GET /physicians/:id/schedule
Obtener agenda del médico.

**Query Parameters:**
- `date_from`: Fecha desde
- `date_to`: Fecha hasta

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "date": "date",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "available": true
    }
  ]
}
```

---

## Reportes

### Base URL
`/api/reports`

### Endpoints

#### GET /reports/studies
Reporte de estudios realizados.

**Query Parameters:**
- `date_from`: Fecha desde (YYYY-MM-DD)
- `date_to`: Fecha hasta (YYYY-MM-DD)
- `modality`: Filtrar por modalidad
- `location_id`: Filtrar por sede
- `format`: pdf|excel|json (default: json)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_studies": 150,
    "by_modality": {
      "RX": 50,
      "TC": 30,
      "RM": 40,
      "ECO": 30
    },
    "by_status": {
      "completed": 120,
      "pending": 20,
      "cancelled": 10
    },
    "studies": [
      {
        "guid": "uuid",
        "studydate": "datetime",
        "patient": "string",
        "studytype": "string",
        "status": "string"
      }
    ]
  }
}
```

#### GET /reports/appointments
Reporte de turnos.

**Query Parameters:**
- `date_from`: Fecha desde
- `date_to`: Fecha hasta
- `status`: Filtrar por estado

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_appointments": 200,
    "by_status": {
      "scheduled": 100,
      "confirmed": 70,
      "cancelled": 30
    },
    "appointments": [...]
  }
}
```

#### GET /reports/revenue
Reporte de facturación.

**Query Parameters:**
- `date_from`: Fecha desde
- `date_to`: Fecha hasta
- `location_id`: Filtrar por sede

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_revenue": 150000,
    "by_location": {
      "Sede A": 80000,
      "Sede B": 70000
    },
    "by_studytype": {
      "Radiografía": 30000,
      "Tomografía": 50000,
      "Resonancia": 70000
    }
  }
}
```

#### GET /reports/patients
Reporte de pacientes.

**Query Parameters:**
- `date_from`: Fecha desde (fecha de registro)
- `date_to`: Fecha hasta

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_patients": 500,
    "new_patients": 50,
    "by_gender": {
      "M": 250,
      "F": 250
    },
    "by_age_range": {
      "0-18": 50,
      "19-40": 200,
      "41-60": 150,
      "60+": 100
    }
  }
}
```

#### GET /reports/equipment-usage
Reporte de uso de equipos.

**Query Parameters:**
- `date_from`: Fecha desde
- `date_to`: Fecha hasta
- `equipment_id`: Filtrar por equipo

**Response (200):**
```json
{
  "success": true,
  "data": {
    "equipment": [
      {
        "equipment_name": "string",
        "total_studies": 50,
        "utilization_rate": 0.75,
        "downtime_hours": 2
      }
    ]
  }
}
```

#### GET /reports/physicians-productivity
Reporte de productividad de médicos.

**Query Parameters:**
- `date_from`: Fecha desde
- `date_to`: Fecha hasta
- `physician_id`: Filtrar por médico

**Response (200):**
```json
{
  "success": true,
  "data": {
    "physicians": [
      {
        "physician_name": "string",
        "total_reports": 45,
        "avg_report_time": 15,
        "pending_reports": 5
      }
    ]
  }
}
```

#### POST /reports/custom
Generar reporte personalizado.

**Request Body:**
```json
{
  "report_type": "string",
  "filters": {
    "date_from": "date",
    "date_to": "date",
    "additional_filters": {}
  },
  "columns": ["string"],
  "format": "pdf|excel|json"
}
```

#### GET /reports/:id/download
Descargar reporte generado.

**Response:** Archivo PDF o Excel

#### GET /reports/dashboard
Datos para dashboard principal.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "today_appointments": 15,
    "pending_studies": 8,
    "pending_reports": 12,
    "equipment_available": 5,
    "revenue_today": 15000,
    "new_patients_week": 25
  }
}
```

#### GET /reports/waitlist
Reporte de lista de espera.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "total_waiting": 50,
    "by_priority": {
      "high": 10,
      "medium": 25,
      "low": 15
    },
    "avg_wait_days": 5
  }
}
```

---

## Configuración

### Base URL
`/api/config`

### Endpoints

#### GET /config/system
Obtener configuración del sistema.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "system_name": "string",
    "version": "string",
    "timezone": "string",
    "language": "string",
    "date_format": "string",
    "currency": "string"
  }
}
```

#### PUT /config/system
Actualizar configuración del sistema.

**Request Body:**
```json
{
  "system_name": "string",
  "timezone": "string",
  "language": "string",
  "date_format": "string"
}
```

#### GET /config/workflow
Obtener configuración de flujo de trabajo.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "auto_confirm_appointments": true,
    "require_referral": false,
    "default_study_duration": 30,
    "email_notifications": true
  }
}
```

#### GET /config/study-types
Listar tipos de estudio disponibles.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "code": "string",
      "description": "string",
      "modality": "string",
      "bodypart": "string",
      "duration": 30,
      "isactive": true
    }
  ]
}
```

#### POST /config/study-types
Crear tipo de estudio.

**Request Body:**
```json
{
  "code": "string",
  "description": "string",
  "modality_id": "uuid",
  "bodypart_id": "uuid",
  "duration": 30
}
```

#### PUT /config/study-types/:id
Actualizar tipo de estudio.

**Response (200):**
```json
{
  "success": true,
  "message": "Tipo de estudio actualizado exitosamente"
}
```

#### DELETE /config/study-types/:id
Eliminar tipo de estudio.

**Response (200):**
```json
{
  "success": true,
  "message": "Tipo de estudio eliminado exitosamente"
}
```

#### GET /config/modalities
Listar modalidades (RX, TC, RM, ECO, etc.).

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "externalcode": "string",
      "description": "string"
    }
  ]
}
```

#### GET /config/body-parts
Listar partes del cuerpo.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "string"
    }
  ]
}
```

#### GET /config/study-groups
Listar grupos de estudio.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "string"
    }
  ]
}
```

#### GET /config/equipment
Listar equipos disponibles.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "code": "string",
      "description": "string",
      "modality": "string",
      "location": "string",
      "status": "string",
      "isactive": true
    }
  ]
}
```

#### POST /config/equipment
Crear equipo.

**Request Body:**
```json
{
  "code": "string",
  "description": "string",
  "modality_id": "uuid",
  "location_id": "uuid",
  "aetitle": "string"
}
```

#### DELETE /config/equipment/:id
Eliminar equipo.

**Response (200):**
```json
{
  "success": true,
  "message": "Equipo eliminado exitosamente"
}
```

#### GET /config/locations
Listar ubicaciones/sedes.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "code": "string",
      "address": "string",
      "city": "string",
      "phone": "string",
      "facility": "string"
    }
  ]
}
```

#### POST /config/locations
Crear ubicación.

**Request Body:**
```json
{
  "name": "string",
  "code": "string",
  "address": "string",
  "city": "string",
  "phone": "string",
  "facility_id": "uuid"
}
```

#### DELETE /config/locations/:id
Eliminar ubicación.

**Response (200):**
```json
{
  "success": true,
  "message": "Ubicación eliminada exitosamente"
}
```

#### GET /config/facilities
Listar establecimientos.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "name": "string",
      "code": "string",
      "email": "string",
      "contact_person": "string",
      "description": "string",
      "address": "string",
      "city": "string",
      "country": "string",
      "phone": "string",
      "status": "string"
    }
  ]
}
```

#### POST /config/facilities
Crear establecimiento.

**Request Body:**
```json
{
  "name": "string",
  "code": "string",
  "email": "string",
  "contact_person": "string",
  "address": "string",
  "city": "string",
  "country": "string",
  "phone": "string"
}
```

#### PUT /config/facilities/:id
Actualizar establecimiento.

**Request Body:**
```json
{
  "name": "string",
  "code": "string",
  "email": "string",
  "contact_person": "string",
  "description": "string",
  "address": "string",
  "city": "string",
  "country": "string",
  "phone": "string",
  "status": "string"
}
```

#### PATCH /config/facilities/:id
Actualizar parcialmente establecimiento (mismos campos que PUT, todos opcionales).

#### DELETE /config/facilities/:id
Eliminar establecimiento.

**Response (200):**
```json
{
  "success": true,
  "message": "Establecimiento eliminado exitosamente"
}
```

---

## Códigos de Error Comunes

- **400 Bad Request**: Datos inválidos en la solicitud
- **401 Unauthorized**: Token de autenticación inválido o ausente
- **403 Forbidden**: Sin permisos para realizar la operación
- **404 Not Found**: Recurso no encontrado
- **409 Conflict**: Conflicto con el estado actual (ej: duplicado)
- **422 Unprocessable Entity**: Validación de datos falló
- **500 Internal Server Error**: Error interno del servidor

## Notas Generales

### Autenticación
Todos los endpoints (excepto `/auth/login`) requieren un token JWT válido en el header:
```
Authorization: Bearer {access_token}
```

### Paginación
Los endpoints que retornan listas soportan paginación con los parámetros:
- `page`: Número de página (default: 1)
- `per_page`: Items por página (default: 20, max: 100)

### Formato de Fechas
- Fechas: `YYYY-MM-DD`
- Fechas con hora: `YYYY-MM-DD HH:MM:SS`
- Timezone: UTC por defecto

### Respuestas Estandarizadas
Todas las respuestas siguen el formato:
```json
{
  "success": true|false,
  "data": {},
  "message": "string"
}
```

### Rate Limiting
- 1000 requests por hora por usuario autenticado
- 100 requests por hora para endpoints públicos

---

**Versión:** 1.0  
**Última actualización:** Diciembre 2025
