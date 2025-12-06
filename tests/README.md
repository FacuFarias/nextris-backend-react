# Tests de API - NextRIS

Esta carpeta contiene las suites de prueba para las APIs REST del sistema NextRIS.

## 📂 Estructura

```
tests/
├── test_api_interactive.py    # Suite interactiva con menú de selección
├── test_auth_api.py            # Tests automatizados API de Autenticación (12 tests)
├── test_patients_api.py        # Tests automatizados API de Pacientes (18 tests)
├── test_studies_api.py         # Tests automatizados API de Estudios (18 tests)
├── test_admin_api.py           # Tests automatizados API de Administración (10 tests)
├── test_appointments_api.py    # Tests automatizados API de Citas/Agenda (11 tests)
├── test_institutional_api.py   # Tests automatizados API de Información Institucional (8 tests)
├── test_medical_api.py         # Tests automatizados API de Médicos y Usuarios (14 tests)
└── README.md                   # Este archivo
```

## 🚀 Test Suite Interactivo

### Uso

```bash
cd /var/www/nextris-dev-react/tests
python3 test_api_interactive.py
```

### Características

- **Menú principal** con selección de módulos:
  - API de Autenticación (6 endpoints)
  - API de Pacientes (20 endpoints)
  - API de Estudios/Exámenes (19 endpoints)
  - API de Administración (6 endpoints)
  - API de Citas/Agenda (7 endpoints)
  - API de Información Institucional (2 endpoints)
  - API de Médicos y Usuarios (7 endpoints)

- **Login automático** con credenciales configuradas
- **Menú por módulo** listando todos los endpoints disponibles
- **Ejecución individual** de cada endpoint
- **Captura de IDs** automática para uso en tests subsiguientes
- **Formato de respuesta** en JSON legible

### Flujo de uso

1. El script realiza login automáticamente
2. Selecciona el módulo (Pacientes o Estudios)
3. Elige el endpoint a probar
4. Ingresa parámetros requeridos (o usa valores por defecto)
5. Visualiza la respuesta completa
6. Vuelve al menú para probar otro endpoint

### Ejemplos de uso

**Listar pacientes:**
- Módulo 1 → Opción 1
- No requiere parámetros adicionales

**Buscar paciente por ID:**
- Módulo 1 → Opción 6
- Usa el último GUID capturado o ingresa uno específico

**Ver tipos de estudios:**
- Módulo 2 → Opción 9
- No requiere parámetros

**Obtener detalles de examen:**
- Módulo 2 → Opción 1
- Ingresa GUID del examen

## 🤖 Tests Automatizados

### Test de API de Autenticación

```bash
python3 test_auth_api.py
```

**Cobertura:** 6 endpoints, 12 tests
- ✅ 100% de tests pasando
- Login staff y pacientes
- Validación de credenciales
- Gestión de tokens JWT
- Refresh token
- Logout y verificación de sesión
- Casos de error (401, 400, 422)

### Test de API de Pacientes

```bash
python3 test_patients_api.py
```

**Cobertura:** 20 endpoints, 18 tests
- ✅ 100% de tests pasando
- CRUD completo de pacientes
- Búsqueda y filtrado
- Fusión de pacientes
- Historial y estadísticas
- Reasignación de estudios

### Test de API de Estudios

```bash
python3 test_studies_api.py
```

**Cobertura:** 19 endpoints, 18 tests
- ✅ 88.9% de tests pasando (16/18)
- Gestión de exámenes
- Worklist DICOM
- Asignación a médicos
- Órdenes y reportes
- Distribución de estudios

**Tests pendientes:**
- Test 11: GET /examinations/<exam_id>/report-data (problema de columna)
- Test 13: POST /examinations/verify-assignability (sin datos de prueba)

### Test de API de Administración

```bash
python3 test_admin_api.py
```

**Cobertura:** 6 endpoints, 10 tests
- ✅ 100% de tests pasando
- Gestión administrativa de exámenes
- Actualización de estados
- Gestión de equipos/máquinas
- Relación equipos-tipos de estudio
- Configuración de días laborables
- Control de acceso y autorización

## ⚙️ Configuración

### Variables de entorno

Los tests usan las siguientes configuraciones por defecto:

```python
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME = "sysadmin"
PASSWORD = "1234"
```

Para cambiar estas configuraciones, edita el archivo correspondiente o define variables de entorno.

### Requisitos

- Python 3.8+
- Biblioteca `requests`
- Servidor Flask corriendo en puerto 5001
- Base de datos PostgreSQL con datos de prueba

### Instalación de dependencias

```bash
pip install requests
```

## 📊 Resultados de Tests

### API de Autenticación
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 12
Tests exitosos: 12
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

### API de Pacientes
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 18
Tests exitosos: 18
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

### API de Estudios
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 18
Tests exitosos: 16
Tests fallidos: 2
Tasa de éxito: 88.9%
==========================================================

