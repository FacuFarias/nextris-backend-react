# Plan de Migración NextRIS - Nuevo Servidor

## Resumen del Proyecto

NextRIS es un sistema de información de radiología (RIS) compuesto por dos aplicaciones:

| Componente | Repositorio | Tecnología | Puerto |
|---|---|---|---|
| **Backend** | `nextris-backend-react` | Python 3.12 + Flask + Gunicorn | 5001 |
| **Frontend** | `nextris-front-react` | React 19 + Vite + TypeScript | 80 (Nginx) |
| **Base de datos** | - | PostgreSQL 16 | 5432 |

### Migración de PDFs de informes (20260821)

Los informes firmados ya no se escriben en disco. Aplicar
`deployment/migrations/20260821_on_demand_report_pdfs.sql` y validar primero
que los informes firmados se renderizan correctamente desde `tbreport`. Luego,
si existe una instalación anterior, eliminar únicamente los PDFs heredados y
la carpeta de salida concreta:

```bash
find /var/www/nextris-dev-react/output_pdfs -maxdepth 1 -type f -name '*.pdf' -delete
rmdir /var/www/nextris-dev-react/output_pdfs 2>/dev/null || true
```

---

## Requisitos del Servidor

- **OS:** Ubuntu 24.04 LTS
- **RAM:** Mínimo 2GB (recomendado 4GB)
- **Disco:** Mínimo 20GB libres
- **Acceso:** Root o usuario con sudo
- **Red:** Acceso a internet para instalar dependencias

---

## Instalación Rápida (Un Solo Comando)

```bash
# Conectar al servidor
ssh root@<IP_DEL_SERVIDOR>

# Clonar el repositorio del backend (contiene los scripts de instalación)
git clone https://github.com/FacuFarias/nextris-backend-react.git /tmp/nextris-setup

# Ejecutar instalación completa
cd /tmp/nextris-setup/deployment/install
chmod +x install-all.sh
sudo bash install-all.sh
```

---

## Instalación Manual Paso a Paso

### Paso 1: Instalar Dependencias del Sistema

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias básicas
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    build-essential \
    gcc \
    libpq-dev \
    ca-certificates \
    gnupg

# Instalar Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Instalar Nginx
sudo apt install -y nginx

# Instalar PostgreSQL 16
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg
sudo apt update
sudo apt install -y postgresql-16

# Verificar instalaciones
python3 --version    # Debe ser 3.12+
node --version       # Debe ser 20+
nginx -v             # Debe ser 1.24+
psql --version       # Debe ser 16
```

### Paso 2: Configurar PostgreSQL

```bash
# Iniciar PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Crear usuario y base de datos
sudo -u postgres psql << 'EOF'
-- Crear usuario
CREATE USER pacs WITH PASSWORD 'pacs_password_cambiar';

-- Crear base de datos
CREATE DATABASE pacsdb OWNER pacs;

-- Dar permisos
GRANT ALL PRIVILEGES ON DATABASE pacsdb TO pacs;
EOF

# Crear el schema y tablas ejecutando el script SQL
# El archivo init-schema.sql está en deployment/sql/
sudo -u postgres psql -d pacsdb -f /path/to/nextris-backend-react/deployment/sql/init-schema.sql

# Dar permisos al usuario pacs sobre el schema
sudo -u postgres psql -d pacsdb << 'EOF'
GRANT ALL ON SCHEMA nextris TO pacs;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA nextris TO pacs;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nextris TO pacs;
ALTER DEFAULT PRIVILEGES IN SCHEMA nextris GRANT ALL ON TABLES TO pacs;
ALTER DEFAULT PRIVILEGES IN SCHEMA nextris GRANT ALL ON SEQUENCES TO pacs;
EOF
```

### Paso 3: Instalar Backend

```bash
# Crear directorio de la aplicación
sudo mkdir -p /var/www/nextris-dev-react

# Clonar repositorio
sudo git clone https://github.com/FacuFarias/nextris-backend-react.git /var/www/nextris-dev-react

# Crear entorno virtual de Python
cd /var/www/nextris-dev-react
sudo python3 -m venv venv

# Instalar dependencias
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt
sudo venv/bin/pip install gunicorn

# Configurar variables de entorno
sudo cp deployment/config/backend.env.example .env
# EDITAR .env con los valores correctos:
#   DB_PASS=<la contraseña que definiste>
#   SECRET_KEY=<generar con: openssl rand -hex 32>
#   IPSERVER=<IP del nuevo servidor>
sudo nano .env

