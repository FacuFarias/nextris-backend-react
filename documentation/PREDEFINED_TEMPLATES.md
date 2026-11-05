# Plantillas de Informes Predefinidos - NextRIS

> **Última actualización:** 2026-05-22
> **Propósito:** Registro de plantillas predefinidas del sistema para evitar consultas repetitivas a la DB.

---

## Estructura de Tablas

### `nextris.isstudytype` - Tipos de Estudio
| Columna | Tipo | Descripción |
|---------|------|-------------|
| guid | varchar(45) | PK, UUID |
| code | varchar(45) | Código del estudio |
| description | text | Nombre del estudio |
| studygroup_id | varchar(45) | FK a isstudytypegroup |
| bodypart_id | varchar(45) | FK a isanatomicalpart |
| modality_id | varchar(45) | FK a ismodality |
| default_predef_id | varchar(45) | FK a tbinfpredef (plantilla default) |

### `nextris.tbinfpredef` - Plantillas de Informes
| Columna | Tipo | Descripción |
|---------|------|-------------|
| guid | varchar(45) | PK, UUID (default: uuid_generate_v4()) |
| tittle | text | Nombre de la plantilla |
| studytype_id | varchar(45) | FK a isstudytype |
| findings | text | Hallazgos |
| impression | text | Impresión diagnóstica |
| technique | text | Técnica utilizada |
| conclusion | text | Conclusión |
| variables | jsonb | Array de variables disponibles |
| isdefault | bit(1) | Si es plantilla por defecto |
| report_type | varchar(20) | 'simple' o 'inteligente' |
| owner_id | varchar(45) | 'nextris' = del sistema, UUID = de usuario |

---

## IDs de Referencia

### Grupos de Estudio (`nextris.isstudytypegroup`)
| GUID | Descripción |
|------|-------------|
| ea0b5844-bdc6-48ab-9f6b-f211a00118c4 | Mama |

### Partes Anatómicas (`nextris.isanatomicalpart`)
| GUID | Descripción |
|------|-------------|
| b5287833-a669-4678-947f-2867b343c71d | Mama |

### Modalidades (`nextris.ismodality`)
| GUID | Descripción | External Code |
|------|-------------|---------------|
| e0010ba8-df9d-435d-98e7-4ef5103b0aec | MAMOGRAFIA | MG |
| 78696a8c-35ac-11ef-b0f7-00ffb9d5e4de | RAYOS X | RX |
| 181df076-340b-11ef-bdff-00ffb9d5e4de | ECOGRAFIA | US |
| 6211f329-35ac-11ef-b0f7-00ffb9d5e4de | RESONANCIA | RMN |
| e0250b6c-3419-11ef-bdff-00ffb9d5e4de | TOMOGRAFIA | CT |

---

## Estudios de Mamografía y sus Plantillas

