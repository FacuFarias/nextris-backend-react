# Integración HL7 ORU^R01 — Documentación para el cliente

## Resumen

Cuando un reporte es firmado en NextRIS, el sistema envía automáticamente un mensaje **HL7 v2.3 ORU^R01** (Unsolicited Observation Result) por **MLLP/TCP** al servidor HL7 configurado.

Este envío está controlado por el flag `hl7_enable_report_sending` en la tabla `tbfacility` de cada institución.

---

## Conexión

| Parámetro | Valor |
|-----------|-------|
| **Protocolo** | MLLP (Minimum Lower Layer Protocol) sobre TCP |
| **Host** | Configurado en variable de entorno `IPSERVER` (default: `127.0.0.1`) |
| **Puerto** | `9193` |
| **Timeout** | 10 segundos |
| **Reintentos** | 3 intentos con 1 segundo de espera entre cada uno |

### MLLP Framing

Los mensajes se envían con los delimitadores MLLP estándar:

```
<VB>  mensaje HL7  <FS><CR>
```

- `<VB>` = `0x0B` (Vertical Tab — Start of Block)
- `<FS>` = `0x1C` (File Separator — End of Block)
- `<CR>` = `0x0D` (Carriage Return)

El servidor receptor debe responder con un **ACK** dentro del mismo bloque MLLP.

---

## Estructura del mensaje ORU^R01

### Segmentos

| Segmento | Nombre | Descripción |
|----------|--------|-------------|
| MSH | Message Header | Encabezado del mensaje |
| PID | Patient Identification | Datos del paciente |
| PV1 | Patient Visit | Ubicación/institución |
| OBR | Observation Request | Datos del estudio/orden |
| OBX | Observation Result | Contenido del reporte (6 segmentos) |

### Ejemplo de mensaje completo

```
MSH|^~\&|RIS|SUS|PACS|Radiology|20260616143025||ORU^R01|a1b2c3d4|P|2.3
PID|||00001234||García^Juan Carlos||19850315|M
PV1|||CLINICA 1
OBR|1||ACC0456||RX TORAX PA Y LATERAL||||||Dr. López
OBX|1|TX|FINDINGS||Se observa campos pulmonares libres. Cardiomegalia leve.\\.br\\No se evidencian infiltrados ni derrame pleural.||||||F
OBX|2|TX|IMPRESSIONS||Cardiomegalia leve. Sin patología pulmonar aguda.||||||F
OBX|3|TX|TECHNIQUES||Radiografía de tórax PA y lateral.||||||F
OBX|4|TX|CONCLUSIONS||Control en 6 meses.||||||F
OBX|5|TX|ACCESSION_NUMBER||ACC0456||||||F
OBX|6|TX|PDF_PATH||output_pdfs/ACC0456_00001234_Garcia_Juan_Carlos.pdf||||||F
```

---

## Detalle de cada segmento

### MSH — Message Header

| Campo | Posición | Valor | Descripción |
|-------|----------|-------|-------------|
| Field Separator | MSH-1 | `\|` | Separador de campos |
| Encoding Characters | MSH-2 | `^~\&` | Caracteres de escape HL7 |
| Sending Application | MSH-3 | `RIS` | Fijo — identifica a NextRIS |
| Sending Facility | MSH-4 | `{facility_name}` | **Nombre de la institución** (para forwarding en Mirth) |
| Receiving Application | MSH-5 | `PACS` | Destino |
| Receiving Facility | MSH-6 | `Radiology` | Destino |
| Date/Time | MSH-7 | `YYYYMMDDHHmmss` | Timestamp del envío |
| Message Type | MSH-9 | `ORU^R01` | Unsolicited Observation Result |
| Message Control ID | MSH-10 | `{uuid8}` | ID único del mensaje |
| Processing ID | MSH-11 | `P` | Production |
| Version ID | MSH-12 | `2.3` | HL7 v2.3 |

### PID — Patient Identification

| Campo | Posición | Valor | Descripción |
|-------|----------|-------|-------------|
| Patient ID | PID-3 | `{patientid}` | ID interno del paciente (ej: `00001234`) |
| Patient Name | PID-5 | `{surname}^{name}` | Apellido^Nombre |
| Date of Birth | PID-7 | `YYYYMMDD` | Fecha de nacimiento |
| Sex | PID-8 | `M`/`F`/`O`/`I` | Sexo del paciente |

### PV1 — Patient Visit

