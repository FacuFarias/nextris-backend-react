# API de Configuración - Documentación Completa

Esta documentación describe todas las APIs de configuración del sistema NEXTRIS disponibles en `/apps/api/config.py`.

**Base URL**: `/api/config`

**Autenticación**: Todas las APIs requieren autenticación JWT mediante el header `Authorization: Bearer <token>`

---

## Tabla de Contenidos

1. [Tipos de Estudio](#tipos-de-estudio)
2. [Localizaciones](#localizaciones)
3. [Instalaciones](#instalaciones)
4. [Modalidades](#modalidades)
5. [Partes del Cuerpo](#partes-del-cuerpo)
6. [Grupos de Estudio](#grupos-de-estudio)
7. [Equipos](#equipos)
8. [Agendas de Equipos](#agendas-de-equipos)
9. [Usuarios](#usuarios)
10. [Roles](#roles)
11. [Pacientes](#pacientes)
12. [Médicos Solicitantes](#médicos-solicitantes)
13. [Agendas de Médicos](#agendas-de-médicos)
14. [Grupos de Estudio por Médico](#grupos-de-estudio-por-médico)

---

## Tipos de Estudio

### GET /config/study-types
Obtiene todos los tipos de estudio con sus relaciones.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "code": "RX-001",
      "description": "Radiografía de Tórax",
      "studygroup": "Radiología Simple",
      "bodypart": "Tórax",
      "modality": "CR",
      "rvu": 1.5,
      "nofviews": 2
    }
  ]
}
```

### POST /config/study-types
Crea un nuevo tipo de estudio.

**Request Body:**
```json
{
  "code": "RX-001",                  // requerido
  "description": "Radiografía de Tórax",  // requerido
  "studygroup_id": "uuid",           // requerido
  "bodypart_id": "uuid",             // requerido
  "modality_id": "uuid",             // requerido
  "rvu": 1.5,                        // opcional
  "nofviews": 2                      // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "message": "Tipo de estudio creado exitosamente",
  "data": {
    "study_type_id": "uuid"
  }
}
```

**Errores comunes:**
- `400`: code, description, studygroup_id, bodypart_id y modality_id son requeridos

### PUT/PATCH /config/study-types/:study_type_id
Actualiza un tipo de estudio existente.

**Path Parameters:**
- `study_type_id` (string, requerido): UUID del tipo de estudio

**Request Body:** (todos los campos son opcionales)
```json
{
  "code": "RX-002",
  "description": "Radiografía de Tórax PA y Lateral",
  "studygroup_id": "uuid",
  "bodypart_id": "uuid",
  "modality_id": "uuid",
  "rvu": 2.0,
  "nofviews": 2
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Tipo de estudio actualizado exitosamente"
}
```

**Errores comunes:**
- `400`: No hay campos para actualizar
- `404`: Tipo de estudio no encontrado

### DELETE /config/study-types/:study_type_id
Elimina un tipo de estudio.

**Path Parameters:**
- `study_type_id` (string, requerido): UUID del tipo de estudio

**Response 200:**
```json
{
  "success": true,
  "message": "Tipo de estudio eliminado exitosamente"
}
```

**Errores comunes:**
- `404`: Tipo de estudio no encontrado

---

## Localizaciones

### GET /config/locations
Obtiene todas las localizaciones del sistema.

**Query Parameters:**
- `include_inactive` (boolean, opcional): Incluir localizaciones inactivas. Default: `false`

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Ubicación Principal",
      "facility_id": "uuid",
      "facility_name": "Hospital Central",
      "status": "active",
      "address": "Calle 123",
      "city": "Ciudad",
      "state": "Estado",
      "zip_code": "12345",
      "country": "País",
      "phone": "+1234567890",
      "email": "contact@hospital.com",
      "timezone": "America/Mexico_City",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### POST /config/locations
Crea una nueva localización.

**Request Body:**
```json
{
  "description": "Nueva Ubicación",  // requerido
  "facility_id": "uuid",             // requerido
  "status": "active",                // opcional, default: "active"
  "address": "Calle 123",            // opcional
  "city": "Ciudad",                  // opcional
  "state": "Estado",                 // opcional
  "zip_code": "12345",               // opcional
  "country": "País",                 // opcional
  "phone": "+1234567890",            // opcional
  "email": "contact@hospital.com",   // opcional
  "timezone": "America/Mexico_City"  // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* objeto location creado */ },
  "message": "Localización creada exitosamente"
}
```

### PUT/PATCH /config/locations/:location_id
Actualiza una localización existente.

**Request Body:** (todos los campos son opcionales)
```json
{
  "description": "Ubicación Actualizada",
  "facility_id": "uuid",
  "status": "inactive",
  "address": "Nueva Calle",
  // ... otros campos
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* objeto location actualizado */ },
  "message": "Localización actualizada exitosamente"
}
```

### DELETE /config/locations/:location_id
Elimina una localización.

**Response 200:**
```json
{
  "success": true,
  "message": "Localización eliminada exitosamente"
}
```

---

## Instalaciones

### GET /config/facilities
Obtiene todas las instalaciones con sus configuraciones.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Hospital Central",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00",
      "smtp_config": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "user@example.com",
        "smtp_password": "encrypted",
        "smtp_from": "noreply@hospital.com",
        "smtp_from_name": "Hospital Central",
        "smtp_use_tls": true
      },
      "backend_config": {
        "backend_db_user": "dbuser",
        "backend_db_password": "encrypted",
        "backend_db_host": "localhost",
        "backend_db_port": 5432,
        "backend_db_name": "pacsdb",
        "backend_base_folder": "/var/www",
        "backend_ipserver": "192.168.1.100"
      },
      "whatsapp_config": {
        "whatsapp_api_url": "https://api.whatsapp.com",
        "whatsapp_token": "token",
        "whatsapp_phone_number_id": "123456",
        "whatsapp_business_account_id": "account_id",
        "whatsapp_webhook_verify_token": "verify_token",
        "whatsapp_is_active": true
      }
    }
  ]
}
```

### POST /config/facilities
Crea una nueva instalación con configuraciones.

**Request Body:**
```json
{
  "description": "Nueva Instalación",  // requerido
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "user@example.com",
  "smtp_password": "password",
  "smtp_from": "noreply@hospital.com",
  "smtp_from_name": "Hospital",
  "smtp_use_tls": true,
  "backend_db_user": "dbuser",
  "backend_db_password": "dbpass",
  "backend_db_host": "localhost",
  "backend_db_port": 5432,
  "backend_db_name": "pacsdb",
  "backend_base_folder": "/var/www",
  "backend_ipserver": "192.168.1.100",
  "whatsapp_api_url": "https://api.whatsapp.com",
  "whatsapp_token": "token",
  "whatsapp_phone_number_id": "123456",
  "whatsapp_business_account_id": "account_id",
  "whatsapp_webhook_verify_token": "verify_token",
  "whatsapp_is_active": true
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* objeto facility creado */ },
  "message": "Instalación creada exitosamente"
}
```

### PUT/PATCH /config/facilities/:facility_id
Actualiza una instalación y sus configuraciones.

**Request Body:** (todos los campos son opcionales)
```json
{
  "description": "Instalación Actualizada",
  "smtp_server": "new-smtp.com",
  // ... cualquier campo de configuración
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* objeto facility actualizado */ },
  "message": "Instalación actualizada exitosamente"
}
```

### DELETE /config/facilities/:facility_id
Elimina una instalación.

**Response 200:**
```json
{
  "success": true,
  "message": "Instalación eliminada exitosamente"
}
```

---

## Modalidades

### GET /config/modalities
Obtiene todas las modalidades.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "CT - Tomografía Computarizada"
    }
  ]
}
```

### POST /config/modalities
Crea una nueva modalidad.

**Request Body:**
```json
{
  "description": "MRI - Resonancia Magnética"  // requerido
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { "guid": "uuid", "description": "MRI - Resonancia Magnética" },
  "message": "Modalidad creada exitosamente"
}
```

### PUT/PATCH /config/modalities/:modality_id
Actualiza una modalidad existente.

**Request Body:**
```json
{
  "description": "MRI - Resonancia Magnética Nuclear"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* modalidad actualizada */ },
  "message": "Modalidad actualizada exitosamente"
}
```

### DELETE /config/modalities/:modality_id
Elimina una modalidad.

**Response 200:**
```json
{
  "success": true,
  "message": "Modalidad eliminada exitosamente"
}
```

---

## Partes del Cuerpo

### GET /config/body-parts
Obtiene todas las partes anatómicas.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Cráneo"
    }
  ]
}
```

### POST /config/body-parts
Crea una nueva parte anatómica.

**Request Body:**
```json
{
  "description": "Tórax"  // requerido
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { "guid": "uuid", "description": "Tórax" },
  "message": "Parte anatómica creada exitosamente"
}
```

### PUT/PATCH /config/body-parts/:bodypart_id
Actualiza una parte anatómica.

**Request Body:**
```json
{
  "description": "Tórax completo"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* parte anatómica actualizada */ },
  "message": "Parte anatómica actualizada exitosamente"
}
```

### DELETE /config/body-parts/:bodypart_id
Elimina una parte anatómica.

**Response 200:**
```json
{
  "success": true,
  "message": "Parte anatómica eliminada exitosamente"
}
```

---

## Grupos de Estudio

### GET /config/study-groups
Obtiene todos los grupos de estudio.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Radiología General"
    }
  ]
}
```

### POST /config/study-groups
Crea un nuevo grupo de estudio.

**Request Body:**
```json
{
  "description": "Tomografía Avanzada"  // requerido
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { "guid": "uuid", "description": "Tomografía Avanzada" },
  "message": "Grupo de estudio creado exitosamente"
}
```

### PUT/PATCH /config/study-groups/:studygroup_id
Actualiza un grupo de estudio.

**Request Body:**
```json
{
  "description": "Tomografía Especializada"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* grupo actualizado */ },
  "message": "Grupo de estudio actualizado exitosamente"
}
```

### DELETE /config/study-groups/:studygroup_id
Elimina un grupo de estudio.

**Response 200:**
```json
{
  "success": true,
  "message": "Grupo de estudio eliminado exitosamente"
}
```

---

## Equipos

### GET /config/equipment
Obtiene todos los equipos.

**Query Parameters:**
- `location_id` (string, opcional): Filtrar por localización

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Tomógrafo Siemens",
      "modality_id": "uuid",
      "modality_name": "CT",
      "location_id": "uuid",
      "location_name": "Sala 1",
      "aetitle": "CT_SIEMENS_01",
      "ip": "192.168.1.100",
      "port": 104,
      "status": "active"
    }
  ]
}
```

### POST /config/equipment
Crea un nuevo equipo.

**Request Body:**
```json
{
  "description": "Resonador Philips",  // requerido
  "modality_id": "uuid",               // requerido
  "location_id": "uuid",               // opcional
  "aetitle": "MRI_PHILIPS_01",         // opcional
  "ip": "192.168.1.101",               // opcional
  "port": 104,                         // opcional
  "status": "active"                   // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* equipo creado */ },
  "message": "Equipo creado exitosamente"
}
```

### PUT/PATCH /config/equipment/:equipment_id
Actualiza un equipo existente.

**Request Body:** (todos los campos son opcionales)
```json
{
  "description": "Resonador Philips Actualizado",
  "status": "inactive"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* equipo actualizado */ },
  "message": "Equipo actualizado exitosamente"
}
```

### DELETE /config/equipment/:equipment_id
Elimina un equipo.

**Response 200:**
```json
{
  "success": true,
  "message": "Equipo eliminado exitosamente"
}
```

---

## Agendas de Equipos

### GET /config/equipment/:equipment_id/schedule
Obtiene la agenda de un equipo específico.

**Path Parameters:**
- `equipment_id` (string, requerido): UUID del equipo

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "day": 1,
      "time_from": "08:00",
      "time_to": "17:00"
    }
  ]
}
```

**Nota sobre el campo `day`:**
- `0` = Domingo
- `1` = Lunes
- `2` = Martes
- `3` = Miércoles
- `4` = Jueves
- `5` = Viernes
- `6` = Sábado

### POST /config/equipment/:equipment_id/schedule
Crea una nueva agenda para un equipo.

**Path Parameters:**
- `equipment_id` (string, requerido): UUID del equipo

**Request Body:**
```json
{
  "day": 1,              // requerido (0-6, donde 0=Domingo, 6=Sábado)
  "time_from": "08:00",  // requerido (formato HH:MM)
  "time_to": "17:00"     // requerido (formato HH:MM)
}
```

**Response 201:**
```json
{
  "success": true,
  "message": "Agenda creada exitosamente",
  "data": {
    "schedule_id": "uuid",
    "day": 1,
    "time_from": "08:00",
    "time_to": "17:00"
  }
}
```

**Errores comunes:**
- `400`: day debe ser un número entre 0 y 6
- `400`: day, time_from y time_to son requeridos
- `404`: Equipo no encontrado

### PUT/PATCH /config/equipment/:equipment_id/schedule/:schedule_id
Actualiza una agenda de equipo existente.

**Path Parameters:**
- `equipment_id` (string, requerido): UUID del equipo
- `schedule_id` (string, requerido): UUID de la agenda

**Request Body:** (todos los campos son opcionales)
```json
{
  "day": 2,
  "time_from": "09:00",
  "time_to": "18:00"
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Agenda actualizada exitosamente"
}
```

**Errores comunes:**
- `400`: day debe ser un número entre 0 y 6
- `400`: No hay campos para actualizar
- `404`: Agenda no encontrada

### DELETE /config/equipment/:equipment_id/schedule/:schedule_id
Elimina una agenda de equipo.

**Path Parameters:**
- `equipment_id` (string, requerido): UUID del equipo
- `schedule_id` (string, requerido): UUID de la agenda

**Response 200:**
```json
{
  "success": true,
  "message": "Agenda eliminada exitosamente"
}
```

**Errores comunes:**
- `404`: Agenda no encontrada

---

## Usuarios

### GET /config/users
Obtiene todos los usuarios del sistema.

**Query Parameters:**
- `include_inactive` (boolean, opcional): Incluir usuarios inactivos. Default: `false`

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "username": "jperez",
      "role": "Administrador",
      "role_id": "uuid",
      "name": "Juan",
      "surname": "Pérez",
      "national_number": "12345678",
      "email": "jperez@hospital.com",
      "phone": "+1234567890",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### POST /config/users
Crea un nuevo usuario.

**Request Body:**
```json
{
  "username": "jperez",            // requerido
  "password": "password123",       // requerido
  "role_id": "uuid",               // requerido
  "name": "Juan",                  // requerido
  "surname": "Pérez",              // requerido
  "national_number": "12345678",   // opcional
  "email": "jperez@hospital.com",  // opcional
  "phone": "+1234567890"           // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* usuario creado (sin password) */ },
  "message": "Usuario creado exitosamente"
}
```

### PUT/PATCH /config/users/:user_id
Actualiza un usuario existente.

**Request Body:** (todos los campos son opcionales)
```json
{
  "username": "jperez2",
  "role_id": "uuid",
  "name": "Juan Carlos",
  "email": "jperez2@hospital.com"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* usuario actualizado */ },
  "message": "Usuario actualizado exitosamente"
}
```

### DELETE /config/users/:user_id
Elimina un usuario.

**Response 200:**
```json
{
  "success": true,
  "message": "Usuario eliminado exitosamente"
}
```

### POST /config/users/:user_id/deactivate
Desactiva un usuario.

**Response 200:**
```json
{
  "success": true,
  "message": "Usuario desactivado exitosamente"
}
```

### POST /config/users/:user_id/activate
Activa un usuario.

**Response 200:**
```json
{
  "success": true,
  "message": "Usuario activado exitosamente"
}
```

### POST /config/users/:user_id/reset-password
Resetea la contraseña de un usuario.

**Request Body:**
```json
{
  "new_password": "newpassword123"  // requerido
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Contraseña reseteada exitosamente"
}
```

---

## Roles

### GET /config/roles
Obtiene todos los roles del sistema.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Administrador"
    }
  ]
}
```

