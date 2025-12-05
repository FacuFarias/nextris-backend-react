#!/bin/bash
# Script para configurar auto-actualización con webhook de GitHub
# Esto permite que el servidor dev se actualice automáticamente cuando el frontend haga push

set -e

APP_DIR="/var/www/nextris-dev"
WEBHOOK_SECRET="nextris_webhook_secret_2025"
WEBHOOK_PORT="9000"

echo "=================================="
echo "  Configurando Auto-Actualización"
echo "=================================="
echo ""

# Instalar dependencias
echo "1. Instalando dependencias..."
pip3 install flask flask-cors >/dev/null 2>&1

# Crear script del webhook
echo "2. Creando script del webhook..."
cat > /opt/github-webhook.py << 'EOF'
from flask import Flask, request, abort
import hmac
import hashlib
import subprocess
import os

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'nextris_webhook_secret_2025')
APP_DIR = '/var/www/nextris-dev'

def verify_signature(payload, signature):
    """Verificar firma de GitHub"""
    if not signature:
        return False
    
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(
        WEBHOOK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    )
    
    return hmac.compare_digest(mac.hexdigest(), signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint del webhook"""
    signature = request.headers.get('X-Hub-Signature-256')
    
    if not verify_signature(request.data, signature):
        abort(401, 'Invalid signature')
    
    event = request.headers.get('X-GitHub-Event')
    
    if event == 'push':
        payload = request.json
        repo_name = payload['repository']['name']
        
        # Solo actualizar si es el repo frontend
        if repo_name == 'Multitenant-NextRIS-Frontend':
            print(f"Actualizando frontend desde commit: {payload['head_commit']['message']}")
            
            # Ejecutar script de actualización
            result = subprocess.run(
                ['/var/www/nextris-dev/deployment/update-dev-server.sh'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return {'status': 'success', 'message': 'Frontend actualizado'}, 200
            else:
                return {'status': 'error', 'message': result.stderr}, 500
        
        return {'status': 'ignored', 'message': 'Repo no es frontend'}, 200
    
    return {'status': 'ok'}, 200

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    print(f"Webhook server iniciado en puerto {os.getenv('WEBHOOK_PORT', '9000')}")
    app.run(host='0.0.0.0', port=int(os.getenv('WEBHOOK_PORT', '9000')))
EOF

# Crear servicio systemd para el webhook
echo "3. Configurando servicio systemd..."
cat > /etc/systemd/system/github-webhook.service << EOF
[Unit]
Description=GitHub Webhook Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt
Environment="WEBHOOK_SECRET=$WEBHOOK_SECRET"
Environment="WEBHOOK_PORT=$WEBHOOK_PORT"
ExecStart=/usr/bin/python3 /opt/github-webhook.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Abrir puerto del webhook en firewall
echo "4. Configurando firewall..."
ufw allow $WEBHOOK_PORT/tcp

# Iniciar webhook
echo "5. Iniciando servicio webhook..."
systemctl daemon-reload
systemctl enable github-webhook
systemctl start github-webhook

# Esperar que inicie
sleep 2

# Verificar estado
if systemctl is-active --quiet github-webhook; then
    echo "✓ Webhook iniciado correctamente"
else
    echo "✗ Error al iniciar webhook"
    journalctl -u github-webhook -n 20
    exit 1
fi

echo ""
echo "=================================="
echo "  ✅ Webhook Configurado!"
echo "=================================="
echo ""
echo "IMPORTANTE: Ahora debes configurar el webhook en GitHub:"
echo ""
echo "1. Ve a: https://github.com/FacuFarias/Multitenant-NextRIS-Frontend/settings/hooks"
echo ""
echo "2. Click en 'Add webhook'"
echo ""
echo "3. Configuración:"
echo "   Payload URL: http://148.230.72.8:$WEBHOOK_PORT/webhook"
echo "   Content type: application/json"
echo "   Secret: $WEBHOOK_SECRET"
echo "   SSL verification: Disable (solo para dev)"
echo "   Events: Just the push event"
echo "   Active: ✓"
echo ""
echo "4. Click 'Add webhook'"
echo ""
echo "¡Listo! Ahora cada push al repo frontend actualizará automáticamente el servidor."
echo ""
echo "Para verificar:"
echo "  - Estado: systemctl status github-webhook"
echo "  - Logs: journalctl -u github-webhook -f"
echo "  - Test: curl http://localhost:$WEBHOOK_PORT/health"
echo ""