# Crear directorios necesarios
sudo mkdir -p media/firmas uploads_dicom
sudo chown -R $(whoami):$(whoami) /var/www/nextris-dev-react

# Configurar servicio systemd
sudo cp deployment/config/nextris-backend.service /etc/systemd/system/
# Editar el service file si la ruta es diferente
sudo systemctl daemon-reload
sudo systemctl enable nextris-backend
sudo systemctl start nextris-backend

# Verificar
sudo systemctl status nextris-backend
curl http://localhost:5001/api/health
```

### Paso 4: Instalar Frontend

```bash
# Clonar repositorio
sudo git clone https://github.com/FacuFarias/nextris-front-react.git /var/www/nextris-front-react

# Instalar dependencias
cd /var/www/nextris-front-react
sudo npm install

# Configurar variables de entorno
sudo cp .env.example .env
# EDITAR .env:
#   VITE_API_URL=/api
#   VITE_APP_NAME=NextRIS
sudo nano .env

# Build de producción
sudo npm run build

# Configurar Nginx
sudo cp /var/www/nextris-dev-react/deployment/config/nextris-nginx.conf /etc/nginx/sites-available/nextris
sudo ln -sf /etc/nginx/sites-available/nextris /etc/nginx/sites-enabled/nextris
sudo rm -f /etc/nginx/sites-enabled/default

# Verificar configuración y reiniciar
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Paso 5: Verificación

```bash
# Backend health check
curl http://localhost:5001/api/health

# Frontend (desde el servidor)
curl -I http://localhost/

# Frontend (desde navegador)
# Abrir http://<IP_DEL_SERVIDOR>/

# Verificar que el frontend puede conectar al backend
curl http://localhost/api/health
```

---

## Configuración de Firewall

```bash
# Instalar UFW si no está
sudo apt install -y ufw

# Permitir SSH
sudo ufw allow 22/tcp

# Permitir HTTP
sudo ufw allow 80/tcp

# Permitir HTTPS (si configuras SSL después)
sudo ufw allow 443/tcp

# Activar firewall
sudo ufw enable
sudo ufw status
```

**Nota:** El puerto 5001 del backend NO se expone al exterior. Nginx hace proxy interno desde el puerto 80.

---

## Variables de Entorno del Backend

Archivo: `/var/www/nextris-dev-react/.env`

```env
# ===========================================
# CONFIGURACIÓN DEL SERVIDOR
# ===========================================
DEBUG=False
FLASK_APP=run.py
FLASK_DEBUG=0
ASSETS_ROOT=/static/assets

# ===========================================
# BASE DE DATOS
# ===========================================
DB_ENGINE=postgresql
DB_USER=pacs
DB_PASS=<CAMBIAR_PASSWORD>
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pacsdb

# ===========================================
# SERVIDOR
# ===========================================
IPSERVER=<IP_DEL_SERVIDOR>

# ===========================================
# SEGURIDAD
# ===========================================
# Generar con: openssl rand -hex 32
SECRET_KEY=<GENERAR_ALEATORIO>
JWT_SECRET_KEY=<GENERAR_ALEATORIO>

# ===========================================
# DICOM VIEWER (opcional)
# ===========================================
# Si no hay PACS, dejar vacío
DICOM_VIEWER_URL=

# ===========================================
# ANALYTICS
# ===========================================
ANALYTICS_ENABLED=False
ANALYTICS_STORE_IP=False
ANALYTICS_GEO_LOOKUP=False

# ===========================================
# ANTHROPIC AI (opcional)
# ===========================================
# Para el asistente "Nexi"
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# ===========================================
# EMAIL (opcional)
# ===========================================
# Para envío de reportes por email
SMTP_SERVER=
SMTP_PORT=587
SMTP_USER=
SMTP_USE_TLS=true
SMTP_FROM=
SMTP_FROM_NAME=NextRIS
RESEND_API_KEY=
```

---

## Variables de Entorno del Frontend

Archivo: `/var/www/nextris-front-react/.env`

```env
# URL del API backend (relativo, Nginx hace proxy)
VITE_API_URL=/api

# Nombre de la aplicación
VITE_APP_NAME=NextRIS

# Versión
VITE_APP_VERSION=1.0.0

# PostHog Analytics (opcional, dejar vacío para deshabilitar)
VITE_POSTHOG_KEY=
VITE_POSTHOG_HOST=https://app.posthog.com
```

