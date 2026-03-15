# API Structured Reports - Implementacion (2026-03-11)

## Objetivo
Documentar los cambios implementados en backend para el modulo de Reportes Estructurados, incluyendo:
- Gestion de parser y relaciones
- Mapeo de variables
- Conceptos y criterios (reglas)
- Evaluacion de criterios

## Archivo principal
- `apps/home/controllers/structured_reports_controller.py`

## Seguridad y acceso
- Todas las rutas del modulo usan `@jwt_required()`.
- Todas validan rol con `_ensure_sysadmin()`.
- Si el usuario no es `Sysadmin`, retorna `403`.

## Estructuras de datos creadas/aseguradas
Las tablas/schemas se aseguran de forma defensiva desde el controlador:

1. `dicom_sr.rel_parser_facility`
- Relacion parser <-> facility
- Unica por `(parser_manifest_id, facility_guid)`

2. `dicom_sr.rel_parser_studytype`
- Relacion parser <-> tipo de estudio
- Unica por `(parser_manifest_id, studytype_guid)`

3. `dicom_sr.variable_definition`
- Catalogo canonico de variables

4. `dicom_sr.facility_variable_mapping`
- Mapeo de variables por parser/facility
- Con soporte de fallback generico

5. `dicom_sr.structured_criteria`
- Criterios clinicos por parser
- Regla guardada en `rule_definition JSONB`

## Endpoints implementados

### 1) Parsers
#### `GET /api/structured-reports/parsers`
Lista parsers y cantidad de asociaciones activas.

Campos relevantes de salida:
- `id`, `parser_name`, `parser_version`, `parser_family`
- `facility_associations_count`, `studytype_associations_count`, `associations_count`

### 2) Relaciones parser-facility
#### `GET /api/structured-reports/parser-facility-relations`
Lista relaciones (opcional filtro `parser_manifest_id`).

#### `POST /api/structured-reports/parser-facility-relations`
Crea/activa relacion parser-facility.

Body:
```json
{
  "parser_manifest_id": 48,
  "facility_guid": "..."
}
```

#### `DELETE /api/structured-reports/parser-facility-relations/<relation_id>`
Elimina relacion.

#### `PUT /api/structured-reports/parser-facility-relations/sync`
Sincroniza set completo de facilities para un parser.

Body:
```json
{
  "parser_manifest_id": 48,
  "facility_guids": ["...", "..."]
}
```

### 3) Relaciones parser-studytype
#### `GET /api/structured-reports/parser-studytype-relations`
Lista relaciones (opcional filtro `parser_manifest_id`).

#### `POST /api/structured-reports/parser-studytype-relations`
Crea/activa relacion parser-studytype.

#### `DELETE /api/structured-reports/parser-studytype-relations/<relation_id>`
Elimina relacion.

#### `PUT /api/structured-reports/parser-studytype-relations/sync`
Sincroniza set completo de studytypes para un parser.

Body:
```json
{
  "parser_manifest_id": 48,
  "studytype_guids": ["...", "..."]
}
```

### 4) Definiciones y mapeos de variables
#### `GET /api/structured-reports/variable-definitions?active=true|false`
Lista variables canonicas.

#### `GET /api/structured-reports/variable-mappings`
Lista mapeos con fallback controlado.

Query params requeridos:
- `parser_family`
- `facility_id`

Opcional:
- `parser_manifest_id` (si se envia, resuelve `parser_family`)

Logica de fallback soportada:
- `specific`
- `mixed_specific_generic_same_family`
- `mixed_specific_generic_parser_family`
- `generic_same_family`
- `generic_parser_family`

#### `POST /api/structured-reports/variable-mappings`
Crea mapeo especifico para facility.

Validaciones importantes:
- Parser existente
- Facility existente
- Relacion parser-facility activa (precondicion)
- Definicion canonica existente
- Al menos una regla: `concept_code_value` o `concept_code_scheme` o `dicom_path_pattern`

Body base:
```json
{
  "parser_manifest_id": 48,
  "facility_guid": "...",
  "canonical_variable_definition_id": 123,
  "concept_code_value": "11726-7",
  "concept_code_scheme": "ln",
  "dicom_path_pattern": "",
  "facility_description": "",
  "facility_name": "",
  "facility_code": "",
  "active": true
}
```

#### `PUT /api/structured-reports/variable-mappings/<mapping_id>`
Actualiza mapeo existente.

#### `DELETE /api/structured-reports/variable-mappings/<mapping_id>`
Elimina mapeo existente.