---

## Pacientes

### GET /config/patients
Obtiene todos los pacientes.

**Query Parameters:**
- `include_inactive` (boolean, opcional): Incluir pacientes inactivos. Default: `false`

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "username": "agomez",
      "name": "Ana",
      "surname": "Gómez",
      "national_number": "87654321",
      "email": "agomez@email.com",
      "phone": "+0987654321",
      "birth_date": "1990-01-15",
      "gender": "F",
      "address": "Calle 456",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### GET /config/patients/:patient_id
Obtiene un paciente específico por ID.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "username": "agomez",
    "name": "Ana",
    "surname": "Gómez",
    // ... todos los campos del paciente
  }
}
```

### POST /config/patients
Crea un nuevo paciente.

**Request Body:**
```json
{
  "name": "Ana",                    // requerido
  "surname": "Gómez",               // requerido
  "national_number": "87654321",    // opcional
  "email": "agomez@email.com",      // opcional
  "phone": "+0987654321",           // opcional
  "birth_date": "1990-01-15",       // opcional
  "gender": "F",                    // opcional (M/F/O)
  "address": "Calle 456"            // opcional
}
```

**Nota:** El username se genera automáticamente (primera letra del nombre + apellido completo). La contraseña por defecto es "next".

**Response 201:**
```json
{
  "success": true,
  "data": { /* paciente creado */ },
  "message": "Paciente creado exitosamente"
}
```

### PUT/PATCH /config/patients/:patient_id
Actualiza un paciente existente.

**Request Body:** (todos los campos son opcionales)
```json
{
  "name": "Ana María",
  "email": "ana.gomez@email.com",
  "phone": "+0987654322"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* paciente actualizado */ },
  "message": "Paciente actualizado exitosamente"
}
```

### POST /config/patients/:patient_id/deactivate
Desactiva un paciente.

**Response 200:**
```json
{
  "success": true,
  "message": "Paciente desactivado exitosamente"
}
```

### POST /config/patients/:patient_id/activate
Activa un paciente.

**Response 200:**
```json
{
  "success": true,
  "message": "Paciente activado exitosamente"
}
```

### POST /config/patients/:patient_id/reset-password
Resetea la contraseña de un paciente.

**Request Body:**
```json
{
  "new_password": "newpassword123"  // requerido
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Contraseña reseteada exitosamente"
}
```

---

## Médicos Solicitantes

### GET /config/requesting-physicians
Obtiene todos los médicos solicitantes.

**Query Parameters:**
- `location_id` (string, opcional): Filtrar por localización

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "description": "Dr. Carlos Ramírez",
      "phone": "+1234567890",
      "mail": "cramirez@hospital.com",
      "note": "Cardiología",
      "location_id": "uuid",
      "location_name": "Consultorio 3"
    }
  ]
}
```

