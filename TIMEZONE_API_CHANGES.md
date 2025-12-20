# 📋 Resumen de Cambios - Inclusión de Timezone en APIs de Citas

## 🎯 Objetivo
Agregar el campo `timezone` a todos los endpoints de citas y agenda para que el frontend pueda ajustar correctamente los horarios según la zona horaria de la ubicación (location).

---

## ✅ Cambios Realizados

### 1️⃣ **POST `/appointments/calendar-events`** ✅
**Descripción:** Obtiene eventos del calendario para editar una cita

**Cambios:**
- Ahora obtiene el `timezone` de la tabla `nextris.tblocation`
- Devuelve `timezone` en el nivel superior de `data`
- **Default:** `America/Argentina/Buenos_Aires` si no existe o está vacío

**Nueva Respuesta:**
```json
{
  "success": true,
  "data": {
    "timezone": "America/Argentina/Buenos_Aires",
    "events": [...],
    "work_hours": [...]
  }
}
```

---

### 2️⃣ **GET `/appointments`** ✅
**Descripción:** Obtiene lista de citas con filtros y paginación

**Cambios:**
- Agregado LEFT JOIN con `nextris.tblocation` para obtener timezone
- Cada cita ahora incluye su `timezone`
- **Default:** `America/Argentina/Buenos_Aires` si no existe

**Nueva Respuesta:**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "guid": "...",
        "patient_name": "...",
        "start": "2025-12-05T10:00:00",
        "end": "2025-12-05T11:00:00",
        "exam": "...",
        "doctor": "...",
        "equipment": "...",
        "is_admitted": false,
        "location_id": "...",
        "equipment_id": "...",
        "modality": "...",
        "timezone": "America/Argentina/Buenos_Aires"  // ← NUEVO
      }
    ],
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

---

### 3️⃣ **POST `/appointments/<appointment_id>/admit`** ✅
**Descripción:** Admisiona una cita y crea el examen en worklist

**Cambios:**
- Obtiene el `timezone` de la ubicación asociada a la cita
- Devuelve `timezone` en los datos de la respuesta
- **Default:** `America/Argentina/Buenos_Aires` si no existe

**Nueva Respuesta:**
```json
{
  "success": true,
  "data": {
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "exam_id": "uuid-del-examen",
    "study_instance_uid": "1.2.840...",
    "timezone": "America/Argentina/Buenos_Aires"  // ← NUEVO
  },
  "message": "Cita admisionada exitosamente"
}
```

---

### 4️⃣ **POST `/admission/create-order`** ✅
**Descripción:** Crea una orden de admisión (worklist) con un examen

**Cambios:**
- Obtiene el `timezone` desde el parámetro `location_id`
- Devuelve `timezone` en los datos de la respuesta
- **Default:** `America/Argentina/Buenos_Aires` si no existe

**Nueva Respuesta:**
```json
{
  "success": true,
  "data": {
    "admission_number": "ADM001",
    "accession_number": "ACC001",
    "exam_id": "uuid-del-examen",
    "study_instance_uid": "1.2.840...",
    "timezone": "America/Argentina/Buenos_Aires"  // ← NUEVO
  },
  "message": "Orden creada exitosamente"
}
```

---

## 📊 Resumen de Modificaciones

| Endpoint | Cambios | Estado |
|----------|---------|--------|
| `POST /appointments/calendar-events` | Devuelve `timezone` | ✅ |
| `GET /appointments` | Agrega `timezone` a cada cita | ✅ |
| `POST /appointments/<id>/admit` | Devuelve `timezone` | ✅ |
| `POST /admission/create-order` | Devuelve `timezone` | ✅ |

---

## 🔧 Detalles Técnicos

### Obtención del Timezone
Todas las APIs utilizan la misma lógica:

```sql
-- Si la cita tiene location_id
SELECT COALESCE(tbl.timezone, 'America/Argentina/Buenos_Aires')
FROM nextris.tblocation tbl
WHERE tbl.guid = tba.location_id

-- Si no hay location, usa el default
COALESCE(timezone, 'America/Argentina/Buenos_Aires')
```

### Consideraciones de Base de Datos
- Las tablas ya tienen las columnas `geographic_location` y `timezone`
- Todas las ubicaciones (locations) están configuradas con:
  - `geographic_location`: "Argentina"
  - `timezone`: "America/Argentina/Buenos_Aires"

---

## 🎓 Uso en Frontend

### Ejemplo con JavaScript/TypeScript

```typescript
// Obtener citas con timezone
const response = await api.get('/appointments?page=1&per_page=20');

response.data.data.forEach(appointment => {
  const { start, end, timezone } = appointment;
  
  // Convertir horarios usando el timezone
  const startDate = new Date(start);
  const endDate = new Date(end);
  
  // El frontend puede usar pytz.js o similar para convertir
  const localStart = convertToTimezone(startDate, timezone);
  const localEnd = convertToTimezone(endDate, timezone);
  
  console.log(`Cita: ${localStart.toLocaleString()}`);
});
```

### Ejemplo con Calendario

```typescript
// Para calendar-events
const response = await api.post('/appointments/calendar-events', {
  equipment_aetitle: 'CT1'
});

const { timezone, events, work_hours } = response.data.data;

// Usar timezone para ajustar visualización del calendario
initializeCalendar({
  timezone: timezone,
  events: events,
  workHours: work_hours
});
```

---

## ✨ Beneficios

✅ **Información consistente:** Todas las APIs devuelven timezone  
✅ **Frontend simplificado:** No necesita hacer queries adicionales  
✅ **Escalable:** Fácil agregar más ubicaciones con diferentes zonas horarias  
✅ **Resistente:** Usa default "America/Argentina/Buenos_Aires" si falta datos  
✅ **Compatible:** Integrable con librerías como pytz.js, moment-timezone, etc.

---

## 🔍 Validación

Se verificó:
- ✅ Sintaxis Python válida
- ✅ Queries SQL correctas
- ✅ LEFT JOINs funcionan correctamente
- ✅ COALESCE con default funciona
- ✅ Respuestas incluyen timezone en todos los endpoints

