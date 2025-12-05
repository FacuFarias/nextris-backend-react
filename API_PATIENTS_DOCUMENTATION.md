# API de Pacientes - Documentación

## Descripción General

API REST completa para la gestión de pacientes en el sistema NextRIS. Incluye 20 endpoints con autenticación JWT para operaciones CRUD, búsquedas, historial médico, reasignación de estudios y gestión de ubicaciones.

**Base URL:** `/api/patients`

**Autenticación:** Todos los endpoints requieren un token JWT válido en el header:
```
Authorization: Bearer <access_token>
```

---

## Tabla de Contenidos

1. [Búsqueda y Listado](#búsqueda-y-listado)
2. [Detalle de Paciente](#detalle-de-paciente)
3. [Creación de Pacientes](#creación-de-pacientes)
4. [Actualización de Pacientes](#actualización-de-pacientes)
5. [Eliminación y Unificación](#eliminación-y-unificación)
6. [Historial y Estudios](#historial-y-estudios)
7. [Reasignación de Estudios](#reasignación-de-estudios)
8. [Ubicaciones](#ubicaciones)
9. [Códigos de Respuesta](#códigos-de-respuesta)
10. [Modelos de Datos](#modelos-de-datos)

---

## Búsqueda y Listado

### 1. Listar Pacientes (con paginación y conteo de estudios)

Obtiene una lista paginada de pacientes con conteo de estudios reportados.

**Endpoint:** `GET /api/patients`

**Query Parameters:**
- `page` (int, opcional): Número de página (default: 1)
- `per_page` (int, opcional): Resultados por página (default: 1000, max: 1000)
- `search` (string, opcional): Término de búsqueda (nombre, apellido, DNI, patientid)

**Ejemplo de Petición:**
```bash
GET /api/patients?page=1&per_page=20&search=juan
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "patients": [
      {
        "guid": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Juan",
        "surname": "Pérez",
        "nationalcode": "12345678",
        "gender": "M",
        "birthdate": "1985-05-15",
        "phone": "555-1234",
        "email": "juan.perez@email.com",
        "patientid": "PAT001",
        "study_count": 5
      }
    ],
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

---

### 2. Listar Pacientes (versión mínima)

Obtiene información mínima de pacientes para autocompletes y selección rápida.

**Endpoint:** `GET /api/patients/minimal`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Juan",
      "surname": "Pérez",
      "gender": "M",
      "birthdate": "15/05/1985",
      "nationalcode": "12345678"
    }
  ]
}
```

---

### 3. Búsqueda Simple de Pacientes

Busca pacientes con un término de búsqueda general.

**Endpoint:** `POST /api/patients/search`

**Body:**
```json
{
  "search_term": "juan"
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "patientid": "PAT001",
      "surname": "Pérez",
      "name": "Juan",
      "nationalcode": "12345678",
      "gender": "M",
      "birthdate": "1985-05-15"
    }
  ]
}
```

---

### 4. Búsqueda Avanzada de Pacientes

Búsqueda con múltiples criterios específicos.

**Endpoint:** `POST /api/patients/search/advanced`

**Body:**
```json
{
  "criteria": {
    "name": "juan",
    "surname": "pérez",
    "national_code": "12345678",
    "patient_id": "PAT001"
  }
}
```

**Respuesta:** Similar a búsqueda simple.

---

### 5. Pacientes por Ubicación

Obtiene pacientes filtrados por una ubicación específica.

**Endpoint:** `POST /api/patients/by-location`

**Body:**
```json
{
  "location_id": "location-guid-here"
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Juan",
      "surname": "Pérez",
      "gender": "M",
      "birthdate": "15/05/1985",
      "nationalcode": "12345678"
    }
  ]
}
```

---

## Detalle de Paciente

### 6. Obtener Detalles Completos de Paciente

**Endpoint:** `GET /api/patients/<guid>`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "guid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Juan",
    "surname": "Pérez",
    "email": "juan.perez@email.com",
    "phone": "555-1234",
    "nationalcode": "12345678",
    "birthdate": "1985-05-15",
    "gender": "M",
    "patientid": "PAT001",
    "healthcard": "HC123456",
    "trial190": null,
    "id_patientdomain": 1,
    "ismerged": false,
    "isanonymous": false
  }
}
```

**Errores:**
- `404`: Paciente no encontrado o sin acceso
- `403`: Usuario sin acceso a dominios de pacientes

---

## Creación de Pacientes

### 7. Crear Paciente Completo

Crea un nuevo paciente con todos los datos y opcionalmente su usuario de acceso.

**Endpoint:** `POST /api/patients`

**Body:**
```json
{
  "name": "Juan",
  "surname": "Pérez",
  "patientid": "PAT001",
  "nationalcode": "12345678",
  "email": "juan.perez@email.com",
  "phone": "555-1234",
  "birthdate": "1985-05-15",
  "gender": "M",
  "healthcard": "HC123456",
  "create_user": true
}
```

**Campos Obligatorios:**
- `name`
- `surname`
- `patientid`

**Campos Opcionales:**
- `nationalcode`
- `email`
- `phone`
- `birthdate` (formato: YYYY-MM-DD)
- `gender` (M/F/O, default: O)
- `healthcard`
- `trial190`
- `create_user` (boolean, crea usuario paciente si es true)

**Respuesta Exitosa (201):**
```json
{
  "success": true,
  "data": {
    "guid": "550e8400-e29b-41d4-a716-446655440000"
  },
  "message": "Paciente creado exitosamente"
}
```

---

### 8. Crear Paciente Rápido

Creación rápida de paciente con datos mínimos.

**Endpoint:** `POST /api/patients/quick`

**Body:**
```json
{
  "nombre": "Juan",
  "apellido": "Pérez",
  "dni": "12345678",
  "fecha_nac": "1985-05-15",
  "sexo": "M"
}
```

**Respuesta Exitosa (201):**
```json
{
  "success": true,
  "message": "Paciente agregado correctamente",
  "guid": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Actualización de Pacientes

### 9. Actualizar Paciente

Actualiza uno o múltiples campos de un paciente.

**Endpoint:** `PUT /api/patients/<guid>`

**Body (enviar solo los campos a actualizar):**
```json
{
  "email": "nuevo.email@email.com",
  "phone": "555-9999",
  "healthcard": "HC999999"
}
```

**Campos Actualizables:**
- `name`
- `surname`
- `patientid`
- `nationalcode`
- `email`
- `phone`
- `birthdate`
- `gender` (mapea a sexcode)
- `healthcard`
- `trial190`
- `isanonymous`
- `ismerged`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Paciente actualizado exitosamente"
}
```

---

### 10. Actualizar Solo Email

Actualiza únicamente el email del paciente.

**Endpoint:** `PATCH /api/patients/<guid>/email`

**Body:**
```json
{
  "email": "nuevo.email@email.com"
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Email actualizado exitosamente"
}
```

---

## Eliminación y Unificación

### 11. Eliminar Paciente

Elimina un paciente. Solo permitido si no tiene estudios asociados.

**Endpoint:** `DELETE /api/patients/<guid>`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Paciente eliminado correctamente"
}
```

**Errores:**
- `404`: Paciente no encontrado
- `400`: No se puede eliminar porque tiene estudios asociados

---

### 12. Unificar Pacientes

Fusiona dos pacientes duplicados, moviendo todos los estudios al paciente maestro.

**Endpoint:** `POST /api/patients/merge`

**Body:**
```json
{
  "master_guid": "guid-del-paciente-correcto",
  "duplicate_guid": "guid-del-paciente-duplicado"
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Pacientes unificados correctamente"
}
```

---

## Historial y Estudios

### 13. Historial Completo de Estudios

Obtiene el historial completo de estudios reportados de un paciente.

**Endpoint:** `GET /api/patients/<guid>/history`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "study-guid",
      "estudio": "Radiografía de Tórax",
      "medico_autor": "Dr. García",
      "medico_referente": "Dr. López",
      "fecha": "05/12/2025 14:30",
      "modalidad": "RX",
      "con_imagen": "Sí",
      "isreported": 1
    }
  ]
}
```

---

### 14. Historial para Reportes

Obtiene un resumen del historial (últimos 10 estudios) para incluir en reportes médicos.

**Endpoint:** `GET /api/patients/<guid>/history/report`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "study-guid",
      "estudio": "Radiografía de Tórax",
      "fecha": "05/12/2025"
    }
  ]
}
```

---

### 15. Cantidad de Estudios

Obtiene el número total de estudios de un paciente.

**Endpoint:** `GET /api/patients/<guid>/studies/count`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "cantidad": 25
  }
}
```

---

## Reasignación de Estudios

### 16. Listar Estudios para Reasignar

Obtiene lista de estudios disponibles para reasignación.

**Endpoint:** `GET /api/studies/reassign/list`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "study-guid",
      "createdon": "2025-12-05T14:30:00",
      "localacc": "ACC001",
      "patientid": "PAT001",
      "patient_name": "Pérez Juan",
      "birthdate": "1985-05-15",
      "study_description": "Radiografía de Tórax",
      "status": "Completed"
    }
  ]
}
```

---

### 17. Reasignar Estudio a Otro Paciente

Cambia la asignación de un estudio a otro paciente.

**Endpoint:** `POST /api/studies/reassign`

**Body:**
```json
{
  "estudio_id": "guid-del-estudio",
  "paciente_id": "guid-del-nuevo-paciente"
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "message": "Estudio reasignado correctamente al paciente PAT002"
}
```

---

### 18. Obtener Enlace de Imágenes de Estudio

Obtiene el UID del estudio para visualización de imágenes DICOM.

**Endpoint:** `GET /api/studies/<exam_id>/image-link`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "study_uid": "1.2.840.113619.2.55.3.2609..",
    "has_images": 1
  }
}
```

---

### 19. Listar Pacientes para Reasignación

Obtiene lista de pacientes disponibles para reasignar estudios.

**Endpoint:** `GET /api/patients/reassign/list`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Juan",
      "surname": "Pérez",
      "nationalcode": "12345678",
      "gender": "M",
      "birthdate": "1985-05-15",
      "phone": "555-1234",
      "email": "juan.perez@email.com",
      "healthcard": "HC123456"
    }
  ]
}
```

---

## Ubicaciones

### 20. Obtener Ubicaciones del Usuario

Lista las ubicaciones a las que el usuario tiene acceso.

**Endpoint:** `GET /api/user/locations`

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "location-guid",
      "name": "Consultorios Centrales",
      "code": "CC001",
      "facility_id": "facility-guid",
      "is_default": true
    }
  ]
}
```

---

## Códigos de Respuesta

### Códigos HTTP Estándar

| Código | Descripción |
|--------|-------------|
| 200 | Operación exitosa |
| 201 | Recurso creado exitosamente |
| 400 | Petición inválida (datos faltantes o incorrectos) |
| 401 | No autenticado (token inválido o expirado) |
| 403 | Sin permisos (acceso denegado) |
| 404 | Recurso no encontrado |
| 500 | Error interno del servidor |

### Formato de Respuesta de Error

```json
{
  "success": false,
  "message": "Descripción del error"
}
```

---

## Modelos de Datos

### Paciente Completo

```typescript
interface Patient {
  guid: string;              // UUID único
  name: string;              // Nombre
  surname: string;           // Apellido
  email?: string;            // Email (opcional)
  phone?: string;            // Teléfono (opcional)
  nationalcode?: string;     // DNI/Cédula (opcional)
  birthdate?: string;        // Fecha de nacimiento ISO (YYYY-MM-DD)
  gender: string;            // M/F/O
  patientid: string;         // ID del paciente en el sistema
  healthcard?: string;       // Número de obra social (opcional)
  trial190?: string;         // Campo específico (opcional)
  id_patientdomain: number;  // ID del dominio del paciente
  ismerged: boolean;         // Si fue fusionado
  isanonymous: boolean;      // Si es anónimo
  study_count?: number;      // Cantidad de estudios (solo en listado)
}
```

### Paciente Mínimo

```typescript
interface PatientMinimal {
  guid: string;
  name: string;
  surname: string;
  gender: string;
  birthdate: string;         // Formato DD/MM/YYYY
  nationalcode?: string;
}
```

### Estudio en Historial

```typescript
interface StudyHistory {
  guid: string;
  estudio: string;           // Descripción del estudio
  medico_autor?: string;     // Médico que reportó
  medico_referente?: string; // Médico que solicitó
  fecha: string;             // Formato DD/MM/YYYY HH:MM
  modalidad: string;         // RX, CT, MR, etc.
  con_imagen: string;        // "Sí" o "No"
  isreported: number;        // 0 o 1
}
```

### Ubicación

```typescript
interface Location {
  guid: string;
  name: string;
  code: string;
  facility_id: string;
  is_default: boolean;
}
```

---

## Notas de Implementación

### Autenticación

Todos los endpoints requieren autenticación JWT. El token se obtiene del endpoint `/api/auth/login` y debe incluirse en cada petición:

```bash
Authorization: Bearer <access_token>
```

### Control de Acceso

- Los usuarios solo pueden ver pacientes de los dominios a los que tienen acceso asignado
- La relación usuario-dominio se gestiona en la tabla `rel_user_patientdomain`
- Los estudios se filtran por ubicaciones del usuario

### Tipos de Datos en PostgreSQL

- **Fechas**: Se manejan en formato ISO (YYYY-MM-DD)
- **Booleanos**: Los campos `isanonymous` e `ismerged` son tipo `bit` (0/1) en BD
- **Campos reportados**: `isreported` es `smallint` (0/1)

### Creación Automática de Usuarios

Cuando se crea un paciente con `create_user: true`:
- Se genera un username automático: primera letra del nombre + apellido
- Si el username existe, se agrega un número secuencial (01, 02, etc.)
- La contraseña por defecto es 'next'
- El usuario queda activo pero requiere cambio de contraseña en primer login

### Búsquedas

Las búsquedas son **case-insensitive** y utilizan `ILIKE` de PostgreSQL:
- Buscan en: nombre, apellido, DNI, patientid
- Soportan búsqueda parcial (substring matching)
- Los resultados están ordenados por apellido y nombre

---

## Ejemplos de Uso

### JavaScript/TypeScript (Fetch)

```javascript
// Login
const loginResponse = await fetch('http://api.nextris.com/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'password',
    user_type: 'staff'
  })
});
const { data } = await loginResponse.json();
const token = data.access_token;

