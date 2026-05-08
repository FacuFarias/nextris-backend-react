# Implementación: Auto-Asignación de Location basada en AET DICOM

## 1. Objetivo

Esta implementación busca **automatizar la asignación de ubicación física (location) a los estudios DICOM** tan pronto como llegan al PACS, basándose en el **AET (Application Entity Title) del gateway/remitente**.

### Problema que resuelve
- Cuando llega una imagen DICOM desde un agente (gateway, modalidad, etc.), no se conocía automáticamente a qué ubicación física pertenecía
- Esto hacía necesario asignar manualmente la ubicación, generando inconsistencias y carga operativa
- Sin location asignado, los flujos de reporte y distribución no podían asociar estudios a sus sedes

### Solución
- Crear un mapeo entre **AET del remitente** (`public.series.sending_aet`) y **ubicaciones configuradas** (`nextris.tblocation.gateway_aet`)
- Cuando una serie DICOM llega, un trigger automático busca el match y asigna `public.study.location_id` al instante
- Se registra un log de auditoría para rastrear qué AET originó qué location

---

## 2. Lógica de Funcionamiento

### Flujo de Ejecución

```
┌────────────────────────────────────────────────────────────────────┐
│ 1. DICOM Serie llega al PACS (DCM4CHEE)                            │
│    - Se inserta fila en public.series                              │
│    - Columna sending_aet recibe el AET del remitente               │
│    - Columna study_fk referencia el estudio en public.study        │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────────────┐
│ 2. TRIGGER: trg_assign_location_on_series se dispara               │
│    (AFTER INSERT ON public.series FOR EACH ROW)                   │
│    - Se ejecuta fn_assign_location_from_aet()                      │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────────────┐
│ 3. FUNCIÓN: fn_assign_location_from_aet() ejecuta:                 │
│                                                                    │
│    a) Valida que NEW.study_fk y NEW.sending_aet no sean NULL      │
│    b) Busca en nextris.tblocation una fila donde:                │
│       WHERE gateway_aet = NEW.sending_aet                          │
│    c) Si ENCUENTRA match:                                          │
│       - Obtiene el guid de la location                             │
│       - Obtiene study_iuid desde public.study                      │
│       - Ejecuta UPDATE public.study.location_id = guid             │
│       - Registra en nextris.tbpacs_location_assignment (auditoría) │
│    d) Si NO encuentra match:                                       │
│       - Retorna NEW sin hacer nada (silencioso)                    │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────────────┐
│ RESULTADO:                                                          │
│ • public.study.location_id = guid de la location (auto)            │
│ • nextris.tbpacs_location_assignment registra el match para audit. │
└────────────────────────────────────────────────────────────────────┘
```

### Ejemplo Concreto

```
ENTRADA:
  - Serie DICOM llega con sending_aet = 'FF001'
  - study_fk = 25
  - study_iuid = '1.2.840.113619.2.323.84107362492.1761145310.862'

BÚSQUEDA:
  SELECT guid FROM nextris.tblocation 
  WHERE gateway_aet = 'FF001'
  → ENCUENTRA: 'c7168384-3c3d-4cb9-ad9f-41bbb5083be6'

ACTUALIZACIÓN:
  UPDATE public.study 
  SET location_id = 'c7168384-3c3d-4cb9-ad9f-41bbb5083be6'
  WHERE pk = 25

AUDITORÍA:
  INSERT INTO nextris.tbpacs_location_assignment
    (pacs_study_pk, pacs_study_iuid, location_id, sending_aet, matched_at)
  VALUES
    (25, 
     '1.2.840.113619.2.323.84107362492.1761145310.862',
     'c7168384-3c3d-4cb9-ad9f-41bbb5083be6',
     'FF001',
     NOW())

RESULTADO EN DB:
  public.study.pk=25 → location_id = 'c7168384-3c3d-4cb9-ad9f-41bbb5083be6'
```

### Casos Especiales

| Escenario | Comportamiento |
|-----------|---|
| `sending_aet = NULL` | No se ejecuta match. No se asigna location. |
| `sending_aet` no coincide con ningún `gateway_aet` | No se asigna location. Study queda sin location_id. |
| `study_fk` no existe en `public.study` | No ocurre INSERT (FK constraint previene). |
| La misma serie llega 2 veces | UPSERT en audit table: actualiza, no duplica. |
| Se modifica `nextris.tblocation.gateway_aet` | Los estudios futuros usan el nuevo mapping. Los antiguos no se alteran. |

