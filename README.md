# NextRIS Backend - React Migration

Backend API REST para el sistema de gestión de imágenes médicas NextRIS, construido con Flask y PostgreSQL.

## 🏗️ Arquitectura

- **Framework**: Flask + Gunicorn
- **Base de datos**: PostgreSQL (148.230.72.8)
- **Autenticación**: JWT (flask-jwt-extended)
- **Puerto**: 5001
- **Servicio**: `nextris-dev-react.service` (systemd)

## 📚 APIs Disponibles

El backend cuenta con **9 módulos principales** y más de **90 endpoints REST**:

### Módulos Implementados

- **Auth**: Login, registro, gestión de usuarios, patientdomains
- **Patients**: CRUD completo con auto-generación de PatientID
- **Studies**: Gestión de estudios médicos y exámenes
- **Admin**: Administración de usuarios y configuraciones
- **Appointments**: Sistema de turnos y citas
- **Institutional**: Configuración institucional
- **Medical**: Physicians y personal médico
- **Reports**: Generación de informes
- **Config**: Facilities, locations, equipment, system settings

Ver [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) para documentación completa.

## ⚙️ Configuración

### Variables de Entorno

Crear archivo `.env` basado en `env.sample`:

```bash
# Base de datos
DB_HOST=148.230.72.8
DB_PORT=5432
DB_NAME=pacs
DB_USER=pacs
DB_PASSWORD=pacs

# JWT
JWT_SECRET_KEY=your-secret-key

# Flask
FLASK_ENV=development
DEBUG=True
```

## 🚀 Instalación y Ejecución

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/FacuFarias/nextris-backend-react.git
cd nextris-backend-react

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Ejecución con Systemd

```bash
# Reiniciar servicio
sudo systemctl restart nextris-dev-react.service

# Ver estado
sudo systemctl status nextris-dev-react.service

# Ver logs
sudo journalctl -u nextris-dev-react.service -f
```

### Ejecución Manual con Gunicorn

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar con configuración de gunicorn
gunicorn --config gunicorn-cfg.py run:app

# O ejecutar en background
nohup gunicorn --config gunicorn-cfg.py run:app > /tmp/gunicorn.log 2>&1 &
```

La aplicación correrá en `http://localhost:5001`

## 🧪 Testing

El proyecto incluye tests completos para todas las APIs:

```bash
# Tests de autenticación (13 tests)
python3 tests/test_auth_api.py

# Tests de pacientes (18 tests)
python3 tests/test_patients_api.py

# Tests de estudios
python3 tests/test_studies_api.py

# Tests de configuración
python3 tests/test_config_api.py

# Y más...
```

## 🔑 Características Principales

### Auto-generación de PatientID

Los pacientes se crean automáticamente con un ID secuencial en formato `NR00000001`, `NR00000002`, etc.

```json
POST /api/patients
{
  "name": "Juan",
  "surname": "Pérez",
  "patientdomain_id": "uuid-del-dominio",
  "nationalcode": "12345678",
  "email": "juan@example.com",
  "gender": "M"
}
```

El `PatientID` se genera automáticamente.

### PatientDomains por Usuario

Endpoint para obtener los dominios de pacientes asignados a un usuario:

```bash
GET /api/auth/user/{user_id}/patientdomains
Authorization: Bearer {jwt_token}
```

### Autenticación JWT

Todas las APIs protegidas requieren token JWT:

```json
POST /api/auth/login
{
  "username": "sysadmin",
  "password": "1234"
}
```

Usar el token en las peticiones:

```bash
Authorization: Bearer {access_token}
```

## 📁 Estructura del Proyecto

```
nextris-backend-react/
├── apps/
│   ├── api/                    # APIs REST
│   │   ├── auth.py            # Autenticación y usuarios
│   │   ├── patients.py        # Gestión de pacientes
│   │   ├── studies.py         # Estudios médicos
│   │   ├── admin.py           # Administración
│   │   ├── appointments.py    # Turnos
│   │   ├── config.py          # Configuración
│   │   ├── institutional.py   # Datos institucionales
│   │   ├── medical.py         # Médicos
│   │   └── reports.py         # Informes
│   ├── authentication/        # Auth tradicional (legacy)
│   ├── home/                  # Rutas HTML (legacy)
│   └── templates/             # Templates Jinja2
├── tests/                     # Tests automatizados
├── deployment/                # Scripts de deployment
├── media/                     # Archivos multimedia
├── API_DOCUMENTATION.md      # Documentación completa
├── requirements.txt          # Dependencias Python
├── run.py                    # Entry point
└── gunicorn-cfg.py          # Configuración Gunicorn
```

## 🔗 Integración con Frontend

El backend está diseñado para trabajar con el frontend React ubicado en:

- **Repositorio**: [nextris-front-react](https://github.com/FacuFarias/nextris-front-react)
- **Puerto Frontend**: 5173 (Vite)
- **CORS**: Configurado para permitir requests desde el frontend

## 📝 Licencia

Proyecto propietario - NextRIS Medical Imaging System
