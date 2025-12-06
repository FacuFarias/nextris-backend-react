# Guía de Mantenimiento - NextRIS Development Server

## Información del Servicio

**Servicio systemd:** `nextris-dev.service`
**Usuario:** `nextris`
**Directorio:** `/var/www/nextris-dev`
**Puerto:** `5000`
**Entorno virtual:** `/var/www/nextris-dev/venv`

---

## Comandos Básicos de Servicio

### Ver estado del servicio
```bash
systemctl status nextris-dev.service
```

### Iniciar el servicio
```bash
sudo systemctl start nextris-dev.service
```

### Detener el servicio
```bash
sudo systemctl stop nextris-dev.service
```

### Reiniciar el servicio
```bash
sudo systemctl restart nextris-dev.service
```

### Recargar configuración (sin interrumpir el servicio)
```bash
sudo systemctl reload nextris-dev.service
```

### Habilitar inicio automático al arrancar el sistema
```bash
sudo systemctl enable nextris-dev.service
```

### Deshabilitar inicio automático
```bash
sudo systemctl disable nextris-dev.service
```

---

## Ver Logs del Servicio

### Ver logs en tiempo real
```bash
journalctl -u nextris-dev.service -f
```

### Ver últimas 50 líneas de logs
```bash
journalctl -u nextris-dev.service -n 50
```

### Ver logs con timestamps detallados
```bash
journalctl -u nextris-dev.service -o verbose
```

### Ver logs desde una fecha específica
```bash
journalctl -u nextris-dev.service --since "2025-12-03 10:00:00"
```

### Ver logs de errores solamente
```bash
journalctl -u nextris-dev.service -p err
```

---

## Actualizar el Código

### 1. Actualizar desde el repositorio Git
```bash
cd /var/www/nextris-dev
sudo -u nextris git pull origin main
```

### 2. Actualizar dependencias Python (si es necesario)
```bash
cd /var/www/nextris-dev
sudo -u nextris venv/bin/pip install -r requirements.txt
```

### 3. Reiniciar el servicio para aplicar cambios
```bash
sudo systemctl restart nextris-dev.service
```

### Script completo de actualización
```bash
#!/bin/bash
cd /var/www/nextris-dev
sudo -u nextris git pull origin main
sudo -u nextris venv/bin/pip install -r requirements.txt
sudo systemctl restart nextris-dev.service
systemctl status nextris-dev.service
```

---

## Mantenimiento de la Base de Datos

### Ver configuración de la base de datos
```bash
cat /var/www/nextris-dev/.env | grep DB
```

### Realizar backup de la base de datos (PostgreSQL)
```bash
# Obtener las credenciales del .env
export $(cat /var/www/nextris-dev/.env | grep DB | xargs)

# Hacer backup
pg_dump -h $DB_HOST -U $DB_USERNAME -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Ejecutar migraciones de base de datos (si usas Flask-Migrate)
```bash
cd /var/www/nextris-dev
sudo -u nextris venv/bin/python -c "from apps import create_app, db; from apps.config import config_dict; app = create_app(config_dict['Debug']); app.app_context().push(); db.create_all()"
```

---

## Gestión del Entorno Virtual

### Activar el entorno virtual manualmente
```bash
cd /var/www/nextris-dev
source venv/bin/activate
```

### Desactivar el entorno virtual
```bash
deactivate
```

### Recrear el entorno virtual desde cero
```bash
cd /var/www/nextris-dev
sudo -u nextris python3 -m venv venv
sudo -u nextris venv/bin/pip install --upgrade pip
sudo -u nextris venv/bin/pip install -r requirements.txt
sudo systemctl restart nextris-dev.service
```

---

## Verificación del Sistema

### Verificar que el servicio está escuchando en el puerto 5000
```bash
netstat -tulpn | grep :5000
# o
lsof -i :5000
```

### Probar la aplicación localmente
```bash
curl http://localhost:5000/login
```

### Ver procesos de Gunicorn activos
```bash
ps aux | grep gunicorn | grep -v grep
```

### Ver uso de recursos del servicio
```bash
systemctl status nextris-dev.service | grep -E "(Memory|CPU)"
```

---

## Troubleshooting

### El servicio no inicia

1. **Verificar logs de error:**
   ```bash
   journalctl -u nextris-dev.service -n 100 --no-pager
   ```

2. **Verificar que el puerto no esté ocupado:**
   ```bash
   lsof -i :5000
   ```

3. **Matar procesos huérfanos:**
   ```bash
   sudo pkill -9 -f "gunicorn.*run:app"
   sudo systemctl start nextris-dev.service
   ```

### Error "Address already in use"

```bash
# Matar todos los procesos en el puerto 5000
sudo fuser -k 5000/tcp
sudo systemctl restart nextris-dev.service
```

### Errores de permisos

```bash
# Verificar propietario de archivos
ls -la /var/www/nextris-dev

