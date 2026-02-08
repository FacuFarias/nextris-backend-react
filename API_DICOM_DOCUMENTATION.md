# API REST - NextRIS DICOM

APIs RESTful para consumo desde aplicaciones React y clientes externos.

## Base URL

```
http://148.230.72.8:5001/api
```

## Autenticación

Todas las APIs requieren autenticación mediante **JWT (JSON Web Token)**.

Incluir el token en el header de cada request:
```
Authorization: Bearer <token>
```

---

## Endpoints Disponibles

### 1. Health Check

**GET** `/api/health`

Verifica que la API está funcionando.

**Response:**
```json
{
  "success": true,
  "message": "NextRIS API is running",
  "version": "1.0.0"
}
```

---

### 2. Subir Estudio DICOM

**POST** `/api/dicom/upload`

Sube un archivo DICOM, lo valida y lo envía al PACS.

**Request:**
- Content-Type: `multipart/form-data`
- Headers: `Authorization: Bearer <token>`
- Body: 
  - `file` (archivo DICOM) - **Obligatorio**
  - `location_id` (UUID de la ubicación) - **Obligatorio**

**Response Success (200):**
```json
{
  "success": true,
  "message": "Archivo DICOM procesado exitosamente",
  "data": {
    "guid": "uuid-del-registro",
    "filename": "20260205_120000_estudio.dcm",
    "original_filename": "estudio.dcm",
    "size": 1048576,
    "size_mb": 1.0,
    "upload_time": "2026-02-05T12:00:00",
    "dicom_info": {
      "patient_name": "PEREZ JUAN",
      "patient_id": "12345678",
      "study_date": "20260205",
      "study_time": "120000",
      "modality": "CT",
      "study_instance_uid": "1.2.3.4.5...",
      "accession_number": "ACC001"
    },
    "pacs_status": "success",
    "pacs_message": "Enviado al PACS exitosamente",
    "uploaded_by": "username"
  }
}
```

**Response Error (400/500):**
```json
{
  "success": false,
  "error": "Mensaje de error"
}
```

---

### 3. Listar Estudios No Vinculados

**GET** `/api/dicom/unlinked-studies`

Lista todos los estudios DICOM cargados que NO están vinculados a ninguna orden.

**Headers:**
- `Authorization: Bearer <token>`

**Query Parameters:**
- `location_id` (opcional): UUID de la ubicación para filtrar estudios

**Response (200):**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "guid": "uuid",
        "filename": "20260205_120000_estudio.dcm",
        "patient_name": "PEREZ JUAN",
        "patient_id": "12345678",
        "study_date": "20260205",
        "study_time": "120000",
        "study_description": "TC ABDOMEN",
        "modality": "CT",
        "study_instance_uid": "1.2.3.4.5...",
        "accession_number": "ACC001",
        "upload_date": "2026-02-05T12:00:00",
        "uploaded_by": "username",
        "pacs_status": "success",
        "file_size_mb": 1.5
      }
    ],
    "total": 1
  }
}
```

---

### 4. Buscar Exámenes Sin Imagen

**GET** `/api/dicom/search-examinations`

Busca exámenes existentes en el sistema que NO tienen imágenes asociadas (isimage = 0).

**Headers:**
- `Authorization: Bearer <token>`

**Query Parameters:**
- `location_id` (**obligatorio**): UUID de la ubicación
- `patient_name` (opcional): Nombre del paciente (búsqueda parcial)
- `patient_id` (opcional): DNI/ID del paciente
- `accession` (opcional): Número de acceso
- `date_from` (opcional): Fecha desde (YYYY-MM-DD)
- `date_to` (opcional): Fecha hasta (YYYY-MM-DD)

**Ejemplo:**
```
GET /api/dicom/search-examinations?location_id=uuid-location&patient_name=Juan&patient_id=12345678
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "guid": "uuid-del-examen",
        "accession": "ACC001",
        "patient_name": "PEREZ JUAN",
        "patient_id": "12345678",
        "date": "2026-02-05T10:00:00",
        "study_type": "TC ABDOMEN",
        "is_image": 0
      }
    ],
    "total": 1
  }
}
```

---

### 5. Vincular Estudio con Orden

**POST** `/api/dicom/link-study`

Vincula un estudio DICOM cargado manualmente con un examen/orden existente.

**Request:**
- Content-Type: `application/json`
- Headers: `Authorization: Bearer <token>`

**Body:**
```json
{
  "upload_guid": "uuid-del-estudio-cargado",
  "examination_guid": "uuid-del-examen-destino"
}
```

**Response Success (200):**
```json
{
  "success": true,
  "message": "Estudio vinculado exitosamente",
  "data": {
    "upload_guid": "uuid",
    "filename": "estudio.dcm",
    "patient_name": "PEREZ JUAN",
    "study_instance_uid": "1.2.3.4.5...",
    "linked_to": "uuid-del-examen"
  }
}
```

**Efectos:**
- Actualiza `islinked = 1` en `tbmanual_uploads`
- Actualiza `isimage = 1` en `tbexamination`
- Establece `linked_examination_guid` y `linked_date`

**Response Error (400/404/500):**
```json
{
  "success": false,
  "error": "Mensaje de error"
}
```

---

## Códigos de Estado HTTP

- `200 OK`: Operación exitosa
- `400 Bad Request`: Datos inválidos o faltantes
- `404 Not Found`: Recurso no encontrado
- `500 Internal Server Error`: Error del servidor

---

## Ejemplos de Uso

### JavaScript/React

```javascript
// Función auxiliar para obtener token del localStorage
const getAuthToken = () => localStorage.getItem('token');

