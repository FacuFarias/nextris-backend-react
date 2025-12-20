# API Documentation: Calendar Events

## POST /appointments/calendar-events

Obtiene eventos del calendario para editar junto con los horarios de trabajo del equipo.

### Request

**Method:** POST  
**URL:** `/api/appointments/calendar-events`  
**Headers:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Body JSON:**
```json
{
  "guid": "optional-event-guid-to-edit",
  "equipment_aetitle": "aetitle-del-equipo"
}
```

### Parameters

- **equipment_aetitle** (string, required): AE Title del equipo del cual obtener eventos
- **guid** (string, optional): GUID del evento a marcar como editable (para modo edición)

### Response

**Success (200):**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "guid": "uuid",
        "start": "2025-12-13T10:00:00",
        "end": "2025-12-13T11:00:00",
        "title": "García Juan - TAC Torax",
        "patient_name": "García Juan",
        "exam": "TAC Torax",
        "idmed": "doctor-guid",
        "idmed_sol": "requesting-doctor-guid",
        "editable": false
      }
    ],
    "work_hours": [
      {
        "day": 1,
        "start": "08:00:00",
        "end": "17:00:00"
      },
      {
        "day": 2,
        "start": "08:00:00", 
        "end": "17:00:00"
      }
    ]
  }
}
```

**Error (400):**
```json
{
  "success": false,
  "message": "El campo equipment_aetitle es requerido"
}
```

### Frontend Usage Example

```javascript
const loadCalendarEvents = async (equipmentAetitle) => {
  try {
    const response = await fetch('/api/appointments/calendar-events', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        equipment_aetitle: equipmentAetitle
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      // result.data.events = eventos para mostrar en calendario
      // result.data.work_hours = horarios laborales para configurar calendario
      return result.data;
    } else {
      console.error('Error:', result.message);
    }
  } catch (error) {
    console.error('Network error:', error);
  }
};

// Uso
const calendarData = await loadCalendarEvents('CT_SIEMENS_01');
```

### Work Hours Format

Los días se mapean de la siguiente forma:
- 0: Domingo
- 1: Lunes  
- 2: Martes
- 3: Miércoles
- 4: Jueves
- 5: Viernes
- 6: Sábado

### Notes

- Este endpoint es perfecto para cargar un calendario de un equipo específico
- Los eventos incluyen toda la información necesaria para mostrar en un componente de calendario
- Los horarios de trabajo permiten configurar las horas laborables en el calendario
- El parámetro `guid` opcional permite marcar un evento como editable (útil para modos de edición)