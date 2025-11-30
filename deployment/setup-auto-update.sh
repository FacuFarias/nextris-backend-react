#!/bin/bash
# Script para configurar auto-actualización con webhook de GitHub
# Esto permite que el servidor dev se actualice automáticamente cuando el frontend haga push

set -e

APP_DIR="/var/www/nextris-dev"
WEBHOOK_SECRET="nextris_webhook_secret_2025"  # Cambiar por algo más seguro

echo "Configurando webhook de GitHub..."

# Instalar dependencias
pip3 install flask flask-cors

# Crear script del webhook
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
    app.run(host='0.0.0.0', port=9000)
EOF

# Crear servicio systemd para el webhook
cat > /etc/systemd/system/github-webhook.service << EOF
[Unit]
Description=GitHub Webhook Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt
Environment="WEBHOOK_SECRET=$WEBHOOK_SECRET"
ExecStart=/usr/bin/python3 /opt/github-webhook.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Configurar nginx para el webhook
cat > /etc/nginx/sites-available/github-webhook << 'EOF'
server {
    listen 80;
    server_name webhook.nextris.cloud;  # Cambiar por tu dominio

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

ln -sf /etc/nginx/sites-available/github-webhook /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Iniciar webhook
systemctl daemon-reload
systemctl enable github-webhook
systemctl start github-webhook

echo ""
echo "✅ Webhook configurado!"
echo ""
echo "Siguiente paso:"
echo "1. Ve a: https://github.com/FacuFarias/Multitenant-NextRIS-Frontend/settings/hooks"
echo "2. Click en 'Add webhook'"
echo "3. Payload URL: http://webhook.nextris.cloud/webhook (o tu IP:9000/webhook)"
echo "4. Content type: application/json"
echo "5. Secret: $WEBHOOK_SECRET"
echo "6. Events: Just the push event"
echo "7. Active: ✓"
echo ""
echo "Ahora cada push al repo frontend actualizará automáticamente el servidor dev!"
