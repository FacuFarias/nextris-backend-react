# Feature: Apertura Automática del Siguiente Reporte al Firmar

## 📋 Descripción
Cuando el usuario firma un reporte, se abre automáticamente el siguiente reporte disponible según la configuración de los 3 checkboxes de filtros (Listo para leer, Ver finalizados, Asignados a mí).

---

## ✅ BACKEND - YA IMPLEMENTADO

### 1. **Nuevo Endpoint: `POST /api/reports/next-exam`**
Obtiene el siguiente examen disponible basado en los filtros configurados.

**Request:**
```json
{
  "current_exam_id": "uuid-del-examen-actual",
  "show_ready": true,
  "show_reported": false,
  "assigned_to_me": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "guid": "uuid-del-siguiente-examen",
    "study_instance_uid": "1.2.840...",
    "patient_name": "Nombre Completo",
    "patient_dni": "12345678",
    "study_type": "ECOCARDIOGRAMA (2D)",
    "accession_number": "ACC049",
    "is_reported": false
  }
}
```

**Response cuando no hay más exámenes:**
```json
{
  "success": true,
  "data": null,
  "message": "No hay más exámenes disponibles"
}
```

---

### 2. **Endpoint Modificado: `POST /api/reports/<exam_id>/sign`**
Ahora acepta parámetros adicionales opcionales.

**Request (nuevo):**
```json
{
  "reporter_physician_id": "uuid (opcional)",
  "get_next": true,
  "show_ready": true,
  "show_reported": false,
  "assigned_to_me": false
}
```

**Response (nuevo):**
```json
{
  "success": true,
  "message": "Reporte firmado exitosamente",
  "next_exam": {
    "guid": "uuid-del-siguiente",
    "study_instance_uid": "...",
    "patient_name": "...",
    "patient_dni": "...",
    "study_type": "...",
    "accession_number": "...",
    "is_reported": false
  }
}
```

**Nota:** El campo `next_exam` solo se incluye si `get_next: true` y si hay un siguiente examen disponible.

---

## 🔨 FRONTEND - PENDIENTE DE IMPLEMENTAR

### **Archivos a modificar:**

1. ✅ `/nextris-front-react/src/modules/redaccion/Radiologia/Radiologia.tsx`
2. ✅ `/nextris-front-react/src/modules/redaccion/Radiologia/redactar-informe/RedactarInforme.tsx`

---

## 📝 PASO 1: Modificar `Radiologia.tsx`

### Objetivo: Guardar las preferencias de filtros en localStorage

**Ubicación:** `/nextris-front-react/src/modules/redaccion/Radiologia/Radiologia.tsx`

### Código a agregar:

#### 1.1 Importar `useEffect`
```tsx
import { useState, useEffect } from "react"
```

#### 1.2 Agregar función para manejar cambios de filtros
Agregar después de la declaración de los estados (línea ~26):

```tsx
// Función para guardar filtros en localStorage
const handleFilterChange = (filterName: string, value: boolean) => {
    localStorage.setItem(`reportFilters_${filterName}`, JSON.stringify(value));
    
    // Actualizar el estado correspondiente
    if (filterName === 'listoParaLeer') setListoParaLeer(value);
    if (filterName === 'verFinalizados') setVerFinalizados(value);
    if (filterName === 'asignadosAMi') setAsignadosAMi(value);
};

// Cargar filtros guardados al montar el componente
useEffect(() => {
    const savedListoParaLeer = localStorage.getItem('reportFilters_listoParaLeer');
    const savedVerFinalizados = localStorage.getItem('reportFilters_verFinalizados');
    const savedAsignadosAMi = localStorage.getItem('reportFilters_asignadosAMi');
    
    if (savedListoParaLeer !== null) setListoParaLeer(JSON.parse(savedListoParaLeer));
    if (savedVerFinalizados !== null) setVerFinalizados(JSON.parse(savedVerFinalizados));
    if (savedAsignadosAMi !== null) setAsignadosAMi(JSON.parse(savedAsignadosAMi));
}, []);
```

