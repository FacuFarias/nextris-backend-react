# 📋 Instrucciones para Sincronizar Documentación con Frontend

## 🎯 Objetivo
Actualizar la documentación de APIs en el repositorio `nextris-front-react` con los cambios realizados para soporte de Timezone.

---

## 📂 Archivos a Sincronizar

### Desde Backend (nextris-dev-react):
```
/var/www/nextris-dev-react/API_APPOINTMENTS_DOCUMENTATION.md
/var/www/nextris-dev-react/API_LOCATIONS_TIMEZONE.md
/var/www/nextris-dev-react/TIMEZONE_API_CHANGES.md
```

### Hacia Frontend (nextris-front-react):
```
nextris-front-react/API_APPOINTMENTS_DOCUMENTATION.md
nextris-front-react/API_LOCATIONS_TIMEZONE.md (Nuevo)
nextris-front-react/TIMEZONE_API_CHANGES.md (Nuevo)
```

---

## 🔄 Proceso de Sincronización

### Opción 1: Usando Git (Recomendado)

#### Paso 1: Copiar archivos actualizados
```bash
# Desde /var/www/nextris-dev-react
cp API_APPOINTMENTS_DOCUMENTATION.md /path/to/nextris-front-react/
cp API_LOCATIONS_TIMEZONE.md /path/to/nextris-front-react/
cp TIMEZONE_API_CHANGES.md /path/to/nextris-front-react/
```

#### Paso 2: Crear commit
```bash
cd /path/to/nextris-front-react
git add API_APPOINTMENTS_DOCUMENTATION.md API_LOCATIONS_TIMEZONE.md TIMEZONE_API_CHANGES.md
git commit -m "docs: agregar soporte de timezone a endpoints de citas

- Actualizado GET /appointments con campo timezone
- Actualizado POST /appointments/calendar-events con timezone
- Actualizado POST /appointments/:id/admit con timezone
- Agregado endpoint POST /admission/create-order con timezone
- Documentación completa de timezone para frontend"
```

#### Paso 3: Push al repositorio
```bash
git push origin main
```

### Opción 2: Manual (Sin Git)

1. Copiar archivos directamente al repositorio frontend
2. Validar cambios con editor de markdown
3. Confirmar que los ejemplos sean correctos

---

## 📝 Cambios Principales Documentados

### 1. GET /appointments
- ✅ Agregado campo `timezone` a cada cita
- **Uso:** El frontend puede usar este valor para ajustar horarios

### 2. POST /appointments/calendar-events  
- ✅ Agregado `timezone` en nivel superior de respuesta
- **Uso:** Calendario debe usar este timezone para work_hours y events

### 3. POST /appointments/:id/admit
- ✅ Agregado `timezone` en datos de respuesta
- **Uso:** Mostrar zona horaria al confirmar admisión

### 4. POST /admission/create-order (Nuevo)
- ✅ Completamente documentado
- ✅ Incluye `timezone` en respuesta
- **Uso:** Crear órdenes directamente con información de timezone

---

## 🎓 Guía para el Frontend

### Usar Timezone en JavaScript/TypeScript

#### Ejemplo 1: Convertir horarios con moment-timezone
```typescript
import moment from 'moment-timezone';

const appointment = {
  start: "2025-12-05T10:00:00",
  timezone: "America/Argentina/Buenos_Aires"
};

const localTime = moment(appointment.start)
  .tz(appointment.timezone)
  .format('DD/MM/YYYY HH:mm:ss');

console.log(localTime); // 05/12/2025 10:00:00
```

#### Ejemplo 2: Con pytz.js
```typescript
import pytz from 'pytz';

const tz = pytz.timezone(appointment.timezone);
const localDt = pytz.localize(
  moment(appointment.start),
  tz
);
```

#### Ejemplo 3: Validar si horario está dentro de work_hours
```typescript
const validateAppointmentTime = (
  start: string,
  timezone: string,
  workHours: any[]
) => {
  const startTime = moment(start).tz(timezone);
  const dayOfWeek = startTime.day();
  const hour = startTime.hour();
  
  const workHour = workHours.find(wh => wh.day === dayOfWeek);
  if (!workHour) return false;
  
  const startHour = parseInt(workHour.start.split(':')[0]);
  const endHour = parseInt(workHour.end.split(':')[0]);
  
  return hour >= startHour && hour < endHour;
};
```

---

## ✅ Checklist de Validación

Después de sincronizar, verificar que:

- [ ] Archivos markdown se abren sin errores
- [ ] Links internos funcionan correctamente
- [ ] Ejemplos JSON son válidos
- [ ] Campos `timezone` aparecen en todas las respuestas
- [ ] CHANGELOG actualizado a v1.2.0
- [ ] Documentación visible en repositorio frontend

---

## 📞 Contacto

Para dudas o cambios adicionales:
- Backend: `/var/www/nextris-dev-react/`
- Frontend: `https://github.com/FacuFarias/nextris-front-react`

---

## 🔗 Referencias

- [API_APPOINTMENTS_DOCUMENTATION.md](/var/www/nextris-dev-react/API_APPOINTMENTS_DOCUMENTATION.md)
- [API_LOCATIONS_TIMEZONE.md](/var/www/nextris-dev-react/API_LOCATIONS_TIMEZONE.md)
- [TIMEZONE_API_CHANGES.md](/var/www/nextris-dev-react/TIMEZONE_API_CHANGES.md)

