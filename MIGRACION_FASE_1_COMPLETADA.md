# Migración a React - Fase 1 Completada

## ✅ Cambios Implementados

### 1. Dependencias Instaladas
Se instalaron las siguientes dependencias en el backend:
- **flask-cors** (4.0.0) - Para permitir peticiones CORS desde React
- **flask-jwt-extended** (4.6.0) - Para autenticación con JWT tokens
- **PyJWT** (2.10.1) - Dependencia de flask-jwt-extended

### 2. Configuración del Backend

#### `apps/__init__.py`
- ✅ Importado `CORS` y `JWTManager`
- ✅ Inicializado JWT en `register_extensions()`
- ✅ Configurado CORS para permitir peticiones desde:
  - `http://localhost:3000` (React dev server - Create React App)
  - `http://localhost:5173` (React dev server - Vite)
  - `http://148.230.72.8:3000` (Producción)
  - `http://148.230.72.8:5173` (Producción)
- ✅ Registrado el nuevo blueprint `/api`

#### `apps/config.py`
- ✅ Agregada configuración JWT:
  - `JWT_SECRET_KEY` - Clave secreta para firmar tokens
  - `JWT_ACCESS_TOKEN_EXPIRES` - 1 hora de duración
  - `JWT_REFRESH_TOKEN_EXPIRES` - 30 días de duración
  - `JWT_TOKEN_LOCATION` - Headers
  - `JWT_HEADER_NAME` - Authorization
  - `JWT_HEADER_TYPE` - Bearer

### 3. Nuevo Blueprint API REST

Se creó la estructura `apps/api/` con los siguientes archivos:

#### `apps/api/__init__.py`
- Blueprint principal con prefijo `/api`
- Endpoint de health check: `GET /api/health`

#### `apps/api/auth.py` - Endpoints de Autenticación

| Endpoint | Método | Descripción | Autenticación |
|----------|--------|-------------|---------------|
| `/api/auth/login` | POST | Login con JWT | No |
| `/api/auth/me` | GET | Usuario actual | JWT requerido |
| `/api/auth/refresh` | POST | Refrescar token | Refresh token |
| `/api/auth/logout` | POST | Logout | JWT requerido |

**Características:**
- Soporta login de staff y pacientes
- Retorna `access_token` y `refresh_token`
- Claims adicionales: `user_type` y `username`
- Validación de contraseñas con bcrypt
- Verificación de usuarios activos

#### `apps/api/patients.py` - Endpoints de Pacientes

| Endpoint | Método | Descripción | Autenticación |
|----------|--------|-------------|---------------|
| `/api/patients` | GET | Lista paginada | JWT requerido |
| `/api/patients/<guid>` | GET | Detalle de paciente | JWT requerido |
| `/api/patients` | POST | Crear paciente | JWT requerido |
| `/api/patients/<guid>` | PUT | Actualizar paciente | JWT requerido |

**Características:**
- Paginación (page, per_page)
- Búsqueda por nombre, apellido o DNI
- Validación de campos requeridos
- Generación automática de GUID

#### `apps/api/studies.py` - Endpoints de Estudios

| Endpoint | Método | Descripción | Autenticación |
|----------|--------|-------------|---------------|
| `/api/studies` | GET | Lista de estudios | JWT requerido |
| `/api/studies/<guid>` | GET | Detalle + series | JWT requerido |
| `/api/studies/patient/<patient_id>` | GET | Estudios de paciente | JWT requerido |

**Características:**
- Filtros: patient_id, modality, date_from, date_to
- Paginación
- Control de acceso (pacientes solo ven sus estudios)
- Incluye información de series

---

## 🧪 Pruebas de Endpoints

### Health Check
```bash
curl http://localhost:5001/api/health
```

**Respuesta:**
```json
{
  "success": true,
  "message": "NextRIS API is running",
  "version": "1.0.0"
}
```