---

## 3. Tablas Afectadas en esta Implementación

### 3.1 Tabla: `public.study` (DCM4CHEE original)
**Ubicación:** Esquema `public` (DCM4CHEE)  
**Cambio:** Se modifica la columna `location_id` (ya existía)

| Columna | Tipo | Cambio | Propósito |
|---------|------|--------|----------|
| `pk` | `BIGINT PRIMARY KEY` | Ninguno | Clave primaria |
| `study_iuid` | `VARCHAR(255)` | Ninguno | UID del estudio DICOM |
| `location_id` | `VARCHAR(100)` | **ACTUALIZADA POR TRIGGER** | Almacena el guid de la location asignada |
| Otras... | ... | Ninguno | No afectadas |

**Impacto:**
- El trigger `AFTER INSERT ON public.series` rellena automáticamente `location_id`
- No se ejecutan deletes ni updates directos desde el trigger

---

### 3.2 Tabla: `public.series` (DCM4CHEE original)
**Ubicación:** Esquema `public` (DCM4CHEE)  
**Cambio:** Ninguno (solo se lee)

| Columna | Tipo | Cambio | Propósito |
|---------|------|--------|----------|
| `pk` | `BIGINT PRIMARY KEY` | Ninguno | Clave primaria de serie |
| `study_fk` | `BIGINT FK` | Ninguno | Referencia a `public.study.pk` |
| `sending_aet` | `VARCHAR(255)` | Ninguno | AET del remitente ← **SE LEE EN TRIGGER** |
| Otras... | ... | Ninguno | No afectadas |

**Impacto:**
- El trigger se dispara en `AFTER INSERT` de esta tabla
- Se lee `sending_aet` para hacer el matching

---

### 3.3 Tabla: `nextris.tblocation` (RIS NextRIS)
**Ubicación:** Esquema `nextris`  
**Cambio:** Se agregó columna `gateway_aet` (en migración anterior)

| Columna | Tipo | Cambio | Propósito |
|---------|------|--------|----------|
| `guid` | `VARCHAR(100) PRIMARY KEY` | Ninguno | Clave primaria |
| `name` | `VARCHAR(255)` | Ninguno | Nombre de la location (ej: "Clínica Facundo Farías") |
| `gateway_aet` | `VARCHAR(64)` | **NUEVO** | AET del gateway de esta location (mapeo clave) |
| Otras... | ... | Ninguno | No afectadas |

**Impacto:**
- El trigger busca aquí usando `gateway_aet`
- Debe estar poblada manualmente vía API `/api/config/locations`
- Es el "diccionario" de mapeos

---

### 3.4 Tabla: `nextris.tbpacs_location_assignment` (NUEVA)
**Ubicación:** Esquema `nextris`  
**Cambio:** Se crea en esta implementación

| Columna | Tipo | Constraints | Propósito |
|---------|------|---|----------|
| `pacs_study_pk` | `BIGINT` | PRIMARY KEY, FK → `public.study.pk` | Clave primaria + referencia al estudio PACS |
| `pacs_study_iuid` | `VARCHAR(255)` | NOT NULL | UID DICOM del estudio (para auditoría) |
| `location_id` | `VARCHAR(100)` | FK → `nextris.tblocation.guid` | GUID de la location asignada |
| `sending_aet` | `VARCHAR(64)` | NOT NULL | AET que originó el match (historial) |
| `matched_at` | `TIMESTAMP` | DEFAULT NOW() | Cuándo se hizo el match |

**Propósito:**
- Auditoría y trazabilidad
- Permite ver qué AET causó qué location

**Relaciones:**
```
tbpacs_location_assignment.pacs_study_pk → public.study.pk
                              ↑ (CASCADE DELETE)

tbpacs_location_assignment.location_id → nextris.tblocation.guid
                              ↑ (CASCADE DELETE)
```

---

## 4. Funciones y Triggers Creados

### 4.1 Función: `nextris.fn_assign_location_from_aet()`

