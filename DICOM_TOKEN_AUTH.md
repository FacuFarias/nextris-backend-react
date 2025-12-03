# Sistema de Autenticación por Token para Visor DICOM

## Descripción General

Este sistema implementa autenticación segura basada en tokens de Keycloak para visualizar estudios DICOM en OHIF Viewer, con control de acceso granular por ubicación (location).

## Flujo de Autenticación

### 1. Usuario Solicita Ver Estudio DICOM

Cuando un usuario hace clic en el ícono del ojo para ver un estudio:

```javascript
// Frontend: nrframework.js
VerDcm(study_instance_uid)
```

### 2. Validación de Permisos (Backend)

El endpoint `/generate_dicom_token` ejecuta el siguiente flujo de seguridad:

#### Paso 1: Verificar Location del Estudio
```sql
SELECT location_id 
FROM nextris.tbexamination 
WHERE studyinstanceuid = %s
```

#### Paso 2: Validar Acceso del Usuario
```sql
SELECT 1 
FROM nextris.rel_user_location 
WHERE user_id = %s AND location_id = %s
```

Si el usuario NO tiene acceso → **403 Forbidden**

### 3. Generación de Token Keycloak

Si el usuario tiene acceso, se genera un token de Keycloak usando credenciales genéricas:

```python
# Usuario genérico de visualización (configurado en .env)
KEYCLOAK_VIEWER_USER=nextrisviewer
KEYCLOAK_VIEWER_PASSWORD=viewer
```

**Características del Token:**
- **Duración:** 5 minutos (configurable en Keycloak)
- **Alcance:** Solo para el `studyInstanceUID` solicitado
- **Usuario:** `nextrisviewer` (sin permisos administrativos)
- **Tipo:** Bearer token JWT de Keycloak

### 4. URL del Visor con Token

La URL generada incluye el token en el fragment (después del `#`):

```
https://viewer.nextris.cloud/viewer?StudyInstanceUIDs=1.2.826...#token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**¿Por qué en el fragment?**
- El fragment (`#token=...`) NO se envía al servidor en las peticiones HTTP
- Solo el navegador lo procesa con JavaScript
- Más seguro que query parameters que se loguean en servidores

### 5. OHIF Viewer Lee el Token

El visor OHIF debe estar configurado para:

1. Leer el token desde `window.location.hash`
2. Incluirlo en todas las peticiones DICOM a DCM4CHEE
3. Validar que el token no haya expirado

## Configuración Requerida

### Variables de Entorno (.env)

```bash
# Keycloak Server
KEYCLOAK_SERVER_URL=https://keycloak.example.com/auth
KEYCLOAK_REALM=nextris
KEYCLOAK_CLIENT_ID=nextris-app
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Usuario genérico de visualización
KEYCLOAK_VIEWER_USER=nextrisviewer
KEYCLOAK_VIEWER_PASSWORD=viewer

# URL del visor DICOM
DICOM_VIEWER_URL=https://viewer.nextris.cloud/viewer
```

### Configuración de Keycloak

#### 1. Crear Cliente en Keycloak

**Nombre:** `nextris-app`
**Client Protocol:** `openid-connect`
**Access Type:** `confidential`
**Valid Redirect URIs:** `https://viewer.nextris.cloud/*`
**Web Origins:** `https://viewer.nextris.cloud`

#### 2. Crear Usuario de Visualización

**Username:** `nextrisviewer`
**Password:** `viewer` (credential permanente, no temporal)
**Email Verified:** Sí
**Enabled:** Sí

#### 3. Asignar Rol de Visualización

Crear rol `dicom-viewer` con permisos:
- Leer estudios DICOM
- Sin permisos de modificación
- Sin acceso administrativo

Asignar el rol al usuario `nextrisviewer`.

#### 4. Configurar Token Lifetime

En **Realm Settings → Tokens:**
- **Access Token Lifespan:** 5 minutos
- **SSO Session Idle:** 5 minutos
- **SSO Session Max:** 10 minutos

## Configuración de OHIF Viewer

### app-config.js

```javascript
window.config = {
  routerBasename: '/viewer',
  extensions: [],
  modes: [],
  
  // Configuración de DataSource
  dataSources: [
    {
      friendlyName: 'DCM4CHEE PACS',
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',
      configuration: {
        name: 'DCM4CHEE',
        wadoUriRoot: 'https://pacs.example.com/dcm4chee-arc/aets/DCM4CHEE/wado',
        qidoRoot: 'https://pacs.example.com/dcm4chee-arc/aets/DCM4CHEE/rs',
        wadoRoot: 'https://pacs.example.com/dcm4chee-arc/aets/DCM4CHEE/rs',
        
        // Interceptor para incluir token
        requestOptions: {
          requestHeaders: () => {
            // Leer token del fragment
            const hash = window.location.hash;
            const tokenMatch = hash.match(/token=([^&]+)/);
            const token = tokenMatch ? tokenMatch[1] : null;
            
            if (token) {
              return {
                Authorization: `Bearer ${token}`
              };
            }
            return {};
          }
        }
      }
    }
  ]
};
```