### Login (Staff)
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "tu_password",
    "user_type": "staff"
  }'
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": {
      "id": "guid-del-usuario",
      "username": "admin",
      "name": "Nombre",
      "surname": "Apellido",
      "email": "email@example.com",
      "user_type": "Administrador",
      "role_id": "guid-del-rol",
      "requires_password_change": false
    }
  },
  "message": "Login exitoso"
}
```

### Obtener Usuario Actual
```bash
curl http://localhost:5001/api/auth/me \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

### Listar Pacientes
```bash
curl "http://localhost:5001/api/patients?page=1&per_page=10&search=juan" \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

### Obtener Estudios de un Paciente
```bash
curl http://localhost:5001/api/studies/patient/PATIENT_GUID \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

---

## 📋 Próximos Pasos

### Fase 2: Frontend React (Pendiente)

1. **Crear proyecto React**
   ```bash
   cd /var/www
   npx create-react-app nextris-frontend
   # O con Vite (más rápido)
   npm create vite@latest nextris-frontend -- --template react
   ```

2. **Instalar dependencias**
   ```bash
   cd nextris-frontend
   npm install axios react-router-dom @tanstack/react-query zustand
   ```

3. **Configurar variables de entorno**
   Crear `.env`:
   ```
   REACT_APP_API_URL=http://148.230.72.8:5001/api
   ```

4. **Crear estructura básica**
   - `src/services/api.js` - Cliente Axios configurado
   - `src/contexts/AuthContext.jsx` - Context de autenticación
   - `src/pages/Login.jsx` - Página de login
   - `src/pages/Dashboard.jsx` - Dashboard principal
   - `src/components/` - Componentes reutilizables

5. **Implementar módulos**
   - Portal de Pacientes (ver estudios)
   - Gestión de Pacientes
   - Agenda de Citas
   - Visualizador DICOM
   - Editor de Informes

---

## 🔧 Configuración Adicional Necesaria

### Para Producción

1. **Nginx como Proxy Reverso**
   ```nginx
   server {
       listen 80;
       server_name nextris.example.com;

       # Frontend React (build estático)
       location / {
           root /var/www/nextris-frontend/build;
           try_files $uri $uri/ /index.html;
       }

       # Backend API
       location /api/ {
           proxy_pass http://localhost:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Variables de Entorno**
   Agregar a `.env` del backend:
   ```
   JWT_SECRET_KEY=clave-super-secreta-cambiar-en-produccion
   ```

3. **HTTPS**
   - Configurar certificado SSL con Let's Encrypt
   - Actualizar CORS origins para HTTPS

---

## 📝 Notas Importantes

### Compatibilidad Retroactiva
- ✅ El sistema actual (templates Jinja2) sigue funcionando
- ✅ Los endpoints API son **adicionales**, no reemplazan nada
- ✅ Puedes migrar módulo por módulo sin afectar el resto

### Seguridad
- Los tokens JWT expiran en 1 hora
- El refresh token dura 30 días
- Los pacientes solo pueden acceder a sus propios estudios
- Todas las rutas API requieren autenticación (excepto login)

### Testing
- Usa Postman o Thunder Client para probar endpoints
- El health check debe responder siempre: `/api/health`
- Verifica CORS haciendo peticiones desde el navegador

---

## 🐛 Solución de Problemas

### Error: "CORS policy"
- Verifica que el origen esté en la lista de CORS en `apps/__init__.py`
- Asegúrate de que el frontend use el puerto correcto (3000 o 5173)

### Error: "Token has expired"
- Usa el refresh token para obtener un nuevo access token
- Endpoint: `POST /api/auth/refresh`

### Error: "Credenciales inválidas"
- Verifica que el usuario exista y esté activo
- Para staff: campo `is_active` debe ser 1
- Para pacientes: campo `status` debe ser activo

---

**Estado actual:** ✅ Backend API REST completamente funcional
**Siguiente fase:** 🚀 Crear frontend React

---

*Última actualización: 4 de diciembre de 2025*
