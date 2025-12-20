# 📍 API de Ubicaciones y Zonas Horarias

## Descripción

Se han agregado dos columnas nuevas a la tabla `nextris.tblocation`:
- **`geographic_location`**: Ubicación geográfica (puede contener coordenadas lat,lng o descripción)
- **`timezone`**: Zona horaria de la ubicación (ej: `America/Argentina/Buenos_Aires`)

Estas columnas permiten determinar automáticamente la zona horaria GMT/UTC de cada ubicación para gestionar correctamente los horarios de las citas y estudios DICOM.

---

## Endpoints API

### 1️⃣ Obtener todas las ubicaciones con sus zonas horarias

```http
GET /api/v1/locations
Authorization: Bearer <token>
```

**Query Parameters (opcional):**
- `facility_id`: Filtrar por facility específica
- `timezone`: Filtrar por zona horaria

**Respuesta:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "uuid-1",
      "facility_id": "uuid-facility",
      "name": "Ubicación A",
      "code": "LOC-001",
      "address": "Calle 123",
      "phone": "123456789",
      "status": "Active",
      "geographic_location": "-34.6037, -58.3816",
      "timezone": "America/Argentina/Buenos_Aires",
      "created_at": "2025-01-01T10:00:00",
      "updated_at": "2025-01-01T10:00:00"
    }
  ],
  "total": 1
}
```

---

### 2️⃣ Obtener una ubicación específica

```http
GET /api/v1/locations/<guid>
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "guid": "uuid-1",
    "facility_id": "uuid-facility",
    "name": "Ubicación A",
    "code": "LOC-001",
    "address": "Calle 123",
    "phone": "123456789",
    "status": "Active",
    "geographic_location": "-34.6037, -58.3816",
    "timezone": "America/Argentina/Buenos_Aires",
    "created_at": "2025-01-01T10:00:00",
    "updated_at": "2025-01-01T10:00:00"
  }
}
```

---

### 3️⃣ Crear una nueva ubicación

```http
POST /api/v1/locations
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "facility_id": "uuid-facility",
  "name": "Ubicación Nueva",
  "code": "LOC-002",
  "address": "Calle 456",
  "phone": "987654321",
  "geographic_location": "-34.6037, -58.3816",
  "timezone": "America/Argentina/Buenos_Aires",
  "status": "Active"
}
```

**Campos requeridos:**
- `facility_id`
- `name`
- `code`

**Campos opcionales:**
- `address`
- `phone`
- `geographic_location` (puede ser coordenadas lat,lng o descripción textual)
- `timezone` (debe ser una zona horaria válida de pytz)
- `status` (default: "Active")

**Respuesta:**
```json
{
  "success": true,
  "message": "Ubicación creada exitosamente",
  "data": {
    "guid": "uuid-nuevo",
    "created_at": "2025-01-01T10:00:00"
  }
}
```

---

### 4️⃣ Actualizar una ubicación

```http
PUT /api/v1/locations/<guid>
Authorization: Bearer <token>
Content-Type: application/json
```

**Body (actualizar parcialmente):**
```json
{
  "geographic_location": "-34.5950, -58.4000",
  "timezone": "America/Argentina/Mendoza",
  "status": "Inactive"
}
```

**Respuesta:**
```json
{
  "success": true,
  "message": "Ubicación actualizada exitosamente"
}
```

---

### 5️⃣ Eliminar una ubicación

```http
DELETE /api/v1/locations/<guid>
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "success": true,
  "message": "Ubicación eliminada exitosamente"
}
```

---

### 6️⃣ Obtener hora actual en una ubicación

```http
POST /api/v1/locations/timezone/current
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "location_guid": "uuid-ubicacion"
}
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "timezone": "America/Argentina/Buenos_Aires",
    "current_time": "2025-01-01T10:30:45.123456-03:00",
    "utc_offset": "-0300"
  }
}
```

---

### 7️⃣ Listar todas las zonas horarias disponibles

```http
GET /api/v1/locations/timezones/list
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "Africa": [
      "Africa/Abidjan",
      "Africa/Accra",
      ...
    ],
    "America": [
      "America/Anchorage",
      "America/Argentina/Buenos_Aires",
      "America/Argentina/Mendoza",
      "America/Chicago",
      ...
    ],
    "Europe": [
      "Europe/London",
      "Europe/Paris",
      ...
    ],
    ...
  },
  "total": 425
}
```

---

## 📊 Estructura de la tabla actualizada

```sql
-- nextris.tblocation
CREATE TABLE nextris.tblocation (
    guid character varying NOT NULL DEFAULT uuid_generate_v4(),
    facility_id character varying NOT NULL,
    name character varying NOT NULL,
    code character varying NOT NULL,
    address character varying,
    phone character varying,
    status character varying DEFAULT 'Active'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    id_patientdomain character varying,
    mail text,
    logo_path text,
    geographic_location character varying,         -- NUEVA
    timezone character varying,                     -- NUEVA
    PRIMARY KEY (guid)
);
```

---

## 🌍 Zonas Horarias Comunes

**Argentina:**
- `America/Argentina/Buenos_Aires` (UTC-3)
- `America/Argentina/Mendoza` (UTC-3)
- `America/Argentina/Rio_Gallegos` (UTC-3)

**Estados Unidos:**
- `America/New_York` (EST/EDT)
- `America/Chicago` (CST/CDT)
- `America/Denver` (MST/MDT)
- `America/Los_Angeles` (PST/PDT)

**Europa:**
- `Europe/London` (GMT/BST)
- `Europe/Paris` (CET/CEST)
- `Europe/Madrid` (CET/CEST)

**Asia:**
- `Asia/Tokyo` (JST)
- `Asia/Shanghai` (CST)
- `Asia/Kolkata` (IST)

---

## 💡 Ejemplos de uso en Python

### Obtener la zona horaria de una ubicación y convertir horarios

```python
import pytz
from datetime import datetime
from apps.home.services.database_service import DatabaseService

