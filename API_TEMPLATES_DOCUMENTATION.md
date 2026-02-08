# API de Plantillas (Templates) - Documentación

## Descripción General

API REST para la gestión de plantillas de informes predefinidos en el sistema NextRIS. Permite crear, leer, actualizar y eliminar plantillas de informes médicos, así como seleccionarlas para aplicar a nuevos reportes.

**Base URL:** `/api/templates`

**Autenticación:** Todos los endpoints requieren un token JWT válido en el header:
```
Authorization: Bearer <access_token>
```

---

## Tabla de Contenidos

1. [Endpoints Disponibles](#endpoints-disponibles)
2. [Listar Plantillas](#listar-plantillas)
3. [Obtener Plantilla Específica](#obtener-plantilla-específica)
4. [Crear Plantilla](#crear-plantilla)
5. [Editar Plantilla](#editar-plantilla)
6. [Eliminar Plantilla](#eliminar-plantilla)
7. [Códigos de Respuesta](#códigos-de-respuesta)
8. [Modelos de Datos](#modelos-de-datos)

---

## Endpoints Disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/templates` | Lista todas las plantillas (con filtros opcionales) |
| GET | `/api/templates/<template_id>` | Obtiene una plantilla específica |
| POST | `/api/templates` | Crea una nueva plantilla |
| PUT | `/api/templates/<template_id>` | Edita una plantilla existente |
| DELETE | `/api/templates/<template_id>` | Elimina una plantilla |

---

## Listar Plantillas

Obtiene la lista de todas las plantillas de informes predefinidos con opciones de filtrado.

**Endpoint:** `GET /api/templates`

**Query Parameters:**
- `study_type_id` (string, opcional): UUID del tipo de estudio para filtrar
- `modality_id` (string, opcional): UUID de la modalidad para filtrar
- `bodypart_id` (string, opcional): UUID de la parte del cuerpo para filtrar
- `simple` (boolean, opcional): Si es `true`, devuelve solo guid, title y study_type_description (más liviano)

**Ejemplo de Petición Simple:**
```bash
GET /api/templates
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Ejemplo con Filtro por Tipo de Estudio:**
```bash
GET /api/templates?study_type_id=cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Ejemplo con Múltiples Filtros:**
```bash
GET /api/templates?study_type_id=cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9&modality_id=abc123&simple=true
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Respuesta Exitosa (200) - Completa:**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Plantilla RX Tórax Normal",
      "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
      "study_type_description": "RX TORAX",
      "findings": "Campos pulmonares de aspecto radiológico normal...",
      "technique": "Se realizó radiografía de tórax en proyección PA...",
      "impression": "Sin alteraciones radiológicas evidentes.",
      "conclusion": "Estudio dentro de parámetros normales."
    },
    {
      "guid": "661e9500-f39c-52e5-b827-557766551111",
      "title": "Plantilla RX Tórax Consolidación",
      "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
      "study_type_description": "RX TORAX",
      "findings": "Consolidación pulmonar en lóbulo inferior derecho...",
      "technique": "Se realizó radiografía de tórax en proyección PA...",
      "impression": "Hallazgos compatibles con proceso infeccioso.",
      "conclusion": "Se sugiere correlación clínica y seguimiento."
    }
  ]
}
```

**Respuesta Exitosa (200) - Modo Simple (`simple=true`):**
```json
{
  "success": true,
  "data": [
    {
      "guid": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Plantilla RX Tórax Normal",
      "study_type_description": "RX TORAX"
    },
    {
      "guid": "661e9500-f39c-52e5-b827-557766551111",
      "title": "Plantilla RX Tórax Consolidación",
      "study_type_description": "RX TORAX"
    }
  ]
}
```

**Respuesta de Error (500):**
```json
{
  "success": false,
  "message": "Error: <descripción del error>"
}
```

---

## Obtener Plantilla Específica

Obtiene los datos completos de una plantilla específica por su GUID.

**Endpoint:** `GET /api/templates/<template_id>`

**Path Parameters:**
- `template_id` (string, requerido): UUID de la plantilla

**Ejemplo de Petición:**
```bash
GET /api/templates/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "guid": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Plantilla RX Tórax Normal",
    "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
    "findings": "Campos pulmonares de aspecto radiológico normal.\nNo se observan infiltrados ni consolidaciones.\nSilueta cardíaca de tamaño y morfología conservados.",
    "technique": "Se realizó radiografía de tórax en proyección PA y lateral con técnica digital.",
    "impression": "Sin alteraciones radiológicas evidentes.",
    "conclusion": "Estudio dentro de parámetros normales."
  }
}
```

**Respuesta de Error (404):**
```json
{
  "success": false,
  "message": "Plantilla no encontrada"
}
```

---

## Crear Plantilla

Crea una nueva plantilla de informe predefinido.

**Endpoint:** `POST /api/templates`

**Body (JSON):**
```json
{
  "title": "Plantilla RX Abdomen Normal",
  "study_type_id": "aa90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
  "findings": "Gas intestinal distribuido de forma normal.\nNo se observan niveles hidroaéreos.\nPsoas y líneas grasas conservadas.",
  "technique": "Se realizó radiografía simple de abdomen en proyección AP en decúbito.",
  "impression": "Patrón radiológico abdominal normal.",
  "conclusion": "Sin hallazgos patológicos.",
  "is_default": false
}
```

**Campos:**
- `title` (string, **requerido**): Nombre de la plantilla
- `study_type_id` (string, **requerido**): UUID del tipo de estudio
- `findings` (string, opcional): Texto de hallazgos
- `technique` (string, opcional): Descripción de la técnica utilizada
- `impression` (string, opcional): Impresión diagnóstica
- `conclusion` (string, opcional): Conclusiones del estudio
- `is_default` (boolean, opcional): Si es la plantilla por defecto para el tipo de estudio

**Ejemplo de Petición:**
```bash
POST /api/templates
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "title": "Plantilla RX Abdomen Normal",
  "study_type_id": "aa90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
  "findings": "Gas intestinal distribuido de forma normal...",
  "technique": "Se realizó radiografía simple de abdomen...",
  "impression": "Patrón radiológico abdominal normal.",
  "conclusion": "Sin hallazgos patológicos.",
  "is_default": false
}
```

**Respuesta Exitosa (201):**
```json
{
  "success": true,
  "data": {
    "guid": "772e9511-g40d-63f6-c938-668877662222",
    "message": "Plantilla creada exitosamente"
  }
}
```

**Respuesta de Error - Campo Requerido (400):**
```json
{
  "success": false,
  "message": "El título es requerido"
}
```

**Respuesta de Error - Tipo de Estudio Requerido (400):**
```json
{
  "success": false,
  "message": "El tipo de estudio es requerido"
}
```

---

## Editar Plantilla

Actualiza los datos de una plantilla existente.

**Endpoint:** `PUT /api/templates/<template_id>`

**Path Parameters:**
- `template_id` (string, requerido): UUID de la plantilla a editar

**Body (JSON):**
```json
{
  "title": "Plantilla RX Tórax Normal Actualizada",
  "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
  "findings": "Campos pulmonares de aspecto radiológico normal ACTUALIZADO...",
  "technique": "Se realizó radiografía de tórax ACTUALIZADO...",
  "impression": "Sin alteraciones radiológicas evidentes ACTUALIZADO.",
  "conclusion": "Estudio dentro de parámetros normales ACTUALIZADO."
}
```

**Ejemplo de Petición:**
```bash
PUT /api/templates/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "title": "Plantilla RX Tórax Normal Actualizada",
  "study_type_id": "cb90d4eb-b298-4e6e-91ea-010a3e4dc8d9",
  "findings": "Campos pulmonares normales...",
  "technique": "Técnica estándar...",
  "impression": "Normal.",
  "conclusion": "Sin alteraciones."
}
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "guid": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Plantilla actualizada exitosamente"
  }
}
```

**Respuesta de Error (404):**
```json
{
  "success": false,
  "message": "Plantilla no encontrada"
}
```

---

## Eliminar Plantilla

Elimina una plantilla de informe. Si la plantilla está configurada como default para algún tipo de estudio, la referencia se limpia automáticamente.

**Endpoint:** `DELETE /api/templates/<template_id>`

**Path Parameters:**
- `template_id` (string, requerido): UUID de la plantilla a eliminar

**Ejemplo de Petición:**
```bash
DELETE /api/templates/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Respuesta Exitosa (200):**
```json
{
  "success": true,
  "data": {
    "message": "Plantilla eliminada exitosamente"
  }
}
```

**Respuesta de Error (404):**
```json
{
  "success": false,
  "message": "Plantilla no encontrada"
}
```

---

## Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| 200 | Operación exitosa (GET, PUT, DELETE) |
| 201 | Plantilla creada exitosamente (POST) |
| 400 | Error de validación (campos requeridos faltantes) |
| 404 | Plantilla no encontrada |
| 500 | Error interno del servidor |

---

## Modelos de Datos

### Template (Plantilla)

Modelo completo de una plantilla de informe predefinido:

```typescript
interface Template {
  guid: string;                    // UUID único de la plantilla
  title: string;                   // Nombre/título de la plantilla
  study_type_id: string;           // UUID del tipo de estudio asociado
  study_type_description?: string; // Descripción del tipo de estudio (solo en lista)
  findings: string;                // Texto de hallazgos/findings
  technique: string;               // Descripción de la técnica utilizada
  impression: string;              // Impresión diagnóstica
  conclusion: string;              // Conclusiones del estudio
}
```

### CreateTemplateRequest

Datos requeridos para crear una nueva plantilla:

```typescript
interface CreateTemplateRequest {
  title: string;                   // Requerido
  study_type_id: string;           // Requerido
  findings?: string;               // Opcional
  technique?: string;              // Opcional
  impression?: string;             // Opcional
  conclusion?: string;             // Opcional
  is_default?: boolean;            // Opcional, default: false
}
```

### UpdateTemplateRequest

Datos para actualizar una plantilla existente:

```typescript
interface UpdateTemplateRequest {
  title?: string;
  study_type_id?: string;
  findings?: string;
  technique?: string;
  impression?: string;
  conclusion?: string;
}
```

---

## Ejemplos de Uso en React/TypeScript

### Listar Plantillas

```typescript
const fetchTemplates = async (studyTypeId?: string) => {
  try {
    const url = studyTypeId 
      ? `/api/templates?study_type_id=${studyTypeId}`
      : '/api/templates';
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
      }
    });
    
    const result = await response.json();
    
    if (result.success) {
      setTemplates(result.data);
    }
  } catch (error) {
    console.error('Error al cargar plantillas:', error);
  }
};
```

### Crear Nueva Plantilla

```typescript
const createTemplate = async (templateData: CreateTemplateRequest) => {
  try {
    const response = await fetch('/api/templates', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(templateData)
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('Plantilla creada:', result.data.guid);
      // Recargar lista de plantillas
      await fetchTemplates();
    } else {
      console.error('Error:', result.message);
    }
  } catch (error) {
    console.error('Error al crear plantilla:', error);
  }
};
```

### Editar Plantilla

```typescript
const updateTemplate = async (templateId: string, updates: UpdateTemplateRequest) => {
  try {
    const response = await fetch(`/api/templates/${templateId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updates)
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('Plantilla actualizada');
      await fetchTemplates();
    }
  } catch (error) {
    console.error('Error al actualizar plantilla:', error);
  }
};
```

### Eliminar Plantilla

```typescript
const deleteTemplate = async (templateId: string) => {
  if (!confirm('¿Estás seguro de eliminar esta plantilla?')) {
    return;
  }
  
  try {
    const response = await fetch(`/api/templates/${templateId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      }
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('Plantilla eliminada');
      await fetchTemplates();
    }
  } catch (error) {
    console.error('Error al eliminar plantilla:', error);
  }
};
```

---

## Notas Importantes

1. **Autenticación**: Todos los endpoints requieren un token JWT válido. Sin autenticación, retornarán error 401.

2. **Plantillas Default**: Al crear una plantilla con `is_default: true`, se establece como plantilla predeterminada para ese tipo de estudio. Solo puede haber una plantilla default por tipo de estudio.

3. **Eliminación de Plantillas Default**: Si se elimina una plantilla que está marcada como default, la referencia en `isstudytype.default_predef_id` se limpia automáticamente.

4. **Campos de Texto**: Los campos `findings`, `technique`, `impression` y `conclusion` pueden contener texto largo con saltos de línea.

5. **Validaciones**: 
   - El `title` es obligatorio y no puede estar vacío
   - El `study_type_id` es obligatorio y debe ser un UUID válido de un tipo de estudio existente

6. **Performance**: El endpoint de listado retorna todas las plantillas sin paginación. Si el número de plantillas crece significativamente, considerar agregar paginación.

---

## Base de Datos

### Tabla: `nextris.tbinfpredef`

```sql
CREATE TABLE nextris.tbinfpredef (
    guid UUID PRIMARY KEY,
    tittle VARCHAR(255),              -- Título de la plantilla
    findings TEXT,                    -- Hallazgos
    impression TEXT,                  -- Impresión diagnóstica
    technique TEXT,                   -- Técnica utilizada
    conclusion TEXT,                  -- Conclusiones
    studytype_id UUID,                -- FK a isstudytype
    FOREIGN KEY (studytype_id) REFERENCES nextris.isstudytype(guid)
);
```

### Relación con Study Types

```sql
-- La tabla isstudytype tiene un campo opcional para plantilla default
ALTER TABLE nextris.isstudytype 
ADD COLUMN default_predef_id UUID REFERENCES nextris.tbinfpredef(guid);
```

---

## Historial de Cambios

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2026-01-11 | Versión inicial de la API de Templates |

---

## Soporte

Para reportar problemas o solicitar nuevas funcionalidades, contactar al equipo de desarrollo.

**Archivo de implementación:** `/var/www/nextris-dev-react/apps/api/templates.py`
**Archivo de tests:** `/var/www/nextris-dev-react/tests/test_templates_api.py`