---

## Configuración de Nginx

Archivo: `/etc/nginx/sites-available/nextris`

```nginx
server {
    listen 80;
    server_name _;

    # Frontend - servir build estático de React
    root /var/www/nextris-front-react/dist;
    index index.html;

    # Tamaño máximo de upload (para DICOM)
    client_max_body_size 500M;

    # SPA fallback - todas las rutas van a index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API al backend Flask/Gunicorn
    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Cache assets estáticos (JS, CSS, imágenes)
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Logs
    access_log /var/log/nginx/nextris-access.log;
    error_log /var/log/nginx/nextris-error.log;
}
```

---

## Servicios Systemd

### Backend (`/etc/systemd/system/nextris-backend.service`)

```ini
[Unit]
Description=NextRIS Backend API (Flask/Gunicorn)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=root
Group=root
WorkingDirectory=/var/www/nextris-dev-react
Environment="PATH=/var/www/nextris-dev-react/venv/bin"
ExecStart=/var/www/nextris-dev-react/venv/bin/gunicorn -w 2 -b 0.0.0.0:5001 --timeout 300 run:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Frontend (solo si usas Vite dev server en lugar de Nginx)

```ini
[Unit]
Description=NextRIS Frontend (Vite Dev Server)
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/nextris-front-react
Environment="PATH=/usr/local/bin:/usr/bin"
ExecStart=/usr/bin/npm run dev:host
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## Estructura de Directorios (Resultado Final)

```
/var/www/
├── nextris-dev-react/              # Backend
│   ├── .env                        # Variables de entorno
│   ├── run.py                      # Entry point
│   ├── gunicorn-cfg.py             # Config Gunicorn
│   ├── requirements.txt            # Dependencias Python
│   ├── venv/                       # Entorno virtual Python
│   ├── apps/
│   │   ├── api/                    # REST API (27 módulos)
│   │   ├── authentication/         # Auth module
│   │   ├── home/                   # Business logic
│   │   ├── static/                 # Assets estáticos
│   │   └── templates/              # Jinja2 templates (legacy)
│   ├── deployment/
│   │   ├── install/                # Scripts de instalación
│   │   ├── sql/                    # Scripts SQL
│   │   ├── config/                 # Archivos de configuración
│   │   └── migrations/             # Migraciones SQL
│   ├── media/firmas/               # Firmas digitales
│   └── uploads_dicom/              # Archivos DICOM subidos
│
└── nextris-front-react/            # Frontend
    ├── .env                        # Variables de entorno
    ├── package.json                # Dependencias Node.js
    ├── node_modules/               # Dependencias instaladas
    ├── dist/                       # Build de producción
    │   ├── index.html
    │   └── assets/                 # JS, CSS, imágenes hasheados
    ├── src/
    │   ├── components/             # Componentes compartidos
    │   ├── modules/                # 14 módulos de funcionalidad
    │   ├── routes/                 # Definición de rutas
    │   ├── services/               # Servicios API globales
    │   ├── context/                # React Context providers
    │   ├── hooks/                  # Custom hooks
    │   └── layouts/                # Layouts (sidebar, footer)
    └── public/                     # Assets públicos
```

---

## Comandos Útiles

### Gestión de Servicios

```bash
# Backend
sudo systemctl start nextris-backend
sudo systemctl stop nextris-backend
sudo systemctl restart nextris-backend
sudo systemctl status nextris-backend

# Logs del backend
sudo journalctl -u nextris-backend -f              # En tiempo real
sudo journalctl -u nextris-backend -n 100           # Últimas 100 líneas
sudo journalctl -u nextris-backend --since "1h ago" # Última hora

# Nginx (frontend)
sudo systemctl restart nginx
sudo systemctl status nginx
sudo nginx -t                                       # Verificar config

# Logs de Nginx
sudo tail -f /var/log/nginx/nextris-access.log
sudo tail -f /var/log/nginx/nextris-error.log

# PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -d pacsdb                     # Conectar a la DB
```

### Actualización del Backend

```bash
cd /var/www/nextris-dev-react
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart nextris-backend
```

### Actualización del Frontend

```bash
cd /var/www/nextris-front-react
git pull origin ui2
npm install
npm run build
sudo systemctl restart nginx
```