## API Endpoints

### POST /generate_dicom_token

Genera token de Keycloak para visualizar un estudio DICOM.

**Request:**
```json
{
  "studyInstanceUID": "1.2.826.0.1.3680043.8.498.13201767099594831302408562419423378227"
}
```

**Response (Éxito):**
```json
{
  "success": true,
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "tokenType": "keycloak",
  "expiresIn": 300,
  "studyInstanceUID": "1.2.826...",
  "location_id": "550e8400-e29b-41d4-a716-446655440000",
  "viewer_user": "nextrisviewer"
}
```

**Response (Sin Acceso):**
```json
{
  "error": "No tiene permisos para visualizar este estudio",
  "location_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### POST /validate_dicom_token

Valida un token JWT (para testing o validación adicional).

**Request:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "studyInstanceUID": "1.2.826..."
}
```

**Response:**
```json
{
  "valid": true,
  "tokenType": "keycloak",
  "note": "Token de Keycloak - validar en DCM4CHEE"
}
```

## Seguridad

### Ventajas del Sistema

1. **Control de Acceso Granular:** Por location/sede
2. **Token de Corta Duración:** 5 minutos máximo
3. **Usuario Sin Privilegios:** `nextrisviewer` solo puede leer
4. **Auditoría:** Logs de quién solicitó qué estudio
5. **No Credenciales en URL:** Token en fragment, no en query params
6. **Integración Estándar:** Compatible con Keycloak/DCM4CHEE

### Consideraciones

- El token NO se puede reutilizar para otros estudios
- El usuario debe tener relación en `rel_user_location`
- Si el estudio no tiene `location_id`, se deniega acceso
- Los logs registran todos los intentos de acceso

## Logs de Auditoría

Cada operación genera logs estructurados:

```
INFO: Acceso autorizado - Usuario: jsmith - Location: uuid-123 - Estudio: 1.2.826...
INFO: Token Keycloak generado - Usuario solicitante: jsmith - Estudio: 1.2.826... - Expira en: 300s
WARNING: Acceso denegado - Usuario: jdoe (uuid-456) - Location: uuid-789 - Estudio: 1.2.826...
```

## Testing

### 1. Probar Generación de Token

```bash
curl -X POST https://your-server.com/generate_dicom_token \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your-session-cookie" \
  -d '{"studyInstanceUID": "1.2.826..."}'
```

### 2. Verificar Token en Keycloak

```bash
curl -X POST https://keycloak.example.com/auth/realms/nextris/protocol/openid-connect/token/introspect \
  -d "token=YOUR_TOKEN" \
  -d "client_id=nextris-app" \
  -d "client_secret=your-secret"
```

## Troubleshooting

### Error: "Configuración de Keycloak incompleta"

Verificar variables en `.env`:
```bash
echo $KEYCLOAK_SERVER_URL
echo $KEYCLOAK_REALM
echo $KEYCLOAK_CLIENT_ID
```

### Error: "No tiene permisos para visualizar este estudio"

Verificar relación usuario-location:
```sql
SELECT * FROM nextris.rel_user_location 
WHERE user_id = 'user-guid';
```

### Error: "Estudio sin ubicación asignada"

Actualizar `location_id` en el estudio:
```sql
UPDATE nextris.tbexamination 
SET location_id = 'location-uuid' 
WHERE studyinstanceuid = '1.2.826...';
```

### Token Expirado

El token de Keycloak expira en 5 minutos. El usuario debe regenerarlo haciendo clic nuevamente en el ícono del ojo.

## Diagrama de Flujo

```
Usuario → Click Ojo
    ↓
Frontend: VerDcm(studyUID)
    ↓
POST /generate_dicom_token
    ↓
¿Existe studyUID en tbexamination? → NO → 404
    ↓ SÍ
Obtener location_id
    ↓
¿Usuario en rel_user_location? → NO → 403
    ↓ SÍ
Solicitar token a Keycloak (nextrisviewer)
    ↓
Token generado (5 min)
    ↓
URL: viewer?StudyInstanceUIDs=...#token=...
    ↓
window.open(URL)
    ↓
OHIF lee token del fragment
    ↓
Peticiones DICOM con Header: Authorization: Bearer {token}
    ↓
DCM4CHEE valida token con Keycloak
    ↓
Imágenes DICOM mostradas
```

## Mantenimiento

- **Rotación de Contraseña:** Cambiar `KEYCLOAK_VIEWER_PASSWORD` periódicamente
- **Monitoreo:** Revisar logs de acceso denegado
- **Limpieza:** Los tokens expiran automáticamente, no requieren limpieza manual
- **Actualización de Permisos:** Gestionar `rel_user_location` según necesidades

## Autor

Implementado por: Facundo Farias
Fecha: Diciembre 2025
Versión: 1.0