### GET /config/requesting-physicians/:physician_id
Obtiene un médico solicitante específico.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "description": "Dr. Carlos Ramírez",
    "phone": "+1234567890",
    "mail": "cramirez@hospital.com",
    "note": "Cardiología",
    "location_id": "uuid",
    "location_name": "Consultorio 3"
  }
}
```

### POST /config/requesting-physicians
Crea un nuevo médico solicitante.

**Request Body:**
```json
{
  "description": "Dr. Carlos Ramírez",  // requerido
  "phone": "+1234567890",               // opcional
  "mail": "cramirez@hospital.com",      // opcional
  "note": "Cardiología",                // opcional
  "location_id": "uuid"                 // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* médico creado */ },
  "message": "Médico solicitante creado exitosamente"
}
```

### PUT/PATCH /config/requesting-physicians/:physician_id
Actualiza un médico solicitante.

**Request Body:** (todos los campos son opcionales)
```json
{
  "description": "Dr. Carlos A. Ramírez",
  "phone": "+1234567891",
  "note": "Cardiología - Especialista"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* médico actualizado */ },
  "message": "Médico solicitante actualizado exitosamente"
}
```

### DELETE /config/requesting-physicians/:physician_id
Elimina un médico solicitante.

**Response 200:**
```json
{
  "success": true,
  "message": "Médico solicitante eliminado exitosamente"
}
```

---

## Agendas de Médicos

### GET /config/physician-schedules
Obtiene todas las agendas de médicos.

**Query Parameters:**
- `physician_id` (string, opcional): Filtrar por médico
- `location_id` (string, opcional): Filtrar por localización

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "physician_id": "uuid",
      "physician_name": "Dr. Juan Pérez",
      "day": "Lunes",
      "time_from": "08:00:00",
      "time_to": "12:00:00",
      "init_day": "2024-01-01",
      "finish_day": "2024-12-31",
      "location_id": "uuid",
      "location_name": "Consultorio 1"
    }
  ]
}
```

