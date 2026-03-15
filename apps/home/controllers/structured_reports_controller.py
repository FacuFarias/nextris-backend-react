import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from apps.home.services import DatabaseService


structured_reports_bp = Blueprint('structured_reports', __name__, url_prefix='')


def _ensure_sysadmin() -> tuple[bool, tuple | None]:
    claims = get_jwt()
    user_type = str(claims.get('user_type') or '').strip()
    if user_type != 'Sysadmin':
        return False, (jsonify({'success': False, 'error': 'Acceso denegado: requiere rol Sysadmin'}), 403)
    return True, None


def _ensure_rel_parser_facility_table() -> None:
    ensure_schema_query = """
        CREATE SCHEMA IF NOT EXISTS dicom_sr
    """
    DatabaseService.execute_query(ensure_schema_query, commit=True)

    query = """
        CREATE TABLE IF NOT EXISTS dicom_sr.rel_parser_facility (
            id SERIAL PRIMARY KEY,
            parser_manifest_id INTEGER NOT NULL,
            facility_guid VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_rel_parser_facility UNIQUE (parser_manifest_id, facility_guid),
            CONSTRAINT fk_rel_parser_facility_parser
                FOREIGN KEY (parser_manifest_id)
                REFERENCES dicom_sr.parser_manifest(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_rel_parser_facility_facility
                FOREIGN KEY (facility_guid)
                REFERENCES nextris.tbfacility(guid)
                ON DELETE CASCADE
        )
    """
    DatabaseService.execute_query(query, commit=True)


def _ensure_rel_parser_studytype_table() -> None:
    ensure_schema_query = """
        CREATE SCHEMA IF NOT EXISTS dicom_sr
    """
    DatabaseService.execute_query(ensure_schema_query, commit=True)

    query = """
        CREATE TABLE IF NOT EXISTS dicom_sr.rel_parser_studytype (
            id SERIAL PRIMARY KEY,
            parser_manifest_id INTEGER NOT NULL,
            studytype_guid VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_rel_parser_studytype UNIQUE (parser_manifest_id, studytype_guid),
            CONSTRAINT fk_rel_parser_studytype_parser
                FOREIGN KEY (parser_manifest_id)
                REFERENCES dicom_sr.parser_manifest(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_rel_parser_studytype_studytype
                FOREIGN KEY (studytype_guid)
                REFERENCES nextris.isstudytype(guid)
                ON DELETE CASCADE
        )
    """
    DatabaseService.execute_query(query, commit=True)


def _ensure_variable_mapping_tables() -> None:
    ensure_schema_query = """
        CREATE SCHEMA IF NOT EXISTS dicom_sr
    """
    DatabaseService.execute_query(ensure_schema_query, commit=True)

    variable_definition_query = """
        CREATE TABLE IF NOT EXISTS dicom_sr.variable_definition (
            id BIGSERIAL PRIMARY KEY,
            canonical_code TEXT UNIQUE NOT NULL,
            canonical_name TEXT NOT NULL,
            unit TEXT,
            value_type TEXT,
            description TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """
    DatabaseService.execute_query(variable_definition_query, commit=True)

    facility_mapping_query = """
        CREATE TABLE IF NOT EXISTS dicom_sr.facility_variable_mapping (
            id BIGSERIAL PRIMARY KEY,
            parser_family TEXT NOT NULL,
            parser_key TEXT,
            semantic_signature TEXT NOT NULL,
            source_type TEXT,
            concept_code_value TEXT,
            concept_code_scheme TEXT,
            concept_code_meaning TEXT,
            canonical_name TEXT NOT NULL,
            canonical_code TEXT,
            unit TEXT,
            facility_id VARCHAR(45) NULL,
            facility_name TEXT,
            facility_code TEXT,
            base_variable_id BIGINT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            facility_guid VARCHAR(100)
        )
    """
    DatabaseService.execute_query(facility_mapping_query, commit=True)

    migration_statements = [
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS facility_guid VARCHAR(100)",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS parser_family TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS parser_key TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS semantic_signature TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS source_type TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS concept_code_value TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS concept_code_scheme TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS concept_code_meaning TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS canonical_name TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS canonical_code TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS unit TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS facility_name TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS facility_code TEXT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS base_variable_id BIGINT",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE dicom_sr.facility_variable_mapping ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
    ]

    for statement in migration_statements:
        DatabaseService.execute_query(statement, commit=True)


def _ensure_structured_criteria_table() -> None:
    ensure_schema_query = """
        CREATE SCHEMA IF NOT EXISTS dicom_sr
    """
    DatabaseService.execute_query(ensure_schema_query, commit=True)

    query = """
        CREATE TABLE IF NOT EXISTS dicom_sr.structured_criteria (
            id BIGSERIAL PRIMARY KEY,
            parser_manifest_id INTEGER NOT NULL,
            criterion_name TEXT NOT NULL,
            rule_definition JSONB NOT NULL,
            output_text TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_structured_criteria_parser
                FOREIGN KEY (parser_manifest_id)
                REFERENCES dicom_sr.parser_manifest(id)
                ON DELETE CASCADE
        )
    """
    DatabaseService.execute_query(query, commit=True)