Fallos:
- Test 11: GET /examinations/<exam_id>/report-data
- Test 13: POST /examinations/verify-assignability
```

### API de Administración
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 10
Tests exitosos: 10
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

### Test de API de Citas/Agenda

```bash
python3 test_appointments_api.py
```

**Cobertura:** 7 endpoints, 11 tests
- ✅ 100% de tests pasando
- Creación de citas (doctor/equipo)
- Listado con filtros (fecha, admisionado)
- Actualización de datos de cita
- Reprogramación de citas
- Eventos del calendario con horas laborables
- Eliminación de citas
- Validación de campos requeridos
- Control de autorización (401)

**Endpoints:**
1. `POST /appointments/calendar-events` - Obtener eventos para calendario
2. `POST /appointments` - Crear nueva cita
3. `GET /appointments` - Listar citas con filtros
4. `PATCH /appointments/<id>` - Actualizar cita
5. `PATCH /appointments/<id>/reschedule` - Reprogramar cita
6. `POST /appointments/<id>/admit` - Admisionar cita (crear examen)
7. `DELETE /appointments/<id>` - Eliminar cita

**Resultados:**
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 11
Tests exitosos: 11
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

### Test de API de Información Institucional

```bash
python3 test_institutional_api.py
```

**Cobertura:** 2 endpoints, 8 tests
- ✅ 100% de tests pasando
- Obtención de información institucional
- Actualización de datos (nombre, dirección, email, teléfono)
- Upload y procesamiento de logo (redimensionado a 100x100px)
- Soporte para múltiples formatos de imagen (PNG, JPG)
- Validación de campos requeridos
- Control de autorización (401)
- Soporte para métodos POST y PUT

**Endpoints:**
1. `GET /institutional/info` - Obtener información institucional
2. `POST/PUT /institutional/info` - Actualizar información institucional (con/sin logo)

**Resultados:**
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 8
Tests exitosos: 8
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

### Test de API de Médicos y Usuarios

```bash
python3 test_medical_api.py
```

**Cobertura:** 7 endpoints, 14 tests
- ✅ 100% de tests pasando
- Gestión de médicos y doctores
- Obtención de grupos de estudio por médico
- Verificación de pertenencia a grupos
- Filtrado de médicos por tipo de estudio
- CRUD completo de usuarios del sistema
- Validación de campos requeridos
- Control de autorización (401)

**Endpoints:**
1. `GET /doctors` - Lista de médicos (con filtro activos)
2. `GET /doctors/<id>/groups` - Grupos de estudio del médico
3. `POST /doctors/check-group-membership` - Verificar pertenencia a grupo
4. `POST /doctors/by-study-type` - Médicos por tipo de estudio
5. `GET /users` - Lista completa de usuarios
6. `POST /users` - Crear nuevo usuario
7. `PATCH/PUT /users/<id>` - Actualizar usuario

**Resultados:**
```
==================== RESUMEN DE TESTS ====================
Tests ejecutados: 14
Tests exitosos: 14
Tests fallidos: 0
Tasa de éxito: 100.0%
==========================================================
```

## 🔍 Debugging

### Ver logs del servidor

```bash
cd /var/www/nextris-dev-react
tail -f logs/gunicorn-error.log
```

### Verificar que el servidor esté corriendo

```bash
curl http://127.0.0.1:5001/api/auth/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"sysadmin","password":"1234","user_type":"staff"}'
```

### Ejecutar un endpoint específico con curl

```bash
# Login y obtener token
TOKEN=$(curl -s http://127.0.0.1:5001/api/auth/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"sysadmin","password":"1234","user_type":"staff"}' \
  | jq -r '.data.access_token')

# Usar el token
curl http://127.0.0.1:5001/api/patients \
  -H "Authorization: Bearer $TOKEN"
```

## 📝 Notas

- Los tests crean datos de prueba temporales
- Se recomienda usar una base de datos de desarrollo
- Algunos endpoints requieren datos existentes en la base de datos
- El test interactivo captura GUIDs automáticamente para facilitar pruebas secuenciales
- Los tests de autenticación verifican el comportamiento de JWT stateless (tokens válidos después de logout)

## 🔗 Referencias

- Código fuente API Autenticación: `/var/www/nextris-dev-react/apps/api/auth.py`
- Documentación API Pacientes: `/var/www/nextris-frontend/API_PATIENTS_DOCUMENTATION.md`
- Código fuente API Pacientes: `/var/www/nextris-dev-react/apps/api/patients.py`
- Código fuente API Estudios: `/var/www/nextris-dev-react/apps/api/studies.py`
- Código fuente API Administración: `/var/www/nextris-dev-react/apps/api/admin.py`
- Código fuente API Citas/Agenda: `/var/www/nextris-dev-react/apps/api/appointments.py`
- Código fuente API Información Institucional: `/var/www/nextris-dev-react/apps/api/institutional.py`
- Código fuente API Médicos y Usuarios: `/var/www/nextris-dev-react/apps/api/medical.py`