// 1. Subir archivo DICOM
const uploadDicom = async (file, locationId) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('location_id', locationId);
  
  const response = await fetch('http://148.230.72.8:5001/api/dicom/upload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: formData
  });
  
  const data = await response.json();
  return data;
};

// 2. Obtener estudios no vinculados (con filtro opcional por location_id)
const getUnlinkedStudies = async (locationId = null) => {
  const url = new URL('http://148.230.72.8:5001/api/dicom/unlinked-studies');
  if (locationId) {
    url.searchParams.append('location_id', locationId);
  }
  
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    }
  });
  
  const data = await response.json();
  return data.data.data; // data.data.data por el formato anidado
};

// 3. Buscar exámenes sin imagen (location_id obligatorio)
const searchExams = async (locationId, filters = {}) => {
  const params = new URLSearchParams({ 
    location_id: locationId,
    ...filters  // { patient_name, patient_id, accession, date_from, date_to }
  });
  
  const response = await fetch(
    `http://148.230.72.8:5001/api/dicom/search-examinations?${params}`,
    {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      }
    }
  );
  
  const data = await response.json();
  return data.data.data; // data.data.data por el formato anidado
};

// 4. Vincular estudio
const linkStudy = async (uploadGuid, examGuid) => {
  const response = await fetch('http://148.230.72.8:5001/api/dicom/link-study', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      upload_guid: uploadGuid,
      examination_guid: examGuid
    })
  });
  
  const data = await response.json();
  return data;
};
```

### cURL

```bash
# Health Check
curl http://148.230.72.8:5001/api/health

# Subir archivo (requiere JWT token)
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@estudio.dcm" \
  -F "location_id=uuid-location" \
  http://148.230.72.8:5001/api/dicom/upload

# Listar estudios no vinculados (sin filtro)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://148.230.72.8:5001/api/dicom/unlinked-studies

# Listar estudios no vinculados (filtrado por location_id)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://148.230.72.8:5001/api/dicom/unlinked-studies?location_id=uuid-location"

# Buscar exámenes (location_id obligatorio)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://148.230.72.8:5001/api/dicom/search-examinations?location_id=uuid-location&patient_name=Juan"

# Vincular estudio
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"upload_guid":"uuid1","examination_guid":"uuid2"}' \
  http://148.230.72.8:5001/api/dicom/link-study
```

---

## Notas Importantes

1. **CORS**: Si consumes la API desde un dominio diferente, necesitas configurar CORS en el servidor Flask
2. **Autenticación**: Todas las APIs requieren una sesión autenticada (login previo)
3. **Límites**: El endpoint de búsqueda retorna máximo 100 resultados
4. **PACS**: Los archivos se envían automáticamente al PACS en `148.230.72.8:11112`
5. **Almacenamiento**: Los archivos DICOM se guardan en `/var/www/nextris-dev-react/uploads_dicom/`

---

## Ubicación de Archivos

- **API Routes**: `/var/www/nextris-dev-react/apps/api/dicom_routes.py`
- **Blueprint**: `/var/www/nextris-dev-react/apps/api/__init__.py`
- **Uploads**: `/var/www/nextris-dev-react/uploads_dicom/`
- **Database**: PostgreSQL - `pacsdb.nextris.tbmanual_uploads` y `pacsdb.nextris.tbexamination`