def _safe_numeric(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _normalize_variable_key(value: str) -> str:
    key = str(value or '').strip().lower()
    if not key:
        return ''

    normalized_chars = []
    last_underscore = False
    for char in key:
        if char.isalnum():
            normalized_chars.append(char)
            last_underscore = False
            continue
        if not last_underscore:
            normalized_chars.append('_')
            last_underscore = True

    normalized = ''.join(normalized_chars).strip('_')
    return normalized


def _evaluate_leaf_condition(condition: dict, variables: dict) -> bool:
    variable_name = str(
        condition.get('variable')
        or condition.get('variable_key')
        or condition.get('variable_label')
        or ''
    ).strip()
    operator = str(condition.get('operator') or '').strip().lower()
    expected_value = condition.get('value')
    expected_value_to = condition.get('value_to')

    if not variable_name or not operator:
        return False

    if variable_name not in variables:
        return False

    candidate_value = variables.get(variable_name)
    candidate_numeric = _safe_numeric(candidate_value)
    expected_numeric = _safe_numeric(expected_value)
    expected_numeric_to = _safe_numeric(expected_value_to)

    if operator in ('>', 'gt'):
        return candidate_numeric is not None and expected_numeric is not None and candidate_numeric > expected_numeric
    if operator in ('>=', 'gte'):
        return candidate_numeric is not None and expected_numeric is not None and candidate_numeric >= expected_numeric
    if operator in ('<', 'lt'):
        return candidate_numeric is not None and expected_numeric is not None and candidate_numeric < expected_numeric
    if operator in ('<=', 'lte'):
        return candidate_numeric is not None and expected_numeric is not None and candidate_numeric <= expected_numeric
    if operator in ('==', '=', 'eq'):
        return str(candidate_value) == str(expected_value)
    if operator in ('!=', '<>', 'ne'):
        return str(candidate_value) != str(expected_value)
    if operator == 'between':
        return (
            candidate_numeric is not None
            and expected_numeric is not None
            and expected_numeric_to is not None
            and expected_numeric <= candidate_numeric <= expected_numeric_to
        )
    if operator == 'contains':
        return str(expected_value).lower() in str(candidate_value).lower()
    if operator == 'in':
        if isinstance(expected_value, list):
            return str(candidate_value) in {str(item) for item in expected_value}
        return False

    return False


def _evaluate_rule_definition(rule_definition: dict, variables: dict) -> bool:
    if not isinstance(rule_definition, dict):
        return False

    conditional_if = rule_definition.get('if')
    if isinstance(conditional_if, dict):
        return _evaluate_rule_definition(conditional_if, variables)

    all_conditions = rule_definition.get('all')
    any_conditions = rule_definition.get('any')
    not_condition = rule_definition.get('not')

    if all_conditions is not None:
        if not isinstance(all_conditions, list) or len(all_conditions) == 0:
            return False
        return all(_evaluate_rule_definition(condition, variables) for condition in all_conditions)

    if any_conditions is not None:
        if not isinstance(any_conditions, list) or len(any_conditions) == 0:
            return False
        return any(_evaluate_rule_definition(condition, variables) for condition in any_conditions)

    if not_condition is not None:
        return not _evaluate_rule_definition(not_condition, variables)

    return _evaluate_leaf_condition(rule_definition, variables)


def _resolve_branch_output_text(branch_payload, variables: dict, fallback_text: str) -> str:
    if isinstance(branch_payload, str):
        return branch_payload.strip()

    if isinstance(branch_payload, dict):
        nested = _evaluate_rule_outcome(branch_payload, variables, fallback_text)
        return str(nested.get('output_text') or '').strip()

    return str(fallback_text or '').strip()


def _evaluate_rule_outcome(rule_definition: dict, variables: dict, fallback_then_text: str) -> dict:
    then_fallback = str(fallback_then_text or '').strip()

    if not isinstance(rule_definition, dict):
        return {
            'matched': False,
            'branch': 'none',
            'output_text': then_fallback,
        }

    matched = _evaluate_rule_definition(rule_definition, variables)
    then_payload = rule_definition.get('then')
    else_payload = rule_definition.get('else')
    else_fallback = str(rule_definition.get('else_output_text') or '').strip()

    if matched:
        output_text = _resolve_branch_output_text(then_payload, variables, then_fallback)
        return {
            'matched': True,
            'branch': 'then' if output_text else 'none',
            'output_text': output_text,
        }

    output_text = _resolve_branch_output_text(else_payload, variables, else_fallback)
    return {
        'matched': False,
        'branch': 'else' if output_text else 'none',
        'output_text': output_text,
    }


def _get_parser_and_key(parser_manifest_id: int):
    parser_row = DatabaseService.execute_query(
        """
        SELECT id, parser_name, parser_version, parser_family
        FROM dicom_sr.parser_manifest
        WHERE id = %s
        LIMIT 1
        """,
        (parser_manifest_id,),
        fetch_one=True,
    )
    if not parser_row:
        return None

    parser_name = str(parser_row[1] or '').strip()
    parser_version = str(parser_row[2] or '').strip()
    parser_family = str(parser_row[3] or '').strip()
    parser_key = f"{parser_name}:{parser_version}" if parser_version else parser_name

    return {
        'id': int(parser_row[0]),
        'parser_name': parser_name,
        'parser_version': parser_version,
        'parser_family': parser_family,
        'parser_key': parser_key,
    }


def _get_facility_by_guid(facility_guid: str):
    return DatabaseService.execute_query(
        """
        SELECT guid, name, code
        FROM nextris.tbfacility
        WHERE guid = %s
        LIMIT 1
        """,
        (facility_guid,),
        fetch_one=True,
    )


def _get_mapping_source_table() -> str:
    row = DatabaseService.execute_query(
        """
        SELECT to_regclass('dicom_sr.parser_mappable_variable'), to_regclass('dicom_sr.facility_variable_mapping')
        """,
        fetch_one=True,
    )

    if row and row[0]:
        return 'dicom_sr.parser_mappable_variable'
    return 'dicom_sr.facility_variable_mapping'


def _source_type_label(source_type: str) -> str:
    source = str(source_type or '').strip().lower()
    labels = {
        'standard_numeric_contextual': 'Estandar contextual',
        'standard_numeric': 'Estandar numerico',
        'private_99gems': 'Privado GE 99GEMS',
    }
    return labels.get(source, source or 'General')


def _slug_node_part(value: str) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return 'na'

    slug = []
    last_dash = False
    for char in text:
        if char.isalnum():
            slug.append(char)
            last_dash = False
            continue
        if not last_dash:
            slug.append('-')
            last_dash = True

    return ''.join(slug).strip('-') or 'na'


def _build_variable_segments(variable_name: str) -> list[str]:
    name = str(variable_name or '').strip()
    if not name:
        return ['Sin nombre']

    dash_parts = [part.strip() for part in name.split('-') if part.strip()]
    if len(dash_parts) >= 2:
        return dash_parts

    pipe_parts = [part.strip() for part in name.split('|') if part.strip()]
    if len(pipe_parts) >= 2:
        return pipe_parts

    return [name]


def _list_parser_variable_items(parser_manifest_id: int, search_term: str = '', source_type_filter: str = '') -> list[dict]:
    parser_info = _get_parser_and_key(int(parser_manifest_id))
    if not parser_info:
        return []

    source_table = _get_mapping_source_table()
    rows = DatabaseService.execute_query(
        f"""
        SELECT
            canonical_name,
            canonical_code,
            unit,
            concept_code_meaning,
            source_type,
            semantic_signature
        FROM {source_table}
        WHERE active = TRUE
          AND parser_family = %s
          AND (%s = '' OR LOWER(COALESCE(source_type, '')) = LOWER(%s))
        ORDER BY canonical_name ASC, canonical_code ASC
        """,
        (parser_info['parser_family'], str(source_type_filter or ''), str(source_type_filter or '')),
    )

    search = str(search_term or '').strip().lower()

    seen_keys = set()
    items = []
    for row in rows:
        canonical_name = str(row[0] or '').strip()
        canonical_code = str(row[1] or '').strip()
        unit = str(row[2] or '').strip()
        concept_code_meaning = str(row[3] or '').strip()
        source_type = str(row[4] or '').strip()
        semantic_signature = str(row[5] or '').strip()

        variable_name = canonical_name or concept_code_meaning or canonical_code
        variable_key = _normalize_variable_key(variable_name)
        if not variable_key:
            continue

        if search:
            haystack = ' '.join([
                variable_name.lower(),
                variable_key.lower(),
                canonical_code.lower(),
                semantic_signature.lower(),
                source_type.lower(),
            ])
            if search not in haystack:
                continue

        dedupe_key = f"{variable_key}|{semantic_signature or canonical_code or variable_name}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        segments = [_source_type_label(source_type)] + _build_variable_segments(variable_name)
        items.append({
            'variable_key': variable_key,
            'variable_name': variable_name,
            'canonical_code': canonical_code or None,
            'unit': unit or None,
            'source_type': source_type or None,
            'semantic_signature': semantic_signature or None,
            'segments': segments,
        })

    return items


def _build_variable_tree(items: list[dict]) -> list[dict]:
    roots: list[dict] = []
    index: dict[str, dict] = {}

    def ensure_group(parent_children: list[dict], path_parts: list[str], label: str) -> dict:
        node_id = '/'.join(path_parts)
        if node_id in index:
            return index[node_id]

        node = {
            'id': node_id,
            'label': label,
            'type': 'group',
            'path': ' > '.join(path_parts),
            'children': [],
            'children_count': 0,
            'metadata': None,
        }
        parent_children.append(node)
        index[node_id] = node
        return node

    for item in items:
        segments = item.get('segments') or []
        if not segments:
            continue

        parent_children = roots
        node_path_parts: list[str] = []

        for segment in segments[:-1]:
            node_path_parts.append(f"grp:{_slug_node_part(segment)}")
            group_node = ensure_group(parent_children, node_path_parts, segment)
            parent_children = group_node['children']

        leaf_label = str(segments[-1])
        leaf_id = '/'.join(node_path_parts + [f"var:{_slug_node_part(item['variable_key'])}"])
        if leaf_id in index:
            continue

        leaf_node = {
            'id': leaf_id,
            'label': leaf_label,
            'type': 'variable',
            'path': ' > '.join(segments),
            'children': [],
            'children_count': 0,
            'metadata': {
                'variable_key': item['variable_key'],
                'variable_name': item['variable_name'],
                'canonical_code': item['canonical_code'],
                'unit': item['unit'],
                'source_type': item['source_type'],
                'semantic_signature': item['semantic_signature'],
            },
        }
        parent_children.append(leaf_node)
        index[leaf_id] = leaf_node

    def finalize(nodes: list[dict]) -> None:
        nodes.sort(key=lambda node: (0 if node['type'] == 'group' else 1, str(node['label']).lower()))
        for node in nodes:
            if node['type'] == 'group':
                finalize(node['children'])
                node['children_count'] = len(node['children'])

    finalize(roots)
    return roots


def _find_node_by_id(nodes: list[dict], node_id: str):
    for node in nodes:
        if node.get('id') == node_id:
            return node
        children = node.get('children') or []
        if children:
            found = _find_node_by_id(children, node_id)
            if found:
                return found
    return None


def _row_to_criterion(row) -> dict:
    return {
        'id': int(row[0]),
        'parser_manifest_id': int(row[1]),
        'parser_name': row[2],
        'parser_version': row[3],
        'parser_family': row[4],
        'criterion_name': row[5],
        'rule_definition': row[6],
        'output_text': row[7],
        'priority': int(row[8] or 100),
        'active': bool(row[9]),
        'created_at': row[10].isoformat() if row[10] else None,
        'updated_at': row[11].isoformat() if row[11] else None,
    }

@structured_reports_bp.route('/api/structured-reports/parsers', methods=['GET'])
@jwt_required()
def list_structured_report_parsers():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_facility_table()
        _ensure_rel_parser_studytype_table()

        query = """
            SELECT
                pm.id,
                pm.parser_name,
                pm.parser_version,
                pm.parser_family,
                pm.compatibility_level,
                pm.is_active,
                pm.supported_manufacturers,
                pm.supported_institutions,
                pm.supported_models,
                pm.supported_sop_class_uids,
                pm.created_at,
                pm.updated_at,
                COALESCE(rel_facility.associations_count, 0) AS facility_associations_count,
                COALESCE(rel_studytype.associations_count, 0) AS studytype_associations_count,
                COALESCE(rel_facility.associations_count, 0) + COALESCE(rel_studytype.associations_count, 0) AS associations_count
            FROM dicom_sr.parser_manifest pm
            LEFT JOIN (
                SELECT parser_manifest_id, COUNT(*) AS associations_count
                FROM dicom_sr.rel_parser_facility
                WHERE is_active = TRUE
                GROUP BY parser_manifest_id
            ) rel_facility ON rel_facility.parser_manifest_id = pm.id
            LEFT JOIN (
                SELECT parser_manifest_id, COUNT(*) AS associations_count
                FROM dicom_sr.rel_parser_studytype
                WHERE is_active = TRUE
                GROUP BY parser_manifest_id
            ) rel_studytype ON rel_studytype.parser_manifest_id = pm.id
            ORDER BY pm.updated_at DESC, pm.id DESC
        """
        rows = DatabaseService.execute_query(query)

        parsers = []
        for row in rows:
            parsers.append({
                'id': row[0],
                'parser_name': row[1],
                'parser_version': row[2],
                'parser_family': row[3],
                'compatibility_level': row[4],
                'is_active': bool(row[5]),
                'supported_manufacturers': row[6] or [],
                'supported_institutions': row[7] or [],
                'supported_models': row[8] or [],
                'supported_sop_class_uids': row[9] or [],
                'created_at': row[10].isoformat() if row[10] else None,
                'updated_at': row[11].isoformat() if row[11] else None,
                'facility_associations_count': int(row[12] or 0),
                'studytype_associations_count': int(row[13] or 0),
                'associations_count': int(row[14] or 0),
            })

        return jsonify({
            'success': True,
            'data': parsers,
            'count': len(parsers),
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-facility-relations', methods=['GET'])
@jwt_required()
def list_parser_facility_relations():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_facility_table()

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)

        base_query = """
            SELECT
                rel.id,
                rel.parser_manifest_id,
                pm.parser_name,
                pm.parser_version,
                rel.facility_guid,
                f.name AS facility_name,
                f.code AS facility_code,
                rel.is_active,
                rel.created_at,
                rel.updated_at
            FROM dicom_sr.rel_parser_facility rel
            INNER JOIN dicom_sr.parser_manifest pm ON pm.id = rel.parser_manifest_id
            INNER JOIN nextris.tbfacility f ON f.guid = rel.facility_guid
        """

        params = None
        if parser_manifest_id:
            base_query += " WHERE rel.parser_manifest_id = %s"
            params = (parser_manifest_id,)

        base_query += " ORDER BY rel.updated_at DESC, rel.id DESC"

        rows = DatabaseService.execute_query(base_query, params)
        relations = []
        for row in rows:
            relations.append({
                'id': row[0],
                'parser_manifest_id': row[1],
                'parser_name': row[2],
                'parser_version': row[3],
                'facility_guid': row[4],
                'facility_name': row[5],
                'facility_code': row[6],
                'is_active': bool(row[7]),
                'created_at': row[8].isoformat() if row[8] else None,
                'updated_at': row[9].isoformat() if row[9] else None,
            })

        return jsonify({'success': True, 'data': relations, 'count': len(relations)}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-facility-relations', methods=['POST'])
@jwt_required()
def create_parser_facility_relation():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_facility_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        facility_guid = payload.get('facility_guid')

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        if not facility_guid:
            return jsonify({'success': False, 'error': 'facility_guid es requerido'}), 400

        parser_exists = DatabaseService.execute_query(
            "SELECT 1 FROM dicom_sr.parser_manifest WHERE id = %s LIMIT 1",
            (parser_manifest_id,),
            fetch_one=True,
        )
        if not parser_exists:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        facility_exists = DatabaseService.execute_query(
            "SELECT 1 FROM nextris.tbfacility WHERE guid = %s LIMIT 1",
            (facility_guid,),
            fetch_one=True,
        )
        if not facility_exists:
            return jsonify({'success': False, 'error': 'Facility no encontrada'}), 404

        insert_query = """
            INSERT INTO dicom_sr.rel_parser_facility (parser_manifest_id, facility_guid, is_active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (parser_manifest_id, facility_guid)
            DO UPDATE SET is_active = TRUE, updated_at = NOW()
            RETURNING id
        """
        inserted = DatabaseService.execute_query(insert_query, (parser_manifest_id, facility_guid), fetch_one=True, commit=True)

        return jsonify({
            'success': True,
            'message': 'Asociación parser-facility guardada correctamente',
            'data': {
                'id': inserted[0] if inserted else None,
                'parser_manifest_id': int(parser_manifest_id),
                'facility_guid': facility_guid,
            },
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-facility-relations/<int:relation_id>', methods=['DELETE'])
@jwt_required()
def delete_parser_facility_relation(relation_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_facility_table()

        existing = DatabaseService.execute_query(
            "SELECT id FROM dicom_sr.rel_parser_facility WHERE id = %s LIMIT 1",
            (relation_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Asociación no encontrada'}), 404

        DatabaseService.execute_query("DELETE FROM dicom_sr.rel_parser_facility WHERE id = %s", (relation_id,), commit=True)

        return jsonify({'success': True, 'message': 'Asociación eliminada correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-facility-relations/sync', methods=['PUT'])
@jwt_required()
def sync_parser_facility_relations():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_facility_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        facility_guids = payload.get('facility_guids')

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        if facility_guids is None:
            return jsonify({'success': False, 'error': 'facility_guids es requerido'}), 400

        if not isinstance(facility_guids, list):
            return jsonify({'success': False, 'error': 'facility_guids debe ser una lista'}), 400

        parser_exists = DatabaseService.execute_query(
            "SELECT 1 FROM dicom_sr.parser_manifest WHERE id = %s LIMIT 1",
            (parser_manifest_id,),
            fetch_one=True,
        )
        if not parser_exists:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        normalized_facilities = [str(guid).strip() for guid in facility_guids if str(guid).strip()]

        if normalized_facilities:
            existing_rows = DatabaseService.execute_query(
                "SELECT guid FROM nextris.tbfacility WHERE guid = ANY(%s)",
                (normalized_facilities,),
            )
            existing_guids = {row[0] for row in existing_rows}
            missing_guids = [guid for guid in normalized_facilities if guid not in existing_guids]
            if missing_guids:
                return jsonify({'success': False, 'error': f'Facilities no encontradas: {", ".join(missing_guids)}'}), 404

            DatabaseService.execute_query(
                "DELETE FROM dicom_sr.rel_parser_facility WHERE parser_manifest_id = %s AND NOT (facility_guid = ANY(%s))",
                (parser_manifest_id, normalized_facilities),
                commit=True,
            )

            for facility_guid in normalized_facilities:
                DatabaseService.execute_query(
                    """
                    INSERT INTO dicom_sr.rel_parser_facility (parser_manifest_id, facility_guid, is_active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (parser_manifest_id, facility_guid)
                    DO UPDATE SET is_active = TRUE, updated_at = NOW()
                    """,
                    (parser_manifest_id, facility_guid),
                    commit=True,
                )
        else:
            DatabaseService.execute_query(
                "DELETE FROM dicom_sr.rel_parser_facility WHERE parser_manifest_id = %s",
                (parser_manifest_id,),
                commit=True,
            )

        return jsonify({'success': True, 'message': 'Relaciones parser-facility actualizadas correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-studytype-relations', methods=['GET'])
@jwt_required()
def list_parser_studytype_relations():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_studytype_table()

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)

        base_query = """
            SELECT
                rel.id,
                rel.parser_manifest_id,
                pm.parser_name,
                pm.parser_version,
                rel.studytype_guid,
                st.description AS studytype_description,
                st.code AS studytype_code,
                rel.is_active,
                rel.created_at,
                rel.updated_at
            FROM dicom_sr.rel_parser_studytype rel
            INNER JOIN dicom_sr.parser_manifest pm ON pm.id = rel.parser_manifest_id
            INNER JOIN nextris.isstudytype st ON st.guid = rel.studytype_guid
        """

        params = None
        if parser_manifest_id:
            base_query += " WHERE rel.parser_manifest_id = %s"
            params = (parser_manifest_id,)

        base_query += " ORDER BY rel.updated_at DESC, rel.id DESC"

        rows = DatabaseService.execute_query(base_query, params)
        relations = []
        for row in rows:
            relations.append({
                'id': row[0],
                'parser_manifest_id': row[1],
                'parser_name': row[2],
                'parser_version': row[3],
                'studytype_guid': row[4],
                'studytype_description': row[5],
                'studytype_code': row[6],
                'is_active': bool(row[7]),
                'created_at': row[8].isoformat() if row[8] else None,
                'updated_at': row[9].isoformat() if row[9] else None,
            })

        return jsonify({'success': True, 'data': relations, 'count': len(relations)}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-studytype-relations', methods=['POST'])
@jwt_required()
def create_parser_studytype_relation():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_studytype_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        studytype_guid = payload.get('studytype_guid')

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        if not studytype_guid:
            return jsonify({'success': False, 'error': 'studytype_guid es requerido'}), 400

        parser_exists = DatabaseService.execute_query(
            "SELECT 1 FROM dicom_sr.parser_manifest WHERE id = %s LIMIT 1",
            (parser_manifest_id,),
            fetch_one=True,
        )
        if not parser_exists:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        studytype_exists = DatabaseService.execute_query(
            "SELECT 1 FROM nextris.isstudytype WHERE guid = %s LIMIT 1",
            (studytype_guid,),
            fetch_one=True,
        )
        if not studytype_exists:
            return jsonify({'success': False, 'error': 'Tipo de estudio no encontrado'}), 404

        insert_query = """
            INSERT INTO dicom_sr.rel_parser_studytype (parser_manifest_id, studytype_guid, is_active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (parser_manifest_id, studytype_guid)
            DO UPDATE SET is_active = TRUE, updated_at = NOW()
            RETURNING id
        """
        inserted = DatabaseService.execute_query(insert_query, (parser_manifest_id, studytype_guid), fetch_one=True, commit=True)

        return jsonify({
            'success': True,
            'message': 'Asociación parser-studytype guardada correctamente',
            'data': {
                'id': inserted[0] if inserted else None,
                'parser_manifest_id': int(parser_manifest_id),
                'studytype_guid': studytype_guid,
            },
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-studytype-relations/<int:relation_id>', methods=['DELETE'])
@jwt_required()
def delete_parser_studytype_relation(relation_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_studytype_table()

        existing = DatabaseService.execute_query(
            "SELECT id FROM dicom_sr.rel_parser_studytype WHERE id = %s LIMIT 1",
            (relation_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Asociación no encontrada'}), 404

        DatabaseService.execute_query("DELETE FROM dicom_sr.rel_parser_studytype WHERE id = %s", (relation_id,), commit=True)

        return jsonify({'success': True, 'message': 'Asociación eliminada correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-studytype-relations/sync', methods=['PUT'])
@jwt_required()
def sync_parser_studytype_relations():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_rel_parser_studytype_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        studytype_guids = payload.get('studytype_guids')

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        if studytype_guids is None:
            return jsonify({'success': False, 'error': 'studytype_guids es requerido'}), 400

        if not isinstance(studytype_guids, list):
            return jsonify({'success': False, 'error': 'studytype_guids debe ser una lista'}), 400

        parser_exists = DatabaseService.execute_query(
            "SELECT 1 FROM dicom_sr.parser_manifest WHERE id = %s LIMIT 1",
            (parser_manifest_id,),
            fetch_one=True,
        )
        if not parser_exists:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        normalized_studytypes = [str(guid).strip() for guid in studytype_guids if str(guid).strip()]

        if normalized_studytypes:
            existing_rows = DatabaseService.execute_query(
                "SELECT guid FROM nextris.isstudytype WHERE guid = ANY(%s)",
                (normalized_studytypes,),
            )
            existing_guids = {row[0] for row in existing_rows}
            missing_guids = [guid for guid in normalized_studytypes if guid not in existing_guids]
            if missing_guids:
                return jsonify({'success': False, 'error': f'Tipos de estudio no encontrados: {", ".join(missing_guids)}'}), 404

            DatabaseService.execute_query(
                "DELETE FROM dicom_sr.rel_parser_studytype WHERE parser_manifest_id = %s AND NOT (studytype_guid = ANY(%s))",
                (parser_manifest_id, normalized_studytypes),
                commit=True,
            )

            for studytype_guid in normalized_studytypes:
                DatabaseService.execute_query(
                    """
                    INSERT INTO dicom_sr.rel_parser_studytype (parser_manifest_id, studytype_guid, is_active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (parser_manifest_id, studytype_guid)
                    DO UPDATE SET is_active = TRUE, updated_at = NOW()
                    """,
                    (parser_manifest_id, studytype_guid),
                    commit=True,
                )
        else:
            DatabaseService.execute_query(
                "DELETE FROM dicom_sr.rel_parser_studytype WHERE parser_manifest_id = %s",
                (parser_manifest_id,),
                commit=True,
            )

        return jsonify({'success': True, 'message': 'Relaciones parser-studytype actualizadas correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variable-definitions', methods=['GET'])
@jwt_required()
def list_variable_definitions():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        active_param = str(request.args.get('active', 'true')).strip().lower()
        active_only = active_param not in ('false', '0', 'no')

        query = """
            SELECT id, canonical_code, canonical_name, unit, value_type, description, active, created_at
            FROM dicom_sr.variable_definition
        """
        params = None
        if active_only:
            query += " WHERE active = TRUE"
        query += " ORDER BY canonical_code ASC"

        rows = DatabaseService.execute_query(query, params)

        items = []
        for row in rows:
            items.append({
                'id': int(row[0]),
                'canonical_code': row[1],
                'canonical_name': row[2],
                'unit': row[3],
                'value_type': row[4],
                'description': row[5],
                'active': bool(row[6]),
                'created_at': row[7].isoformat() if row[7] else None,
            })

        return jsonify({'success': True, 'data': items, 'count': len(items)}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variable-mappings', methods=['GET'])
@jwt_required()
def list_variable_mappings():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        parser_family = (request.args.get('parser_family') or '').strip()
        parser_manifest_id = request.args.get('parser_manifest_id', type=int)
        facility_id = (request.args.get('facility_id') or '').strip()

        parser_info = None
        if parser_manifest_id:
            parser_info = _get_parser_and_key(parser_manifest_id)
            if not parser_info:
                return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404
            if not parser_family:
                parser_family = parser_info['parser_family']

        if not parser_family:
            return jsonify({'success': False, 'error': 'parser_family es requerido'}), 400
        if not facility_id:
            return jsonify({'success': False, 'error': 'facility_id es requerido'}), 400

        source_table = _get_mapping_source_table()

        select_clause = f"""
            SELECT
                id,
                parser_family,
                parser_key,
                semantic_signature,
                source_type,
                concept_code_value,
                concept_code_scheme,
                concept_code_meaning,
                canonical_name,
                canonical_code,
                unit,
                facility_id,
                facility_name,
                facility_code,
                base_variable_id,
                active,
                created_at,
                updated_at
            FROM {source_table}
            WHERE active = TRUE
              AND parser_family = %s
              AND {{facility_filter}}
            ORDER BY updated_at DESC NULLS LAST, created_at DESC, id DESC
        """

        def _fetch_rows(target_parser_family: str, target_facility_id: str | None):
            if target_facility_id is None:
                query = select_clause.replace('{facility_filter}', 'facility_id IS NULL')
                return DatabaseService.execute_query(query, (target_parser_family,))

            query = select_clause.replace('{facility_filter}', 'facility_id = %s')
            return DatabaseService.execute_query(query, (target_parser_family, target_facility_id))

        def _row_signature(row) -> str:
            semantic_signature = str(row[3] or '').strip()
            if semantic_signature:
                return semantic_signature
            parser_key = str(row[2] or '').strip()
            if parser_key:
                return f"parser_key::{parser_key}"
            return f"id::{row[0]}"

        specific_rows = _fetch_rows(parser_family, facility_id)
        generic_same_family_rows = _fetch_rows(parser_family, None)

        selected_rows = []
        fallback_mode = 'specific'
        fallback_parser_family = parser_family

        if specific_rows:
            selected_rows.extend([(row, 'specific', parser_family) for row in specific_rows])
            specific_signatures = {_row_signature(row) for row in specific_rows}

            generic_added = 0
            for row in generic_same_family_rows:
                signature = _row_signature(row)
                if signature in specific_signatures:
                    continue
                selected_rows.append((row, 'generic_same_family', parser_family))
                specific_signatures.add(signature)
                generic_added += 1

            if generic_added > 0:
                fallback_mode = 'mixed_specific_generic_same_family'
            elif parser_family != 'generic_sr':
                generic_parser_family_rows = _fetch_rows('generic_sr', None)
                generic_family_added = 0
                for row in generic_parser_family_rows:
                    signature = _row_signature(row)
                    if signature in specific_signatures:
                        continue
                    selected_rows.append((row, 'generic_parser_family', 'generic_sr'))
                    specific_signatures.add(signature)
                    generic_family_added += 1

                if generic_family_added > 0:
                    fallback_mode = 'mixed_specific_generic_parser_family'
                    fallback_parser_family = 'generic_sr'
        else:
            if generic_same_family_rows:
                fallback_mode = 'generic_same_family'
                selected_rows.extend([(row, 'generic_same_family', parser_family) for row in generic_same_family_rows])
            elif parser_family != 'generic_sr':
                fallback_mode = 'generic_parser_family'
                fallback_parser_family = 'generic_sr'
                generic_parser_family_rows = _fetch_rows('generic_sr', None)
                selected_rows.extend([(row, 'generic_parser_family', 'generic_sr') for row in generic_parser_family_rows])

        items = []
        for row, row_scope, row_effective_parser_family in selected_rows:
            is_generic_row = row_scope in ('generic_same_family', 'generic_parser_family')
            display_facility_name = row[12] if row[12] else ('Genérico' if is_generic_row else None)
            items.append({
                'id': int(row[0]),
                'parser_family': row[1],
                'source_parser_family': row[1],
                'parser_key': row[2],
                'semantic_signature': row[3],
                'source_type': row[4],
                'concept_code_value': row[5],
                'concept_code_scheme': row[6],
                'concept_code_meaning': row[7],
                'canonical_name': row[8],
                'canonical_code': row[9],
                'unit': row[10],
                'facility_id': row[11],
                'facility_name': display_facility_name,
                'facility_code': row[13],
                'base_variable_id': row[14],
                'active': bool(row[15]),
                'created_at': row[16].isoformat() if row[16] else None,
                'updated_at': row[17].isoformat() if row[17] else None,
                'mapping_scope': row_scope,
                'requested_parser_family': parser_family,
                'effective_parser_family': row_effective_parser_family,
            })

        return jsonify({
            'success': True,
            'data': items,
            'count': len(items),
            'fallback_mode': fallback_mode,
            'source_table': source_table,
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variable-mappings', methods=['POST'])
@jwt_required()
def create_variable_mapping():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()
        _ensure_rel_parser_facility_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        facility_guid = str(payload.get('facility_guid') or '').strip()
        canonical_variable_definition_id = payload.get('canonical_variable_definition_id')

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400
        if not facility_guid:
            return jsonify({'success': False, 'error': 'facility_guid es requerido'}), 400
        if not canonical_variable_definition_id:
            return jsonify({'success': False, 'error': 'canonical_variable_definition_id es requerido'}), 400

        parser_info = _get_parser_and_key(int(parser_manifest_id))
        if not parser_info:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        facility_row = _get_facility_by_guid(facility_guid)
        if not facility_row:
            return jsonify({'success': False, 'error': 'Facility no encontrada'}), 404

        relation_exists = DatabaseService.execute_query(
            """
            SELECT 1
            FROM dicom_sr.rel_parser_facility
            WHERE parser_manifest_id = %s
              AND facility_guid = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (int(parser_manifest_id), facility_guid),
            fetch_one=True,
        )
        if not relation_exists:
            return jsonify({
                'success': False,
                'error': 'Debe asociar primero el parser con la facility en Rel Parser Facility',
            }), 400

        definition_row = DatabaseService.execute_query(
            "SELECT id, canonical_code, canonical_name, unit FROM dicom_sr.variable_definition WHERE id = %s LIMIT 1",
            (int(canonical_variable_definition_id),),
            fetch_one=True,
        )
        if not definition_row:
            return jsonify({'success': False, 'error': 'Definición canónica no encontrada'}), 404

        concept_code_value = payload.get('concept_code_value')
        concept_code_scheme = payload.get('concept_code_scheme')
        dicom_path_pattern = payload.get('dicom_path_pattern')
        facility_description = payload.get('facility_description')
        facility_name = (payload.get('facility_name') or '').strip()
        facility_code = (payload.get('facility_code') or '').strip()
        active = bool(payload.get('active', True))

        if not (concept_code_value or concept_code_scheme or dicom_path_pattern):
            return jsonify({
                'success': False,
                'error': 'Debe ingresar al menos una regla: concept_code_value, concept_code_scheme o dicom_path_pattern',
            }), 400

        semantic_signature = (
            f"{parser_info['parser_family']}::"
            f"{(concept_code_scheme or '').strip()}::"
            f"{(concept_code_value or '').strip()}::"
            f"{(dicom_path_pattern or '').strip()}::"
            f"{(definition_row[1] or '').strip()}"
        )

        insert_query = """
            INSERT INTO dicom_sr.facility_variable_mapping (
                parser_family,
                facility_id,
                parser_key,
                semantic_signature,
                source_type,
                concept_code_value,
                concept_code_scheme,
                concept_code_meaning,
                canonical_name,
                canonical_code,
                unit,
                facility_name,
                facility_code,
                base_variable_id,
                active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        inserted = DatabaseService.execute_query(
            insert_query,
            (
                parser_info['parser_family'],
                str(facility_guid),
                parser_info['parser_key'],
                semantic_signature,
                'manual',
                concept_code_value,
                concept_code_scheme,
                facility_description or definition_row[2],
                definition_row[2],
                definition_row[1],
                definition_row[3],
                facility_name or facility_row[1],
                facility_code or facility_row[2],
                None,
                active,
            ),
            fetch_one=True,
            commit=True,
        )

        return jsonify({
            'success': True,
            'message': 'Mapeo de variable creado correctamente',
            'data': {
                'id': int(inserted[0]) if inserted else None,
            },
        }), 201
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variable-mappings/<int:mapping_id>', methods=['DELETE'])
@jwt_required()
def delete_variable_mapping(mapping_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        existing = DatabaseService.execute_query(
            "SELECT id FROM dicom_sr.facility_variable_mapping WHERE id = %s LIMIT 1",
            (mapping_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Mapeo no encontrado'}), 404

        DatabaseService.execute_query(
            "DELETE FROM dicom_sr.facility_variable_mapping WHERE id = %s",
            (mapping_id,),
            commit=True,
        )

        return jsonify({'success': True, 'message': 'Mapeo eliminado correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variable-mappings/<int:mapping_id>', methods=['PUT'])
@jwt_required()
def update_variable_mapping(mapping_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        existing = DatabaseService.execute_query(
            """
            SELECT id, parser_family, parser_key, facility_id
            FROM dicom_sr.facility_variable_mapping
            WHERE id = %s
            LIMIT 1
            """,
            (mapping_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Mapeo no encontrado'}), 404

        payload = request.get_json(silent=True) or {}
        canonical_variable_definition_id = payload.get('canonical_variable_definition_id')
        concept_code_value = payload.get('concept_code_value')
        concept_code_scheme = payload.get('concept_code_scheme')
        dicom_path_pattern = payload.get('dicom_path_pattern')
        facility_description = payload.get('facility_description')
        facility_name = (payload.get('facility_name') or '').strip()
        facility_code = (payload.get('facility_code') or '').strip()
        active = bool(payload.get('active', True))

        if not canonical_variable_definition_id:
            return jsonify({'success': False, 'error': 'canonical_variable_definition_id es requerido'}), 400

        if not (concept_code_value or concept_code_scheme or dicom_path_pattern):
            return jsonify({
                'success': False,
                'error': 'Debe ingresar al menos una regla: concept_code_value, concept_code_scheme o dicom_path_pattern',
            }), 400

        definition_row = DatabaseService.execute_query(
            "SELECT id, canonical_code, canonical_name, unit FROM dicom_sr.variable_definition WHERE id = %s LIMIT 1",
            (int(canonical_variable_definition_id),),
            fetch_one=True,
        )
        if not definition_row:
            return jsonify({'success': False, 'error': 'Definición canónica no encontrada'}), 404

        parser_family = str(existing[1] or '').strip()

        semantic_signature = (
            f"{parser_family}::"
            f"{(concept_code_scheme or '').strip()}::"
            f"{(concept_code_value or '').strip()}::"
            f"{(dicom_path_pattern or '').strip()}::"
            f"{(definition_row[1] or '').strip()}"
        )

        DatabaseService.execute_query(
            """
            UPDATE dicom_sr.facility_variable_mapping
            SET
                semantic_signature = %s,
                concept_code_value = %s,
                concept_code_scheme = %s,
                concept_code_meaning = %s,
                canonical_name = %s,
                canonical_code = %s,
                unit = %s,
                facility_name = %s,
                facility_code = %s,
                active = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                semantic_signature,
                concept_code_value,
                concept_code_scheme,
                facility_description or definition_row[2],
                definition_row[2],
                definition_row[1],
                definition_row[3],
                facility_name or None,
                facility_code or None,
                active,
                mapping_id,
            ),
            commit=True,
        )

        return jsonify({'success': True, 'message': 'Mapeo actualizado correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/criteria', methods=['GET'])
@jwt_required()
def list_structured_criteria():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_structured_criteria_table()

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)
        include_inactive = str(request.args.get('include_inactive', 'false')).strip().lower() in ('true', '1', 'yes')

        query = """
            SELECT
                c.id,
                c.parser_manifest_id,
                pm.parser_name,
                pm.parser_version,
                pm.parser_family,
                c.criterion_name,
                c.rule_definition,
                c.output_text,
                c.priority,
                c.active,
                c.created_at,
                c.updated_at
            FROM dicom_sr.structured_criteria c
            INNER JOIN dicom_sr.parser_manifest pm ON pm.id = c.parser_manifest_id
            WHERE (%s IS NULL OR c.parser_manifest_id = %s)
              AND (%s = TRUE OR c.active = TRUE)
            ORDER BY c.priority ASC, c.updated_at DESC, c.id DESC
        """

        rows = DatabaseService.execute_query(
            query,
            (parser_manifest_id, parser_manifest_id, include_inactive),
        )

        items = [_row_to_criterion(row) for row in rows]
        return jsonify({'success': True, 'data': items, 'count': len(items)}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parser-variables', methods=['GET'])
@jwt_required()
def list_parser_variables_for_criteria():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)
        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        parser_info = _get_parser_and_key(int(parser_manifest_id))
        if not parser_info:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        search_term = str(request.args.get('search') or '').strip()
        source_type = str(request.args.get('source_type') or '').strip()
        items = _list_parser_variable_items(int(parser_manifest_id), search_term, source_type)

        return jsonify({'success': True, 'data': items, 'count': len(items)}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/parsers/<int:parser_manifest_id>/variables/tree', methods=['GET'])
@jwt_required()
def list_parser_variable_tree(parser_manifest_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_variable_mapping_tables()

        parser_info = _get_parser_and_key(int(parser_manifest_id))
        if not parser_info:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        search_term = str(request.args.get('search') or '').strip()
        source_type = str(request.args.get('source_type') or '').strip()

        items = _list_parser_variable_items(int(parser_manifest_id), search_term, source_type)
        nodes = _build_variable_tree(items)

        return jsonify({
            'success': True,
            'data': {
                'parser_manifest_id': int(parser_manifest_id),
                'parser_family': parser_info['parser_family'],
                'nodes': nodes,
                'total_variables': len(items),
            },
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variables/nodes/<path:node_id>', methods=['GET'])
@jwt_required()
def get_parser_variable_node(node_id: str):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)
        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        items = _list_parser_variable_items(int(parser_manifest_id))
        nodes = _build_variable_tree(items)
        node = _find_node_by_id(nodes, str(node_id or '').strip())
        if not node:
            return jsonify({'success': False, 'error': 'Nodo no encontrado'}), 404

        return jsonify({'success': True, 'data': node}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variables/nodes/<path:node_id>/children', methods=['GET'])
@jwt_required()
def get_parser_variable_node_children(node_id: str):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        parser_manifest_id = request.args.get('parser_manifest_id', type=int)
        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400

        items = _list_parser_variable_items(int(parser_manifest_id))
        nodes = _build_variable_tree(items)
        node = _find_node_by_id(nodes, str(node_id or '').strip())
        if not node:
            return jsonify({'success': False, 'error': 'Nodo no encontrado'}), 404

        return jsonify({
            'success': True,
            'data': node.get('children') or [],
            'count': len(node.get('children') or []),
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/variables/resolve', methods=['POST'])
@jwt_required()
def resolve_parser_variable_node():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        node_id = str(payload.get('node_id') or '').strip()

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400
        if not node_id:
            return jsonify({'success': False, 'error': 'node_id es requerido'}), 400

        items = _list_parser_variable_items(int(parser_manifest_id))
        nodes = _build_variable_tree(items)
        node = _find_node_by_id(nodes, node_id)
        if not node:
            return jsonify({'success': False, 'error': 'Nodo no encontrado'}), 404

        if str(node.get('type')) != 'variable':
            return jsonify({'success': False, 'error': 'El nodo no es una variable seleccionable'}), 400

        metadata = node.get('metadata') or {}
        return jsonify({
            'success': True,
            'data': {
                'node_id': node.get('id'),
                'label': node.get('label'),
                'path': node.get('path'),
                'variable_key': metadata.get('variable_key'),
                'variable_name': metadata.get('variable_name'),
                'canonical_code': metadata.get('canonical_code'),
                'unit': metadata.get('unit'),
                'source_type': metadata.get('source_type'),
                'semantic_signature': metadata.get('semantic_signature'),
            },
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/criteria', methods=['POST'])
@jwt_required()
def create_structured_criterion():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_structured_criteria_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        criterion_name = str(payload.get('criterion_name') or '').strip()
        rule_definition = payload.get('rule_definition')
        output_text = str(payload.get('output_text') or '').strip()
        priority = payload.get('priority', 100)
        active = bool(payload.get('active', True))

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400
        if not criterion_name:
            return jsonify({'success': False, 'error': 'criterion_name es requerido'}), 400
        if not isinstance(rule_definition, dict):
            return jsonify({'success': False, 'error': 'rule_definition debe ser un objeto JSON'}), 400
        if not output_text:
            return jsonify({'success': False, 'error': 'output_text es requerido'}), 400

        parser_exists = DatabaseService.execute_query(
            "SELECT 1 FROM dicom_sr.parser_manifest WHERE id = %s LIMIT 1",
            (int(parser_manifest_id),),
            fetch_one=True,
        )
        if not parser_exists:
            return jsonify({'success': False, 'error': 'Parser no encontrado'}), 404

        insert_query = """
            INSERT INTO dicom_sr.structured_criteria (
                parser_manifest_id,
                criterion_name,
                rule_definition,
                output_text,
                priority,
                active
            ) VALUES (%s, %s, %s::jsonb, %s, %s, %s)
            RETURNING id
        """

        inserted = DatabaseService.execute_query(
            insert_query,
            (
                int(parser_manifest_id),
                criterion_name,
                json.dumps(rule_definition),
                output_text,
                int(priority),
                active,
            ),
            fetch_one=True,
            commit=True,
        )

        return jsonify({
            'success': True,
            'message': 'Criterio creado correctamente',
            'data': {'id': int(inserted[0]) if inserted else None},
        }), 201
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/criteria/<int:criterion_id>', methods=['PUT'])
@jwt_required()
def update_structured_criterion(criterion_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_structured_criteria_table()

        existing = DatabaseService.execute_query(
            "SELECT id FROM dicom_sr.structured_criteria WHERE id = %s LIMIT 1",
            (criterion_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Criterio no encontrado'}), 404

        payload = request.get_json(silent=True) or {}
        criterion_name = str(payload.get('criterion_name') or '').strip()
        rule_definition = payload.get('rule_definition')
        output_text = str(payload.get('output_text') or '').strip()
        priority = payload.get('priority', 100)
        active = bool(payload.get('active', True))

        if not criterion_name:
            return jsonify({'success': False, 'error': 'criterion_name es requerido'}), 400
        if not isinstance(rule_definition, dict):
            return jsonify({'success': False, 'error': 'rule_definition debe ser un objeto JSON'}), 400
        if not output_text:
            return jsonify({'success': False, 'error': 'output_text es requerido'}), 400

        DatabaseService.execute_query(
            """
            UPDATE dicom_sr.structured_criteria
               SET criterion_name = %s,
                   rule_definition = %s::jsonb,
                   output_text = %s,
                   priority = %s,
                   active = %s,
                   updated_at = NOW()
             WHERE id = %s
            """,
            (
                criterion_name,
                json.dumps(rule_definition),
                output_text,
                int(priority),
                active,
                criterion_id,
            ),
            commit=True,
        )

        return jsonify({'success': True, 'message': 'Criterio actualizado correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/criteria/<int:criterion_id>', methods=['DELETE'])
@jwt_required()
def delete_structured_criterion(criterion_id: int):
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_structured_criteria_table()

        existing = DatabaseService.execute_query(
            "SELECT id FROM dicom_sr.structured_criteria WHERE id = %s LIMIT 1",
            (criterion_id,),
            fetch_one=True,
        )
        if not existing:
            return jsonify({'success': False, 'error': 'Criterio no encontrado'}), 404

        DatabaseService.execute_query(
            "DELETE FROM dicom_sr.structured_criteria WHERE id = %s",
            (criterion_id,),
            commit=True,
        )

        return jsonify({'success': True, 'message': 'Criterio eliminado correctamente'}), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@structured_reports_bp.route('/api/structured-reports/criteria/evaluate', methods=['POST'])
@jwt_required()
def evaluate_structured_criteria():
    try:
        allowed, error_response = _ensure_sysadmin()
        if not allowed:
            return error_response

        _ensure_structured_criteria_table()

        payload = request.get_json(silent=True) or {}
        parser_manifest_id = payload.get('parser_manifest_id')
        variables = payload.get('variables') or {}

        if not parser_manifest_id:
            return jsonify({'success': False, 'error': 'parser_manifest_id es requerido'}), 400
        if not isinstance(variables, dict):
            return jsonify({'success': False, 'error': 'variables debe ser un objeto JSON'}), 400

        rows = DatabaseService.execute_query(
            """
            SELECT
                c.id,
                c.parser_manifest_id,
                pm.parser_name,
                pm.parser_version,
                pm.parser_family,
                c.criterion_name,
                c.rule_definition,
                c.output_text,
                c.priority,
                c.active,
                c.created_at,
                c.updated_at
            FROM dicom_sr.structured_criteria c
            INNER JOIN dicom_sr.parser_manifest pm ON pm.id = c.parser_manifest_id
            WHERE c.parser_manifest_id = %s
              AND c.active = TRUE
            ORDER BY c.priority ASC, c.updated_at DESC, c.id DESC
            """,
            (int(parser_manifest_id),),
        )

        matched_items = []
        evaluated_items = []
        for row in rows:
            criterion = _row_to_criterion(row)
            rule_definition = criterion.get('rule_definition')
            outcome = _evaluate_rule_outcome(rule_definition, variables, criterion.get('output_text'))
            output_text = str(outcome.get('output_text') or '').strip()

            evaluated_item = {
                'criterion_id': criterion['id'],
                'criterion_name': criterion['criterion_name'],
                'output_text': output_text,
                'priority': criterion['priority'],
                'matched': bool(outcome.get('matched')),
                'branch': outcome.get('branch') or 'none',
            }
            evaluated_items.append(evaluated_item)

            if bool(outcome.get('matched')):
                matched_items.append({
                    'criterion_id': criterion['id'],
                    'criterion_name': criterion['criterion_name'],
                    'output_text': output_text,
                    'priority': criterion['priority'],
                    'branch': outcome.get('branch') or 'then',
                })

        composed_lines = [
            item['output_text']
            for item in evaluated_items
            if str(item.get('output_text') or '').strip()
        ]

        return jsonify({
            'success': True,
            'data': {
                'matches': matched_items,
                'evaluated_items': evaluated_items,
                'composed_output': '\n'.join(composed_lines),
            },
            'count': len(matched_items),
        }), 200
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500
