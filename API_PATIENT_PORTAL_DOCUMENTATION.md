# API del Portal de Pacientes - Documentación Completa

Esta documentación describe las APIs del portal de pacientes del sistema NEXTRIS disponibles en `/apps/api/patient_portal.py`.

**Base URL**: `/api/patient-portal`

**Autenticación**: Todas las APIs requieren autenticación JWT del paciente mediante el header `Authorization: Bearer <patient_token>`

**IMPORTANTE**: Estas APIs son específicas para pacientes autenticados. El token JWT debe corresponder a un usuario de tipo paciente (`tbuser_patient`), no a un usuario del sistema.

---

## Tabla de Contenidos

1. [Obtener Mi Perfil](#obtener-mi-perfil)
2. [Actualizar Mi Perfil](#actualizar-mi-perfil)
3. [Cambiar Contraseña](#cambiar-contraseña)
4. [Obtener Mis Estudios](#obtener-mis-estudios)

---

## Obtener Mi Perfil

### GET /patient-portal/my-profile

Obtiene los datos completos del perfil del paciente autenticado.

**Autenticación**: JWT del paciente (token obtenido al iniciar sesión como paciente)

**Ejemplo Request:**
```bash
GET /api/patient-portal/my-profile
Authorization: Bearer <patient_jwt_token>
```

**Response 200 - Success:**
```json
{
  "success": true,
  "data": {
    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "jperez",
    "account_status": "Active",
    "last_login": "2026-01-10T15:30:00",
    "name": "Juan",
    "surname": "Pérez",
    "full_name": "Pérez, Juan",
    "national_code": "12345678",
    "patient_id_number": "20-12345678-9",
    "birthdate": "1990-01-15",
    "age": 36,
    "sex_code": "M",
    "sex": "Masculino",
    "phone": "+5491112345678",
    "email": "juan.perez@email.com",
    "address": "Calle Falsa 123",
    "city": "Buenos Aires",
    "state": "CABA",
    "zip_code": "1000",
    "health_card": "123456789"
  }
}
```

**Campos de Respuesta:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `patient_id` | string (UUID) | Identificador único del paciente en tbuser_patient |
| `username` | string | Nombre de usuario para login |
| `account_status` | string | Estado de la cuenta: "Active" / "Inactive" |
| `last_login` | string (ISO 8601) | Última vez que el paciente inició sesión |
| `name` | string | Nombre del paciente |
| `surname` | string | Apellido del paciente |
| `full_name` | string | Nombre completo formato "Apellido, Nombre" |
| `national_code` | string | Documento nacional (DNI) |
| `patient_id_number` | string | CUIL del paciente |
| `birthdate` | string (YYYY-MM-DD) | Fecha de nacimiento |
| `age` | integer | Edad calculada en años |
| `sex_code` | string | Código de sexo: "M" / "F" / "O" |
| `sex` | string | Sexo en texto: "Masculino" / "Femenino" / "Otro" |
| `phone` | string | Teléfono de contacto |
| `email` | string | Email de contacto |
| `address` | string | Dirección |
| `city` | string | Ciudad |
| `state` | string | Provincia/Estado |
| `zip_code` | string | Código postal |
| `health_card` | string | Número de carnet de obra social |

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Paciente no encontrado"
}
```

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Error: descripción del error"
}
```

**Notas:**
- La edad se calcula automáticamente basada en la fecha de nacimiento
- Todos los datos provienen de las tablas `tbuser_patient` y `datapatient`
- El paciente solo puede ver su propia información

---

## Actualizar Mi Perfil

### PUT/PATCH /patient-portal/my-profile

Permite al paciente actualizar sus datos de contacto y dirección.

**Autenticación**: JWT del paciente

**Request Body (JSON):**
```json
{
  "phone": "+5491112345678",
  "email": "nuevo.email@example.com",
  "address": "Nueva Dirección 456",
  "city": "Buenos Aires",
  "state": "CABA",
  "zip_code": "1000"
}
```

**Campos Permitidos:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `phone` | string | No | Teléfono de contacto |
| `email` | string | No | Email de contacto |
| `address` | string | No | Dirección |
| `city` | string | No | Ciudad |
| `state` | string | No | Provincia/Estado |
| `zip_code` | string | No | Código postal |

**Ejemplo Request:**
```bash
PUT /api/patient-portal/my-profile
Authorization: Bearer <patient_jwt_token>
Content-Type: application/json

{
  "phone": "+5491198765432",
  "email": "juan.nuevo@email.com",
  "address": "Av. Corrientes 1234"
}
```

**Response 200 - Success:**
Retorna el perfil completo actualizado (mismo formato que GET /my-profile)
```json
{
  "success": true,
  "data": {
    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "jperez",
    "name": "Juan",
    "surname": "Pérez",
    "phone": "+5491198765432",
    "email": "juan.nuevo@email.com",
    "address": "Av. Corrientes 1234",
    ...
  }
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "No hay campos válidos para actualizar"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Paciente no encontrado"
}
```

**RESTRICCIONES DE SEGURIDAD:**

Por razones de seguridad, los siguientes campos **NO** pueden ser modificados por el paciente desde el portal:
- `name` (Nombre)
- `surname` (Apellido)
- `national_code` (DNI)
- `patient_id_number` (CUIL)
- `birthdate` (Fecha de nacimiento)
- `sex_code` (Sexo)
- `health_card` (Carnet obra social)

Estos campos solo pueden ser actualizados por personal administrativo a través de las APIs de configuración (`/config/patients`).

**Notas:**
- Todos los campos en el body son opcionales
- Solo se actualizan los campos enviados en el request
- Después de actualizar, retorna automáticamente el perfil completo

---

## Cambiar Contraseña

### POST /patient-portal/change-password

Permite al paciente cambiar su propia contraseña de forma segura.

**Autenticación**: JWT del paciente

**Request Body (JSON):**
```json
{
  "current_password": "contraseña_actual",
  "new_password": "nueva_contraseña",
  "confirm_password": "nueva_contraseña"
}
```

**Campos Requeridos:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `current_password` | string | Contraseña actual del paciente (para verificación) |
| `new_password` | string | Nueva contraseña deseada (mínimo 4 caracteres) |
| `confirm_password` | string | Confirmación de la nueva contraseña (debe coincidir) |

**Ejemplo Request:**
```bash
POST /api/patient-portal/change-password
Authorization: Bearer <patient_jwt_token>
Content-Type: application/json

{
  "current_password": "miPasswordActual123",
  "new_password": "miNuevaPassword456",
  "confirm_password": "miNuevaPassword456"
}
```

**Response 200 - Success:**
```json
{
  "success": true,
  "message": "Contraseña actualizada exitosamente"
}
```

**Response 400 - Bad Request:**
```json
{
  "success": false,
  "message": "Se requieren current_password, new_password y confirm_password"
}
```
o
```json
{
  "success": false,
  "message": "La nueva contraseña y su confirmación no coinciden"
}
```
o
```json
{
  "success": false,
  "message": "La nueva contraseña debe tener al menos 4 caracteres"
}
```

**Response 401 - Unauthorized:**
```json
{
  "success": false,
  "message": "La contraseña actual es incorrecta"
}
```

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Paciente no encontrado"
}
```

**Validaciones:**
1. Los tres campos son obligatorios
2. La contraseña actual debe ser correcta
3. La nueva contraseña y su confirmación deben coincidir
4. La nueva contraseña debe tener al menos 4 caracteres

**Seguridad:**
- Las contraseñas se almacenan hasheadas usando `werkzeug.security`
- Se verifica la contraseña actual antes de permitir el cambio
- No se retorna información sensible en las respuestas

---

## Obtener Mis Estudios

### GET /patient-portal/my-studies

Obtiene el listado de estudios médicos realizados al paciente autenticado.

**Autenticación**: JWT del paciente

**Query Parameters:**

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `page` | integer | No | 1 | Número de página |
| `per_page` | integer | No | 20 | Items por página (máximo: 100) |
| `status` | string | No | - | Filtrar por estado: "reported" (con informe) o "pending" (sin informe) |

**Ejemplo Request - Todos los estudios:**
```bash
GET /api/patient-portal/my-studies?page=1&per_page=20
Authorization: Bearer <patient_jwt_token>
```

**Ejemplo Request - Solo estudios reportados:**
```bash
GET /api/patient-portal/my-studies?status=reported&page=1&per_page=10
Authorization: Bearer <patient_jwt_token>
```

**Response 200 - Success:**
```json
{
  "success": true,
  "data": [
    {
      "examination_id": "123e4567-e89b-12d3-a456-426614174000",
      "order_id": "234e5678-e89b-12d3-a456-426614174001",
      "accession_number": "ACC001234",
      "study_type": "TOMOGRAFIA DE TORAX",
      "modality": "CT",
      "study_date": "2026-01-10",
      "study_time": "14:30:00",
      "status": "Reportado",
      "has_report": true,
      "has_images": true,
      "referring_physician": "Dr. García",
      "location": "Sede Central",
      "urgency": "Normal",
      "report_date": "2026-01-10T16:00:00"
    },
    {
      "examination_id": "345e6789-e89b-12d3-a456-426614174002",
      "order_id": "456e7890-e89b-12d3-a456-426614174003",
      "accession_number": "ACC001235",
      "study_type": "RADIOGRAFIA DE TORAX",
      "modality": "RX",
      "study_date": "2026-01-08",
      "study_time": "10:15:00",
      "status": "Pendiente",
      "has_report": false,
      "has_images": true,
      "referring_physician": "Dra. Martínez",
      "location": "Sucursal Norte",
      "urgency": "Urgente",
      "report_date": null
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20
}
```

**Campos de Respuesta:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `examination_id` | string (UUID) | ID del examen |
| `order_id` | string (UUID) | ID de la orden médica |
| `accession_number` | string | Número de acceso del estudio |
| `study_type` | string | Tipo de estudio (ej: "TOMOGRAFIA DE TORAX") |
| `modality` | string | Modalidad del estudio (ej: "CT", "RX", "MR") |
| `study_date` | string (YYYY-MM-DD) | Fecha en que se realizó el estudio |
| `study_time` | string (HH:MM:SS) | Hora en que se realizó el estudio |
| `status` | string | Estado: "Reportado" o "Pendiente" |
| `has_report` | boolean | `true` si el estudio tiene informe médico |
| `has_images` | boolean | `true` si el estudio tiene imágenes DICOM |
| `referring_physician` | string | Médico que solicitó el estudio |
| `location` | string | Ubicación donde se realizó el estudio |
| `urgency` | string | "Urgente" o "Normal" |
| `report_date` | string (ISO 8601) | Fecha/hora de creación del informe (null si no hay) |

**Response 404 - Not Found:**
```json
{
  "success": false,
  "message": "Paciente no encontrado"
}
```

**Response 500 - Error:**
```json
{
  "success": false,
  "message": "Error: descripción del error"
}
```

**Filtros Disponibles:**

1. **Sin filtro**: Retorna todos los estudios (reportados y pendientes)
2. **`status=reported`**: Solo estudios con informe médico (`isreported = 1`)
3. **`status=pending`**: Solo estudios sin informe (`isreported = 0`)

**Ordenamiento:**
Los estudios se ordenan por fecha/hora del estudio en orden descendente (más recientes primero).

**Paginación:**
- Default: 20 estudios por página
- Máximo: 100 estudios por página
- Incluye total de resultados para implementar paginación en frontend

**Notas:**
- El paciente solo ve sus propios estudios
- Incluye estudios de todas las ubicaciones del sistema
- `has_images` verifica si existen imágenes DICOM asociadas

---

## Flujo de Trabajo Típico del Portal de Pacientes

### 1. Login del Paciente
```bash
POST /api/auth/patient-login
{
  "username": "jperez",
  "password": "miPassword"
}
# Retorna JWT token
```

### 2. Ver Perfil
```bash
GET /api/patient-portal/my-profile
Authorization: Bearer <token>
```

### 3. Actualizar Datos de Contacto
```bash
PUT /api/patient-portal/my-profile
Authorization: Bearer <token>
{
  "phone": "+5491112345678",
  "email": "nuevo@email.com"
}
```

### 4. Cambiar Contraseña (primer login o por seguridad)
```bash
POST /api/patient-portal/change-password
Authorization: Bearer <token>
{
  "current_password": "passwordActual",
  "new_password": "nuevoPassword",
  "confirm_password": "nuevoPassword"
}
```

### 5. Ver Estudios Médicos
```bash
# Ver todos los estudios
GET /api/patient-portal/my-studies?page=1&per_page=20
Authorization: Bearer <token>

# Ver solo estudios con informe
GET /api/patient-portal/my-studies?status=reported
Authorization: Bearer <token>
```

---

## Códigos de Error Comunes

| Código | Descripción | Causa Común |
|--------|-------------|-------------|
| 400 | Bad Request | Falta campos requeridos o datos inválidos |
| 401 | Unauthorized | Token JWT inválido o contraseña incorrecta |
| 404 | Not Found | Paciente no encontrado en la base de datos |
| 500 | Internal Server Error | Error de base de datos o del servidor |

---

## Consideraciones de Seguridad

### Autenticación
- **Token JWT específico de paciente**: El token debe provenir de `tbuser_patient`, no de `tbuser`
- **Validación de identidad**: Cada endpoint verifica que el token corresponda al paciente autenticado
- **Sin acceso cruzado**: Un paciente solo puede ver/modificar su propia información

### Protección de Datos Sensibles
- **Datos no modificables**: Nombre, DNI, fecha de nacimiento, sexo protegidos contra modificación
- **Contraseñas hasheadas**: Uso de `werkzeug.security` para hash bcrypt
- **Verificación de contraseña actual**: Requerida antes de cambiar contraseña

### Privacidad
- **Aislamiento de datos**: Cada paciente solo accede a sus propios estudios y perfil
- **Filtrado automático**: Las queries incluyen filtros por `patient_id` automáticamente
- **Sin exposición de IDs de otros pacientes**: Las respuestas no contienen información de terceros

---

## Tablas de Base de Datos Utilizadas

| Tabla | Propósito |
|-------|-----------|
| `nextris.tbuser_patient` | Usuarios pacientes (login, estado, relación con datapatient) |
| `nextris.datapatient` | Datos personales del paciente |
| `nextris.tborder` | Órdenes médicas |
| `nextris.tbexamination` | Exámenes/estudios realizados |
| `nextris.isstudytype` | Tipos de estudio |
| `nextris.ismodality` | Modalidades de imagen |
| `nextris.isrequestingphysician` | Médicos solicitantes |
| `nextris.tblocation` | Ubicaciones/sedes |
| `nextris.tbreport` | Informes médicos |
| `nextris.tbimage` | Imágenes DICOM |

---

## Registro de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-01-10 | 1.0 | Creación inicial de las APIs del portal de pacientes |
| 2026-01-10 | 1.0 | Implementación de endpoints: my-profile (GET/PUT), change-password, my-studies |
| 2026-01-10 | 1.0 | Seguridad: Restricción de campos modificables, validación de contraseñas |

---

## Próximas Funcionalidades (Roadmap)

- **Ver Informe PDF**: Endpoint para descargar/visualizar informes médicos
- **Ver Imágenes DICOM**: Integración con visor DICOM para pacientes
- **Historial de Cambios**: Log de modificaciones al perfil
- **Notificaciones**: Alertas cuando un estudio tiene informe disponible
- **Descargar Estudios**: Exportar informes e imágenes
- **Solicitar Turnos**: Integración con sistema de agendamiento

---

## Soporte

Para preguntas o issues relacionados con las APIs del portal de pacientes, contactar al equipo de desarrollo de NextRIS.