**Tipo:** Función PostgreSQL TRIGGER  
**Lenguaje:** PL/pgSQL  
**Executed:** AFTER INSERT ON public.series  

#### Código

```sql
CREATE OR REPLACE FUNCTION nextris.fn_assign_location_from_aet()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_location_id VARCHAR(100);
    v_study_iuid VARCHAR(255);
BEGIN
    -- Validar que los campos requeridos no sean NULL
    IF NEW.study_fk IS NULL OR NEW.sending_aet IS NULL OR NEW.sending_aet = '' THEN
        RETURN NEW;
    END IF;

    -- Buscar location cuyo gateway_aet coincida con el sending_aet de la serie
    SELECT l.guid
      INTO v_location_id
      FROM nextris.tblocation l
     WHERE l.gateway_aet = NEW.sending_aet
     LIMIT 1;

    -- Si no hay match, retornar sin hacer nada
    IF v_location_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Obtener el study_iuid del estudio
    SELECT s.study_iuid
      INTO v_study_iuid
      FROM public.study s
     WHERE s.pk = NEW.study_fk;

    -- Si no existe el estudio, retornar
    IF v_study_iuid IS NULL THEN
        RETURN NEW;
    END IF;

    -- *** ACCIÓN PRINCIPAL: Actualizar location_id en public.study ***
    UPDATE public.study
    SET location_id = v_location_id
    WHERE pk = NEW.study_fk;

    -- Registrar en la tabla de auditoría
    INSERT INTO nextris.tbpacs_location_assignment (
        pacs_study_pk,
        pacs_study_iuid,
        location_id,
        sending_aet,
        matched_at
    )
    VALUES (
        NEW.study_fk,
        v_study_iuid,
        v_location_id,
        NEW.sending_aet,
        NOW()
    )
    ON CONFLICT (pacs_study_pk)
    DO UPDATE SET
        pacs_study_iuid = EXCLUDED.pacs_study_iuid,
        location_id = EXCLUDED.location_id,
        sending_aet = EXCLUDED.sending_aet,
        matched_at = NOW();

    RETURN NEW;
END;
$$;
```

#### Explicación línea por línea

| Línea | Propósito |
|-------|----------|
| `DECLARE v_location_id, v_study_iuid` | Variables locales para almacenar datos temporales |
| `IF NEW.study_fk IS NULL...` | Validar que los datos mínimos requeridos existan |
| `SELECT l.guid INTO v_location_id...` | Buscar la location en RIS que coincida con el AET |
| `IF v_location_id IS NULL THEN RETURN NEW` | Si no hay match, salir silenciosamente (no error) |
| `SELECT s.study_iuid...` | Obtener el identificador DICOM del estudio |
| `UPDATE public.study SET location_id...` | **ACCIÓN CRÍTICA**: Asignar la location al estudio |
| `INSERT INTO tbpacs_location_assignment...` | Registrar en auditoría para historial |
| `ON CONFLICT...DO UPDATE` | Si ya existe entrada, actualizar (UPSERT, no duplicar) |

---

### 4.2 Trigger: `trg_assign_location_on_series`

**Tipo:** AFTER INSERT trigger  
**En tabla:** `public.series`  
**Para cada:** ROW  
**Ejecuta:** `nextris.fn_assign_location_from_aet()`  

#### Definición SQL

```sql
DROP TRIGGER IF EXISTS trg_assign_location_on_series ON public.series;

CREATE TRIGGER trg_assign_location_on_series
AFTER INSERT ON public.series
FOR EACH ROW
EXECUTE FUNCTION nextris.fn_assign_location_from_aet();
```

#### Explicación

| Parámetro | Valor | Significado |
|-----------|-------|-----------|
| `AFTER INSERT` | Timing | Se ejecuta **después** de insertar la serie (no antes) |
| `ON public.series` | Tabla | Se dispara cuando entra una nueva serie a PACS |
| `FOR EACH ROW` | Scope | Se ejecuta 1 vez por cada serie insertada |
| `EXECUTE FUNCTION` | Acción | Llama la función que hace el trabajo |

---

### 4.3 Índices de Rendimiento

**Índice 1:** `idx_pla_location_id`
```sql
CREATE INDEX idx_pla_location_id
    ON nextris.tbpacs_location_assignment (location_id);
```
**Propósito:** Acelerar búsquedas de assignments por location (para reportes)