### POST /config/physician-schedules
Crea una nueva agenda para un médico.

**Request Body:**
```json
{
  "physician_id": "uuid",       // requerido
  "day": "Lunes",               // requerido (Lunes-Domingo)
  "time_from": "08:00",         // requerido
  "time_to": "12:00",           // requerido
  "init_day": "2024-01-01",     // opcional
  "finish_day": "2024-12-31",   // opcional
  "location_id": "uuid"         // opcional
}
```

**Response 201:**
```json
{
  "success": true,
  "data": { /* agenda creada */ },
  "message": "Agenda creada exitosamente"
}
```

### PUT/PATCH /config/physician-schedules/:schedule_id
Actualiza una agenda de médico.

**Request Body:** (todos los campos son opcionales)
```json
{
  "day": "Martes",
  "time_from": "09:00",
  "time_to": "13:00"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": { /* agenda actualizada */ },
  "message": "Agenda actualizada exitosamente"
}
```

### DELETE /config/physician-schedules/:schedule_id
Elimina una agenda de médico.

**Response 200:**
```json
{
  "success": true,
  "message": "Agenda eliminada exitosamente"
}
```

---

## Grupos de Estudio por Médico

### GET /config/physicians/:physician_id/study-groups
Obtiene los grupos de estudio que lee un médico específico.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid",
      "studygroup_id": "uuid",
      "studygroup_name": "Tomografía General"
    }
  ]
}
```

### POST /config/physicians/:physician_id/study-groups
Agrega un grupo de estudio a un médico.

**Request Body:**
```json
{
  "studygroup_id": "uuid"  // requerido
}
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "guid": "uuid",
    "studygroup_id": "uuid",
    "studygroup_name": "Tomografía General"
  },
  "message": "Grupo de estudio agregado exitosamente"
}
```

### DELETE /config/physicians/:physician_id/study-groups/:relation_id
Elimina un grupo de estudio de un médico.

**Response 200:**
```json
{
  "success": true,
  "message": "Grupo de estudio eliminado exitosamente"
}
```

---

## Códigos de Error Comunes

### 400 Bad Request
```json
{
  "success": false,
  "message": "Descripción del error de validación"
}
```

### 401 Unauthorized
```json
{
  "msg": "Missing Authorization Header"
}
```

### 404 Not Found
```json
{
  "success": false,
  "message": "Recurso no encontrado"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "message": "Error: Descripción del error del servidor"
}
```

---

## Notas Importantes

1. **Autenticación**: Todas las APIs requieren un token JWT válido en el header `Authorization`.

2. **Formato de Fechas**: Las fechas se manejan en formato ISO 8601 (`YYYY-MM-DD` o `YYYY-MM-DDTHH:mm:ss`).

3. **Formato de Horas**: Las horas se manejan en formato `HH:mm` o `HH:mm:ss`.

4. **UUIDs**: Todos los identificadores (`guid`, `*_id`) son UUIDs v4.

5. **Días de la Semana**: Los días válidos son: `Lunes`, `Martes`, `Miércoles`, `Jueves`, `Viernes`, `Sábado`, `Domingo`.

6. **Contraseñas**: Las contraseñas se almacenan hasheadas usando `werkzeug.security`.

7. **Generación Automática de Username**: 
   - Pacientes: Primera letra del nombre + apellido completo (ej: Ana Gómez → agomez)
   - Si ya existe, se agrega número incremental (agomez1, agomez2, etc.)

8. **Contraseña por Defecto**: 
   - Pacientes: "next"
   - Usuarios: Debe especificarse en la creación

9. **Validaciones**:
   - Los campos marcados como "requerido" deben estar presentes en el request
   - Los campos opcionales pueden omitirse o enviarse como `null`
   - Las foreign keys se validan antes de insertar/actualizar

10. **Transacciones**: Todas las operaciones de escritura usan transacciones con commit/rollback automático en caso de error.
