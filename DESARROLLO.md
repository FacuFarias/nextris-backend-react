# Entorno de Desarrollo React - NextRIS

## Configuración Actual

Se han creado **DOS instancias** del sistema NextRIS:

### 🟢 Producción (Puerto 5000)
- **Directorio:** `/var/www/nextris-dev`
- **Puerto:** `5000`
- **URL:** `http://148.230.72.8:5000`
- **Servicio:** `nextris-dev.service`
- **Estado:** ✅ **NO TOCAR - Sistema en producción**

### 🔵 Desarrollo/Migración React (Puerto 5001)
- **Directorio:** `/var/www/nextris-dev-react`
- **Puerto:** `5001`
- **URL:** `http://148.230.72.8:5001`
- **Servicio:** `nextris-dev-react.service`
- **Estado:** 🚧 **Usar para migración a React**

---

## Acceso a las Instancias

### Instancia de Producción (5000)
```
http://148.230.72.8:5000/login
```

### Instancia de Desarrollo (5001)
```
http://148.230.72.8:5001/login
```

---

## Gestión del Servicio de Desarrollo (Puerto 5001)

### Ver estado
```bash
systemctl status nextris-dev-react.service
```

### Reiniciar
```bash
sudo systemctl restart nextris-dev-react.service
```

### Detener
```bash
sudo systemctl stop nextris-dev-react.service
```

### Iniciar
```bash
sudo systemctl start nextris-dev-react.service
```

### Ver logs en tiempo real
```bash
journalctl -u nextris-dev-react.service -f
```

### Ver últimos errores
```bash
journalctl -u nextris-dev-react.service -p err -n 50
```

---

## Trabajar en el Entorno de Desarrollo

### Navegar al directorio
```bash
cd /var/www/nextris-dev-react
```

### Activar entorno virtual
```bash
source venv/bin/activate
```

### Editar archivos
```bash
# Editar rutas
nano apps/authentication/routes.py
nano apps/home/routes.py

# Editar templates
nano apps/templates/accounts/login.html
```

### Aplicar cambios
```bash
# Opción 1: Reiniciar servicio
sudo systemctl restart nextris-dev-react.service

# Opción 2: El flag --reload debería detectar cambios automáticamente
# pero a veces es mejor reiniciar manualmente
```

---

## Instalar Dependencias para React

### 1. Instalar Flask-CORS y Flask-JWT-Extended
```bash
cd /var/www/nextris-dev-react
source venv/bin/activate
pip install flask-cors flask-jwt-extended
pip freeze > requirements.txt
```

### 2. Crear estructura de API
```bash
cd /var/www/nextris-dev-react/apps
mkdir api
touch api/__init__.py
touch api/auth.py
touch api/patients.py
touch api/studies.py
```

### 3. Reiniciar servicio
```bash
sudo systemctl restart nextris-dev-react.service
```

---

## Crear Proyecto React Frontend

### Opción 1: En el mismo servidor
```bash
cd /var/www/nextris-dev-react
npm install -g create-react-app  # Si no está instalado
npx create-react-app frontend-react
cd frontend-react
npm install axios react-router-dom @tanstack/react-query zustand
```

### Opción 2: En máquina de desarrollo local
```bash
# En tu computadora local
npx create-react-app nextris-frontend
cd nextris-frontend

# Instalar dependencias
npm install axios react-router-dom @tanstack/react-query zustand

# Configurar proxy para desarrollo (package.json)
# Agregar: "proxy": "http://148.230.72.8:5001"

# Iniciar desarrollo
npm start
```

---

## Probar Cambios sin Afectar Producción

### Verificar que la instancia de desarrollo funciona
```bash
curl http://localhost:5001/login
```

### Verificar que la instancia de producción sigue funcionando
```bash
curl http://localhost:5000/login
```

### Ver ambos servicios corriendo
```bash
ps aux | grep gunicorn | grep -E "(5000|5001)"
```

---

## Migrar Cambios de Desarrollo a Producción

Cuando estés listo para llevar los cambios a producción:

### 1. Hacer backup de producción
```bash
cd /var/www
sudo tar -czf nextris-dev-backup-$(date +%Y%m%d).tar.gz nextris-dev
```

### 2. Copiar cambios específicos
```bash
# Copiar archivos modificados de desarrollo a producción
sudo cp /var/www/nextris-dev-react/apps/api/* /var/www/nextris-dev/apps/api/
sudo cp /var/www/nextris-dev-react/requirements.txt /var/www/nextris-dev/
```

### 3. Actualizar dependencias en producción
```bash
cd /var/www/nextris-dev
sudo -u nextris venv/bin/pip install -r requirements.txt
```

### 4. Reiniciar producción
```bash
sudo systemctl restart nextris-dev.service
```

---

## Arquitectura Recomendada para Migración