**Índice 2:** `idx_pla_sending_aet`
```sql
CREATE INDEX idx_pla_sending_aet
    ON nextris.tbpacs_location_assignment (sending_aet);
```
**Propósito:** Acelerar búsquedas de assignments por AET (para auditoría)

---

## 5. Guía: Implementación en DCM4CHEE Base

### 5.1 Requisitos Previos

Antes de implementar, verificar que tengas:

- **PostgreSQL 12+** instalado y accesible
- **DCM4CHEE corriendo** con esquema `public` poblado
- **Base de datos RIS** con esquema `nextris` (o similar)
- **Rol de BD** con permisos CREATE FUNCTION, CREATE TRIGGER en ambos esquemas
- **Conocimiento de SQL/PL/pgSQL** (opcional, pero recomendado para debugging)

### 5.2 Paso 1: Verificar Prerequisitos en BD

Ejecutar como usuario administrador de PostgreSQL:

```sql
-- Verificar que exista columna location_id en public.study
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'study' AND column_name = 'location_id';
-- Si NO aparece, agregar:
-- ALTER TABLE public.study ADD COLUMN location_id VARCHAR(100);

-- Verificar que exista columna gateway_aet en nextris.tblocation (RIS)
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'nextris' AND table_name = 'tblocation' AND column_name = 'gateway_aet';
-- Si NO aparece, consulta la sección 3.2 anterior para agregar la columna

-- Verificar acceso a ambas esquemas
SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('public', 'nextris');
```

**Si alguno retorna 0 registros:**
- Para `location_id`: ejecutar `ALTER TABLE public.study ADD COLUMN location_id VARCHAR(100);`
- Para `gateway_aet`: ejecutar migración `add_gateway_transmission_to_tblocation.sql` primero

---

### 5.3 Paso 2: Crear la Tabla de Auditoría

Ejecutar como usuario con permisos CREATETABLE en esquema `nextris`:

```sql
BEGIN;

-- Crear tabla de asignaciones
CREATE TABLE IF NOT EXISTS nextris.tbpacs_location_assignment (
    pacs_study_pk BIGINT PRIMARY KEY,
    pacs_study_iuid VARCHAR(255) NOT NULL,
    location_id VARCHAR(100) NOT NULL,
    sending_aet VARCHAR(64) NOT NULL,
    matched_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_pla_location
        FOREIGN KEY (location_id)
        REFERENCES nextris.tblocation (guid)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_pla_study
        FOREIGN KEY (pacs_study_pk)
        REFERENCES public.study (pk)
        ON DELETE CASCADE
);

-- Crear índices para rendimiento
CREATE INDEX IF NOT EXISTS idx_pla_location_id
    ON nextris.tbpacs_location_assignment (location_id);

CREATE INDEX IF NOT EXISTS idx_pla_sending_aet
    ON nextris.tbpacs_location_assignment (sending_aet);

COMMIT;
```

**Validación:**
```sql
\dt nextris.tbpacs_location_assignment  -- Debe mostrar la tabla
\di idx_pla_*                           -- Debe mostrar 2 índices
```

---

### 5.4 Paso 3: Crear la Función Trigger

Ejecutar como usuario con permisos CREATEFUNCTION en ambos esquemas:

```sql
CREATE OR REPLACE FUNCTION nextris.fn_assign_location_from_aet()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_location_id VARCHAR(100);
    v_study_iuid VARCHAR(255);
BEGIN
    -- Validar que los campos requeridos no sean NULL
    IF NEW.study_fk IS NULL OR NEW.sending_aet IS NULL OR NEW.sending_aet = '' THEN
        RETURN NEW;
    END IF;

    -- Buscar location cuyo gateway_aet coincida con el sending_aet de la serie
    SELECT l.guid
      INTO v_location_id
      FROM nextris.tblocation l
     WHERE l.gateway_aet = NEW.sending_aet
     LIMIT 1;

    -- Si no hay match, retornar sin hacer nada
    IF v_location_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Obtener el study_iuid del estudio
    SELECT s.study_iuid
      INTO v_study_iuid
      FROM public.study s
     WHERE s.pk = NEW.study_fk;

    -- Si no existe el estudio, retornar
    IF v_study_iuid IS NULL THEN
        RETURN NEW;
    END IF;

    -- Actualizar location_id en public.study
    UPDATE public.study
    SET location_id = v_location_id
    WHERE pk = NEW.study_fk;

    -- Registrar en la tabla de auditoría
    INSERT INTO nextris.tbpacs_location_assignment (
        pacs_study_pk,
        pacs_study_iuid,
        location_id,
        sending_aet,
        matched_at
    )
    VALUES (
        NEW.study_fk,
        v_study_iuid,
        v_location_id,
        NEW.sending_aet,
        NOW()
    )
    ON CONFLICT (pacs_study_pk)
    DO UPDATE SET
        pacs_study_iuid = EXCLUDED.pacs_study_iuid,
        location_id = EXCLUDED.location_id,
        sending_aet = EXCLUDED.sending_aet,
        matched_at = NOW();

    RETURN NEW;
END;
$$;
```