| Campo | Posición | Valor | Descripción |
|-------|----------|-------|-------------|
| Assigned Location | PV1-3 | `{location_name}` | **Nombre de la ubicación/sede** |

### OBR — Observation Request

| Campo | Posición | Valor | Descripción |
|-------|----------|-------|-------------|
| Set ID | OBR-1 | `1` | Fijo |
| Placer Order Number | OBR-2 | `{accession_number}` | Número de acceso del estudio |
| Universal Service ID | OBR-4 | `{study_description}` | Descripción del tipo de estudio |
| Ordering Provider | OBR-16 | `{referring_physician}` | Médico referente/solicitante |

### OBX — Observation Result (6 segmentos)

| OBX# | Set ID | Type | Identifier | Value | Descripción |
|-------|--------|------|------------|-------|-------------|
| 1 | 1 | TX | `FINDINGS` | Texto libre | Hallazgos del estudio |
| 2 | 2 | TX | `IMPRESSIONS` | Texto libre | Impresión diagnóstica |
| 3 | 3 | TX | `TECHNIQUES` | Texto libre | Técnica utilizada |
| 4 | 4 | TX | `CONCLUSIONS` | Texto libre | Conclusión/recomendación |
| 5 | 5 | TX | `ACCESSION_NUMBER` | Texto | Número de acceso (redundante para referencia) |
| 6 | 6 | TX | `PDF_PATH` | Texto | Ruta relativa del PDF firmado |

Todos los OBX tienen:
- `Observation Result Status` = `F` (Final)
- `Units`, `References Range`, `Abnormal Flags` = vacíos

---

## Caracteres especiales HL7

Los textos del reporte pueden contener caracteres que deben escaparse para HL7:

| Carácter original | Escape HL7 | Código |
|-------------------|------------|--------|
| `\|` (pipe) | `\E\` | Separador de campos |
| `^` (caret) | `\S\` | Component separator |
| `&` (ampersand) | `\T\` | Sub-component separator |
| `~` (tilde) | `\R\` | Repetition separator |
| `\` (backslash) | `\\` | Escape character |
| Salto de línea | `\.br\` | Segment terminator |

---

## Mirth Connect — Creación del canal paso a paso

### Paso 1: Crear el canal

1. Abrir Mirth Connect Administrator
2. Ir a **Channels** → **New Channel**
3. Configurar:
   - **Name**: `NextRIS ORU Receiver` (o el nombre que prefieras)
   - **Description**: `Recibe reportes firmados de NextRIS via HL7 ORU^R01`
   - **Data Type**: `HL7V2`

### Paso 2: Source Connector (TCP Listener)

Ir a la pestaña **Source** → **Source Connector**:

| Campo | Valor |
|-------|-------|
| **Protocol** | `TCP Listener` |
| **Listener Interface** | `0.0.0.0` (escucha en todas las interfaces) |
| **Port** | `9193` |
| **Transmission Mode** | `MLLP` |
| **Override MLLP** | No (usa los defaults) |
| **Start of Block Byte** | `11` (0x0B) |
| **End of Block Byte** | `28` (0x1C) |
| **End of Block Extra Byte** | `13` (0x0D) |
| **Char-set** | `UTF-8` |
| **Receive Timeout (ms)** | `10000` |

**Response**: El canal automáticamente envía el ACK generado por el transformer (ver paso 3).

### Paso 3: Source Transformer (JavaScript)

Ir a **Source** → **Edit Transformer** → agregar un **JavaScript Step**:

```javascript
// ============================================================
// NextRIS ORU^R01 Parser
// Extrae datos del mensaje ORU y los pone en el channel map
// ============================================================

// --- MSH ---
var sendingFacility = $('MSH').getField(4);  // Nombre de la facility (SUS, etc.)
var messageControlId = $('MSH').getField(10);
var messageType = $('MSH').getField(9);

// --- PID ---
var patientId = $('PID').getField(3);         // ID del paciente
var patientName = $('PID').getField(5);       // Apellido^Nombre
var patientDob = $('PID').getField(7);        // YYYYMMDD
var patientSex = $('PID').getField(8);        // M/F/O/I

// Separar apellido y nombre
var nameParts = patientName.split('^');
var patientSurname = nameParts[0] || '';
var patientFirstName = nameParts[1] || '';

// --- PV1 ---
var locationName = $('PV1').getField(3);      // Nombre de la ubicación

// --- OBR ---
var accessionNumber = $('OBR').getField(2);   // Número de acceso
var studyDescription = $('OBR').getField(4);  // Descripción del estudio
var orderingProvider = $('OBR').getField(16); // Médico referente