### Backup de Base de Datos

```bash
# Backup completo
sudo -u postgres pg_dump pacsdb > /tmp/pacsdb_backup_$(date +%Y%m%d).sql

# Backup solo schema nextris
sudo -u postgres pg_dump -n nextris pacsdb > /tmp/nextris_schema_$(date +%Y%m%d).sql

# Restaurar
sudo -u postgres psql -d pacsdb < /tmp/pacsdb_backup_20260508.sql
```

### Generar Contraseñas Seguras

```bash
# Generar SECRET_KEY
openssl rand -hex 32

# Generar contraseña de DB
openssl rand -base64 24
```

---

## Troubleshooting

### El backend no inicia

```bash
# Ver logs
sudo journalctl -u nextris-backend -n 50 --no-pager

# Probar manualmente
cd /var/www/nextris-dev-react
source venv/bin/activate
python run.py

# Verificar que el puerto esté libre
sudo netstat -tlnp | grep 5001
```

### Error de conexión a la base de datos

```bash
# Verificar que PostgreSQL está corriendo
sudo systemctl status postgresql

# Probar conexión
psql -h localhost -U pacs -d pacsdb

# Si falla, verificar pg_hba.conf
sudo nano /etc/postgresql/16/main/pg_hba.conf
# Agregar: local   pacsdb   pacs   md5

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

### El frontend muestra "Network Error" o no carga datos

```bash
# Verificar que Nginx está proxy correctamente
curl http://localhost/api/health

# Si falla, verificar la config de Nginx
sudo nginx -t
sudo cat /etc/nginx/sites-available/nextris

# Ver logs de error
sudo tail -20 /var/log/nginx/nextris-error.log
```

### Error 502 Bad Gateway

```bash
# El backend no está corriendo
sudo systemctl status nextris-backend
sudo systemctl restart nextris-backend

# Verificar que el puerto es correcto
sudo netstat -tlnp | grep 5001
```

### Permisos incorrectos

```bash
sudo chown -R root:root /var/www/nextris-dev-react
sudo chown -R root:root /var/www/nextris-front-react
sudo chmod -R 755 /var/www/nextris-dev-react/media
sudo chmod -R 755 /var/www/nextris-dev-react/uploads_dicom
```

---

## Checklist Post-Instalación

- [ ] PostgreSQL está corriendo y acepta conexiones
- [ ] La base de datos `pacsdb` existe con el schema `nextris`
- [ ] Las tablas core están creadas (verificar con `\dt nextris.*` en psql)
- [ ] El backend responde en `http://localhost:5001/api/health`
- [ ] El frontend carga en `http://<IP_DEL_SERVIDOR>/`
- [ ] El login funciona (usuario por defecto: crear con el script o manualmente)
- [ ] Los logs no muestran errores críticos
- [ ] El firewall permite tráfico en puerto 80
- [ ] Las variables de entorno están configuradas correctamente
- [ ] Los directorios de output tienen permisos de escritura

---

## Notas de Seguridad

1. **Cambiar todas las contraseñas por defecto** antes de poner en producción
2. **Generar SECRET_KEY aleatorio** con `openssl rand -hex 32`
3. **No exponer el puerto 5001** al exterior (solo Nginx en puerto 80)
4. **Configurar HTTPS** con Let's Encrypt si se usa dominio
5. **El archivo .env** contiene credenciales, proteger con permisos 600
6. **PostgreSQL** solo escucha en localhost por defecto (no requiere cambios)

---

## Arquitectura de Red

```
Internet
    │
    ▼
┌─────────────────────┐
│   Puerto 80 (HTTP)  │
│       Nginx         │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌──────────────┐
│ dist/  │  │ /api/* proxy │
│ React  │  │  → :5001     │
│ Build  │  └──────┬───────┘
└────────┘         │
                   ▼
           ┌──────────────┐
           │   Gunicorn   │
           │   Flask API  │
           │   Puerto 5001│
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │  PostgreSQL  │
           │  Puerto 5432 │
           │  (localhost) │
           └──────────────┘
```

---

## Repositorios GitHub

| Repo | URL | Branch |
|---|---|---|
| Backend | https://github.com/FacuFarias/nextris-backend-react.git | main |
| Frontend | https://github.com/FacuFarias/nextris-front-react.git | ui2 |

---

*Documento generado: 2026-05-08*
*Sistema original: 148.230.72.8*
