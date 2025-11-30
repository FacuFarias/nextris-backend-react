#!/bin/bash
# Script para actualizar el servidor de desarrollo cuando el frontend cambie
# Ejecutar en la VPS cuando quieras traer cambios nuevos del frontend

set -e

APP_DIR="/var/www/nextris-dev"
APP_NAME="nextris-dev"

echo "=================================="
echo "  Actualizando Frontend en Dev"
echo "=================================="
echo ""

cd $APP_DIR

echo "1. Actualizando código backend..."
sudo -u nextris git pull origin feature/1

echo "2. Actualizando submódulo frontend..."
sudo -u nextris git submodule update --remote --merge

echo "3. Sincronizando archivos frontend..."
sudo -u nextris bash -c "
    rm -rf apps/static apps/templates
    cp -r frontend/static apps/static
    cp -r frontend/templates apps/templates
"

echo "4. Reiniciando servidor..."
systemctl restart $APP_NAME

echo ""
echo "✅ Actualización completada!"
echo "El servidor se reinició automáticamente"
echo ""
echo "Ver logs: sudo journalctl -u $APP_NAME -f"