// --- OBX (6 segmentos) ---
var findings = '';
var impressions = '';
var techniques = '';
var conclusions = '';
var obxAccession = '';
var pdfPath = '';

for (var i = 0; i < $('OBX').length(); i++) {
    var obx = $('OBX')[i];
    var identifier = obx.getField(3);
    var value = obx.getField(5);

    switch (identifier) {
        case 'FINDINGS':
            findings = value;
            break;
        case 'IMPRESSIONS':
            impressions = value;
            break;
        case 'TECHNIQUES':
            techniques = value;
            break;
        case 'CONCLUSIONS':
            conclusions = value;
            break;
        case 'ACCESSION_NUMBER':
            obxAccession = value;
            break;
        case 'PDF_PATH':
            pdfPath = value;
            break;
    }
}

// --- Poner todo en el Channel Map ---
channelMap.put('sendingFacility', sendingFacility);
channelMap.put('messageControlId', messageControlId);
channelMap.put('patientId', patientId);
channelMap.put('patientSurname', patientSurname);
channelMap.put('patientFirstName', patientFirstName);
channelMap.put('patientDob', patientDob);
channelMap.put('patientSex', patientSex);
channelMap.put('locationName', locationName);
channelMap.put('accessionNumber', accessionNumber);
channelMap.put('studyDescription', studyDescription);
channelMap.put('orderingProvider', orderingProvider);
channelMap.put('findings', findings);
channelMap.put('impressions', impressions);
channelMap.put('techniques', techniques);
channelMap.put('conclusions', conclusions);
channelMap.put('pdfPath', pdfPath);

// --- Generar ACK ---
var ackMessage = 'MSH|^~\\&|MIRTH|MIRTH|RIS|' + sendingFacility + '|'
    + DateUtil.getCurrentDate('yyyyMMddHHmmss')
    + '||ACK^R01|' + messageControlId + '|P|2.3\r'
    + 'MSA|AA|' + messageControlId + '|Message accepted\r';

channelMap.put('ackMessage', ackMessage);

logger.info('[ORU] Recibido de ' + sendingFacility + ' | Location: ' + locationName
    + ' | Accession: ' + accessionNumber + ' | Patient: ' + patientSurname + ', ' + patientFirstName);
```

**Response Template**: En la pestaña **Response**, configurar:
- **Response Type**: `Custom`
- **Response**: `${ackMessage}` (usa el ACK generado en el JavaScript)

### Paso 4: Destination Connector(s)

Según lo que quieras hacer con el reporte, configurar uno o más destinos:

#### Opción A: Destino a base de datos (guardar reporte)

| Campo | Valor |
|-------|-------|
| **Protocol** | `Database Writer` |
| **Data Type** | `Raw` |
| **Driver** | `PostgreSQL` (o el que uses) |
| **URL** | `jdbc:postgresql://148.230.72.8:5432/pacsdb` |
| **User** | `pacs` |
| **Password** | `pacs` |

**SQL Query**:
```sql
INSERT INTO nextris.tbhl7_oru_log (
    guid, sending_facility, location_name, patient_id,
    patient_name, accession_number, study_description,
    findings, impressions, techniques, conclusions,
    pdf_path, received_at, raw_message
) VALUES (
    uuid_generate_v4(),
    '${sendingFacility}',
    '${locationName}',
    '${patientId}',
    '${patientSurname}, ${patientFirstName}',
    '${accessionNumber}',
    '${studyDescription}',
    '${findings}',
    '${impressions}',
    '${techniques}',
    '${conclusions}',
    '${pdfPath}',
    NOW(),
    ${message.encodedData}
)
```

#### Opción B: Destino HTTP/REST (reenviar a otro sistema)

| Campo | Valor |
|-------|-------|
| **Protocol** | `HTTP Sender` |
| **Data Type** | `Raw` |
| **URL** | `https://tu-sistema-destino.com/api/hl7/oru` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

**Body** (JSON):
```json
{
    "facility": "${sendingFacility}",
    "location": "${locationName}",
    "patient_id": "${patientId}",
    "patient_name": "${patientSurname}, ${patientFirstName}",
    "accession": "${accessionNumber}",
    "study": "${studyDescription}",
    "findings": "${findings}",
    "impressions": "${impressions}",
    "techniques": "${techniques}",
    "conclusions": "${conclusions}",
    "pdf_path": "${pdfPath}"
}
```

#### Opción C: Destino a archivo (backup/debug)