#### 1.3 Actualizar los checkboxes
Reemplazar los 3 checkboxes existentes (líneas ~100-140):

**Checkbox 1: "Listo para leer"**
```tsx
<Checkbox
    id="listo-leer"
    checked={listoParaLeer}
    onCheckedChange={(checked) => handleFilterChange('listoParaLeer', checked as boolean)}
    className="data-[state=checked]:bg-brand-purple data-[state=checked]:border-brand-purple"
/>
```

**Checkbox 2: "Ver finalizados"**
```tsx
<Checkbox
    id="finalizados"
    checked={verFinalizados}
    onCheckedChange={(checked) => handleFilterChange('verFinalizados', checked as boolean)}
    className="data-[state=checked]:bg-brand-purple data-[state=checked]:border-brand-purple"
/>
```

**Checkbox 3: "Asignados a mí"**
```tsx
<Checkbox
    id="asignados"
    checked={asignadosAMi}
    onCheckedChange={(checked) => handleFilterChange('asignadosAMi', checked as boolean)}
    className="data-[state=checked]:bg-brand-purple data-[state=checked]:border-brand-purple"
/>
```

---

## 📝 PASO 2: Modificar `RedactarInforme.tsx`

### Objetivo: Al firmar, solicitar el siguiente reporte y abrirlo automáticamente

**Ubicación:** `/nextris-front-react/src/modules/redaccion/Radiologia/redactar-informe/RedactarInforme.tsx`

### Código a modificar:

#### 2.1 Localizar las dos llamadas a `api.post('/reports/${informeGuid}/sign')`

Hay dos lugares donde se firma el reporte:
- Línea ~808 (en el evento onKeyDown del Input)
- Línea ~857 (en el onClick del PrimaryButton)

#### 2.2 Reemplazar AMBAS llamadas con este código:

**ANTES:**
```tsx
await api.post(`/reports/${informeGuid}/sign`);

setIsSigned(true);
setIsSignModalOpen(false);
setPassword('');
toast.success('Informe firmado exitosamente');
```

**DESPUÉS:**
```tsx
// Obtener filtros guardados desde localStorage
const show_ready = JSON.parse(localStorage.getItem('reportFilters_listoParaLeer') || 'true');
const show_reported = JSON.parse(localStorage.getItem('reportFilters_verFinalizados') || 'false');
const assigned_to_me = JSON.parse(localStorage.getItem('reportFilters_asignadosAMi') || 'false');

// Firmar reporte y solicitar el siguiente
const response = await api.post(`/reports/${informeGuid}/sign`, {
    get_next: true,
    show_ready,
    show_reported,
    assigned_to_me
});

setIsSigned(true);
setIsSignModalOpen(false);
setPassword('');
toast.success('Informe firmado exitosamente');

// Si hay un siguiente examen, abrirlo automáticamente
if (response.data.next_exam) {
    const nextExam = response.data.next_exam;
    
    // Mostrar notificación
    toast.info(`Abriendo siguiente reporte: ${nextExam.patient_name}`);
    
    // Abrir el siguiente reporte después de 1.5 segundos
    setTimeout(() => {
        const url = `/redaccion/radiologia/redactar-informe/${nextExam.guid}/${nextExam.study_instance_uid}`;
        window.open(
            url,
            '_blank',
            'toolbar=no,location=no,directories=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=1400,height=900,top=50,left=100'
        );
        
        // Opcional: Cerrar la ventana actual
        // window.close();
    }, 1500);
} else {
    toast.info('No hay más reportes disponibles con los filtros actuales');
}
```

---

## 🎯 Comportamiento Esperado

### Flujo completo:

1. **Usuario configura filtros en la lista de reportes:**
   - ☑️ Listo para leer
   - ☐ Ver finalizados
   - ☐ Asignados a mí
   - **Los filtros se guardan automáticamente en localStorage**

2. **Usuario abre un reporte para redactar:**
   - Completa los hallazgos, impresiones, etc.
   - Hace clic en "Firmar Informe"
   - Ingresa su contraseña

