# 🚀 Quick Start - Sincronizar Documentación al Frontend

## Ubicación de Archivos Actualizados

### En el Backend (Actual):
```
/var/www/nextris-dev-react/API_APPOINTMENTS_DOCUMENTATION.md
/var/www/nextris-dev-react/API_LOCATIONS_TIMEZONE.md
/var/www/nextris-dev-react/TIMEZONE_API_CHANGES.md
/var/www/nextris-dev-react/SYNC_FRONTEND_DOCS.md
```

## Comando Rápido para Copiar

Si tienes acceso al repositorio frontend:

```bash
# Copiar documentación actualizada
cp /var/www/nextris-dev-react/API_APPOINTMENTS_DOCUMENTATION.md ~/nextris-front-react/
cp /var/www/nextris-dev-react/API_LOCATIONS_TIMEZONE.md ~/nextris-front-react/
cp /var/www/nextris-dev-react/TIMEZONE_API_CHANGES.md ~/nextris-front-react/

# Ir al directorio del frontend
cd ~/nextris-front-react

# Hacer commit
git add API_APPOINTMENTS_DOCUMENTATION.md API_LOCATIONS_TIMEZONE.md TIMEZONE_API_CHANGES.md
git commit -m "docs: agregar soporte de timezone en endpoints de citas (v1.2.0)"
git push origin main
```

## Qué Se Actualizó en la Documentación

### ✅ GET /appointments
Ahora devuelve `timezone` en cada cita

### ✅ POST /appointments/calendar-events  
Ahora devuelve `timezone` en nivel superior de la respuesta

### ✅ POST /appointments/:id/admit
Ahora devuelve `timezone` junto a admission_number, accession_number, etc.

### ✅ POST /admission/create-order
Nuevo endpoint completamente documentado con timezone

### ✅ Data Types
Actualizado para incluir campo `timezone` en Appointment Object

### ✅ CHANGELOG
Versión 1.2.0 con todos los cambios de timezone

## Validación Post-Sincronización

Verificar en GitHub (https://github.com/FacuFarias/nextris-front-react) que:

- [ ] API_APPOINTMENTS_DOCUMENTATION.md se ve correctamente
- [ ] Los ejemplos JSON son válidos
- [ ] Las secciones de timezone aparecen en todos los endpoints
- [ ] El CHANGELOG muestra v1.2.0

## Preguntas Frecuentes

**¿Qué es el campo timezone?**
- Es la zona horaria de la ubicación (location) asociada a la cita
- Ejemplo: `America/Argentina/Buenos_Aires`
- El frontend puede usarlo para convertir horarios UTC a hora local

**¿Todos los endpoints devuelven timezone?**
- Sí: GET /appointments, POST /appointments/calendar-events, POST /appointments/:id/admit, POST /admission/create-order

**¿Qué pasa si una cita no tiene ubicación?**
- Se usa el default: `America/Argentina/Buenos_Aires`

**¿Necesito hacer cambios en el frontend?**
- No es obligatorio, pero es recomendable usar el timezone para mostrar horarios correctamente
- Ver ejemplos en SYNC_FRONTEND_DOCS.md

## Documentación Adicional

Para más detalles, consulta:
- `TIMEZONE_API_CHANGES.md` - Cambios técnicos detallados
- `API_LOCATIONS_TIMEZONE.md` - API de locations y timezones
- `SYNC_FRONTEND_DOCS.md` - Guía completa de sincronización
