# Guía de Despliegue del Servidor de Desarrollo

Esta guía te ayudará a configurar un servidor de desarrollo en tu VPS para que el equipo de frontend pueda ver sus cambios en tiempo real.

## 🎯 Objetivo

Configurar un entorno de desarrollo donde:
- El programador frontend hace push a su repo
- Los cambios se reflejan automáticamente en el servidor dev
- El frontend **NO** tiene acceso al código backend
- Usa la misma base de datos (o una copia)

## 📋 Requisitos Previos

- VPS con Ubuntu 20.04+ (Debian o CentOS también funciona)
- Acceso root o sudo
- Dominio o subdominio (opcional, se puede usar IP:puerto)
- Python 3.8+
- PostgreSQL accesible

## 🚀 Instalación

### Opción 1: Instalación Automática (Recomendado)

1. **Conectar a tu VPS por SSH:**
```bash
ssh root@tu-vps-ip
```

2. **Copiar el script de instalación:**
```bash
# Descargar el script
wget https://raw.githubusercontent.com/FacuFarias/Multitenant-NextRIS/feature/1/deployment/setup-dev-server.sh

# Dar permisos de ejecución
chmod +x setup-dev-server.sh
```

3. **EDITAR el script con tus datos:**
```bash
nano setup-dev-server.sh
```

Modificar estas variables:
```bash
REPO_URL="https://github.com/FacuFarias/Multitenant-NextRIS.git"
BRANCH="feature/1"  # o main
DEV_PORT="5001"
DOMAIN="dev.nextris.cloud"  # o tu IP
```

Y la configuración de base de datos en el `.env`:
```bash
DB_USER=tu_usuario
DB_PASS=tu_password
DB_HOST=148.230.72.8
DB_PORT=5432
DB_NAME=pacsdb
```

4. **Ejecutar el script:**
```bash
sudo bash setup-dev-server.sh
```

5. **Verificar que funciona:**
```bash
# Ver estado del servicio
sudo systemctl status nextris-dev

# Ver logs
sudo journalctl -u nextris-dev -f
```

6. **Acceder desde el navegador:**
- Si configuraste dominio: `http://dev.nextris.cloud`
- Si usas IP: `http://tu-ip:5001`

### Opción 2: Instalación Manual

Si prefieres instalar paso a paso, sigue el script `setup-dev-server.sh` línea por línea.

## 🔄 Actualización Manual

Cuando el frontend haga cambios:

```bash
# Conectar a la VPS
ssh root@tu-vps-ip

# Ejecutar script de actualización
cd /var/www/nextris-dev/deployment
bash update-dev-server.sh
```

## 🤖 Auto-actualización (Opcional)

Para que el servidor se actualice automáticamente cuando el frontend haga push:

### 1. Configurar webhook en la VPS

```bash
# En tu VPS
cd /var/www/nextris-dev/deployment
bash setup-auto-update.sh
```

### 2. Configurar webhook en GitHub

1. Ve a: https://github.com/FacuFarias/Multitenant-NextRIS-Frontend/settings/hooks
2. Click "Add webhook"
3. Configuración:
   - **Payload URL:** `http://webhook.nextris.cloud/webhook` (o tu IP:9000/webhook)
   - **Content type:** `application/json`
   - **Secret:** El secret que configuraste en el script
   - **Events:** Just the push event
   - **Active:** ✓

4. Save

Ahora cada vez que el frontend haga push, el servidor dev se actualizará automáticamente! 🎉

## 🔐 Configuración DNS (Si usas subdominio)

En tu proveedor de DNS (Cloudflare, etc.):

```
Tipo: A
Nombre: dev
Contenido: IP-de-tu-VPS
TTL: Auto
```

Para el webhook (si lo usas):
```
Tipo: A
Nombre: webhook
Contenido: IP-de-tu-VPS
TTL: Auto
```

## 🛠️ Comandos Útiles

```bash
# Ver estado del servicio
sudo systemctl status nextris-dev

# Ver logs en tiempo real
sudo journalctl -u nextris-dev -f

# Reiniciar servidor
sudo systemctl restart nextris-dev

# Detener servidor
sudo systemctl stop nextris-dev

# Iniciar servidor
sudo systemctl start nextris-dev

# Ver configuración de nginx
sudo nano /etc/nginx/sites-available/nextris-dev

# Reiniciar nginx
sudo systemctl restart nginx

# Actualizar manualmente
cd /var/www/nextris-dev/deployment
bash update-dev-server.sh
```

## 🐛 Troubleshooting

### El servidor no inicia

```bash
# Ver logs de error
sudo journalctl -u nextris-dev -n 50

# Verificar que el puerto está libre
sudo netstat -tlnp | grep 5001

# Probar manualmente
cd /var/www/nextris-dev
sudo -u nextris venv/bin/python run.py
```

### Error de base de datos

Verificar credenciales en `/var/www/nextris-dev/.env`

### Nginx error

```bash
# Verificar configuración
sudo nginx -t

# Ver logs
sudo tail -f /var/log/nginx/error.log
```

### Webhook no funciona

```bash
# Ver logs del webhook
sudo journalctl -u github-webhook -f

# Verificar que está corriendo
sudo systemctl status github-webhook

# Probar manualmente
curl http://localhost:9000/health
```

## 📊 Monitoreo

Ver uso de recursos:

```bash
# CPU y memoria
htop

# Espacio en disco
df -h

# Logs de acceso
sudo tail -f /var/log/nginx/access.log
```

## 🔄 Workflow del Frontend Developer

1. **Clonar su repo:**
```bash
git clone https://github.com/FacuFarias/Multitenant-NextRIS-Frontend.git
```

2. **Hacer cambios locales** en HTML, CSS, JS

3. **Commit y push:**
```bash
git add .
git commit -m "Descripción de cambios"
git push origin main
```

4. **Ver cambios:**
- Con webhook: Automáticamente en 1-2 minutos
- Sin webhook: Avisarte para que ejecutes `update-dev-server.sh`
- Acceder a: `http://dev.nextris.cloud`

## 📞 Soporte

Si tienes problemas, revisa los logs y la configuración. Para issues específicos, contacta al equipo de backend.

---

**¡Listo para desarrollo! 🚀**