# Corregir permisos si es necesario
sudo chown -R nextris:nextris /var/www/nextris-dev
```

### Error de módulos Python no encontrados

```bash
cd /var/www/nextris-dev
sudo -u nextris venv/bin/pip install -r requirements.txt --force-reinstall
sudo systemctl restart nextris-dev.service
```

### Servicio se reinicia constantemente

```bash
# Ver logs en tiempo real
journalctl -u nextris-dev.service -f

# Verificar configuración del .env
cat /var/www/nextris-dev/.env

# Probar la aplicación manualmente
cd /var/www/nextris-dev
sudo -u nextris venv/bin/python run.py
```

---

## Configuración de Gunicorn

### Archivo de configuración del servicio
```bash
sudo nano /etc/systemd/system/nextris-dev.service
```

### Parámetros actuales de Gunicorn:
- `-w 2`: 2 workers (procesos)
- `-b 0.0.0.0:5000`: Escucha en todas las interfaces, puerto 5000
- `--reload`: Recarga automática cuando hay cambios en el código
- `--timeout 300`: Timeout de 300 segundos

### Recargar systemd después de cambios
```bash
sudo systemctl daemon-reload
sudo systemctl restart nextris-dev.service
```

---

## Monitoreo y Performance

### Ver memoria utilizada por el servicio
```bash
ps aux | grep gunicorn | awk '{sum+=$6} END {print "Memory (MB):", sum/1024}'
```

### Ver conexiones activas al puerto 5000
```bash
netstat -an | grep :5000 | grep ESTABLISHED | wc -l
```

### Reiniciar el servicio sin downtime (con múltiples workers)
```bash
sudo systemctl reload nextris-dev.service
```

---

## Backups

### Script de backup completo
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/nextris"
DATE=$(date +%Y%m%d_%H%M%S)

# Crear directorio de backup
mkdir -p $BACKUP_DIR

# Backup del código
tar -czf $BACKUP_DIR/code_$DATE.tar.gz -C /var/www nextris-dev \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.git'

# Backup de la base de datos
export $(cat /var/www/nextris-dev/.env | grep DB | xargs)
pg_dump -h $DB_HOST -U $DB_USERNAME -d $DB_NAME > $BACKUP_DIR/db_$DATE.sql

echo "Backup completado: $BACKUP_DIR"
```

---

## Comandos Útiles Rápidos

```bash
# Reiniciar después de cambios en el código
sudo systemctl restart nextris-dev.service

# Ver si hay errores
journalctl -u nextris-dev.service -p err -n 50

# Ver logs en tiempo real
journalctl -u nextris-dev.service -f

# Verificar estado
systemctl status nextris-dev.service

# Probar la aplicación
curl -I http://localhost:5000/login
```

---

## Contacto y Documentación

- **Documentación completa:** `/var/www/nextris-dev/README.md`
- **Arquitectura:** `/var/www/nextris-dev/ARQUITECTURA_GUIA.md`
- **Distribución de funciones:** `/var/www/nextris-dev/DISTRIBUCION_FUNCIONES.md`

---

**Última actualización:** 3 de diciembre de 2025
