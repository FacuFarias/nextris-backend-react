# API de Integración - NextRIS / Clínica Parque

## Tab de Contenidos

1. [Autenticación](#1-autenticación)
2. [Endpoints de Pacientes](#2-endpoints-de-pacientes)
   - [2.1 Crear Paciente](#21-crear-paciente)
   - [2.2 Actualizar Paciente](#22-actualizar-paciente)
   - [2.3 Crear Paciente desde DICOM (PACS)](#23-crear-paciente-desde-dicom-pacs)
   - [2.4 Resetear Contraseña de Usuario Portal](#24-resetear-contraseña-de-usuario-portal)
3. [Endpoints de Órdenes](#3-endpoints-de-órdenes)
   - [3.1 Crear Orden (Worklist)](#31-crear-orden-para-ejecutar-y-leer)
   - [3.2 Crear Exámenes (batch)](#32-crear-exámenes-batch)
4. [Endpoints de Reportes](#4-endpoints-de-reportes)
   - [4.1 Recibir Reporte Finalizado](#41-recibir-reporte-finalizado)
   - [4.2 Notificación de Apertura de Estudio](#42-notificación-de-apertura-de-estudio)
   - [4.3 Enviar Addenda](#43-enviar-addenda)
5. [Integración PACS (dcm4chee)](#5-integración-pacs-dcm4chee)
   - [5.1 Trigger: Auto-creación de paciente](#51-trigger-auto-creación-de-paciente)
   - [5.2 Trigger: Auto-creación de examen](#52-trigger-auto-creación-de-examen)
   - [5.3 Listener de portal (deshabilitado)](#53-listener-de-portal-deshabilitado)
6. [Códigos de Respuesta](#6-códigos-de-respuesta)
7. [Ejemplos completos](#7-ejemplos-completos)

---

## 1. Autenticación

Todas las peticiones requieren autenticación mediante Bearer Token en el header HTTP.

| Campo | Valor |
|-------|-------|
| **Header** | `Authorization` |
| **Formato** | `Bearer <token>` |
| **Token** | `Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=` |

**Ejemplo:**
```
Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=
```

**Protocolo:** HTTP/POST  
**Content-Type:** `application/json`

### Convención de username para usuarios portal

En esta implementación de NextRIS, el `username` del usuario portal de un paciente siempre se sincroniza con el `patientid`. No se utiliza el formato `nombre+apellido`. Cuando se crea o actualiza un paciente a través de la API de Clínica Parque, el username se iguala automáticamente al `patientid`. En caso de que un paciente ya tenga un usuario portal con un username diferente, los endpoints `/patients/update` y `/resetpassword` lo sobrescriben con el `patientid` actual.

---

## 2. Endpoints de Pacientes

### 2.1 Crear Paciente

Registra un nuevo paciente en la base de datos del sistema. También crea un usuario de acceso con el mismo `patientid`.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/patients` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "patient": {
    "id": "ID_INTERNO_123",
    "dni": "12345678",
    "name": "NOMBRE_DEL_PACIENTE",
    "birthdate": "1993-09-20",
    "sex": "M",
    "patient_type": "F",
    "healthcard_type": "Particular"
  }
}
```

#### Campos del objeto `patient`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | String | Sí | Identificador único del paciente en el sistema origen |
| `dni` | String | Sí | Documento Nacional de Identidad |
| `name` | String | Sí | Nombre completo del paciente (se divide en nombre y apellido) |
| `birthdate` | String | Sí | Fecha de nacimiento (formato: `YYYY-MM-DD`) |
| `sex` | String | Sí | Sexo del paciente: `M` (Masculino), `F` (Femenino), `O` (Otro) |
| `patient_type` | String | Sí | Tipo de paciente: `T` (Temporal), `F` (Final), `N` (Neonatal) |
| `healthcard_type` | String | Sí | Tipo de cobertura: `Particular`, `Obra Social`, `Prepaga` |

#### Usuario creado automáticamente

| Campo | Valor |
|-------|-------|
| **Username** | `patientid` (mismo que el campo `id`) |
| **Password** | Últimos 3 caracteres del `id` |
| **Status** | `Active` |
| **firstlogin** | `0` (no obliga a cambiar contraseña) |

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Paciente creado exitosamente. 2 estudio(s) vinculado(s).",
  "guid": "3d607adb-9baf-4d56-9ee6-76d7b7273125",
  "patientid": "ID_INTERNO_123",
  "username": "ID_INTERNO_123",
  "linked_studies": [
    { "accession_number": "ACC001", "study_uid": "1.2.3...", "admision_number": "ADM000001", "examination_guid": "..." }
  ]
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/patients \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "id": "ID_INTERNO_123",
      "dni": "12345678",
      "name": "JUAN PEREZ",
      "birthdate": "1993-09-20",
      "sex": "M",
      "patient_type": "F",
      "healthcard_type": "Particular"
    }
  }'
```

---

### 2.2 Actualizar Paciente

Modifica los datos de un paciente existente. El campo `old_id` es obligatorio para localizar el registro.

Si el paciente tiene un usuario portal, su `username` se sincroniza automáticamente con el nuevo `patientid`.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/patients/update` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "patient": {
    "old_id": "ID_INTERNO_123",
    "id": "ID_INTERNO_123_NUEVO",
    "dni": "12345678",
    "name": "NOMBRE_PACIENTE_CORREGIDO",
    "birthdate": "1993-09-20",
    "sex": "M",
    "patient_type": "F",
    "healthcard_type": "Obra Social"
  }
}
```

#### Campos del objeto `patient`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `old_id` | String | Sí | Identificador actual del paciente (clave de búsqueda) |
| `id` | String | Sí | Identificador nuevo o definitivo |
| `dni` | String | Sí | Documento Nacional de Identidad corregido |
| `name` | String | Sí | Nombre completo corregido |
| `birthdate` | String | Sí | Fecha de nacimiento corregida (formato: `YYYY-MM-DD`) |
| `sex` | String | Sí | Sexo del paciente: `M`, `F`, `O` |
| `patient_type` | String | Sí | Tipo de paciente: `T` (Temporal), `F` (Final), `N` (Neonatal) |
| `healthcard_type` | String | Sí | Tipo de cobertura: `Particular`, `Obra Social`, `Prepaga` |

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Paciente actualizado exitosamente",
  "guid": "3d607adb-9baf-4d56-9ee6-76d7b7273125",
  "patientid": "ID_INTERNO_123_NUEVO"
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/patients/update \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "old_id": "ID_INTERNO_123",
      "id": "ID_INTERNO_123_NUEVO",
      "dni": "12345678",
      "name": "JUAN PEREZ GARCIA",
      "birthdate": "1993-09-20",
      "sex": "M",
      "patient_type": "F",
      "healthcard_type": "Obra Social"
    }
  }'
```

---

### 2.3 Crear Paciente desde DICOM (PACS)

Crea un paciente en NextRIS usando los datos DICOM almacenados en el PACS (dcm4chee). Busca el estudio por `study_uid` o `accession_no`, extrae los datos del paciente desde las tablas del PACS y crea el paciente + usuario portal.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/patients/from-dicom` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "study_uid": "3310260.2739"
}
```
O alternativamente:
```json
{
  "accession_no": "3310260_2739"
}
```

#### Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `study_uid` | String | Sí* | Study Instance UID del estudio en el PACS |
| `accession_no` | String | Sí* | Accession Number del estudio en el PACS |

> *Se requiere al menos uno de los dos campos.

#### Comportamiento

1. Busca el estudio en `public.study` (esquema PACS)
2. Obtiene el paciente desde `public.patient` + `public.person_name`
3. Extrae el PatientID (tag DICOM 0010,0020) desde `public.dicomattrs` (binario)
4. Parsea nombre DICOM (`LASTNAME^FIRSTNAME^...`)
5. Convierte birthdate de `YYYYMMDD` a `YYYY-MM-DD`
6. Crea paciente en `nextris.datapatient` con `patientid` = DICOM PatientID
7. Crea usuario portal: username = PatientID, password = últimos 3 dígitos
8. **Vincula estudios PACS existentes**: busca TODOS los estudios del paciente en el PACS y crea exámenes en `tbexamination` con `isimage=1`

#### Mapeo de datos

| DICOM | PACS | nextris.datapatient |
|-------|------|---------------------|
| (0010,0020) PatientID | dicomattrs.attrs (binario) | `patientid` |
| (0010,0010) PatientName | person_name.alphabetic_name | `name` + `surname` |
| (0010,0030) PatientBirthDate | patient.pat_birthdate | `birthdate` |
| (0010,0040) PatientSex | patient.pat_sex | `sexcode` |
| — | default | `patient_type = 'F'` |
| — | default | `healthcard_type = 'Particular'` |

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Paciente creado exitosamente desde DICOM. 6 estudio(s) adicional(es) vinculado(s).",
  "guid": "c2f8a253-828b-4054-bf82-94aa3e2452c8",
  "patientid": "50755",
  "username": "50755",
  "source": "dicom",
  "linked_studies": [
    { "accession_number": "ACC001", "study_uid": "1.2.3...", "admision_number": "ADM000001", "examination_guid": "..." }
  ]
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:5001/api/clinicaparque/patients/from-dicom \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{"study_uid": "3310260.2739"}'
```

---

### 2.4 Resetear Contraseña de Usuario Portal

Actualiza la contraseña del usuario portal asociado a un paciente. Si no se envía una contraseña, se usan los últimos 3 dígitos del DNI.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/resetpassword` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "patient_id": "82416",
  "password": "nuevapass123"
}
```

#### Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `patient_id` | String | Sí | Identificador del paciente en NextRIS |
| `password` | String | No | Nueva contraseña. Si se omite, se usan los últimos 3 dígitos del DNI |

#### Comportamiento

1. Busca el paciente en `nextris.datapatient` por `patientid`
2. Busca el usuario portal en `nextris.tbuser_patient` asociado al paciente
3. Si no se envió `password`, toma los últimos 3 dígitos del `nationalcode` (DNI)
4. Actualiza la contraseña (se guarda hasheada con bcrypt)
5. Si el usuario portal ya existe, su `username` se sincroniza con el `patient_id`

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Contraseña actualizada exitosamente",
  "patient_id": "82416",
  "username": "82416"
}
```

#### Códigos de error

| Código | Mensaje |
|--------|---------|
| 400 | `patient_id es requerido` |
| 400 | `DNI no disponible para generar password por defecto` |
| 404 | `Paciente con id {id} no encontrado` |
| 404 | `Usuario portal no encontrado para paciente {id}` |

#### Ejemplo cURL (con password explícita)

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/resetpassword \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "82416", "password": "miclave123"}'
```

#### Ejemplo cURL (password por defecto = últimos 3 dígitos del DNI)

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/resetpassword \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "82416"}'
```

---

## 3. Endpoints de Órdenes

### 3.1 Crear Orden para Ejecutar y Leer

Crea un paciente (si no existe), un examen con `isexecuted=0` e `isreported=0`, y envía la orden al worklist DICOM vía HL7.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/orders_to_execute_and_read` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

Body para paciente Final (F):
```json
{
  "patient": {
    "id": "ID_INTERNO_123",
    "dni": "12345678",
    "name": "NOMBRE_DEL_PACIENTE",
    "birthdate": "1993-09-20",
    "sex": "M",
    "patient_type": "F",
    "healthcard_type": "Particular"
  },
  "order": {
    "orderId": "ORD-1001",
    "accessionNumber": "ACC-556677",
    "procedure_code": "COD-01",
    "procedure_name": "DESCRIPCION_DEL_ESTUDIO",
    "modality": "CR",
    "AET": "PACS_SERVER",
    "scheduledTime": "2026-05-14T10:30:00Z",
    "rad_id": "ID_MEDICO",
    "priority_id": 1,
    "laterality_id": "UUID_LATERALIDAD",
    "study_reason": "Dolor torácico",
    "req_doctor": "Dr. Juan García"
  }
}
```

Body para paciente Temporal (T) o Neonatal (N):
```json
{
  "patient": {
    "id": "ID_INTERNO_123",
    "patient_type": "T"
  },
  "order": { ... }
}
```

#### Campos del objeto `patient` (tipo F)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | String | Sí | Identificador único del paciente en el sistema origen |
| `patient_type` | String | Sí | Tipo de paciente: `T` (Temporal), `F` (Final), `N` (Neonatal) |
| `dni` | String | Sí | Documento Nacional de Identidad |
| `name` | String | Sí | Nombre completo del paciente |
| `birthdate` | String | Sí | Fecha de nacimiento (`YYYY-MM-DD`) |
| `sex` | String | Sí | Sexo: `M`, `F`, `O` |
| `healthcard_type` | String | Sí | Tipo de cobertura: `Particular`, `Obra Social`, `Prepaga` |

#### Campos del objeto `patient` (tipo T o N)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | String | Sí | Identificador único del paciente en el sistema origen |
| `patient_type` | String | Sí | Tipo de paciente: `T` (Temporal), `N` (Neonatal) |

#### Campos del objeto `order`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `orderId` | String | Sí | Número de orden o solicitud |
| `accessionNumber` | String | Sí | Número de acceso (clave DICOM) |
| `procedure_code` | String | Sí | Código del estudio/procedimiento |
| `procedure_name` | String | Sí* | Descripción del estudio |
| `study_description` | String | No* | Descripción del estudio; si `procedure_code` aún no existe en NextRIS, se usa para resolver y actualizar el tipo de estudio del examen |
| `modality` | String | Sí | Modalidad: `CR`, `CT`, `MR`, `DX`, etc. |
| `AET` | String | Sí | AE Title del equipo |
| `scheduledTime` | String | Sí | Fecha/hora programada (ISO 8601) |
| `rad_id` | String | No | Identificador del radiólogo; si se omite se guarda vacío/`NULL` |
| `priority_id` | Int | No | Prioridad: `0` (Rutina), `1` (Urgente); por defecto `0` |
| `laterality_id` | UUID | No | UUID de la lateralidad existente en `islaterality` |
| `study_reason` | String | No | Razón o motivo del estudio |
| `req_doctor` | String | No | Nombre del médico referente (se guarda en `requestingphysician_name`) |

\* Se debe enviar `procedure_name` o `study_description`.

#### Comportamiento

1. **Paciente**: Si no existe, lo crea junto con su usuario (username=`id`, password=últimos 3 dígitos)
2. **Examen**: Crea entrada en `tbexamination` con:
   - `isexecuted = 0`
   - `isreported = 0`
   - `status = 'Scheduled'`
   - `requestingphysician_name`: valor de `req_doctor`
   - `history`: incluye razón del estudio si se provee
   - `idreferringphysician`: radiólogo resuelto por `rad_id`, o `NULL` si no se informa
   - `idseverity`: severidad urgente cuando `priority_id` es `1`; rutina (`NULL`) cuando es `0`
   - `laterality_id`: lateralidad recibida, si se informa

Si el examen ya fue creado previamente por PACS y el código recibido todavía
no existe en `isstudytype`, el endpoint busca `study_description` (o, si no se
envía, `procedure_name`) por descripción. Cuando encuentra una coincidencia,
actualiza `tbexamination.studytype_id` en el mismo procesamiento de la orden.
3. **Reporte**: Crea entrada vacía en `tbreport`
4. **Worklist**: Envía orden HL7 al worklist DICOM

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Orden creada exitosamente",
  "examination_guid": "eb752b1d-32ed-4824-a300-4555e43dfed7",
  "report_guid": "54900e6f-b0ad-45d9-9eb4-eff2d59a8957",
  "admision_number": "ADM000005",
  "accession_number": "ACC-556677",
  "patient_guid": "04c415e0-f86e-491b-aa59-7ebe44ceefc5",
  "worklist_created": true,
  "study_instance_uid": "1.2.840.113619.2.55.3..."
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/orders_to_execute_and_read \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "id": "ID_INTERNO_123",
      "dni": "12345678",
      "name": "NOMBRE_DEL_PACIENTE",
      "birthdate": "1993-09-20",
      "sex": "M",
      "patient_type": "F",
      "healthcard_type": "Particular"
    },
    "order": {
      "orderId": "ORD-1001",
      "accessionNumber": "ACC-556677",
      "procedure_code": "COD-01",
      "procedure_name": "Radiografía de Tórax",
      "modality": "CR",
      "AET": "PACS_SERVER",
      "scheduledTime": "2026-05-14T10:30:00Z",
      "rad_id": "ID_MEDICO",
      "priority_id": 1,
      "laterality_id": "UUID_LATERALIDAD"
    }
  }'
```

---

### 3.2 Crear Exámenes (batch)

Recibe una o múltiples órdenes y crea exámenes listos para redactar. Crea paciente si no existe.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/orders` |
| **Método** | `POST` |
| **Auth** | No requiere (endpoint público) |

#### Estructura del JSON

```json
{
  "patient_id": "12345",
  "patient_name": "Juan Pérez",
  "accession_number": "ACC-001",
  "machine": "CT-01",
  "procedure_id": "uuid-del-tipo-de-estudio"
}
```

O múltiples órdenes en array:
```json
[
  { "patient_id": "...", "patient_name": "...", "accession_number": "...", "machine": "...", "procedure_id": "..." },
  { "patient_id": "...", "patient_name": "...", "accession_number": "...", "machine": "...", "procedure_id": "..." }
]
```

#### Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `patient_id` | String | Sí | ID del paciente en el sistema externo |
| `patient_name` | String | Sí | Nombre completo del paciente |
| `accession_number` | String | Sí | Número de acceso / estudio |
| `machine` | String | No | AE Title o descripción del equipo; si se omite, el examen queda sin equipo asignado |
| `procedure_id` | String | Sí* | GUID o código del tipo de estudio (`isstudytype`) |
| `procedure_code` | String | Sí* | Código del tipo de estudio, por ejemplo `3153` |

\* Se debe enviar `procedure_id` o `procedure_code`.

Al recibir una orden, el examen se marca internamente con `tbexamination."w-order" = 1`.
Los estudios creados automáticamente por PACS permanecen con `"w-order" = 0` hasta
que llegue su orden asociada.

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "created": 2,
  "failed": 0,
  "results": [
    { "accession_number": "ACC-001", "examination_guid": "...", "report_guid": "...", "status": "created" }
  ],
  "errors": []
}
```

---

## 4. Endpoints de Reportes

### 4.1 Recibir Reporte Finalizado

Crea o actualiza un paciente, examen y reporte en el sistema. Utilizado para sincronizar reportes finalizados desde el sistema externo.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/reports` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "patient": {
    "id": "PAC-98765",
    "dni": "12345678",
    "name": "Juan Pérez",
    "birthdate": "1985-05-14",
    "sex": "M"
  },
  "order": {
    "orderId": "ORD-2026-001",
    "accessionNumber": "ACC123456",
    "procedure_code": "RX-01",
    "procedure_description": "Radiografía de Tórax Frontal",
    "rad_id": "RAD-005",
    "report_type": "NR",
    "report_date": "2026-05-19",
    "modality": "RX",
    "priority_id": 0
  },
  "report": {
    "study_reason": "Tos crónica y dolor torácico.",
    "technique": "Se realizan proyecciones posteroanterior y lateral de tórax.",
    "narrative": "Estructuras óseas de la caja torácica conservadas.",
    "findings": "Campos pulmonares limpios, sin evidencia de infiltrados.",
    "impressions": "Estudio radiográfico de tórax dentro de límites normales.",
    "conclusions": "No se observan hallazgos patológicos agudos.",
    "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789"
  }
}
```

#### Campos del objeto `patient`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | String | Sí | Identificador único del paciente en el sistema origen |
| `dni` | String | Sí | Documento Nacional de Identidad |
| `name` | String | Sí | Nombre completo del paciente |
| `birthdate` | String | Sí | Fecha de nacimiento (`YYYY-MM-DD`) |
| `sex` | String | Sí | Sexo: `M`, `F`, `O` |

#### Campos del objeto `order`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `orderId` | String | Sí | Número de orden o solicitud |
| `accessionNumber` | String | Sí | Número de acceso (clave para DICOM) |
| `procedure_code` | String | Sí | Código del estudio/procedimiento |
| `procedure_description` | String | No | Descripción o nombre del estudio |
| `rad_id` | String | No | Identificador del radiólogo (busca por GUID, username o nationalnumber) |
| `report_type` | String | Sí | Tipo de reporte: `NR` (Nuevo), `NV` (Nueva Versión), `A` (Addenda) |
| `report_date` | String | No | Fecha del estudio (`YYYY-MM-DD`) |
| `modality` | String | Sí | Modalidad: `RX`, `CT`, `MR`, `DX`, etc. |
| `priority_id` | Int | No | Prioridad: `0` (Rutina), `1` (Urgente) |

#### Campos del objeto `report`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `study_reason` | String | No | Motivo del estudio |
| `technique` | String | No | Técnica utilizada |
| `narrative` | String | No | Narrativa del estudio |
| `findings` | String | No | Hallazgos |
| `impressions` | String | No | Impresiones diagnósticas |
| `conclusions` | String | No | Conclusiones |
| `study_uid` | String | Sí | UID único del estudio DICOM (Study Instance UID) |

#### Tipos de Reporte (`report_type`)

| Código | Descripción | Comportamiento |
|--------|-------------|----------------|
| `NR` | Nuevo Reporte | Crea un nuevo reporte o actualiza el existente |
| `NV` | Nueva Versión | Actualiza el reporte existente con nueva versión |
| `A` | Addenda | Anexa texto al reporte existente con tag `[ADDENDA DD/MM/YYYY]` |

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Reporte (NR) procesado exitosamente",
  "examination_guid": "6c4cd2ae-98a5-4e28-9374-4cb5225cb3e6",
  "report_guid": "853b4297-184b-43fa-9a95-1c1c38fcbede",
  "accession_number": "ACC123456",
  "report_type": "NR"
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/reports \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "id": "PAC-98765",
      "dni": "12345678",
      "name": "Juan Pérez",
      "birthdate": "1985-05-14",
      "sex": "M"
    },
    "order": {
      "orderId": "ORD-2026-001",
      "accessionNumber": "ACC123456",
      "procedure_code": "RX-01",
      "procedure_description": "Radiografía de Tórax Frontal",
      "rad_id": "RAD-005",
      "report_type": "NR",
      "report_date": "2026-05-19",
      "modality": "RX",
      "priority_id": 0
    },
    "report": {
      "study_reason": "Tos crónica y dolor torácico.",
      "technique": "Se realizan proyecciones posteroanterior y lateral de tórax.",
      "findings": "Campos pulmonares limpios.",
      "impressions": "Estudio dentro de límites normales.",
      "conclusions": "Sin hallazgos patológicos.",
      "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789"
    }
  }'
```

---

### 4.2 Notificación de Apertura de Estudio

Registra un evento cuando un paciente abre o visualiza su estudio/reporte. Permite mantener trazabilidad de accesos.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/study-open` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "event": {
    "eventType": "PATIENT_VIEW",
    "timestamp": "2026-05-19T21:56:00Z"
  },
  "patient": {
    "id": "PAC-98765",
    "dni": "12345678"
  },
  "order": {
    "orderId": "ORD-2026-001",
    "accessionNumber": "ACC123456"
  },
  "study": {
    "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789"
  }
}
```

#### Campos del objeto `event`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `eventType` | String | Sí | Tipo de evento (valor fijo: `PATIENT_VIEW`) |
| `timestamp` | String | Sí | Fecha y hora del evento en formato ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`) |

#### Campos del objeto `patient`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | String | Sí | Identificador único del paciente |
| `dni` | String | No | Documento Nacional de Identidad |

#### Campos del objeto `order`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `orderId` | String | No | Número de orden o solicitud |
| `accessionNumber` | String | Sí* | Número de acceso (Accession Number) |

#### Campos del objeto `study`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `study_uid` | String | Sí* | UID único del estudio DICOM |

> *Se requiere al menos uno: `accessionNumber` o `study_uid`

#### Respuesta exitosa (200)

```json
{
  "status": "success",
  "message": "Event processed successfully",
  "examination_found": true
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/study-open \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "eventType": "PATIENT_VIEW",
      "timestamp": "2026-05-19T21:56:00Z"
    },
    "patient": {
      "id": "PAC-98765",
      "dni": "12345678"
    },
    "order": {
      "orderId": "ORD-2026-001",
      "accessionNumber": "ACC123456"
    },
    "study": {
      "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789"
    }
  }'
```

---

### 4.3 Enviar Addenda

Anexa una aclaración, corrección o ampliación a un reporte previamente finalizado. El texto se agrega con un tag de fecha `[ADDENDA DD/MM/YYYY]`.

| Propiedad | Valor |
|-----------|-------|
| **URL** | `/api/clinicaparque/addenda` |
| **Método** | `POST` |
| **Auth** | Bearer Token |

#### Estructura del JSON

```json
{
  "patient": {
    "id": "PAC-98765",
    "dni": "12345678",
    "name": "Juan Pérez",
    "birthdate": "1985-05-14",
    "sex": "M"
  },
  "order": {
    "orderId": "ORD-2026-001",
    "accessionNumber": "ACC123456",
    "procedure_code": "RX-01",
    "procedure_description": "Radiografía de Tórax Frontal",
    "rad_id": "RAD-005",
    "report_type": "A",
    "report_date": "2026-05-19",
    "modality": "RX",
    "priority_id": 0
  },
  "report": {
    "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789",
    "findings": "Se revisa el estudio a solicitud de neumonología.",
    "impressions": "Sin hallazgos adicionales.",
    "conclusions": "Se mantiene la conclusión original."
  }
}
```

#### Campos requeridos

| Campo | Nodo | Descripción |
|-------|------|-------------|
| `accessionNumber` | order | Número de acceso (debe coincidir con el estudio original) |
| `study_uid` | report | UID del estudio DICOM (debe coincidir con el estudio original) |
| `findings` | report | Texto de hallazgos a anexar |
| `impressions` | report | Texto de impresiones a anexar |
| `conclusions` | report | Texto de conclusiones a anexar |

#### Reglas de negocio

- El `accessionNumber` + `study_uid` deben coincidir con un estudio existente
- El texto nuevo se anexa al existente con el tag `[ADDENDA DD/MM/YYYY]`
- Si no se encuentra el estudio, retorna error 400

#### Respuesta exitosa (200)

```json
{
  "success": true,
  "message": "Addenda anexada correctamente",
  "examination_guid": "6c4cd2ae-98a5-4e28-9374-4cb5225cb3e6",
  "report_guid": "853b4297-184b-43fa-9a95-1c1c38fcbede",
  "accession_number": "ACC123456"
}
```

#### Ejemplo cURL

```bash
curl -X POST http://<SERVER>:<PORT>/api/clinicaparque/addenda \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "id": "PAC-98765",
      "dni": "12345678",
      "name": "Juan Pérez",
      "birthdate": "1985-05-14",
      "sex": "M"
    },
    "order": {
      "orderId": "ORD-2026-001",
      "accessionNumber": "ACC123456",
      "procedure_code": "RX-01",
      "rad_id": "RAD-005",
      "report_type": "A",
      "report_date": "2026-05-19",
      "modality": "RX"
    },
    "report": {
      "study_uid": "1.2.840.113619.2.55.3.2831165.456.123456789",
      "findings": "Se revisa el estudio; se confirma ausencia de nódulos.",
      "impressions": "Sin hallazgos adicionales.",
      "conclusions": "Se mantiene la conclusión original."
    }
  }'
```

---

## 5. Integración PACS (dcm4chee)

Cuando una imagen llega al PACS dcm4chee, se ejecutan automáticamente dos triggers en la base de datos `pacsdb` (ambos schemas `public` y `nextris` coexisten en la misma BD).

### 5.1 Trigger: Auto-creación de paciente

| Componente | Valor |
|------------|-------|
| **Trigger** | `trg_new_pacs_patient` |
| **Tabla** | `public.patient` |
| **Evento** | AFTER INSERT (DEFERRED) |
| **Función** | `public.fn_create_nextris_patient_from_pacs()` |

#### Flujo

1. dcm4chee recibe imagen → INSERT en `public.patient` + `public.person_name` + `public.dicomattrs`
2. Al hacer COMMIT, el trigger deferred se ejecuta
3. La función parsea el PatientID (tag 0010,0020) del blob binario `dicomattrs.attrs`
4. Verifica que no exista ya un paciente con ese PatientID en `nextris.datapatient`
5. Parsea nombre (`LASTNAME^FIRSTNAME^...`), birthdate (`YYYYMMDD`), sex
6. INSERT en `nextris.datapatient` con `patientid` = DICOM PatientID

#### Mapeo

| nextris.datapatient | Origen |
|---------------------|--------|
| `patientid` | DICOM PatientID (0010,0020) de dicomattrs |
| `nationalcode` | DICOM PatientID (mismo valor) |
| `name` | Segundo componente de `alphabetic_name` |
| `surname` | Primer componente de `alphabetic_name` |
| `birthdate` | `pat_birthdate` convertido de YYYYMMDD |
| `sexcode` | `pat_sex` (M/F/I) |
| `patient_type` | `'F'` (Final) |
| `healthcard_type` | `'Particular'` |

#### Funciones auxiliares

| Función | Descripción |
|---------|-------------|
| `_parse_dicom_patient_id(bytea)` | Extrae PatientID del blob binario de dicomattrs |
| `_clean_study_desc(varchar)` | Limpia prefijos de descripción (ECO 1:, MAMO:, END:) |

### 5.2 Trigger: Auto-creación de examen

| Componente | Valor |
|------------|-------|
| **Trigger** | `trg_new_pacs_study` |
| **Tabla** | `public.study` |
| **Evento** | AFTER INSERT (DEFERRED) |
| **Función** | `public.fn_create_nextris_examination_from_pacs()` |

#### Flujo

1. dcm4chee recibe estudio → INSERT en `public.study`
2. Al hacer COMMIT, el trigger deferred se ejecuta
3. Si existe una orden sin imagen, intenta reconciliarla por `accession_no`,
   `PatientName` normalizado y el mismo día del estudio/orden
4. Si la reconciliación tiene éxito, actualiza `studyinstanceuid` con el UID
   real del PACS y marca `isimage = 1`
5. Si no existe una orden, busca el paciente en `nextris.datapatient` por
   DICOM PatientID
6. Limpia `study_desc` y busca coincidencia con `nextris.isstudytype.description`
7. Genera número de admisión (`ADM000001`, `ADM000002`, ...)
8. Crea examen en `nextris.tbexamination` con `isimage = 1`
9. Crea reporte vacío en `nextris.tbreport`

La reconciliación no exige que el PatientID DICOM sea igual al PatientID de la
orden: cuando coinciden accession, nombre y fecha, se conserva el paciente de
la orden. La migración que instala esta regla es
`20260902_reconcile_pacs_studies_by_patient_accession_date.sql`.

#### Mapeo de examen

| nextris.tbexamination | Origen |
|-----------------------|--------|
| `idpatient` | GUID del paciente en nextris |
| `studytype_id` | Match de `study_desc` contra `isstudytype.description` |
| `admisionnumber` | Generado: `ADM000001`, `ADM000002`, ... |
| `localacc` | `accession_no` del estudio PACS |
| `studyinstanceuid` | `study_iuid` del estudio PACS |
| `status` | `'Scheduled'` |
| `isexecuted` | `0` |
| `isreported` | `0` |
| `isimage` | `1` |

#### Matching de study type

1. Limpia el `study_desc` del PACS (ej: `"ECO 1:  ECOGRAFIA ABDOMINAL"` → `"ECOGRAFIA ABDOMINAL"`)
2. Match exacto (case-insensitive) contra `isstudytype.description`
3. Si no hay match exacto, busca si el desc limpio CONTIENE la descripción del study type
4. Si no hay match, `studytype_id` queda NULL

### 5.3 Listener de portal (deshabilitado)

El código para crear usuarios portal automáticamente vía NOTIFY/LISTEN existe pero está deshabilitado.

| Componente | Archivo |
|------------|---------|
| Listener | `apps/home/services/pacs_patient_listener.py` |
| Canal | `pacs_new_patient` |
| Startup | Comentado en `run.py` |

Para re-deshabilitar:
1. Descomentar el bloque NOTIFY en `fn_create_nextris_patient_from_pacs()`
2. Descomentar `start_pacs_listener()` en `run.py`

---

## 6. Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| **200** | OK - La acción fue procesada correctamente |
| **400** | Bad Request - JSON inválido, datos incorrectos o campos faltantes |
| **401** | Unauthorized - Token inválido, expirado o ausente |
| **500** | Internal Server Error - Error interno del servidor |

### Ejemplo de respuesta de error

```json
{
  "success": false,
  "message": "Campos faltantes: dni, name, birthdate"
}
```

---

## 7. Ejemplos completos

### Flujo completo: Crear orden → Enviar reporte → Anexar addenda

**Paso 1: Crear orden (worklist)**
```bash
curl -X POST http://192.168.0.76:5001/api/clinicaparque/orders_to_execute_and_read \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {"id": "PAC-001", "dni": "12345678", "name": "JUAN PEREZ", "birthdate": "1985-05-14", "sex": "M", "patient_type": "F", "healthcard_type": "Particular"},
    "order": {"orderId": "ORD-001", "accessionNumber": "ACC-001", "procedure_code": "RX-01", "procedure_name": "Radiografía de Tórax", "modality": "CR", "AET": "PACS_SERVER", "scheduledTime": "2026-05-22T10:00:00Z", "rad_id": "RAD-005", "priority_id": 0, "study_reason": "Dolor torácico", "req_doctor": "Dr. García"}
  }'
```

**Paso 2: Enviar reporte finalizado**
```bash
curl -X POST http://192.168.0.76:5001/api/clinicaparque/reports \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {"id": "PAC-001", "dni": "12345678", "name": "Juan Pérez", "birthdate": "1985-05-14", "sex": "M"},
    "order": {"orderId": "ORD-001", "accessionNumber": "ACC-001", "procedure_code": "RX-01", "report_type": "NR", "modality": "RX"},
    "report": {"findings": "Campos pulmonares limpios.", "impressions": "Normal.", "conclusions": "Sin patología.", "study_uid": "1.2.840.113619.2.55.3.123"}
  }'
```

**Paso 3: Notificar apertura del estudio**
```bash
curl -X POST http://192.168.0.76:5001/api/clinicaparque/study-open \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {"eventType": "PATIENT_VIEW", "timestamp": "2026-05-19T21:56:00Z"},
    "patient": {"id": "PAC-001", "dni": "12345678"},
    "order": {"orderId": "ORD-001", "accessionNumber": "ACC-001"},
    "study": {"study_uid": "1.2.840.113619.2.55.3.123"}
  }'
```

**Paso 4: Enviar addenda**
```bash
curl -X POST http://192.168.0.76:5001/api/clinicaparque/addenda \
  -H "Authorization: Bearer Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s=" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {"id": "PAC-001", "dni": "12345678", "name": "Juan Pérez", "birthdate": "1985-05-14", "sex": "M"},
    "order": {"orderId": "ORD-001", "accessionNumber": "ACC-001", "procedure_code": "RX-01", "report_type": "A", "modality": "RX"},
    "report": {"study_uid": "1.2.840.113619.2.55.3.123", "findings": "Addenda: Se confirma ausencia de nódulos.", "impressions": "Sin cambios.", "conclusions": "Se mantiene conclusión original."}
  }'
```

---

## Resumen de Endpoints

| Endpoint | Método | Auth | Descripción |
|----------|--------|------|-------------|
| `/api/clinicaparque/patients` | POST | Bearer | Crear paciente + usuario |
| `/api/clinicaparque/patients/update` | POST | Bearer | Actualizar paciente |
| `/api/clinicaparque/patients/from-dicom` | POST | Bearer | Crear paciente desde DICOM PACS |
| `/api/clinicaparque/resetpassword` | POST | Bearer | Resetear contraseña de usuario portal |
| `/api/clinicaparque/orders` | POST | — | Crear exámenes (batch) |
| `/api/clinicaparque/orders_to_execute_and_read` | POST | Bearer | Crear orden + worklist |
| `/api/clinicaparque/reports` | POST | Bearer | Recibir reporte finalizado |
| `/api/clinicaparque/study-open` | POST | Bearer | Notificar apertura de estudio |
| `/api/clinicaparque/addenda` | POST | Bearer | Anexar addenda a reporte |

---

## Notas importantes

1. **Token**: El token debe enviarse en cada petición en el header `Authorization`
2. **Fechas**: Todas las fechas deben tener formato `YYYY-MM-DD`
3. **Timestamps**: En ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`)
4. **IDs**: Los identificadores (`id`, `orderId`, `accessionNumber`) deben ser únicos en el sistema origen
5. **study_uid**: Es el DICOM Study Instance UID y debe ser único por estudio
6. **Addenda**: Se anexa al reporte existente con tag `[ADDENDA DD/MM/YYYY]`
7. **Puerto**: Configurar según el entorno (por defecto: 5001)
8. **Usuarios**: Al crear paciente, se genera usuario automático (username=`id`, password=últimos 3 dígitos)
9. **Vinculación automática**: Al crear paciente (vía API o DICOM), se buscan y vinculan automáticamente todos los estudios existentes en el PACS para ese paciente
# Compatibilidad de campos de reportes

La integración acepta el formato canónico `study_reason`, `content` y
`conclusion`, además del payload histórico. En los envíos salientes se conserva
el contrato existente: `findings` contiene `content`, `conclusions` contiene
`conclusion`, y `technique`/`impressions` se envían vacíos. Las addendas se
anexan como bloques fechados dentro de Contenido y/o Conclusión.
