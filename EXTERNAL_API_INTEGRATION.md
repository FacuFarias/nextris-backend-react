# API Externa NextRIS - Guía de Integración

## Endpoint Principal

### POST /api/external/receive-study

Recibe un paciente, examen y reporte. El reporte se firma automáticamente; el PDF se genera bajo demanda.

**URL:** `http://<IP_SERVIDOR>/api/external/receive-study`

**No requiere autenticación.**

---

### Formato del Request

```json
{
  "patient": {
    "name": "Juan",
    "surname": "Perez",
    "dni": "12345678",
    "birthdate": "1980-05-15",
    "sexcode": "M",
    "email": "juan@email.com",
    "phone": "1155555555"
  },
  "examination": {
    "studytype_id": "uuid-tipo-estudio",
    "history": "Dolor torácico"
  },
  "report": {
    "findings": "Hallazgos del estudio...",
    "impressions": "Impresión diagnóstica...",
    "techniques": "Técnica utilizada...",
    "conclusions": "Conclusión final..."
  },
  "rad_id": "jghibaudo",
  "study_uid": "1.2.840.113619.2.55.3.1234"
}
```

---

### Campos

#### patient (REQUERIDO)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| name | string | SÍ | Nombre del paciente |
| surname | string | SÍ | Apellido del paciente |
| dni | string | SÍ | DNI / Documento de identidad |
| birthdate | string | NO | Fecha de nacimiento (YYYY-MM-DD) |
| sexcode | string | NO | Sexo: M, F, I (Indeterminado) |
| email | string | NO | Email del paciente |
| phone | string | NO | Teléfono del paciente |

**Lógica de búsqueda:** Si ya existe un paciente con el mismo `dni`, se reutiliza. Si no existe, se crea uno nuevo.

**Usuario portal:** Se crea automáticamente con:
- Username = DNI (ej: "12345678")
- Password = últimos 3 dígitos del DNI (ej: "678")
- No pide cambio de contraseña

#### examination (REQUERIDO)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| studytype_id | string | SÍ | UUID del tipo de estudio |
| history | string | NO | Historia clínica |

#### report (REQUERIDO)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| findings | string | SÍ | Hallazgos del estudio |
| impressions | string | SÍ | Impresión diagnóstica |
| techniques | string | SÍ | Técnica utilizada |
| conclusions | string | SÍ | Conclusión del estudio |

**Nota:** El reporte se firma automáticamente y se marca como `isreported=1`. El PDF sólo se genera cuando un consumidor lo solicita.

#### rad_id (OPCIONAL)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| rad_id | string | NO | Username del radiólogo que firma el reporte |

Si se proporciona, se asigna como `iduser` en el reporte (quien firma). Debe ser un username válido existente en la tabla `tbuser`.

#### study_uid (OPCIONAL)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| study_uid | string | NO | StudyInstanceUID de la imagen en el PACS |

Si se proporciona, el sistema intentará vincular el estudio del PACS al examen creado. Si el study_uid no existe en el PACS, el examen se crea sin vincular.

---

### Formato del Response

```json
{
  "success": true,
  "request_id": "uuid-de-la-transaccion",
  "patient": {
    "guid": "uuid-del-paciente",
    "nationalcode": "12345678",
    "username": "12345678",
    "is_new": true,
    "portal_user_created": true
  },
  "examination": {
    "guid": "uuid-del-examen",
    "admisionnumber": "ADM001",
    "studytype_id": "uuid-tipo-estudio"
  },
  "report": {
    "guid": "uuid-del-reporte",
    "rad_id": "jghibaudo"
  },
  "pacs_link": {
    "linked": true,
    "study_uid": "1.2.840.113619.2.55.3.1234",
    "error": null
  }
}
```

---

### Códigos de Respuesta

| Código | Significado |
|--------|-------------|
| 201 | Creado exitosamente |
| 400 | Error de validación (campos faltantes) |
| 500 | Error interno del servidor |

---

### Ejemplo con cURL

```bash
curl -X POST http://192.168.0.76/api/external/receive-study \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "name": "Maria",
      "surname": "Lopez",
      "dni": "40222333",
      "birthdate": "1992-08-20",
      "sexcode": "F"
    },
    "examination": {
      "studytype_id": "ce56d4af-dfc9-475b-bcdb-c000ea28267c"
    },
    "report": {
      "findings": "Hallazgos del estudio de mamografía bilateral",
      "impressions": "BI-RADS 2 - Hallazgos benignos",
      "techniques": "Mamografía bilateral en proyecciones CC y MLO",
      "conclusions": "Control rutinario sin hallazgos patológicos"
    },
    "rad_id": "jghibaudo"
  }'
```

