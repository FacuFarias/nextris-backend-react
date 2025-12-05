# Documentación de APIs - Nextris

Esta documentación describe todos los endpoints REST disponibles en el sistema Nextris.

## Tabla de Contenidos

1. [Autenticación](#autenticación)
2. [Pacientes](#pacientes)
3. [Estudios](#estudios)
4. [Administración](#administración)
5. [Turnos](#turnos)
6. [Institucional](#institucional)
7. [Médicos](#médicos)
8. [Reportes](#reportes)
9. [Configuración](#configuración)

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

## Turnos

### Base URL
`/api/appointments`

### Endpoints

#### GET /appointments
Listar turnos.

**Query Parameters:**
- `date`: Fecha específica (YYYY-MM-DD)
- `equipment_id`: Filtrar por equipo
- `status`: Filtrar por estado
- `patient_id`: Filtrar por paciente

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "appointmentdate": "datetime",
      "patient_name": "string",
      "studytype": "string",
      "equipment": "string",
      "status": "string",
      "duration": 30
    }
  ]
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
