# Módulo de Carga de Estudios DICOM

## Descripción
Módulo para cargar archivos DICOM y enviarlos automáticamente al PACS.

## Archivos creados

### Backend
- `/apps/home/controllers/upload_studies.py` - Controlador con todas las APIs DICOM

### Frontend
- `/apps/templates/home/cargar_estudio.html` - Plantilla HTML
- `/apps/static/assets/js/uploadStudies.js` - Lógica JavaScript

### Carpeta de uploads
- `/uploads_dicom/` - Carpeta donde se almacenan los archivos subidos

## Endpoints API

### 1. POST /api/dicom/upload
Sube un archivo DICOM individual y lo envía al PACS.

**Request:** multipart/form-data con campo 'file'
**Response:**
```json
{
  "success": true,
  "message": "Archivo DICOM procesado exitosamente",
  "data": {
    "filename": "20260205_123456_archivo.dcm",
    "original_filename": "archivo.dcm",
    "size": 1024000,
    "size_mb": 1.02,
    "upload_time": "2026-02-05T12:34:56",
    "dicom_info": {
      "patient_name": "DOE^JOHN",
      "patient_id": "12345",
      "modality": "CR",
      "study_description": "CHEST PA"
    },
    "pacs_status": "success",
    "pacs_message": "Enviado al PACS exitosamente"
  }
}
```

### 2. GET /api/dicom/files
Lista todos los archivos DICOM subidos.

**Response:**
```json
{
  "success": true,
  "data": {
    "files": [...],
    "total": 10
  }
}
```

### 3. DELETE /api/dicom/delete/<filename>
Elimina un archivo DICOM (solo Sysadmin).

### 4. POST /api/dicom/scan-path
Escanea un directorio buscando archivos DICOM.

**Request:**
```json
{
  "path": "/ruta/al/directorio"
}
```

### 5. POST /api/dicom/batch-upload
Envía múltiples archivos DICOM al PACS.

**Request:**
```json
{
  "files": [
    "/ruta/archivo1.dcm",
    "/ruta/archivo2.dcm"
  ]
}
```

## Configuración PACS

En `upload_studies.py`:
```python
PACS_HOST = '148.230.72.8'
PACS_PORT = 11112
PACS_AET = 'DCM4CHEE'
LOCAL_AET = 'NEXTRIS_UPLOADER'
```

## Permisos
- **Técnico y Sysadmin**: Pueden acceder al módulo y subir archivos
- **Sysadmin**: Puede eliminar archivos

## Características
- ✅ Drag & drop de archivos
- ✅ Selección múltiple
- ✅ Validación de archivos DICOM
- ✅ Envío automático al PACS
- ✅ Barra de progreso
- ✅ Lista de archivos subidos
- ✅ Extracción de metadata DICOM
- ✅ Manejo de errores

## Uso
1. Acceder a http://148.230.72.8:5001/cargar_estudio.html
2. Arrastrar archivos DICOM o hacer clic para seleccionar
3. Los archivos se suben automáticamente y se envían al PACS
4. Ver resultados en la lista de archivos subidos