### 1. MAMOGRAFIA 3D - TOMOSINTESIS
- **Código:** 2809
- **Study Type GUID:** `59059362-050d-4236-b88e-643275a5068b`
- **Plantilla GUID:** `819f70ed-29f0-42cf-9738-d82edff866d4`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
No se identifican hallazgos sospechosos en la tomosíntesis.
No se observan microcalcificaciones agrupadas sospechosas.
No se evidencian masas ni distorsiones arquitectónicas.
```
- **Impression:** Estudio de mamografía 3D (tomosíntesis) sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital 3D (tomosíntesis) bilateral en proyecciones craneocaudal y oblicua mediolateral.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 2. MAMOGRAFIA 3D CON CONTRASTE
- **Código:** 2866
- **Study Type GUID:** `57354a1c-0274-4ba1-81cb-1bec89fb8616`
- **Plantilla GUID:** `369dcb19-7659-4830-87eb-e7ea3554aaae`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
Estudio realizado con administración de medio de contraste yodado intravenoso.
No se identifican realces patológicos sospechosos.
No se observan masas con captación anómala de contraste.
No se evidencian microcalcificaciones agrupadas sospechosas.
```
- **Impression:** Mamografía 3D con contraste sin hallazgos sospechosos de malignidad. Sin realces patológicos.
- **Technique:** Mamografía digital 3D (tomosíntesis) bilateral con administración de contraste yodado IV. Proyecciones craneocaudal y oblicua mediolateral.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 3. MAMOGRAFIA BILATERAL CON PROYECCION AXILAR CON TECNICA DE ECKLUND
- **Código:** 2952
- **Study Type GUID:** `b956961e-fbca-4820-80cf-84146c4fea2e`
- **Plantilla GUID:** `9c7f8f81-1875-469c-8fd3-ec270e12337c`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
Proyección axilar con técnica de Ecklund realizada correctamente.
No se identifican hallazgos sospechosos en regiones axilares.
No se observan adenopatías sospechosas.
No se evidencian masas ni microcalcificaciones agrupadas.
```
- **Impression:** Mamografía bilateral con proyección axilar (técnica de Ecklund) sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital bilateral en proyecciones craneocaudal y oblicua mediolateral. Proyección axilar con técnica de Ecklund.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 4. MAMOGRAFIA DIGITAL BILATERAL F Y P
- **Código:** 2216
- **Study Type GUID:** `c194273e-5933-4f08-af49-19cab6d3c3ce`
- **Plantilla GUID:** `bfbc5ab0-9e9f-44e0-ab1e-7b13195e0d29`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
No se identifican hallazgos sospechosos.
No se observan masas ni distorsiones arquitectónicas.
No se evidencian microcalcificaciones agrupadas sospechosas.
Patrón vascular normal.
```
- **Impression:** Mamografía digital bilateral sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital bilateral en proyecciones craneocaudal y oblicua mediolateral (frente y perfil).
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 5. MAMOGRAFIA DIGITAL BILATERAL F Y P C/PROY. AXILAR
- **Código:** 2217
- **Study Type GUID:** `f3f194f6-544c-4d50-b66f-fd8cabb958da`
- **Plantilla GUID:** `2434394f-38f5-4b93-beba-4f1bc679d8b4`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
Proyección axilar incluida.
No se identifican hallazgos sospechosos en regiones axilares.
No se observan adenopatías sospechosas.
No se evidencian masas ni microcalcificaciones agrupadas.
```
- **Impression:** Mamografía digital bilateral con proyección axilar sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital bilateral en proyecciones craneocaudal, oblicua mediolateral y axilar.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 6. MAMOGRAFIA DIGITAL CON COMPRESION MAGNIFICACION F Y P
- **Código:** 2218
- **Study Type GUID:** `8cf89934-ed6e-4f9e-b545-d98ed8232cd9`
- **Plantilla GUID:** `4e6587d8-4034-416e-873c-4b6d92794641`
- **Variables:** `[DENSIDAD]`
- **Findings:**
```
Las mamas presentan tejido fibroglandular de densidad [DENSIDAD].
Estudio realizado con compresión y magnificación.
No se identifican hallazgos sospechosos en las proyecciones con magnificación.
No se observan microcalcificaciones sospechosas mejor caracterizadas.
No se evidencian masas ni distorsiones arquitectónicas.
```
- **Impression:** Mamografía digital con compresión y magnificación sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital bilateral en proyecciones craneocaudal y oblicua mediolateral con compresión y magnificación.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 7. MAMOGRAFIA DIGITAL UNILATERAL
- **Código:** 2219
- **Study Type GUID:** `a56a3097-7735-4f9d-91b1-d6deae6663e0`
- **Plantilla GUID:** `b5088d73-f3ce-4488-975d-fb3ed6fb5726`
- **Variables:** `[LATERALIDAD]`, `[DENSIDAD]`
- **Findings:**
```
La mama [LATERALIDAD] presenta tejido fibroglandular de densidad [DENSIDAD].
No se identifican hallazgos sospechosos.
No se observan masas ni distorsiones arquitectónicas.
No se evidencian microcalcificaciones agrupadas sospechosas.
```
- **Impression:** Mamografía digital unilateral [LATERALIDAD] sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital unilateral [LATERALIDAD] en proyecciones craneocaudal y oblicua mediolateral.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 8. MAMOGRAFIA DIGITAL UNILATERAL C/PROY. AXILAR
- **Código:** 2220
- **Study Type GUID:** `d98fd7e2-f037-418e-9b12-0c2cb2131758`
- **Plantilla GUID:** `9f4e28fd-947b-493c-ae4f-9c0b15672d3d`
- **Variables:** `[LATERALIDAD]`, `[DENSIDAD]`
- **Findings:**
```
La mama [LATERALIDAD] presenta tejido fibroglandular de densidad [DENSIDAD].
Proyección axilar incluida.
No se identifican hallazgos sospechosos en región axilar.
No se observan adenopatías sospechosas.
No se evidencian masas ni microcalcificaciones agrupadas.
```
- **Impression:** Mamografía digital unilateral [LATERALIDAD] con proyección axilar sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital unilateral [LATERALIDAD] en proyecciones craneocaudal, oblicua mediolateral y axilar.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 9. MAMOGRAFIA UNILATERAL CON PROYECCION AXILAR CON TECNICA DE ECKLUND
- **Código:** 3046
- **Study Type GUID:** `390c4c6d-8613-4ff5-8592-804431d9ff86`
- **Plantilla GUID:** `e64f8258-ba88-4d53-8367-aca8dc58aed8`
- **Variables:** `[LATERALIDAD]`, `[DENSIDAD]`
- **Findings:**
```
La mama [LATERALIDAD] presenta tejido fibroglandular de densidad [DENSIDAD].
Proyección axilar con técnica de Ecklund realizada correctamente.
No se identifican hallazgos sospechosos en región axilar.
No se observan adenopatías sospechosas.
No se evidencian masas ni microcalcificaciones agrupadas.
```
- **Impression:** Mamografía unilateral [LATERALIDAD] con proyección axilar (técnica de Ecklund) sin hallazgos sospechosos de malignidad.
- **Technique:** Mamografía digital unilateral [LATERALIDAD] en proyecciones craneocaudal y oblicua mediolateral. Proyección axilar con técnica de Ecklund.
- **Conclusion:** Sin hallazgos sospechosos. Se recomienda seguimiento según indicación médica.

### 10. MARCACION ESTEREOTAXICA
- **Código:** 76
- **Study Type GUID:** `1be01ae2-d0cb-40e9-81d0-984493450cd9`
- **Plantilla GUID:** `65d20389-4918-4623-85e5-faecd2fe4e4d`
- **Variables:** `[LATERALIDAD]`, `[POSICION]`, `[DISTANCIA]`, `[TIPO_LESION]`
- **Findings:**
```
Procedimiento de marcación estereotáxica realizado en mama [LATERALIDAD].
Se localiza lesión en posición [POSICION] (horaria) a [DISTANCIA] cm del pezón.
Tipo de lesión: [TIPO_LESION].
Se colocó arpón/clip de localización correctamente.
Imagen post-marcación confirma posición adecuada del marcador.
```
- **Impression:** Marcación estereotáxica exitosa de lesión en mama [LATERALIDAD]. Localización confirmada.
- **Technique:** Marcación estereotáxica guiada por mamografía digital. Colocación de arpón/clip de localización.
- **Conclusion:** Procedimiento exitoso. Lesión correctamente marcada para cirugía.

---

## Resumen Rápido - SQL para Consultas

### Obtener todos los estudios de mamografía con sus plantillas
```sql
SELECT st.code, st.description, p.tittle, p.guid as template_guid, st.guid as study_guid
FROM nextris.isstudytype st
JOIN nextris.tbinfpredef p ON st.default_predef_id = p.guid
WHERE st.modality_id = 'e0010ba8-df9d-435d-98e7-4ef5103b0aec'
ORDER BY st.code;
```

### Obtener plantilla por código de estudio
```sql
SELECT p.*
FROM nextris.tbinfpredef p
JOIN nextris.isstudytype st ON p.studytype_id = st.guid
WHERE st.code = '2809' AND p.owner_id = 'nextris';
```

### Obtener todas las plantillas del sistema
```sql
SELECT p.guid, p.tittle, st.code, st.description
FROM nextris.tbinfpredef p
JOIN nextris.isstudytype st ON p.studytype_id = st.guid
WHERE p.owner_id = 'nextris'
ORDER BY st.code;
```

---

## Notas para Crear Nuevas Plantillas

### Campos requeridos para INSERT en `tbinfpredef`
```sql
INSERT INTO nextris.tbinfpredef (
    guid,              -- gen_random_uuid() o uuid_generate_v4()
    tittle,            -- Nombre de la plantilla (mismo que el estudio)
    studytype_id,      -- GUID del estudio en isstudytype
    findings,          -- Texto de hallazgos (puede usar variables)
    impression,        -- Impresión diagnóstica
    technique,         -- Técnica utilizada
    conclusion,        -- Conclusión/recomendación
    variables,         -- JSON array: '["VAR1", "VAR2"]'
    isdefault,         -- B'0' o B'1'
    report_type,       -- 'simple' o 'inteligente'
    owner_id           -- 'nextris' para sistema, UUID para usuario
) VALUES (...);
```

### Vincular plantilla como default del estudio
```sql
UPDATE nextris.isstudytype
SET default_predef_id = 'GUID_PLANTILLA'
WHERE guid = 'GUID_ESTUDIO';
```

### Crear estudio + plantilla + vincular (ejemplo completo)
```sql
-- 1. Crear estudio
INSERT INTO nextris.isstudytype (guid, code, description, studygroup_id, bodypart_id, modality_id)
VALUES (gen_random_uuid(), 'CODIGO', 'DESCRIPCION', 'GROUP_GUID', 'BODYPART_GUID', 'MODALITY_GUID')
RETURNING guid;

-- 2. Crear plantilla (usar el guid del paso 1 como studytype_id)
INSERT INTO nextris.tbinfpredef (guid, tittle, studytype_id, findings, impression, technique, conclusion, variables, isdefault, report_type, owner_id)
VALUES (gen_random_uuid(), 'TITULO', 'STUDY_GUID', '...', '...', '...', '...', '[]', B'0', 'simple', 'nextris')
RETURNING guid;

-- 3. Vincular
UPDATE nextris.isstudytype SET default_predef_id = 'TEMPLATE_GUID' WHERE guid = 'STUDY_GUID';
```
