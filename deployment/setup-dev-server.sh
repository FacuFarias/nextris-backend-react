#!/bin/bash
# Script de configuración del entorno de desarrollo en VPS
# Ejecutar este script en tu VPS como root o con sudo

set -e

echo "=================================="
echo "  NextRIS - Setup Dev Environment"
echo "=================================="
echo ""

# Variables de configuración (EDITAR SEGÚN TU VPS)
APP_NAME="nextris-dev"
APP_USER="nextris"
APP_DIR="/var/www/nextris-dev"
REPO_URL="https://github.com/FacuFarias/Multitenant-NextRIS.git"
BRANCH="feature/1"  # o main
PYTHON_VERSION="python3"
DEV_PORT="5001"
DOMAIN="dev.nextris.cloud"  # o tu IP:5001

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}1. Actualizando sistema...${NC}"
apt-get update
apt-get upgrade -y

echo -e "${YELLOW}2. Instalando dependencias...${NC}"
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    supervisor \
    postgresql-client

echo -e "${YELLOW}3. Creando usuario de aplicación...${NC}"
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    echo -e "${GREEN}Usuario $APP_USER creado${NC}"
else
    echo -e "${GREEN}Usuario $APP_USER ya existe${NC}"
fi

echo -e "${YELLOW}4. Clonando repositorio...${NC}"
if [ -d "$APP_DIR" ]; then
    echo "Directorio ya existe, actualizando..."
    cd $APP_DIR
    sudo -u $APP_USER git pull
else
    sudo -u $APP_USER git clone --recurse-submodules -b $BRANCH $REPO_URL $APP_DIR
fi

cd $APP_DIR

echo -e "${YELLOW}5. Configurando entorno virtual...${NC}"
sudo -u $APP_USER $PYTHON_VERSION -m venv venv
sudo -u $APP_USER venv/bin/pip install --upgrade pip
sudo -u $APP_USER venv/bin/pip install -r requirements.txt
sudo -u $APP_USER venv/bin/pip install gunicorn

echo -e "${YELLOW}6. Configurando variables de entorno...${NC}"
cat > $APP_DIR/.env << EOF
DEBUG=True
FLASK_APP=run.py
FLASK_DEBUG=1

# Configurar según tu base de datos
DB_USER=pacs
DB_PASS=pacs
DB_HOST=148.230.72.8
DB_PORT=5432
DB_NAME=pacsdb

IPSERVER=148.230.72.8
BASE_FOLDER=/app/output_pdfs

SECRET_KEY=nextris_dev_secret_key_12345
DICOM_VIEWER_URL=https://viewer.nextris.cloud/
EOF

chown $APP_USER:$APP_USER $APP_DIR/.env

echo -e "${YELLOW}7. Sincronizando frontend...${NC}"
cd $APP_DIR
sudo -u $APP_USER bash -c "
    git submodule update --remote --merge
    rm -rf apps/static apps/templates
    cp -r frontend/static apps/static
    cp -r frontend/templates apps/templates
"

echo -e "${YELLOW}8. Configurando Gunicorn...${NC}"
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=NextRIS Development Server
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:$DEV_PORT --reload run:app

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo -e "${YELLOW}9. Configurando Nginx...${NC}"
cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$DEV_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (si lo necesitas)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts más largos para desarrollo
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static {
        alias $APP_DIR/apps/static;
        expires 1d;
    }

    location /media {
        alias $APP_DIR/media;
        expires 1d;
    }
}
EOF

# Habilitar sitio
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

echo -e "${YELLOW}10. Iniciando servicios...${NC}"
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl start $APP_NAME

echo ""
echo -e "${GREEN}=================================="
echo "  ✅ Instalación completada!"
echo "==================================${NC}"
echo ""
echo "Servidor de desarrollo disponible en:"
echo "  → http://$DOMAIN"
echo "  → http://$(curl -s ifconfig.me):$DEV_PORT (si no usas dominio)"
echo ""
echo "Comandos útiles:"
echo "  sudo systemctl status $APP_NAME    # Ver estado"
echo "  sudo systemctl restart $APP_NAME   # Reiniciar"
echo "  sudo journalctl -u $APP_NAME -f    # Ver logs"
echo ""
