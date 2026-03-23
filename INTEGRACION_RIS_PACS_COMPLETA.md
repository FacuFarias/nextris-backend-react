# Integracion RIS-PACS Completa

## 1. Objetivo
Este documento describe de forma integral como funciona hoy la integracion entre RIS (`nextris`) y PACS (`dcm4chee`), incluyendo:
- flujo de carga DICOM manual a PACS,
- deteccion de estudios no vinculados,
- vinculacion estudio-imagen con orden RIS,
- desvinculacion manual,
- desvinculacion automatica al cancelar orden/admision,
- impacto en frontend (pantallas y comportamiento),
- modelo de datos, consultas y troubleshooting.

Fecha de referencia: `2026-03-22`

---

## 2. Alcance tecnico
### 2.1 Sistemas involucrados
- RIS Backend: Flask + PostgreSQL (`nextris-dev-react`)
- Frontend React: `nextris-front-react`
- PACS: dcm4chee (esquema `public`, tabla `study`)
- Integracion STOW-RS para envio de DICOM a PACS

### 2.2 Repositorios y rutas clave
- Backend APIs: `apps/api/dicom_routes.py`
- Cancelaciones con desvinculacion:
  - `apps/api/studies.py` (`DELETE /worklist/<exam_id>`)
  - `apps/api/admissions.py` (`DELETE /admissions/<admission_guid>`)
- Migracion de tabla de vinculos: `deployment/sql/20260322_create_tbpacs_study_link.sql`
- Frontend de vinculacion/desvinculacion:
  - `src/modules/redaccion/cargar-estudios/CargarEstudios.tsx`
  - `src/modules/redaccion/cargar-estudios/components/VincularImagenTab.tsx`
  - `src/modules/redaccion/cargar-estudios/components/DesvincularImagenTab.tsx`

---

## 3. Modelo de datos de la integracion

## 3.1 Tabla legacy de carga manual
Tabla: `nextris.tbmanual_uploads`

Campos funcionales clave:
- `guid`: identificador de upload
- `study_instance_uid`: StudyInstanceUID DICOM
- `location_id`: ubicacion RIS
- `islinked`: `0/1` si esta vinculado a una orden
- `linked_examination_guid`: guid de `tbexamination` vinculado
- `linked_date`: fecha de vinculacion
- metadata DICOM: paciente, modalidad, descripcion, etc.

Uso actual:
- sigue activa para carga manual y trazabilidad por archivo/instancia,
- se actualiza en vincular/desvincular,
- convive con la tabla nueva `tbpacs_study_link`.

## 3.2 Tabla nueva de vinculos RIS-PACS
Tabla: `nextris.tbpacs_study_link`

Definida por migracion: `deployment/sql/20260322_create_tbpacs_study_link.sql`.

Campos clave:
- `id` (PK)
- `pacs_study_pk` (FK logica a `public.study.pk`)
- `pacs_study_iuid` (StudyInstanceUID PACS)
- `order_guid` (orden RIS, referencia a `nextris.tbexamination.guid`)
- `order_study_uuid` (UID de estudio guardado en orden)
- `manual_upload_guid` (opcional, puente con carga manual)
- `link_status`: `linked` o `unlinked`
- `source`: `manual`, `reconcile`, `auto`
- `linked_at`, `unlinked_at`
- `linked_by_user_guid`, `linked_by_username`
- `unlinked_reason`
- `created_at`, `updated_at`

Indices y restricciones importantes:
- `ux_tbpacs_study_link_order_active` -> una sola vinculacion activa por orden
- `ux_tbpacs_study_link_study_pk_active` -> un solo uso activo por estudio PACS
- `ux_tbpacs_study_link_study_iuid_active` -> unicidad activa por StudyInstanceUID

## 3.3 PACS: columna `location_id`
Tabla: `public.study` (dcm4chee)

Uso en integracion:
- para filtrar estudios PACS no vinculados por ubicacion,
- soporta modo global con `location_id=all`.

## 3.4 Orden RIS
Tabla: `nextris.tbexamination`

Campos funcionales para integracion:
- `guid`: id orden
- `localacc`: accession local
- `studyinstanceuid`: UID RIS/PACS asociado
- `isimage`: bandera de orden con imagen (`0/1`)
- `location_id`: ubicacion de la orden

---

## 4. Endpoints y contratos

## 4.1 Carga manual DICOM
### Endpoint
`POST /api/manual/upload`

### Auth
Sin JWT (actualmente abierto).

### Input
`multipart/form-data`
- `file`: archivo DICOM
- `location_id`: obligatorio