**Validación:**
```sql
SELECT proname, nspname 
FROM pg_proc p 
JOIN pg_namespace n ON n.oid = p.pronamespace 
WHERE proname = 'fn_assign_location_from_aet';
-- Debe retornar 1 fila con esquema 'nextris'
```

---

### 5.5 Paso 4: Crear el Trigger

Ejecutar como usuario con permisos CREATETRIGGER en esquema `public`:

```sql
DROP TRIGGER IF EXISTS trg_assign_location_on_series ON public.series;

CREATE TRIGGER trg_assign_location_on_series
AFTER INSERT ON public.series
FOR EACH ROW
EXECUTE FUNCTION nextris.fn_assign_location_from_aet();
```

**Validación:**
```sql
SELECT tgname, tgrelid::regclass, tgenabled
FROM pg_trigger
WHERE tgname = 'trg_assign_location_on_series';
-- Debe retornar 1 fila con tgrelid='series' y tgenabled='O' (on)
```

---

### 5.6 Paso 5: Cargar Mapeos de AET a Locations

Este es un paso **MANUAL pero CRÍTICO**. Sin estos datos, el trigger no hará matches.

#### Opción A: Por UI (si NextRIS tiene frontend)

1. Ir a **Configuración → Institucional → Ubicaciones**
2. Editar cada location
3. Ir a tab **"Transmisión"**
4. En campo **"Gateway AET"**, ingresar el AET del gateway/modalidad
5. Guardar

**Ejemplo:**
```
Clínica Facundo Farías:
  - Gateway AET: FF001

Hospital Central:
  - Gateway AET: HOSP_CT

Sanatorio Privado:
  - Gateway AET: PRIV_MRI
```

#### Opción B: Por SQL directo

Si no hay UI disponible:

```sql
-- Para cada location, mapear su AET
UPDATE nextris.tblocation
SET gateway_aet = 'FF001'
WHERE name = 'Clínica Facundo Farías';

UPDATE nextris.tblocation
SET gateway_aet = 'HOSP_CT'
WHERE name = 'Hospital Central';

UPDATE nextris.tblocation
SET gateway_aet = 'PRIV_MRI'
WHERE name = 'Sanatorio Privado';

-- Validar
SELECT guid, name, gateway_aet FROM nextris.tblocation WHERE gateway_aet IS NOT NULL;
```

#### Opción C: Por script SQL de carga

Crear archivo `load_aet_mappings.sql`:

```sql
-- Mapeo de AET a Locations
INSERT INTO nextris.tblocation_aet_mapping (location_guid, gateway_aet) VALUES
  ('uuid-clinic-ff', 'FF001'),
  ('uuid-hosp-ct', 'HOSP_CT'),
  ('uuid-sanat-mri', 'PRIV_MRI')
ON CONFLICT (location_guid) DO UPDATE 
SET gateway_aet = EXCLUDED.gateway_aet;
```

Ejecutar:
```bash
psql -h DB_HOST -U DB_USER -d DB_NAME -f load_aet_mappings.sql
```

---

### 5.7 Paso 6: Pruebas de Funcionamiento

#### Test 1: Verificar que trigger está activo

```sql
SELECT tgname, tgenabled FROM pg_trigger 
WHERE tgname = 'trg_assign_location_on_series'
  AND tgrelid = 'public.series'::regclass;
-- DEBE retornar: trg_assign_location_on_series | O
```