3. **Al firmar:**
   - Backend marca el examen como reportado
   - Backend genera el PDF
   - Backend busca el siguiente examen con los mismos filtros guardados
   - Backend devuelve el siguiente examen (si existe)

4. **Frontend recibe la respuesta:**
   - ✅ Si hay siguiente examen:
     - Muestra toast: "Abriendo siguiente reporte: [Nombre del paciente]"
     - Espera 1.5 segundos
     - Abre el siguiente reporte en una nueva ventana
   - ❌ Si NO hay más exámenes:
     - Muestra toast: "No hay más reportes disponibles con los filtros actuales"

---

## 🔍 Detalles Técnicos

### Keys de localStorage:
```javascript
'reportFilters_listoParaLeer'   // boolean
'reportFilters_verFinalizados'  // boolean
'reportFilters_asignadosAMi'    // boolean
```

### Valores por defecto si no existen en localStorage:
- `listoParaLeer`: `true`
- `verFinalizados`: `false`
- `asignadosAMi`: `false`

### Lógica de filtros en backend:
- **show_ready=true + show_reported=false**: Solo exámenes NO reportados (pendientes)
- **show_ready=false + show_reported=true**: Solo exámenes YA reportados (finalizados)
- **show_ready=true + show_reported=true**: TODOS los exámenes (reportados y no reportados)
- **show_ready=false + show_reported=false**: NINGÚN examen (lista vacía)

### Orden de búsqueda del siguiente examen:
- Se ordenan por `CreatedOn DESC` (más reciente primero)
- Se filtra que `CreatedOn <= fecha_del_examen_actual`
- Se excluye el examen actual
- Se limita a 1 resultado

---

## ✅ Testing

### Escenarios a probar:

1. **Caso feliz:**
   - Filtros: Listo para leer ✓
   - Hay 5 reportes pendientes
   - Firmar el primero → Debe abrir el segundo automáticamente

2. **Último reporte:**
   - Filtros: Listo para leer ✓
   - Hay 1 solo reporte pendiente
   - Firmar el último → Debe mostrar "No hay más reportes disponibles"

3. **Cambio de filtros:**
   - Filtros iniciales: Listo para leer ✓
   - Cambiar a: Ver finalizados ✓
   - Los filtros deben persistir al recargar la página

4. **Filtro "Asignados a mí":**
   - Activar: Asignados a mí ✓
   - Solo debe buscar siguiente entre los asignados al usuario actual

5. **Múltiples ventanas:**
   - Abrir 2 reportes en ventanas diferentes
   - Firmar ambos
   - Ambos deben abrir el siguiente correctamente

---

## 📌 Notas Importantes

1. **No cerrar ventana actual:** Por ahora, NO cerrar la ventana actual después de abrir el siguiente (está comentado con `// window.close();`). Evaluar esto después con el usuario.

2. **Tiempo de espera:** El delay de 1.5 segundos antes de abrir el siguiente reporte es para que el usuario vea el toast de confirmación.

3. **Persistencia:** Los filtros se guardan en localStorage del navegador, por lo que persisten entre sesiones.

4. **Compatibilidad:** La funcionalidad es compatible con el flujo actual. Si el backend no incluye `next_exam` en la respuesta (por ejemplo, en versiones antiguas), simplemente no abrirá nada automáticamente.

---

## ❓ FAQ

**P: ¿Qué pasa si el usuario tiene la ventana del siguiente reporte ya abierta?**
R: Se abrirá una nueva ventana adicional. El navegador no detecta ventanas duplicadas con window.open().

**P: ¿Se puede abrir en la misma ventana en lugar de una nueva?**
R: Sí, reemplazar `window.open()` con `window.location.href = url` (pero la ventana actual se perdería).

**P: ¿Qué pasa si la conexión falla al obtener el siguiente examen?**
R: El backend tiene un try-catch que NO falla la firma si hay error al obtener el siguiente. El reporte se firma exitosamente pero simplemente no se abre el siguiente.

---

## 👨‍💻 Implementado por
Backend: IA Assistant
Frontend: [Pendiente de asignar]

Fecha: 29 de enero de 2026
