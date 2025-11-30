#!/bin/bash
# Script de instalación rápida para Ubuntu 24.04
# Servidor: 148.230.72.8:5000

set -e

echo "=================================="
echo "  NextRIS Dev - Instalación Rápida"
echo "  Ubuntu 24.04"
echo "=================================="
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Verificar que somos root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Por favor ejecuta como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}1. Actualizando sistema...${NC}"
apt-get update
apt-get upgrade -y

echo -e "${YELLOW}2. Instalando dependencias...${NC}"
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    postgresql-client \
    build-essential \
    curl

echo -e "${YELLOW}3. Creando usuario de aplicación...${NC}"
if ! id "nextris" &>/dev/null; then
    useradd -m -s /bin/bash nextris
    echo -e "${GREEN}Usuario nextris creado${NC}"
else
    echo -e "${GREEN}Usuario nextris ya existe${NC}"
fi

echo -e "${YELLOW}4. Clonando repositorio...${NC}"
if [ -d "/var/www/nextris-dev" ]; then
    echo "Directorio ya existe, eliminando..."
    rm -rf /var/www/nextris-dev
fi

sudo -u nextris git clone --recurse-submodules -b feature/1 \
    https://github.com/FacuFarias/Multitenant-NextRIS.git \
    /var/www/nextris-dev

cd /var/www/nextris-dev

echo -e "${YELLOW}5. Configurando entorno virtual...${NC}"
sudo -u nextris python3 -m venv venv
sudo -u nextris venv/bin/pip install --upgrade pip
sudo -u nextris venv/bin/pip install -r requirements.txt
sudo -u nextris venv/bin/pip install gunicorn

echo -e "${YELLOW}6. Configurando variables de entorno...${NC}"
cat > /var/www/nextris-dev/.env << 'EOF'
DEBUG=True
FLASK_APP=run.py
FLASK_DEBUG=1

DB_USER=pacs
DB_PASS=pacs
DB_HOST=148.230.72.8
DB_PORT=5432
DB_NAME=pacsdb

IPSERVER=148.230.72.8
BASE_FOLDER=/var/www/nextris-dev/output_pdfs

SECRET_KEY=nextris_dev_secret_key_12345
DICOM_VIEWER_URL=https://viewer.nextris.cloud/
EOF

chown nextris:nextris /var/www/nextris-dev/.env

echo -e "${YELLOW}7. Creando directorios necesarios...${NC}"
mkdir -p /var/www/nextris-dev/output_pdfs
mkdir -p /var/www/nextris-dev/media/firmas
chown -R nextris:nextris /var/www/nextris-dev/output_pdfs
chown -R nextris:nextris /var/www/nextris-dev/media

echo -e "${YELLOW}8. Sincronizando frontend...${NC}"
cd /var/www/nextris-dev
sudo -u nextris bash -c "
    git submodule update --remote --merge
    rm -rf apps/static apps/templates
    cp -r frontend/static apps/static
    cp -r frontend/templates apps/templates
"

echo -e "${YELLOW}9. Configurando servicio systemd...${NC}"
cat > /etc/systemd/system/nextris-dev.service << 'EOF'
[Unit]
Description=NextRIS Development Server
After=network.target

[Service]
User=nextris
Group=nextris
WorkingDirectory=/var/www/nextris-dev
Environment="PATH=/var/www/nextris-dev/venv/bin"
ExecStart=/var/www/nextris-dev/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 --reload --timeout 300 run:app

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo -e "${YELLOW}10. Configurando firewall...${NC}"
ufw allow 5000/tcp
echo -e "${GREEN}Puerto 5000 abierto${NC}"

echo -e "${YELLOW}11. Iniciando servicio...${NC}"
systemctl daemon-reload
systemctl enable nextris-dev
systemctl start nextris-dev

# Esperar un momento para que inicie
sleep 3

# Verificar estado
if systemctl is-active --quiet nextris-dev; then
    echo ""
    echo -e "${GREEN}=================================="
    echo "  ✅ ¡INSTALACIÓN EXITOSA!"
    echo "==================================${NC}"
    echo ""
    echo -e "${GREEN}Servidor disponible en:${NC}"
    echo -e "  👉 ${YELLOW}http://148.230.72.8:5000${NC}"
    echo ""
    echo -e "${GREEN}Comandos útiles:${NC}"
    echo "  systemctl status nextris-dev    # Ver estado"
    echo "  systemctl restart nextris-dev   # Reiniciar"
    echo "  journalctl -u nextris-dev -f    # Ver logs en tiempo real"
    echo "  journalctl -u nextris-dev -n 50 # Ver últimos 50 logs"
    echo ""
    echo -e "${GREEN}Archivos importantes:${NC}"
    echo "  /var/www/nextris-dev/.env       # Variables de entorno"
    echo "  /var/www/nextris-dev/deployment/update-dev-server.sh # Actualizar"
    echo ""
else
    echo ""
    echo -e "${RED}=================================="
    echo "  ⚠️  ERROR AL INICIAR"
    echo "==================================${NC}"
    echo ""
    echo "El servicio no se inició correctamente. Ver logs:"
    journalctl -u nextris-dev -n 30
    exit 1
fi