| Campo | Valor |
|-------|-------|
| **Protocol** | `File Writer` |
| **Data Type** | `Raw` |
| **Destination Directory** | `/opt/mirth/oru-backup/` |
| **File Name** | `oru_${sendingFacility}_${accessionNumber}_${date.get('yyyyMMddHHmmss')}.hl7` |

### Paso 5: Routing por Facility (opcional)

Si necesitás enviar a diferentes destinos según la institución, usar **Channel Router**:

1. Ir a **Channel** → **Edit Transformer** (a nivel de canal)
2. Agregar un **JavaScript Router**:

```javascript
var facility = $('sendingFacility');

if (facility == 'SUS') {
    return 'Destino_SUS';
} else if (facility == 'CLINICA_PRIVADA') {
    return 'Destino_Privada';
} else {
    return 'Destino_Default';
}
```

Luego cada destino tiene su propio connector con la configuración correspondiente.

### Paso 6: Deploy y prueba

1. **Guardar** el canal (Ctrl+S)
2. **Deploy** el canal (botón Deploy o F7)
3. Verificar que el canal esté en estado **STARTED** (verde)
4. Firmar un reporte en NextRIS de una facility con `hl7_enable_report_sending = true`
5. En Mirth, ir a **Messages** del canal para ver el mensaje recibido
6. Verificar que el ACK se envió correctamente

---

## Resumen rápido de configuración

| Componente | Configuración |
|------------|---------------|
| **Source Protocol** | TCP Listener / MLLP |
| **Puerto** | `9193` |
| **Char-set** | UTF-8 |
| **SOB** | `0x0B` (11) |
| **EOB** | `0x1C` (28) + `0x0D` (13) |
| **Response** | ACK^R01 con MSA\|AA |
| **Data Type** | HL7V2 |

---

## Flujo completo

```
1. Usuario firma reporte en NextRIS
       │
       ▼
2. Se guarda el reporte y se genera el PDF
       │
       ▼
3. Se consulta tbfacility.hl7_enable_report_sending
       │
       ├─ FALSE → No se envía nada. Fin.
       │
       ├─ TRUE
       │    ▼
       │  4. Se reúnen datos: paciente, examen, reporte, facility, location
       │    ▼
       │  5. Se construye el mensaje ORU^R01
       │    ▼
       │  6. Se envía por MLLP/TCP al servidor HL7
       │    ▼
       │  7. Se espera ACK del receptor
       │    ▼
       │  8. Si falla, se reintentan hasta 3 veces (1s entre cada intento)
       │    ▼
       │  9. Se loguea el resultado (éxito o fallo)
       │
       ▼
10. La firma se considera exitosa independientemente del resultado HL7
```

---

## Logs

Todos los eventos se loguean con el prefijo `[HL7_ORU]`:

| Log | Significado |
|-----|-------------|
| `[HL7_ORU] Enviando ORU para examen {id}, facility: {name}, location: {name}` | Inicio del envío |
| `[HL7_ORU] ORU enviado exitosamente para examen {id}` | ACK recibido correctamente |
| `[HL7_ORU] Falló el envío del ORU para examen {id}` | No se recibió ACK tras 3 reintentos |
| `[HL7_ORU] HL7 report sending deshabilitado para facility: {name}` | Flag deshabilitado, no se envía |
| `[HL7_ORU] Error interno: {error}` | Error procesando datos |
| `[HL7_ORU] Error de conexión: {error}` | Error de conexión a DB |
| `[HL7_ORU] Intento {n} falló: {error}` | Reintento individual fallido |

---

## Prueba rápida con netcat

Para verificar que el mensaje llega correctamente, se puede levantar un listener con netcat:

```bash
# En el servidor receptor
nc -l -p 9193
```

Luego firmar un reporte en NextRIS y verificar que se recibe el mensaje ORU en la consola de netcat.

---

## Notas importantes

- **No bloquea la firma**: El envío HL7 es asíncrono al flujo de firma. Si falla, la firma igual se considera exitosa.
- **Sin cola de mensajes**: Actualmente no hay sistema de retry persistente. Si los 3 reintentos fallan, el mensaje se pierde. Esto se puede implementar posteriormente.
- **Un solo destino**: El servidor HL7 destino es global (variable `IPSERVER`), no por facility. El forwarding por facility se hace en Mirth usando el campo `MSH-4`.
- **Reportes vacíos**: Si el reporte no tiene contenido (findings, impressions, etc. vacíos), el ORU igual se envía con los campos OBX vacíos.
