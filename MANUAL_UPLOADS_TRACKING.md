# Sistema de Tracking de Estudios DICOM Manuales

## Descripción

Sistema implementado para trackear estudios DICOM cargados manualmente y controlar su vinculación con órdenes del sistema NextRIS.

## Base de Datos

### Tabla: `nextris.tbmanual_uploads`

Registra todos los estudios DICOM cargados manualmente a través de la interfaz web.

#### Estructura

```sql
CREATE TABLE nextris.tbmanual_uploads (
    -- Identificador único
    guid VARCHAR(36) PRIMARY KEY,
    
    -- Información del archivo
    filename VARCHAR(500) NOT NULL,
    filepath VARCHAR(1000),
    file_size BIGINT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Información DICOM extraída
    patient_name VARCHAR(200),
    patient_id VARCHAR(100),
    study_date VARCHAR(20),
    study_time VARCHAR(20),
    study_description TEXT,
    modality VARCHAR(20),
    study_instance_uid VARCHAR(200) UNIQUE,
    series_instance_uid VARCHAR(200),
    sop_instance_uid VARCHAR(200),
    accession_number VARCHAR(100),
    
    -- Estado de vinculación
    islinked INTEGER DEFAULT 0,  -- 0 = No vinculado, 1 = Vinculado
    linked_examination_guid VARCHAR(36),  -- GUID del examen vinculado
    linked_date TIMESTAMP,
    
    -- Usuario que subió
    uploaded_by_user_guid VARCHAR(36),
    uploaded_by_username VARCHAR(100),
    
    -- Estado del envío al PACS
    pacs_status VARCHAR(20),  -- 'success', 'error', 'pending'
    pacs_message TEXT,
    pacs_sent_date TIMESTAMP,
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Campo `islinked`

- **0**: El estudio NO está vinculado a ninguna orden del sistema
- **1**: El estudio está vinculado a una orden existente

#### Índices

- `idx_manual_uploads_islinked`: Para búsquedas por estado de vinculación
- `idx_manual_uploads_upload_date`: Para ordenar por fecha de carga
- `idx_manual_uploads_patient_id`: Para búsquedas por ID de paciente
- `idx_manual_uploads_accession`: Para búsquedas por número de acceso
- `idx_manual_uploads_study_uid`: Para búsquedas por Study Instance UID

## Endpoints API

### 1. `/api/dicom/upload` [POST]
**Descripción**: Sube un archivo DICOM, valida su contenido, lo envía al PACS y registra en la base de datos.

**Request**: `multipart/form-data` con campo `file`

**Response**:
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
      "modality": "CT"
    },
    "pacs_status": "success",
    "uploaded_by": "username"
  }
}
```

**Acciones automáticas**:
1. Valida que es un archivo DICOM
2. Extrae metadatos DICOM
3. Envía al PACS (148.230.72.8:11112)
4. Registra en `tbmanual_uploads` con `islinked=0`

### 2. `/api/dicom/unlinked-studies` [GET]
**Descripción**: Lista todos los estudios cargados que NO están vinculados a ninguna orden.

**Response**:
```json
{
  "success": true,
  "data": {
    "studies": [
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

**Query**: Filtra por `islinked = 0`

### 3. `/api/dicom/search-examinations` [GET]
**Descripción**: Busca exámenes existentes en el sistema para vincular con estudios DICOM.

**Query Parameters**:
- `patient_name`: Nombre del paciente (búsqueda parcial)
- `patient_id`: DNI/ID del paciente
- `accession`: Número de acceso
- `date_from`: Fecha desde (YYYY-MM-DD)
- `date_to`: Fecha hasta (YYYY-MM-DD)

**Response**:
```json
{
  "success": true,
  "data": {
    "examinations": [
      {
        "guid": "uuid-del-examen",
        "accession": "ACC001",
        "patient_name": "PEREZ JUAN",
        "patient_id": "12345678",
        "date": "2026-02-05T10:00:00",
        "modality": "CT",
        "study_type": "TC ABDOMEN",
        "equipment": "Equipo 1",
        "is_reported": 0,
        "is_publicated": 0
      }
    ],
    "total": 1
  }
}
```

### 4. `/api/dicom/link-study` [POST]
**Descripción**: Vincula un estudio DICOM cargado con un examen existente.

**Request**:
```json
{
  "upload_guid": "uuid-del-estudio-cargado",
  "examination_guid": "uuid-del-examen-destino"
}
```

**Response**:
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

**Acciones**:
1. Verifica que el examen existe
2. Actualiza `islinked = 1`
3. Establece `linked_examination_guid`
4. Registra `linked_date`

## Workflow

### 1. Carga Manual de Estudios

```
Usuario → Upload DICOM → Validación → PACS → DB
                                        ↓
                                   islinked=0