### Proceso
1. valida extension (`dcm`, `dicom`, `dic`),
2. guarda temporalmente archivo,
3. valida DICOM y extrae tags,
4. envia a PACS por STOW-RS,
5. inserta fila en `tbmanual_uploads` con `islinked=0`.

### Output
- `success`, `message`, `data` con metadata del upload y estado PACS.

---

## 4.2 Lista de estudios no vinculados
### Endpoint
`GET /api/manual/unlinked-studies?location_id=<uuid|all>`

### Auth
Sin JWT (actualmente abierto).

### Comportamiento
Devuelve combinacion de:
- estudios manuales `tbmanual_uploads` con `islinked=0`, agrupados por `study_instance_uid`.
- estudios PACS (`public.study`) sin link activo en `tbpacs_study_link`.

### Reglas de filtro por ubicacion
- `location_id=<uuid>`: filtra manual por `tbmanual_uploads.location_id` y PACS por `public.study.location_id`.
- `location_id=all`: no aplica filtro de ubicacion (global).

### Output por item
Campos relevantes:
- `source`: `manual` o `pacs`
- `pacs_study_pk`: solo para `source=pacs`
- `study_instance_uid`
- datos de paciente/fecha/mod/descripcion

---

## 4.3 Busqueda de ordenes sin imagen
### Endpoint
`GET /api/dicom/search-examinations`

### Auth
JWT requerido.

### Parametros
- `location_id` (`uuid` o `all`)
- filtros opcionales: `patient_name`, `patient_id`, `accession`, `date_from`, `date_to`

### Regla principal
- solo ordenes con `isimage IS NULL OR isimage = 0`.

### Ubicacion
- `location_id=<uuid>`: filtra por `tbexamination.location_id`.
- `location_id=all`: no filtra por ubicacion.

---

## 4.4 Vincular estudio con orden
### Endpoint
`POST /api/dicom/link-study`

### Auth
JWT requerido.

### Input valido
Siempre requiere:
- `examination_guid`

Y ademas uno de:
- `upload_guid` (flujo manual),
- `pacs_study_pk` (flujo PACS),
- `study_instance_uid` (reconciliacion por UID).

### Logica de vinculacion
1. valida existencia de orden en `tbexamination`.
2. resuelve estudio objetivo (manual o PACS).
3. si existe `tbpacs_study_link`, aplica relink seguro:
   - cierra links activos previos de la orden o estudio (`link_status='unlinked'`),
   - inserta nuevo link activo con auditoria de usuario JWT.
4. si es flujo manual, marca en `tbmanual_uploads` todas las instancias del `study_instance_uid`:
   - `islinked=1`, `linked_examination_guid=<orden>`, `linked_date=now`.
5. actualiza orden:
   - `tbexamination.isimage=1`
   - `tbexamination.studyinstanceuid=<uid real del estudio>`.

### Fuente (`source`)
- `manual` cuando se usa `upload_guid`.
- `reconcile` cuando se vincula desde PACS/UID.

---

## 4.5 Lista de estudios vinculados (nueva)
### Endpoint
`GET /api/dicom/linked-studies?location_id=<uuid|all>`

### Auth
JWT requerido.

### Comportamiento
- Si existe `tbpacs_study_link`: lista solo links activos (`link_status='linked'`) enriquecidos con datos RIS y PACS.
- Fallback legacy (si no existe tabla): reconstruye desde `tbmanual_uploads.islinked=1`.

### Campos de salida
- `link_id`, `examination_guid`, `order_study_uuid`
- `pacs_study_pk`, `study_instance_uid`
- `source`, `linked_at`, `linked_by`
- `order_accession`, `order_date`, `location_id`
- `patient_name`, `patient_id`, `study_type`
- `pacs_accession`, `pacs_study_description`, `pacs_patient_name`

---

## 4.6 Desvincular estudio (nueva)
### Endpoint
`POST /api/dicom/unlink-study`

### Auth
JWT requerido.

### Input soportado
Opcion A:
- `link_id`

Opcion B:
- `examination_guid` + opcional `pacs_study_pk` o `study_instance_uid`

Opcional:
- `reason`

### Logica de desvinculacion
1. si existe `tbpacs_study_link`:
   - marca `link_status='unlinked'`, setea `unlinked_at`, `unlinked_reason`.
2. limpia consistencia legacy en `tbmanual_uploads` para ese par orden/estudio.
3. cuenta links activos remanentes (tabla nueva + manual legacy).
4. si no quedan links activos para la orden:
   - `tbexamination.isimage=0`.

### Output
- `examination_guid`
- `study_instance_uid`
- `remaining_active_links`
- `remaining_active_manual_links`

