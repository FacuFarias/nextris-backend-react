# SOLUCIÓN: Error 401 UNAUTHORIZED en Cargar Estudios DICOM

## Problema Identificado

El error `401 (UNAUTHORIZED)` en las peticiones:
- `GET /api/dicom/unlinked-studies`
- `POST /api/dicom/upload`

Significa que **no hay un token JWT válido** en el navegador.

## Por qué ocurre esto

El sistema React usa autenticación JWT (JSON Web Tokens). Cuando inicias sesión:

1. El backend genera un token JWT
2. El frontend lo guarda en `localStorage` bajo la clave `authData`
3. Cada petición al backend incluye este token en el header `Authorization: Bearer <token>`
4. El backend valida el token y permite el acceso

**Si no hay token o expiró → Error 401**

## SOLUCIÓN

### Paso 1: Verifica si estás logueado

1. Abre el navegador en: **http://148.230.72.8:5173/**
2. ¿Ves la página de login o ya estás dentro del sistema?

### Paso 2: Si ves la página de login

1. Ingresa tus credenciales de usuario
2. Haz clic en "Ingresar al Sistema"
3. Una vez logueado, prueba nuevamente cargar estudios

### Paso 3: Si ya estás logueado pero sigues viendo el error

El token puede haber expirado. Para verificar:

1. Abre las DevTools del navegador (presiona **F12**)
2. Ve a la pestaña **"Application"** (Chrome) o **"Almacenamiento"** (Firefox)
3. En el panel izquierdo, expande **"Local Storage"**
4. Haz clic en **http://148.230.72.8:5173**
5. Busca la clave **`authData`**

#### Si `authData` NO existe o está vacío:

**Solución:** Necesitas volver a hacer login

1. Busca el botón de "Cerrar sesión" o "Logout" en la aplicación
2. Cierra sesión
3. Vuelve a hacer login con tus credenciales
4. El sistema guardará un nuevo token

#### Si `authData` existe y tiene contenido:

**Contenido esperado:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "...",
    "username": "...",
    "name": "...",
    "user_type": "staff"
  }
}
```

**Si el formato es correcto:**

El token puede haber expirado. Cierra sesión y vuelve a loguearte.

**Si el formato es incorrecto:**

1. Borra manualmente la clave `authData` en DevTools
2. Recarga la página (F5)
3. Vuelve a hacer login

### Paso 4: Probar después de login

Una vez que hayas iniciado sesión correctamente:

1. Ve al módulo de **"Cargar Estudios"**
2. Intenta subir un archivo DICOM
3. Debería funcionar sin errores 401

## Verificación del Login API

Si quieres probar que el login funciona correctamente desde la línea de comandos:

```bash
# Cambiar "admin" y "admin123" por tu usuario/contraseña real
curl -X POST http://148.230.72.8:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "user_type": "staff"
  }'
```

Deberías recibir una respuesta con `access_token` y `refresh_token`.

## Notas Importantes

- **Seguridad:** Los tokens JWT tienen un tiempo de expiración. Cuando expiran, debes volver a loguearte.
- **Sincronización:** Si abres la aplicación en varias pestañas, el token se comparte entre todas.
- **Logout:** Siempre cierra sesión correctamente para limpiar el token del navegador.

## Si el problema persiste

Contacta al administrador del sistema para verificar:
- Tu cuenta de usuario está activa
- Tienes permisos para acceder al módulo de cargar estudios
- La configuración del JWT en el backend está correcta
