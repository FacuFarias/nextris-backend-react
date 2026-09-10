# API REST NextRIS - Documentación

## Módulos Implementados

### 1. **Authentication API** (`auth.py`)
- **Endpoints:** 6
- **Tests:** 12 (100%)
- **Funcionalidad:** Login, registro, cambio de contraseña, tokens JWT

### 2. **Patients API** (`patients.py`)
- **Endpoints:** 20
- **Tests:** 18 (100%)
- **Funcionalidad:** CRUD de pacientes, búsqueda, historial médico

### 3. **Studies API** (`studies.py`)
- **Endpoints:** 19
- **Tests:** 18 (88.9%)
- **Funcionalidad:** Gestión de estudios, exámenes, tipos de estudio

### 4. **Admin API** (`admin.py`)
- **Endpoints:** 6
- **Tests:** 10 (100%)
- **Funcionalidad:** Configuración del sistema, gestión de usuarios admin

### 5. **Appointments API** (`appointments.py`)
- **Endpoints:** 7
- **Tests:** 11 (100%)
- **Funcionalidad:** Gestión de turnos y citas médicas

### 6. **Institutional API** (`institutional.py`)
- **Endpoints:** 2
- **Tests:** 8 (100%)
- **Funcionalidad:** Gestión de sucursales y centros médicos

### 7. **Medical API** (`medical.py`)
- **Endpoints:** 7
- **Tests:** 14 (100%)
- **Funcionalidad:** Gestión de médicos, grupos médicos, usuarios del sistema

### 8. **Reports API** (`reports.py`)
- **Endpoints:** 11
- **Tests:** 15 (100%)
- **Funcionalidad:** Gestión de reportes médicos, plantillas predefinidas, PDFs

#### Endpoints de Reports API:

1. **GET** `/report-templates/<template_id>` - Obtener plantilla de reporte
2. **GET** `/study-types/<study_type_id>/default-template` - Plantilla por defecto
3. **GET** `/predefined-reports` - Listar reportes predefinidos
4. **GET** `/predefined-reports/<predef_id>` - Obtener reporte predefinido
5. **POST** `/predefined-reports` - Crear reporte predefinido
6. **PATCH/PUT** `/predefined-reports/<predef_id>` - Actualizar predefinido
7. **PATCH/PUT** `/reports/<exam_id>` - Guardar datos de reporte
8. **POST** `/reports/<exam_id>/sign` - Firmar reporte
9. **POST** `/reports/<exam_id>/unsign` - Quitar firma de reporte
10. **GET** `/reports/<exam_id>/pdf` - Obtener PDF del reporte

### 9. **Config API** (`config.py`) ✨ NUEVO
- **Endpoints:** 14
- **Tests:** 20 (100%)
- **Funcionalidad:** Configuración del sistema, tipos de estudio, equipos, ubicaciones

#### Endpoints de Config API:

1. **GET** `/config/system` - Obtener configuración del sistema
2. **PUT/PATCH** `/config/system` - Actualizar configuración
3. **GET/PUT** `/config/workflow` - Consultar o configurar el retardo de envío de reportes firmados a Clínica Parque
4. **GET** `/config/modalities` - Listar modalidades
5. **GET** `/config/body-parts` - Listar partes del cuerpo
6. **GET** `/config/study-groups` - Listar grupos de estudio
7. **GET** `/config/study-types` - Listar tipos de estudio
8. **POST** `/config/study-types` - Crear tipo de estudio
9. **PUT/PATCH** `/config/study-types/<id>` - Actualizar tipo de estudio
10. **DELETE** `/config/study-types/<id>` - Eliminar tipo de estudio
11. **GET** `/config/equipment` - Listar equipos
12. **POST** `/config/equipment` - Crear equipo
13. **DELETE** `/config/equipment/<id>` - Eliminar equipo
14. **GET** `/config/locations` - Listar ubicaciones
15. **POST** `/config/locations` - Crear ubicación
16. **DELETE** `/config/locations/<id>` - Eliminar ubicación

## Estadísticas Globales

- **Total de Endpoints:** 92
- **Total de Tests:** 126
- **Cobertura Promedio:** ~98%

## Ejecutar Tests

### Test Individual
```bash
cd /var/www/nextris-dev-react
python3 tests/test_reports_api.py
```

### Todos los Tests
```bash
cd /var/www/nextris-dev-react/tests
python3 test_auth_api.py
python3 test_patients_api.py
python3 test_studies_api.py
python3 test_admin_api.py
python3 test_appointments_api.py
python3 test_institutional_api.py
python3 test_medical_api.py
python3 test_reports_api.py
python3 test_config_api.py
```

## Autenticación

Todos los endpoints (excepto `/auth/login` y `/auth/register`) requieren autenticación JWT.

### Headers requeridos:
```
Authorization: Bearer <token>
Content-Type: application/json
```

## Credenciales de Prueba

- **Usuario:** sysadmin
- **Contraseña:** 1234

## Estructura de Respuestas

Todas las respuestas siguen el formato estándar:

```json
{
  "success": true|false,
  "message": "Mensaje descriptivo",
  "data": {...}  // Opcional
}
```

## Base de Datos

- **Motor:** PostgreSQL
- **Host:** 148.230.72.8
- **Schema:** nextris
- **Puerto:** 5001 (API)

## Tablas Utilizadas por Reports API

- `nextris.isreporttemplate` - Plantillas de reportes
- `nextris.tbinfpredef` - Reportes predefinidos
- `nextris.tbreport` - Reportes de exámenes
- `nextris.tbexamination` - Exámenes
- `nextris.isstudytype` - Tipos de estudio

## Tablas Utilizadas por Config API

- `nextris.isstudytype` - Tipos de estudio
- `nextris.isstudytypegroup` - Grupos de estudio
- `nextris.ismodality` - Modalidades
- `nextris.isanatomicalpart` - Partes del cuerpo
- `nextris.isequipment` - Equipos médicos
- `nextris.tblocation` - Ubicaciones/Sucursales
- `nextris.config_workflow` - Configuración de workflow

## Próximos Módulos

- Billing API
- Notifications API
- Analytics API
# Reportes: contrato canónico

Los endpoints de reportes y plantillas aceptan y devuelven `study_reason`,
`content` y `conclusion`. Los nombres históricos (`findings`, `techniques`,
`impressions`, `conclusions`) siguen disponibles únicamente como aliases
deprecados para clientes legacy.