# Obtener la zona horaria de una ubicación
def get_location_timezone(location_guid):
    with DatabaseService.get_db_cursor() as (cursor, conn):
        cursor.execute(
            "SELECT timezone FROM nextris.tblocation WHERE guid = %s",
            (location_guid,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

# Convertir hora UTC a la zona horaria local
def utc_to_local(utc_time, timezone_str):
    tz = pytz.timezone(timezone_str)
    utc_tz = pytz.UTC
    utc_dt = utc_tz.localize(utc_time)
    return utc_dt.astimezone(tz)

# Uso
location_guid = "uuid-ubicacion"
tz = get_location_timezone(location_guid)
local_time = utc_to_local(datetime.utcnow(), tz)
print(f"Hora local: {local_time}")
```

### Validar si un horario de cita es válido en una ubicación

```python
import pytz
from datetime import datetime, timedelta

def validate_appointment_time(appointment_datetime, location_guid):
    """Validar si el horario de la cita es válido en la zona horaria de la ubicación"""
    tz = get_location_timezone(location_guid)
    
    if not tz:
        return False, "Ubicación sin zona horaria configurada"
    
    # Convertir el datetime de la cita a la zona horaria local
    tz_obj = pytz.timezone(tz)
    local_time = appointment_datetime.astimezone(tz_obj)
    
    # Validar horario (ejemplo: entre 8:00 y 18:00)
    hour = local_time.hour
    
    if hour < 8 or hour >= 18:
        return False, f"Horario fuera de servicio en {tz}"
    
    return True, "Horario válido"
```

---

## ✅ Pasos completados

1. ✅ Agregadas columnas `geographic_location` y `timezone` a `nextris.tblocation`
2. ✅ Creado API CRUD completo para gestionar ubicaciones
3. ✅ Implementada validación de zonas horarias
4. ✅ Endpoints para obtener hora actual en una ubicación
5. ✅ Endpoint para listar todas las zonas horarias disponibles

## 🚀 Próximas integraciones

Puedes ahora:
- Integrar estas columnas en las citas para validar horarios locales
- Usar la zona horaria en los reportes DICOM
- Convertir automáticamente horarios UTC a horarios locales
- Validar disponibilidad de equipos considerando su zona horaria