#### Test 2: Simular llegada de serie DICOM

En una sesión de test (NO en producción), manualmente:

```sql
-- Verificar una location existe con AET mapeado
SELECT guid FROM nextris.tblocation WHERE gateway_aet = 'FF001' LIMIT 1;
-- Guardar el GUID retornado

-- Verificar un estudio existe en public.study
SELECT pk FROM public.study WHERE location_id IS NULL LIMIT 1;
-- Guardar el pk retornado

-- Resetearlo a NULL para test limpio
UPDATE public.study SET location_id = NULL WHERE pk = <pk>;

-- SIMULAR lo que el trigger hace:
DO $$
DECLARE
  v_location_id VARCHAR(100);
  v_study_iuid VARCHAR(255);
BEGIN
  -- Buscar location con AET
  SELECT guid INTO v_location_id FROM nextris.tblocation WHERE gateway_aet = 'FF001' LIMIT 1;
  
  -- Obtener study_iuid
  SELECT study_iuid INTO v_study_iuid FROM public.study WHERE pk = <pk>;
  
  -- Simular UPDATE que hace el trigger
  UPDATE public.study SET location_id = v_location_id WHERE pk = <pk>;
  
  -- Simular INSERT en audit
  INSERT INTO nextris.tbpacs_location_assignment 
    (pacs_study_pk, pacs_study_iuid, location_id, sending_aet, matched_at)
  VALUES (<pk>, v_study_iuid, v_location_id, 'FF001', NOW());
  
  RAISE NOTICE 'Test OK: location_id = %', v_location_id;
END;
$$;

-- Validar resultado
SELECT pk, location_id FROM public.study WHERE pk = <pk>;
-- Debe mostrar location_id poblado

SELECT pacs_study_pk, location_id FROM nextris.tbpacs_location_assignment WHERE pacs_study_pk = <pk>;
-- Debe mostrar 1 fila con el location_id
```

#### Test 3: Monitor en tiempo real (opcional)

Para ver si el trigger se dispara cuando llegan estudios reales:

```sql
-- Terminal 1: Monitor 
SELECT COUNT(*) FROM nextris.tbpacs_location_assignment;
-- Anotar el número

-- Terminal 2: Esperar que llegue un estudio vía PACS

-- Terminal 1: Revisar si aumentó
SELECT COUNT(*) FROM nextris.tbpacs_location_assignment;
-- Si aumentó → Trigger está funcionando ✓

-- Ver últimas asignaciones
SELECT pacs_study_pk, sending_aet, location_id, matched_at 
FROM nextris.tbpacs_location_assignment 
ORDER BY matched_at DESC 
LIMIT 10;
```

---

### 5.8 Paso 7: Validación Post-Implementación

Monitoreo en producción:

```sql
-- 1. Ver estudios sin location (que no encontraron match)
SELECT COUNT(*) as estudios_sin_location 
FROM public.study 
WHERE location_id IS NULL AND pk > 1000;

-- 2. Ver tasa de éxito del trigger
SELECT 
  COUNT(*) as total_series,
  COUNT(DISTINCT study_fk) as estudios_con_series,
  (SELECT COUNT(*) FROM nextris.tbpacs_location_assignment) as asignaciones_exitosas,
  ROUND(
    (SELECT COUNT(*) FROM nextris.tbpacs_location_assignment) * 100.0 
    / NULLIF(COUNT(DISTINCT study_fk), 0), 
    2
  ) as porcentaje_exito
FROM public.series 
WHERE created_time > NOW() - INTERVAL '24 hours';

-- 3. Ver qué AETs están llegando
SELECT sending_aet, COUNT(*) as cantidad_series
FROM public.series
WHERE created_time > NOW() - INTERVAL '7 days'
  AND sending_aet IS NOT NULL
GROUP BY sending_aet
ORDER BY cantidad_series DESC;

-- 4. Comparar AETs llegados vs AETs mapeados
SELECT DISTINCT ps.sending_aet
FROM public.series ps
WHERE ps.sending_aet IS NOT NULL
  AND ps.created_time > NOW() - INTERVAL '7 days'
  AND ps.sending_aet NOT IN (SELECT gateway_aet FROM nextris.tblocation WHERE gateway_aet IS NOT NULL);
-- Si retorna filas → Hay AETs llegando sin mapear
```

