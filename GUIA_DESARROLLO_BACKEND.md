# 🔧 Guía de Desarrollo Backend - NextRIS

> **Autor:** Equipo NextRIS  
> **Fecha:** 30 de Noviembre 2025  
> **Proyecto:** Multitenant-NextRIS (Backend)

---

## 📋 Índice

1. [Arquitectura del Proyecto](#arquitectura)
2. [Configuración Inicial](#configuración-inicial)
3. [Workflow de Desarrollo](#workflow)
4. [Trabajar con el Frontend](#frontend)
5. [Base de Datos](#base-de-datos)
6. [Testing y Debugging](#testing)
7. [Despliegue](#despliegue)
8. [Comandos Útiles](#comandos)

---

## 🏗️ Arquitectura del Proyecto {#arquitectura}

```
Multitenant-NextRIS/
├── apps/
│   ├── authentication/      # Sistema de login/usuarios
│   ├── home/
│   │   ├── controllers/     # Lógica de negocio
│   │   ├── models/          # Modelos de datos
│   │   ├── services/        # Servicios (HL7, DB, Config)
│   │   └── utils/           # Utilidades
│   ├── static/              # ⚠️ SINCRONIZADO desde frontend
│   └── templates/           # ⚠️ SINCRONIZADO desde frontend
├── frontend/                # 📦 Git submodule (repositorio separado)
├── deployment/              # Scripts de deploy
├── .env                     # Variables de entorno
└── run.py                   # Punto de entrada
```

### ⚠️ IMPORTANTE: Archivos sincronizados

**NO MODIFIQUES DIRECTAMENTE:**
- `apps/static/` - Se sobrescribe desde `frontend/static/`
- `apps/templates/` - Se sobrescribe desde `frontend/templates/`

**SÍ PUEDES MODIFICAR:**
- `apps/authentication/` - Sistema de autenticación
- `apps/home/controllers/` - Controladores
- `apps/home/models/` - Modelos
- `apps/home/services/` - Servicios backend
- `apps/config.py` - Configuración Flask
- `.env` - Variables de entorno

---

## ⚙️ Configuración Inicial {#configuración-inicial}

### 1. Clonar el repositorio

```powershell
cd D:\Softinhealth
git clone https://github.com/FacuFarias/Multitenant-NextRIS.git
cd Multitenant-NextRIS
git checkout feature/1
```

### 2. Inicializar el submódulo frontend

```powershell
git submodule init
git submodule update
```

Esto descarga el frontend en la carpeta `/frontend/`

### 3. Crear entorno virtual Python

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 4. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 5. Configurar variables de entorno

Edita el archivo `.env`:

```env
# Base de datos
DB_ENGINE=postgresql
DB_NAME=pacsdb
DB_HOST=148.230.72.8
DB_PORT=5432
DB_USERNAME=pacs
DB_PASSWORD=pacs

# Flask
SECRET_KEY=tu_clave_secreta_aqui
DEBUG=True

# Servidor
IPSERVER=148.230.72.8
PORT=5000

# DICOM Viewer
DICOM_VIEWER_URL=https://viewer.nextris.cloud/

# Assets
ASSETS_ROOT=/static/assets
```

### 6. Sincronizar frontend inicial

```powershell
.\update-frontend.ps1
```

Este script copia `frontend/static/` y `frontend/templates/` a `apps/`

---

## 🔄 Workflow de Desarrollo {#workflow}

### Flujo típico de trabajo:

```
1. Actualizar código → 2. Hacer cambios backend → 3. Probar local → 4. Commit → 5. Push
```

### 1. Antes de empezar a trabajar

```powershell
# Activar entorno virtual
.\venv\Scripts\activate

# Actualizar código del repositorio
git pull origin feature/1

# Actualizar submódulo frontend (si el frontend cambió)
git submodule update --remote --merge

# Sincronizar archivos frontend
.\update-frontend.ps1
```

### 2. Hacer cambios en el backend

Trabaja normalmente en:
- `apps/authentication/` - Sistema de usuarios
- `apps/home/controllers/` - Lógica de negocio
- `apps/home/models/` - Modelos de datos
- `apps/home/services/` - Servicios (HL7, Database, Config)
- `apps/home/routes.py` - Rutas/endpoints

### 3. Ejecutar en local para probar

```powershell
python run.py
```

La aplicación estará en: `http://localhost:5000`

### 4. Commit tus cambios

```powershell
git add .
git commit -m "Descripción clara del cambio"
```

### 5. Push al repositorio

```powershell
git push origin feature/1
```

---

## 🎨 Trabajar con el Frontend {#frontend}

### ¿Cuándo necesito actualizar el frontend?

**El programador frontend hace cambios → Tú necesitas sincronizarlos**

### Actualizar frontend manualmente

```powershell
# Opción 1: Usando el script
.\update-frontend.ps1

# Opción 2: Manual
git submodule update --remote --merge
Remove-Item -Recurse -Force apps\static, apps\templates
Copy-Item -Recurse frontend\static apps\static
Copy-Item -Recurse frontend\templates apps\templates
```

### Ver cambios del frontend

```powershell
cd frontend
git log --oneline -10
```

### ¿Necesito hacer commit del submódulo?

**Sí, si actualizaste el frontend:**

```powershell
git add frontend
git commit -m "Actualizar submódulo frontend a última versión"
git push origin feature/1
```

---

## 🗄️ Base de Datos {#base-de-datos}

### Conexión a PostgreSQL

**Datos de conexión:**
- Host: `148.230.72.8`
- Puerto: `5432`
- Database: `pacsdb`
- Usuario: `pacs`
- Password: `pacs`

### Conectar con pgAdmin o cliente SQL

```
postgresql://pacs:pacs@148.230.72.8:5432/pacsdb
```

### Tablas principales

```sql
-- Usuarios del sistema
nextris.tbuser

-- Pacientes
nextris.tbuser_patient

-- Citas
nextris.tb_appointment

-- Órdenes
nextris.tb_order

-- Estudios
nextris.tb_study

-- Exámenes
nextris.tb_examination
```

### Consultas útiles

```python
# En tus controladores
from apps.home.services.database_service import DatabaseService

db = DatabaseService()

# Obtener conexión
conn = db.get_connection()
cursor = conn.cursor()

# Ejecutar query
cursor.execute("SELECT * FROM nextris.tbuser WHERE username = %s", (username,))
result = cursor.fetchone()

# Cerrar
cursor.close()
conn.close()
```

---

## 🧪 Testing y Debugging {#testing}

### Ejecutar en modo debug

Ya está configurado en `.env`:
```env
DEBUG=True
```

Cuando corres `python run.py`, Flask muestra errores detallados.

### Ver logs en tiempo real

```powershell
# En local, Flask imprime en consola
python run.py
```

### Debugging con breakpoints

Agrega en tu código:
```python
import pdb; pdb.set_trace()
```

O usa VS Code debugger:

**Configuración `.vscode/launch.json`:**
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Flask",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "run.py",
                "FLASK_ENV": "development"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "jinja": true
        }
    ]
}
```

### Testing endpoints con curl

```powershell
# Login
Invoke-WebRequest -Uri "http://localhost:5000/login" -Method GET

# API endpoint
Invoke-RestMethod -Uri "http://localhost:5000/api/patients" -Method GET
```

---

## 🚀 Despliegue {#despliegue}

### Servidor de desarrollo (VPS)

**Ubicación:** `148.230.72.8:5000`

El servidor tiene auto-actualización del **frontend**, pero **NO del backend**.

### ¿Cómo actualizar el backend en el servidor?

```powershell
# SSH al servidor
ssh root@148.230.72.8

# Ir al directorio
cd /var/www/nextris-dev

# Pull cambios del backend
sudo -u nextris git pull origin feature/1

# Reiniciar servicio
systemctl restart nextris-dev

# Ver logs
journalctl -u nextris-dev -f
```

### Ver estado del servidor

```powershell
ssh root@148.230.72.8 "systemctl status nextris-dev"
```

### Ver logs del servidor

```powershell
ssh root@148.230.72.8 "journalctl -u nextris-dev -n 50"
```

---

## 📝 Comandos Útiles {#comandos}

### Git

```powershell
# Ver estado
git status

# Ver cambios
git diff

# Ver historial
git log --oneline -10

# Crear rama nueva
git checkout -b feature/nueva-funcionalidad

# Cambiar de rama
git checkout feature/1

# Ver todas las ramas
git branch -a

# Actualizar submódulo frontend
git submodule update --remote --merge
```

### Python/Flask

```powershell
# Activar entorno virtual
.\venv\Scripts\activate

# Instalar nueva librería
pip install nombre-libreria
pip freeze > requirements.txt

# Ejecutar aplicación
python run.py

# Shell interactivo de Python
python

# Probar imports
python -c "from apps.home.controllers.patient_controller import *"
```

### Base de datos

```powershell
# Conectar a PostgreSQL desde consola
psql -h 148.230.72.8 -U pacs -d pacsdb

# Backup de base de datos
ssh root@148.230.72.8 "pg_dump -h localhost -U pacs pacsdb > backup_$(date +%Y%m%d).sql"
```

---

## 🔥 Casos Comunes

### "El frontend no se ve actualizado"

```powershell
# 1. Actualizar submódulo
git submodule update --remote --merge

# 2. Sincronizar archivos
.\update-frontend.ps1

# 3. Reiniciar Flask
# Ctrl+C y volver a ejecutar
python run.py
```

### "Error de importación de módulo"

```powershell
# Reinstalar dependencias
pip install -r requirements.txt

# Verificar entorno virtual activo
# Deberías ver (venv) en el prompt
```

### "No puedo conectar a la base de datos"

1. Verifica `.env` tenga los datos correctos
2. Verifica conectividad:
```powershell
Test-NetConnection -ComputerName 148.230.72.8 -Port 5432
```

### "El servidor da error 500"

```powershell
# Ver logs en el servidor
ssh root@148.230.72.8 "journalctl -u nextris-dev -n 100"
```

---

## 📚 Recursos Adicionales

- **Documentación Flask:** https://flask.palletsprojects.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Jinja2 Templates:** https://jinja.palletsprojects.com/
- **PostgreSQL:** https://www.postgresql.org/docs/

---

## 🆘 Soporte

- **Repositorio Backend:** https://github.com/FacuFarias/Multitenant-NextRIS
- **Repositorio Frontend:** https://github.com/FacuFarias/Multitenant-NextRIS-Frontend
- **Servidor Dev:** http://148.230.72.8:5000

---

## ⚠️ RECORDATORIOS IMPORTANTES

1. ❌ **NO modifiques** `apps/static/` ni `apps/templates/` directamente
2. ✅ **SÍ actualiza** el submódulo frontend regularmente
3. ✅ **SÍ usa** `update-frontend.ps1` después de actualizar el submódulo
4. ✅ **SÍ trabaja** en la rama `feature/1`
5. ✅ **SÍ haz commit** cuando actualices el submódulo frontend

---

**¡Listo para desarrollar! 🚀**