---

### Ejemplo con Python (requests)

```python
import requests

url = "http://192.168.0.76/api/external/receive-study"

payload = {
    "patient": {
        "name": "Maria",
        "surname": "Lopez",
        "dni": "40222333",
        "birthdate": "1992-08-20",
        "sexcode": "F"
    },
    "examination": {
        "studytype_id": "ce56d4af-dfc9-475b-bcdb-c000ea28267c"
    },
    "report": {
        "findings": "Hallazgos del estudio de mamografía bilateral",
        "impressions": "BI-RADS 2 - Hallazgos benignos",
        "techniques": "Mamografía bilateral en proyecciones CC y MLO",
        "conclusions": "Control rutinario sin hallazgos patológicos"
    },
    "rad_id": "jghibaudo"
}

response = requests.post(url, json=payload)
print(response.json())
```

---

### Ejemplo con JavaScript (fetch)

```javascript
const url = "http://192.168.0.76/api/external/receive-study";

const payload = {
  patient: {
    name: "Maria",
    surname: "Lopez",
    dni: "40222333",
    birthdate: "1992-08-20",
    sexcode: "F"
  },
  examination: {
    studytype_id: "ce56d4af-dfc9-475b-bcdb-c000ea28267c"
  },
  report: {
    findings: "Hallazgos del estudio de mamografía bilateral",
    impressions: "BI-RADS 2 - Hallazgos benignos",
    techniques: "Mamografía bilateral en proyecciones CC y MLO",
    conclusions: "Control rutinario sin hallazgos patológicos"
  },
  rad_id: "jghibaudo"
};

fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## Consulta de Logs

### GET /api/external/logs

Consulta el historial de llamadas a la API.

**Query params opcionales:**
- `nationalcode` - Filtrar por DNI
- `status` - Filtrar por status (success/error)
- `date_from` - Fecha desde (YYYY-MM-DD)
- `date_to` - Fecha hasta (YYYY-MM-DD)
- `page` - Número de página (default: 1)
- `per_page` - Resultados por página (default: 50, max: 200)

**Ejemplo:**
```bash
curl "http://192.168.0.76/api/external/logs?nationalcode=40222333"
```

### GET /api/external/logs/<request_id>

Obtiene el detalle completo de una llamada específica.

**Ejemplo:**
```bash
curl "http://192.168.0.76/api/external/logs/3b2fd1c2-1a1e-48b5-9ddd-2ac113fd8952"
```

---

## Comportamiento del Sistema

### Paciente nuevo vs existente
- Si el `dni` ya existe en la base de datos, se reutiliza el paciente existente
- Se le agrega el nuevo examen a ese paciente
- El campo `is_new` en la respuesta indica si el paciente fue creado o reutilizado

### Credenciales del portal
- Username = DNI
- Password = últimos 3 dígitos del DNI
- No pide cambio de contraseña en el primer login
- Acceso: `http://<IP>/pacientes`

### Firma automática del reporte
- El reporte se firma automáticamente al recibirlo
- El PDF con firma digital se genera bajo demanda desde el contenido vigente
- Se marca `isreported=1` en el examen

### Vinculación con PACS
- Si se envía `study_uid`, el sistema busca el estudio en el PACS
- Si lo encuentra, vincula automáticamente
- Si no lo encuentra, crea el examen sin vincular y retorna el error en `pacs_link.error`
- El examen se crea de todas formas (comportamiento permisivo)

### IDs requeridos
- `studytype_id`: UUID del tipo de estudio. Consultar con el administrador del sistema.

---

## IDs de prueba disponibles

| Tipo | ID | Descripción |
|------|-----|-------------|
| studytype_id | `ce56d4af-dfc9-475b-bcdb-c000ea28267c` | BIOPSIA ESTEREOTAXICA |
| rad_id | `jghibaudo` | Juan Ghibaudo (Administrador) |

---

## Consulta de IDs disponibles

Para obtener los IDs de study types, usar este endpoint (requiere autenticación JWT):

```bash
# Login para obtener token
TOKEN=$(curl -s -X POST http://<IP>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<usuario>", "password": "<password>", "user_type": "staff"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# Study types
curl -H "Authorization: Bearer $TOKEN" http://<IP>/api/study-types

# Usuarios (radiólogos)
curl -H "Authorization: Bearer $TOKEN" http://<IP>/api/users_physician
```