---

## 4.7 Cancelacion de orden en worklist
### Endpoint
`DELETE /api/worklist/<exam_id>`

### Auth
JWT requerido.

### Efecto de integracion
- cambia estado examen (`Status='Cancelled'`, `IsExecuted=1`),
- limpia `tbmanual_uploads` vinculadas a la orden,
- si existe `tbpacs_study_link`, marca todos los links activos de la orden como `unlinked` con motivo de cancelacion.

---

## 4.8 Cancelacion de admision
### Endpoint
`DELETE /api/admissions/<admission_guid>`

### Auth
JWT requerido.

### Efecto de integracion
- `tbexamination.IsAdmitted=0`,
- limpia `tbmanual_uploads` vinculadas a la orden,
- marca links activos en `tbpacs_study_link` como `unlinked` con motivo de cancelacion de admision.

---

## 5. Flujos funcionales end-to-end

## 5.1 Flujo A: Carga manual y vinculacion
1. Usuario selecciona direccion en frontend.
2. Sube archivo DICOM en tab `Cargar Estudio Dicom`.
3. Backend envia a PACS y guarda en `tbmanual_uploads` como no vinculado.
4. En tab `Vincular Imagen`, panel izquierdo muestra estudio no vinculado.
5. Panel derecho muestra ordenes RIS sin imagen (`isimage=0`).
6. Usuario vincula.
7. Backend crea/actualiza link y marca orden con imagen (`isimage=1`).

## 5.2 Flujo B: Vinculacion directa con estudio PACS
1. `manual/unlinked-studies` incluye estudios PACS no vinculados (`source=pacs`).
2. Usuario elige estudio PACS + orden RIS.
3. Se llama `POST /api/dicom/link-study` con `pacs_study_pk`.
4. Se crea vinculacion activa en `tbpacs_study_link` y se actualiza orden.

## 5.3 Flujo C: Desvinculacion manual desde UI
1. Usuario entra a tab `Desvincular Imagen`.
2. Lista links activos con filtro por direccion/all.
3. Selecciona fila y confirma motivo.
4. Backend ejecuta `POST /api/dicom/unlink-study`.
5. Si orden queda sin links activos, vuelve a `isimage=0`.
6. La orden reaparece en `search-examinations` para relink.

## 5.4 Flujo D: Desvinculacion automatica por cancelacion
1. Usuario cancela orden (`/worklist/<id>` o `/admissions/<id>`).
2. Se limpian links manuales y tabla de links.
3. Se conserva historial con `link_status='unlinked'` y motivo.

---

## 6. Frontend: comportamiento actual
Pantalla principal: `CargarEstudios.tsx`

Tabs:
- `Cargar Estudio Dicom`
- `Vincular Imagen`
- `Desvincular Imagen`

## 6.1 Vincular Imagen
Componente: `VincularImagenTab.tsx`

- Selector de direccion con opcion `Todas las ubicaciones`.
- Izquierda: estudios no vinculados (`/manual/unlinked-studies`).
- Derecha: ordenes sin imagen (`/dicom/search-examinations`).
- Vinculacion con confirmacion modal.
- Permite vincular fuente manual o PACS.

## 6.2 Desvincular Imagen
Componente: `DesvincularImagenTab.tsx`

- Selector de direccion con opcion global.
- Lista de links activos (`/dicom/linked-studies`).
- Filtro por paciente, dni, accession, tipo o UID.
- Desvinculacion con motivo (`/dicom/unlink-study`).
- Invalida caches de linked/unlinked/orders via React Query.

---

## 7. Reglas de negocio consolidadas
1. Una orden activa solo puede tener un link activo en `tbpacs_study_link` (indice parcial).
2. Un estudio PACS activo solo puede estar vinculado a una orden activa.
3. Al relink, primero se cierra link anterior para mantener historial.
4. `tbmanual_uploads` se mantiene por compatibilidad y trazabilidad por instancia.
5. `tbexamination.isimage` representa estado operativo de "orden con imagen".
6. Si no quedan links activos de una orden, `isimage` se resetea a `0`.
7. `location_id=all` habilita vista/operacion global multi-sede.

---

## 8. Seguridad y autorizacion
- Requieren JWT:
  - `/dicom/search-examinations`
  - `/dicom/link-study`
  - `/dicom/linked-studies`
  - `/dicom/unlink-study`
  - endpoints de cancelacion (`worklist`, `admissions`)
- No requieren JWT actualmente:
  - `/manual/upload`
  - `/manual/unlinked-studies`