// Listar pacientes
const patientsResponse = await fetch('http://api.nextris.com/api/patients?page=1&per_page=20', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
const patients = await patientsResponse.json();
```

### Python (Requests)

```python
import requests

# Login
login_response = requests.post(
    'http://api.nextris.com/api/auth/login',
    json={
        'username': 'admin',
        'password': 'password',
        'user_type': 'staff'
    }
)
token = login_response.json()['data']['access_token']

# Crear paciente
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
create_response = requests.post(
    'http://api.nextris.com/api/patients',
    headers=headers,
    json={
        'name': 'Juan',
        'surname': 'Pérez',
        'patientid': 'PAT001',
        'nationalcode': '12345678',
        'email': 'juan@email.com',
        'gender': 'M'
    }
)
```

### cURL

```bash
# Login
TOKEN=$(curl -X POST http://api.nextris.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password","user_type":"staff"}' \
  | jq -r '.data.access_token')

# Listar pacientes
curl -X GET "http://api.nextris.com/api/patients?page=1&per_page=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

---

## Testing

Se incluye un script de testing completo en `test_patients_api.py` que verifica todos los endpoints.

**Ejecutar tests:**
```bash
python3 test_patients_api.py --all
```

**Resultado esperado:**
```
Total de tests: 18
Tests exitosos: 18
Tests fallidos: 0
Porcentaje de éxito: 100.00%
```

---

## Changelog

### Versión 1.0.0 (Diciembre 2025)
- Migración completa de 20 endpoints desde controladores tradicionales a API REST
- Implementación de autenticación JWT
- Control de acceso por dominios de pacientes
- Testing completo al 100%
- Documentación completa

---

## Soporte

Para reportar issues o solicitar nuevas funcionalidades, por favor crear un issue en el repositorio de GitHub.

**Repositorio:** https://github.com/FacuFarias/nextris-front-react

---

**Última actualización:** Diciembre 5, 2025  
**Versión:** 1.0.0  
**Autor:** NextRIS Development Team