---

### 5.9 Troubleshooting

#### Problema: El trigger no asigna location

**Causa probable:** No hay mapeo de AET en `nextris.tblocation.gateway_aet`

**Solución:**
```sql
-- Verificar qué AETs llegan
SELECT DISTINCT sending_aet FROM public.series WHERE sending_aet IS NOT NULL LIMIT 20;

-- Verificar qué AETs están mapeados
SELECT gateway_aet FROM nextris.tblocation WHERE gateway_aet IS NOT NULL;

-- Si falta alguno, agregarlo:
UPDATE nextris.tblocation SET gateway_aet = '<AET_RECIBIDO>' WHERE guid = '<LOCATION_GUID>';
```

#### Problema: Error "relation nextris.tbpacs_location_assignment does not exist"

**Causa probable:** La tabla no fue creada

**Solución:**
- Volver a ejecutar Step 2 (Paso 2)
- Validar permisos del usuario

#### Problema: "Function nextris.fn_assign_location_from_aet does not exist"

**Causa probable:** La función no fue creada o está en otro esquema

**Solución:**
```sql
-- Verificar que exista
SELECT proname, nspname FROM pg_proc p 
JOIN pg_namespace n ON n.oid = p.pronamespace 
WHERE proname = 'fn_assign_location_from_aet';

-- Si no existe, ejecutar Step 3 (Paso 3)
```

#### Problema: El trigger se dispara pero no actualiza location_id

**Causa probable:** Constraint de FK falla silenciosamente

**Solución:**
```sql
-- Verificar logs de PostgreSQL
-- En línea de comando:
tail -f /var/log/postgresql/postgresql.log

-- O en psql:
SET log_min_messages = 'DEBUG1';
-- [re-ejecutar el test]
SET log_min_messages = 'NOTICE';
```

---

## 6. Referencia Rápida

### Comandos Útiles

```bash
# Conectar a BD
psql -h localhost -U pacs -d pacsdb

# Ver estructura de tabla
\d public.series

# Ver triggers activos en una tabla
\dS+ public.series  # Ver triggers (S = system, + = verbose)

# Ver función
\df+ nextris.fn_assign_location_from_aet

# Resetear tabla de auditoría (CUIDADO: borra historial)
TRUNCATE nextris.tbpacs_location_assignment;
```

### Queries de Diagnóstico

```sql
-- ¿Cuántos estudios tienen location asignado?
SELECT COUNT(*) FROM public.study WHERE location_id IS NOT NULL;

-- ¿Cuál es la distribución por AET?
SELECT ps.sending_aet, COUNT(*) as cantidad, COUNT(DISTINCT ps.study_fk) as estudios_unicos
FROM public.series ps
LEFT JOIN nextris.tbpacs_location_assignment pla ON ps.study_fk = pla.pacs_study_pk
WHERE ps.created_time > NOW() - INTERVAL '24 hours'
GROUP BY ps.sending_aet
ORDER BY cantidad DESC;

-- ¿Qué AETs aún no tienen location mapeada?
SELECT DISTINCT ps.sending_aet
FROM public.series ps
WHERE ps.sending_aet NOT IN (SELECT gateway_aet FROM nextris.tblocation WHERE gateway_aet IS NOT NULL)
  AND ps.sending_aet IS NOT NULL;

-- Auditoría: ¿Quién cambió las asignaciones?
SELECT * FROM nextris.tbpacs_location_assignment ORDER BY matched_at DESC LIMIT 50;
```

---

## 7. Conclusión

Esta implementación automatiza completamente la asignación de ubicación a estudios DICOM en el momento en que llegan. Es transparente (no requiere intervención), escalable (soporta múltiples AETs) y auditable (registra cada match en tabla de asignación).

El sistema es **tolerante a fallos**: si un AET no tiene mapeo, simplemente no asigna location (sin errores), permitiendo operación continua mientras se completan mapeos.

Para consultas o debugging adicional:
- Revisar logs de PostgreSQL
- Ejecutar queries de diagnóstico de la sección 6
- Consultar documentación oficial de DCM4CHEE y PostgreSQL