### 5) Conceptos y criterios
#### `GET /api/structured-reports/criteria`
Lista criterios.

Query params:
- `parser_manifest_id` (opcional)
- `include_inactive=true|false`

#### `GET /api/structured-reports/parser-variables?parser_manifest_id=<id>`
Devuelve variables disponibles para construir criterios (builder UI).

Salida por item:
- `variable_key` (normalizada a snake_case)
- `variable_name`
- `canonical_code`
- `unit`
- `source_type`
- `semantic_signature`

#### `POST /api/structured-reports/criteria`
Crea criterio.

Body base:
```json
{
  "parser_manifest_id": 48,
  "criterion_name": "Estenosis carotidea severa",
  "rule_definition": {
    "all": [
      {
        "variable": "ica_cca_velocity_ratio",
        "operator": ">=",
        "value": 4
      }
    ]
  },
  "output_text": "Hallazgos compatibles con estenosis severa...",
  "priority": 10,
  "active": true
}
```

Body con rama `else` opcional:
```json
{
  "parser_manifest_id": 48,
  "criterion_name": "Estenosis carotidea severa por ratio ICA/CCA",
  "rule_definition": {
    "all": [
      {
        "variable": "ica_cca_velocity_ratio",
        "operator": ">=",
        "value": 4
      }
    ],
    "else_output_text": "No se documenta estenosis severa por ratio ICA/CCA"
  },
  "output_text": "Hallazgos compatibles con estenosis severa por ratio ICA/CCA",
  "priority": 10,
  "active": true
}
```

Forma avanzada (API): `if/then/else` anidado en `rule_definition`.
```json
{
  "if": {
    "all": [
      {
        "variable": "ica_cca_velocity_ratio",
        "operator": ">=",
        "value": 4
      }
    ]
  },
  "then": "Hallazgos compatibles con estenosis severa",
  "else": {
    "if": {
      "all": [
        {
          "variable": "ica_cca_velocity_ratio",
          "operator": ">=",
          "value": 2
        }
      ]
    },
    "then": "Hallazgos compatibles con estenosis moderada",
    "else": "Sin evidencia de estenosis significativa"
  }
}
```

#### `PUT /api/structured-reports/criteria/<criterion_id>`
Actualiza criterio.

#### `DELETE /api/structured-reports/criteria/<criterion_id>`
Elimina criterio.

#### `POST /api/structured-reports/criteria/evaluate`
Evalua criterios activos de un parser contra un set de variables.

Body:
```json
{
  "parser_manifest_id": 48,
  "variables": {
    "ica_cca_velocity_ratio": 4.3
  }
}
```

Respuesta:
- `matches[]`
- `evaluated_items[]` (incluye rama `then`/`else` y `matched` por criterio)
- `composed_output` (join por salto de linea)

## Motor de reglas
Funciones principales:
- `_evaluate_leaf_condition`
- `_evaluate_rule_definition`

Operadores soportados:
- `>` / `gt`
- `>=` / `gte`
- `<` / `lt`
- `<=` / `lte`
- `==` / `=` / `eq`
- `!=` / `<>` / `ne`
- `between`
- `contains`
- `in`

Nodos logicos soportados en `rule_definition`:
- `all` (AND)
- `any` (OR)
- `not`
- `if` (condicion explicita)

Ramas de salida soportadas en `rule_definition`:
- `then`: texto o bloque condicional anidado
- `else`: texto o bloque condicional anidado
- `else_output_text`: fallback simple para rama `else` (modo builder actual)

Compatibilidad:
- `output_text` (columna legacy) se mantiene como salida por defecto de la rama `then`.
- Criterios existentes sin `else` siguen funcionando sin cambios.

## Normalizacion de variables
La funcion `_normalize_variable_key` convierte nombre libre a clave estable (snake_case simplificada), para facilitar uso uniforme desde frontend y evaluacion.

## Datos iniciales cargados (operativo)
Se cargo un lote inicial de criterios para:
- `GEVividS70CarotidSRParser`
- `parser_manifest_id = 48`

Incluye criterios de:
- Ratio ICA/CCA
- PSV ICA proximal (izq/der)
- CCA bajo flujo
- Velocidades vertebrales
- Control de calidad por correccion angular

## Formato de respuesta API
Patron general:
```json
{
  "success": true,
  "data": {},
  "count": 0,
  "message": "...",
  "error": null
}
```

Notas:
- En errores se retorna `success=false` y `error` descriptivo.
- En endpoints de creacion se retorna `201` cuando corresponde.