```

### 2. Consulta de Estudios No Vinculados

```sql
SELECT * FROM nextris.tbmanual_uploads 
WHERE islinked = 0
ORDER BY upload_date DESC;
```

### 3. Vinculación con Orden Existente

```
Buscar Orden → Seleccionar → Vincular → islinked=1
                                          ↓
                                linked_examination_guid
```

## Queries Útiles

### Ver todos los estudios no vinculados
```sql
SELECT 
    filename,
    patient_name,
    patient_id,
    study_date,
    modality,
    upload_date,
    uploaded_by_username
FROM nextris.tbmanual_uploads
WHERE islinked = 0
ORDER BY upload_date DESC;
```

### Ver estudios vinculados con su orden
```sql
SELECT 
    mu.filename,
    mu.patient_name,
    mu.study_date,
    e.localacc,
    mu.linked_date
FROM nextris.tbmanual_uploads mu
INNER JOIN nextris.tbexamination e ON mu.linked_examination_guid = e.guid
WHERE mu.islinked = 1
ORDER BY mu.linked_date DESC;
```

### Contar estudios por estado
```sql
SELECT 
    CASE islinked 
        WHEN 0 THEN 'No vinculado'
        WHEN 1 THEN 'Vinculado'
    END as estado,
    COUNT(*) as cantidad
FROM nextris.tbmanual_uploads
GROUP BY islinked;
```

### Ver estudios por usuario
```sql
SELECT 
    uploaded_by_username,
    COUNT(*) as total_uploads,
    SUM(CASE WHEN islinked = 0 THEN 1 ELSE 0 END) as no_vinculados,
    SUM(CASE WHEN islinked = 1 THEN 1 ELSE 0 END) as vinculados
FROM nextris.tbmanual_uploads
GROUP BY uploaded_by_username
ORDER BY total_uploads DESC;
```

## Interfaz Web

### Pestaña "Cargar Estudio DICOM"
- Drag & drop de archivos DICOM
- Validación automática
- Envío al PACS
- Registro en base de datos

### Pestaña "Vincular Imagen" (en desarrollo)
- Búsqueda de estudios no vinculados
- Búsqueda de órdenes existentes
- Vinculación manual

## Seguridad

- Todos los endpoints requieren autenticación (`@login_required`)
- Los archivos se almacenan con nombres seguros (`secure_filename`)
- Se registra el usuario que realizó la carga
- Foreign keys mantienen integridad referencial

## Ubicación de Archivos

- **Controlador**: `/var/www/nextris-dev-react/apps/home/controllers/upload_studies.py`
- **Script SQL**: `/var/www/nextris-dev-react/scripts/create_tbmanual_uploads.sql`
- **Template**: `/var/www/nextris-dev-react/apps/templates/home/cargar_estudio.html`
- **JavaScript**: `/var/www/nextris-dev-react/apps/static/assets/js/uploadStudies.js`
- **Uploads**: `/var/www/nextris-dev-react/uploads_dicom/`

## Instalación

```bash
# Crear la tabla
PGPASSWORD='pacs' psql -U pacs -h localhost -d pacsdb \
  -f /var/www/nextris-dev-react/scripts/create_tbmanual_uploads.sql

# Reiniciar servicio
sudo systemctl restart nextris-dev-react
```