Nota recomendada:
- evaluar cierre de endpoints manuales con JWT o token de servicio para entornos productivos estrictos.

---

## 9. SQL de verificacion operativa

## 9.1 Ver links activos
```sql
SELECT id, order_guid, pacs_study_pk, pacs_study_iuid, source, linked_at
FROM nextris.tbpacs_study_link
WHERE link_status = 'linked'
ORDER BY linked_at DESC;
```

## 9.2 Ver historial de desvinculaciones
```sql
SELECT id, order_guid, pacs_study_iuid, link_status, linked_at, unlinked_at, unlinked_reason
FROM nextris.tbpacs_study_link
WHERE link_status = 'unlinked'
ORDER BY unlinked_at DESC;
```

## 9.3 Ver archivos manuales aun vinculados
```sql
SELECT study_instance_uid, linked_examination_guid, COUNT(*) AS instances
FROM nextris.tbmanual_uploads
WHERE islinked = 1
GROUP BY study_instance_uid, linked_examination_guid
ORDER BY COUNT(*) DESC;
```

## 9.4 Detectar ordenes inconsistentes
```sql
SELECT e.guid, e.isimage,
       COALESCE(ls.cnt, 0) AS active_link_count,
       COALESCE(mu.cnt, 0) AS active_manual_count
FROM nextris.tbexamination e
LEFT JOIN (
  SELECT order_guid, COUNT(*) AS cnt
  FROM nextris.tbpacs_study_link
  WHERE link_status = 'linked'
  GROUP BY order_guid
) ls ON ls.order_guid = e.guid
LEFT JOIN (
  SELECT linked_examination_guid AS order_guid, COUNT(*) AS cnt
  FROM nextris.tbmanual_uploads
  WHERE islinked = 1
  GROUP BY linked_examination_guid
) mu ON mu.order_guid = e.guid
WHERE (e.isimage = 1 AND COALESCE(ls.cnt, 0) = 0 AND COALESCE(mu.cnt, 0) = 0)
   OR (e.isimage = 0 AND (COALESCE(ls.cnt, 0) > 0 OR COALESCE(mu.cnt, 0) > 0));
```

---

## 10. Troubleshooting

## 10.1 "No aparecen estudios PACS no vinculados"
Revisar:
- existencia de `tbpacs_study_link`,
- que el estudio no tenga link activo,
- filtro de `location_id` (usar `all` para descartar filtro).

## 10.2 "No aparecen ordenes para vincular"
Revisar:
- `tbexamination.isimage` debe ser `0` o `NULL`,
- filtro por `location_id`,
- filtros de frontend (nombre/dni/fecha).

## 10.3 "Desvincule pero no reaparece la orden"
Revisar:
- respuesta de `/dicom/unlink-study` (`remaining_active_links`),
- si aun existe otro link activo para la misma orden,
- cache frontend (refetch/invalidaciones).

## 10.4 "Error de envio a PACS"
Revisar:
- Keycloak token service account,
- URL STOW-RS,
- logs backend de `send_to_pacs`.

---

## 11. Checklist de pruebas recomendadas
1. Subir DICOM manual con direccion valida.
2. Confirmar alta en PACS y en `tbmanual_uploads` (`islinked=0`).
3. Vincular manual -> orden: validar `isimage=1` y link activo.
4. Vincular PACS -> orden: validar `tbpacs_study_link` con `source='reconcile'`.
5. Desvincular desde tab: validar link a `unlinked`, limpiar legacy y `isimage` segun remanentes.
6. Cancelar por worklist/admision: validar desvinculacion automatica y motivo registrado.
7. Probar `location_id=all` en listar no vinculados, ordenes sin imagen y vinculados.

---

## 12. Limitaciones actuales y mejoras sugeridas
1. Endpoints manuales (`/manual/upload`, `/manual/unlinked-studies`) estan sin JWT.
2. `linked-studies` limita a 500 filas; podria requerir paginacion server-side.
3. No hay proceso batch de reconciliacion automatica (`source='auto'` reservado para futuro).
4. Convive logica legacy + nueva; recomendable plan de migracion controlada para consolidar lectura/escritura.

---

## 13. Resumen ejecutivo
La integracion actual queda soportada por una estrategia hibrida robusta:
- compatibilidad legacy con `tbmanual_uploads`,
- tabla canonical de relacion RIS-PACS (`tbpacs_study_link`) con historial,
- operaciones completas de vincular/desvincular,
- propagacion de estado operativo a la orden (`tbexamination.isimage`),
- soporte multi-ubicacion con opcion global `all`,
- UI dedicada tanto para vinculacion como para desvinculacion.