```
/var/www/nextris-dev-react/
├── apps/                              # Backend Flask
│   ├── api/                          # NUEVO: API REST
│   │   ├── __init__.py
│   │   ├── auth.py                   # Endpoints de autenticación
│   │   ├── patients.py               # Endpoints de pacientes
│   │   ├── studies.py                # Endpoints de estudios
│   │   └── appointments.py           # Endpoints de citas
│   ├── authentication/               # Mantener para compatibilidad
│   └── home/                         # Mantener para compatibilidad
│
├── frontend-react/                   # NUEVO: Aplicación React
│   ├── public/
│   ├── src/
│   │   ├── components/              # Componentes reutilizables
│   │   ├── pages/                   # Páginas principales
│   │   ├── services/                # Servicios de API
│   │   ├── contexts/                # Contextos (Auth, etc.)
│   │   ├── hooks/                   # Custom hooks
│   │   ├── utils/                   # Utilidades
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
│
└── venv/                             # Entorno virtual Python
```

---

## Variables de Entorno

### Archivo .env del desarrollo (Puerto 5001)
```bash
cat /var/www/nextris-dev-react/.env
```

Contenido actual:
```
DEBUG=True
FLASK_APP=run.py
FLASK_DEBUG=1
FLASK_PORT=5001
ASSETS_ROOT=/static/assets
DB_USER=pacs
DB_PASS=pacs
DB_HOST=148.230.72.8
DB_PORT=5432
DB_NAME=pacsdb
IPSERVER=148.230.72.8
BASE_FOLDER=/app/output_pdfs
SECRET_KEY=nextris_123456789
DICOM_VIEWER_URL=https://viewer.nextris.cloud/
```

### Agregar variables para JWT
```bash
echo "JWT_SECRET_KEY=tu-clave-super-secreta-cambiar-en-produccion" >> /var/www/nextris-dev-react/.env
```

---

## Testing de la Instancia de Desarrollo

### Test 1: Verificar login
```bash
curl -X POST http://localhost:5001/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=1234&login=1"
```

### Test 2: Verificar ruta React
```bash
curl http://localhost:5001/react-login
```

### Test 3: Verificar API (después de implementarla)
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"1234","user_type":"staff"}'
```

---

## Comparación de Instancias

| Característica | Producción (5000) | Desarrollo (5001) |
|----------------|-------------------|-------------------|
| Directorio | `/var/www/nextris-dev` | `/var/www/nextris-dev-react` |
| Puerto | 5000 | 5001 |
| Servicio | `nextris-dev.service` | `nextris-dev-react.service` |
| Base de datos | Compartida (mismo PostgreSQL) | Compartida (mismo PostgreSQL) |
| Logs | `journalctl -u nextris-dev.service` | `journalctl -u nextris-dev-react.service` |
| Propósito | ✅ Sistema estable | 🔧 Desarrollo/Testing |

---

## Troubleshooting

### El puerto 5001 no responde
```bash
# Ver logs
journalctl -u nextris-dev-react.service -n 50

# Reiniciar servicio
sudo systemctl restart nextris-dev-react.service

# Verificar que no esté ocupado el puerto
lsof -i :5001
```

### Cambios no se reflejan
```bash
# El flag --reload debería detectar cambios, pero si no:
sudo systemctl restart nextris-dev-react.service

# O tocar el archivo run.py para forzar reload
touch /var/www/nextris-dev-react/run.py
```

### Conflictos con producción
```bash
# Ambas instancias comparten la misma base de datos
# Ten cuidado con migraciones o cambios de esquema

# Para usar base de datos diferente (opcional):
# 1. Crear nueva base de datos en PostgreSQL
# 2. Modificar .env de desarrollo con nuevo DB_NAME
```

---

## Comandos Rápidos

```bash
# Ver estado de ambos servicios
systemctl status nextris-dev.service nextris-dev-react.service

# Reiniciar desarrollo
sudo systemctl restart nextris-dev-react.service

# Ver logs de desarrollo
journalctl -u nextris-dev-react.service -f

# Editar código
cd /var/www/nextris-dev-react

# Comparar archivos entre instancias
diff /var/www/nextris-dev/apps/authentication/routes.py \
     /var/www/nextris-dev-react/apps/authentication/routes.py
```

---

## Siguientes Pasos

1. **Instalar dependencias para API REST:**
   ```bash
   cd /var/www/nextris-dev-react
   source venv/bin/activate
   pip install flask-cors flask-jwt-extended
   ```

2. **Crear estructura de API** siguiendo la guía en `MIGRACION_REACT.md`

3. **Crear proyecto React** en `/var/www/nextris-dev-react/frontend-react`

4. **Implementar endpoints gradualmente** sin afectar producción

5. **Probar exhaustivamente** en el puerto 5001

6. **Migrar a producción** cuando esté listo y probado

---

## Notas Importantes

⚠️ **Ambas instancias comparten la misma base de datos PostgreSQL**
- Ten cuidado con cambios en el esquema de base de datos
- Los datos son compartidos entre ambas instancias
- Las sesiones de usuario son independientes

⚠️ **La instancia de desarrollo usa --reload**
- Los cambios en el código se detectan automáticamente
- Puede haber un pequeño delay (1-2 segundos)
- En algunos casos necesitarás reiniciar manualmente

✅ **Beneficios de esta configuración:**
- Puedes experimentar sin romper producción
- Fácil comparar código entre versiones
- Pruebas con datos reales
- Rollback simple si algo sale mal

---

**Creado:** 4 de diciembre de 2025
**Puerto Producción:** 5000 - **NO TOCAR**
**Puerto Desarrollo:** 5001 - **USAR PARA REACT**
