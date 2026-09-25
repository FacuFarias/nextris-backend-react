# -*- encoding: utf-8 -*-
"""
API REST para gestión de reportes médicos y plantillas predefinidas
Endpoints para CRUD de reportes, plantillas y generación de PDFs
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
from apps.api.permissions import get_user_permission_codes, require_permission
import uuid
import os
import re
import html
from decimal import Decimal, InvalidOperation
from datetime import timezone
from apps.services.report_fields import (
    canonical_fields_from_row,
    fields_are_complete,
    legacy_aliases,
    merge_template_study_reason,
    normalize_report_payload,
)
from apps.services.clinicaparque_workflow import (
    WORKFLOW_ALREADY_READ,
    WORKFLOW_CANCELLED,
    apply_already_read,
    apply_cancel,
    ensure_workflow_schema,
)
VALID_REPORT_TYPES = {'simple', 'inteligente'}

# Flags para ejecutar migraciones de esquema solo una vez por ciclo de vida del proceso
_schema_report_type_ensured = False
_schema_template_location_ensured = False
_schema_user_default_ensured = False
_schema_applied_template_ensured = False


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None


def normalize_user_id(identity):
    if isinstance(identity, dict):
        return identity.get('id') or identity.get('guid') or identity.get('user_id')
    return identity


def parse_filter_values(value):
    """Parsea un valor simple o una lista separada por comas para filtros."""
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


def _serialize_utc_datetime(value):
    """Expose UTC-naive database timestamps with an explicit UTC offset."""
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _serialize_examination_note(row):
    """Convert a database note row to the public API shape."""
    return {
        'id': str(row[0]),
        'author_id': str(row[1]) if row[1] else '',
        'author_username': row[2] or '',
        'author_display_name': row[3] or row[2] or '',
        'message': row[4] or '',
        'created_on': row[5].isoformat() if row[5] else None,
    }


def _resolve_examination_note_author(cursor):
    """Resolve the authenticated author from the JWT and identity tables."""
    identity = normalize_user_id(get_jwt_identity())
    claims = get_jwt()
    user_type = claims.get('user_type', 'staff')
    username = claims.get('username', '')
    display_name = username or str(identity or '')

    if user_type == 'patient':
        cursor.execute("""
            SELECT up.guid, up.username, COALESCE(dp.name, ''), COALESCE(dp.surname, '')
            FROM nextris.tbuser_patient up
            LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
            WHERE up.guid = %s
        """, (identity,))
    else:
        cursor.execute("""
            SELECT guid, username, COALESCE(name, ''), COALESCE(surname, '')
            FROM nextris.tbuser
            WHERE guid = %s
        """, (identity,))

    author = cursor.fetchone()
    if author:
        author_id, db_username, first_name, surname = author
        username = db_username or username or str(identity or '')
        display_name = ' '.join(part for part in (first_name, surname) if part).strip()
        display_name = display_name or username
        return str(author_id), username, display_name

    return str(identity or ''), username or str(identity or ''), display_name


def ensure_user_default_schema(connection):
    """Garantiza la tabla de defaults personales antes de leerla en el redactor."""
    global _schema_user_default_ensured
    if _schema_user_default_ensured:
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.tbinfpredef_user_default (
                user_id       VARCHAR(45) NOT NULL,
                template_id   VARCHAR(45) NOT NULL,
                study_type_id VARCHAR(45) NOT NULL,
                created_on    TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, study_type_id)
            )
            """
        )
        connection.commit()
        _schema_user_default_ensured = True
    finally:
        cursor.close()


def ensure_applied_template_schema(connection):
    """Garantiza que el reporte pueda conservar la plantilla aplicada."""
    global _schema_applied_template_ensured
    if _schema_applied_template_ensured:
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            ALTER TABLE nextris.tbreport
            ADD COLUMN IF NOT EXISTS applied_template_id VARCHAR(45)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbreport_applied_template_id
            ON nextris.tbreport (applied_template_id)
            """
        )
        connection.commit()
        _schema_applied_template_ensured = True
    finally:
        cursor.close()


def ensure_report_type_schema(connection):
    """Garantiza columna report_type y normaliza datos historicos. Solo corre una vez por proceso."""
    global _schema_report_type_ensured
    if _schema_report_type_ensured:
        return
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'nextris'
                  AND table_name = 'tbinfpredef'
                  AND column_name = 'report_type'
            )
            """
        )
        has_report_type = bool(cursor.fetchone()[0])

        if not has_report_type:
            cursor.execute(
                """
                ALTER TABLE nextris.tbinfpredef
                ADD COLUMN report_type VARCHAR(20) NOT NULL DEFAULT 'simple'
                """
            )

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'nextris'
                  AND table_name = 'tbinfpredef'
                  AND column_name = 'isdefault'
            )
            """
        )
        if not cursor.fetchone()[0]:
            cursor.execute(
                """
                ALTER TABLE nextris.tbinfpredef
                ADD COLUMN isdefault SMALLINT NOT NULL DEFAULT 0
                """
            )

        cursor.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = LOWER(TRIM(COALESCE(report_type, '')))
            """
        )
        cursor.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = 'simple'
            WHERE report_type = '' OR report_type IS NULL
            """
        )
        cursor.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = 'simple'
            WHERE report_type NOT IN ('simple', 'inteligente')
            """
        )

        connection.commit()
        _schema_report_type_ensured = True
    finally:
        cursor.close()

def ensure_template_location_schema(connection):
    """Garantiza tabla de relacion plantilla-location. Solo corre una vez por proceso."""
    global _schema_template_location_ensured
    if _schema_template_location_ensured:
        return
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.rel_infpredef_location (
                guid VARCHAR(45) PRIMARY KEY,
                template_id VARCHAR(45) NOT NULL,
                location_id VARCHAR(45) NOT NULL,
                created_on TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_rel_infpredef_location UNIQUE (template_id, location_id)
            )
            """
        )
        connection.commit()
        _schema_template_location_ensured = True
    finally:
        cursor.close()

def _is_structured_reports_enabled(cursor, facility_id):
    """Indica si la facility tiene habilitado el modulo structured_reports."""
    # Deshabilitado temporalmente — forzado a False
    return False

def _fetch_template_content(cursor, template_id):
    """Obtiene el contenido base de una plantilla por ID."""
    cursor.execute(
        """
        SELECT
            ip.guid,
            ip.study_reason,
            ip.content,
            ip.conclusion,
            ip.findings,
            ip.impression,
            ip.technique,
            COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') AS report_type
        FROM nextris.tbinfpredef ip
        WHERE ip.guid = %s
        LIMIT 1
        """,
        (template_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    report_type = row[7] if row[7] in VALID_REPORT_TYPES else 'simple'
    fields = canonical_fields_from_row(
        row[1], row[2], row[3],
        legacy_findings=row[4], legacy_impressions=row[5],
        legacy_technique=row[6], legacy_conclusion=row[3],
    )
    return {
        'template_id': str(row[0]),
        **fields,
        **legacy_aliases(fields),
        'report_type': report_type,
    }


def _serialize_template_candidate(row, report_type):
    fields = canonical_fields_from_row(
        row[1], row[2], row[3],
        legacy_technique=row[4], legacy_findings=row[5],
        legacy_impressions=row[6], legacy_conclusion=row[3],
    )
    return {
        'template_id': str(row[0]),
        **fields,
        **legacy_aliases(fields),
        'report_type': report_type,
    }

def _select_predefined_template_for_exam(
    cursor,
    study_type_id,
    location_id,
    structured_enabled,
    default_predef_id=None,
    user_id=None,
):
    """Selecciona plantilla siguiendo la regla inteligente/simple por facility."""
    if not study_type_id:
        return None

    if structured_enabled:
        if location_id:
            cursor.execute(
                """
                SELECT
                    ip.guid,
                    ip.study_reason,
                    ip.content,
                    ip.conclusion,
                    ip.technique,
                    ip.findings,
                    ip.impression,
                    'inteligente' AS report_type
                FROM nextris.tbinfpredef ip
                WHERE ip.studytype_id = %s
                  AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'inteligente'
                  AND (
                    EXISTS (
                        SELECT 1
                        FROM nextris.rel_infpredef_location rel_match
                        WHERE rel_match.template_id = ip.guid
                          AND rel_match.location_id = %s
                    )
                    OR NOT EXISTS (
                        SELECT 1
                        FROM nextris.rel_infpredef_location rel_any
                        WHERE rel_any.template_id = ip.guid
                    )
                  )
                ORDER BY
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM nextris.rel_infpredef_location rel_pri
                            WHERE rel_pri.template_id = ip.guid
                              AND rel_pri.location_id = %s
                        ) THEN 0
                        ELSE 1
                    END,
                    ip.tittle ASC
                LIMIT 1
                """,
                (study_type_id, location_id, location_id),
            )
        else:
            cursor.execute(
                """
                SELECT
                    ip.guid,
                    ip.study_reason,
                    ip.content,
                    ip.conclusion,
                    ip.technique,
                    ip.findings,
                    ip.impression,
                    'inteligente' AS report_type
                FROM nextris.tbinfpredef ip
                WHERE ip.studytype_id = %s
                  AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'inteligente'
                ORDER BY ip.tittle ASC
                LIMIT 1
                """,
                (study_type_id,),
            )

        intelligent = cursor.fetchone()
        if intelligent:
            return _serialize_template_candidate(intelligent, 'inteligente')

    # Fallback simple (siempre, con o sin modulo structured_reports).
    # El default personal tiene prioridad sobre el default del tipo de estudio.
    if user_id:
        cursor.execute(
            """
            SELECT
                ip.guid,
                ip.study_reason,
                ip.content,
                ip.conclusion,
                ip.technique,
                ip.findings,
                ip.impression,
                'simple' AS report_type
            FROM nextris.tbinfpredef_user_default ud
            JOIN nextris.tbinfpredef ip ON ip.guid = ud.template_id
            WHERE ud.user_id = %s
              AND ud.study_type_id = %s
              AND ip.studytype_id = %s
              AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'simple'
            LIMIT 1
            """,
            (user_id, study_type_id, study_type_id),
        )
        user_default = cursor.fetchone()
        if user_default:
            return _serialize_template_candidate(user_default, 'simple')

    if default_predef_id:
        cursor.execute(
            """
            SELECT
                ip.guid,
                ip.study_reason,
                ip.content,
                ip.conclusion,
                ip.technique,
                ip.findings,
                ip.impression,
                'simple' AS report_type
            FROM nextris.tbinfpredef ip
            WHERE ip.guid = %s
              AND ip.studytype_id = %s
              AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'simple'
            LIMIT 1
            """,
            (default_predef_id, study_type_id),
        )
        default_simple = cursor.fetchone()
        if default_simple:
            return _serialize_template_candidate(default_simple, 'simple')

    # Compatibilidad con instalaciones antiguas que guardaban el default
    # únicamente en tbinfpredef.isdefault.
    cursor.execute(
        """
        SELECT
            ip.guid,
            ip.study_reason,
            ip.content,
            ip.conclusion,
            ip.technique,
            ip.findings,
            ip.impression,
            'simple' AS report_type
        FROM nextris.tbinfpredef ip
        WHERE ip.studytype_id = %s
          AND ip.isdefault = 1
          AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'simple'
        ORDER BY ip.tittle ASC
        LIMIT 1
        """,
        (study_type_id,),
    )
    legacy_default = cursor.fetchone()
    if legacy_default:
        return _serialize_template_candidate(legacy_default, 'simple')

    cursor.execute(
        """
        SELECT
            ip.guid,
            ip.study_reason,
            ip.content,
            ip.conclusion,
            ip.technique,
            ip.findings,
            ip.impression,
            'simple' AS report_type
        FROM nextris.tbinfpredef ip
        WHERE ip.studytype_id = %s
          AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'simple'
        ORDER BY ip.tittle ASC
        LIMIT 1
        """,
        (study_type_id,),
    )
    simple_row = cursor.fetchone()
    if simple_row:
        return _serialize_template_candidate(simple_row, 'simple')

    # Fallback legacy de seguridad: usar default_predef_id aunque no sea simple.
    if default_predef_id:
        legacy_template = _fetch_template_content(cursor, default_predef_id)
        if not legacy_template:
            return None
        if (not structured_enabled) and legacy_template.get('report_type') != 'simple':
            return None
        return legacy_template

    return None


def _render_report_pdf_response(exam_id):
    """Renderiza un informe firmado en memoria y crea la respuesta HTTP."""
    from io import BytesIO
    from apps.services.report_pdf_service import ReportPdfNotAvailable, render_report_pdf

    try:
        rendered = render_report_pdf(exam_id)
    except ReportPdfNotAvailable:
        return jsonify({
            'success': False,
            'message': 'Informe PDF no disponible',
            'code': 'REPORT_NOT_AVAILABLE',
        }), 404
    except Exception as error:
        return jsonify({'success': False, 'message': f'Error generando PDF: {error}'}), 500

    as_attachment = request.args.get('download', '').lower() in ('1', 'true', 'yes', 'on')
    response = send_file(
        BytesIO(rendered.content),
        as_attachment=as_attachment,
        download_name=rendered.filename,
        mimetype='application/pdf',
        max_age=0,
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


def _normalize_placeholder_key(raw_value):
    """Normaliza el nombre de variable para permitir matching tolerante."""
    if raw_value is None:
        return ''
    value = str(raw_value).strip().lower()
    if not value:
        return ''

    # Normalizar wrappers legacy frecuentes en plantillas/chips.
    value = re.sub(r'^[\[\{\(\s]+', '', value)
    value = re.sub(r'[\]\}\)\s]+$', '', value)

    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def _get_mapping_source_table(cursor):
    """Resuelve tabla fuente de variables mapeables (vista nueva o fallback legacy)."""
    cursor.execute(
        """
        SELECT to_regclass('dicom_sr.parser_mappable_variable'), to_regclass('dicom_sr.facility_variable_mapping')
        """
    )
    row = cursor.fetchone()
    if row and row[0]:
        return 'dicom_sr.parser_mappable_variable'
    return 'dicom_sr.facility_variable_mapping'


def _source_type_label(source_type):
    source = str(source_type or '').strip().lower()
    labels = {
        'standard_numeric_contextual': 'Estandar contextual',
        'standard_numeric': 'Estandar numerico',
        'private_99gems': 'Privado GE 99GEMS',
    }
    return labels.get(source, source or 'General')


def _slug_node_part(value):
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


def _build_variable_segments(variable_name):
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


def _get_sr_parser_context(cursor, study_instance_uid):
    """Obtiene parser asociado al ultimo SR del estudio y su parser_manifest_id."""
    if not study_instance_uid:
        return None

    try:
        cursor.execute(
            """
            SELECT
                id,
                parser_name,
                parser_version,
                parser_family,
                status
            FROM dicom_sr.sr_document
            WHERE study_instance_uid = %s
            ORDER BY COALESCE(processing_finished_at, received_at, created_at) DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (study_instance_uid,),
        )
        row = cursor.fetchone()
    except Exception:
        return None

    if not row:
        return None

    sr_document_id = row[0]
    parser_name = str(row[1] or '').strip()
    parser_version = str(row[2] or '').strip()
    parser_family = str(row[3] or '').strip()
    status = str(row[4] or '').strip()

    parser_manifest_id = None
    if parser_family:
        try:
            cursor.execute(
                """
                SELECT id
                FROM dicom_sr.parser_manifest
                WHERE parser_family = %s
                ORDER BY
                    CASE
                        WHEN parser_name = %s AND parser_version = %s THEN 0
                        WHEN parser_name = %s THEN 1
                        ELSE 2
                    END,
                    COALESCE(updated_at, created_at) DESC NULLS LAST,
                    id DESC
                LIMIT 1
                """,
                (parser_family, parser_name, parser_version, parser_name),
            )
            parser_row = cursor.fetchone()
            if parser_row:
                parser_manifest_id = int(parser_row[0])
        except Exception:
            parser_manifest_id = None

    return {
        'sr_document_id': int(sr_document_id),
        'status': status,
        'parser_name': parser_name or None,
        'parser_version': parser_version or None,
        'parser_family': parser_family or None,
        'parser_manifest_id': parser_manifest_id,
    }


def _list_parser_variable_items_for_family(cursor, parser_family):
    if not parser_family:
        return []

    source_table = _get_mapping_source_table(cursor)
    cursor.execute(
        f"""
        SELECT
            canonical_name,
            canonical_code,
            unit,
            concept_code_meaning,
            source_type,
            semantic_signature
        FROM {source_table}
        WHERE COALESCE(active, TRUE) = TRUE
          AND parser_family = %s
        ORDER BY canonical_name ASC, canonical_code ASC
        """,
        (parser_family,),
    )
    rows = cursor.fetchall() or []

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
        variable_key = _normalize_placeholder_key(variable_name)
        if not variable_key:
            continue

        dedupe_key = f"{variable_key}|{semantic_signature or canonical_code or variable_name}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        segments = [_source_type_label(source_type)] + _build_variable_segments(variable_name)
        items.append(
            {
                'variable_key': variable_key,
                'variable_name': variable_name,
                'canonical_code': canonical_code or None,
                'unit': unit or None,
                'source_type': source_type or None,
                'semantic_signature': semantic_signature or None,
                'segments': segments,
            }
        )

    return items


def _get_sr_extracted_candidates(cursor, study_instance_uid):
    """Obtiene mediciones extraidas del ultimo SR del estudio para matching contextual."""
    if not study_instance_uid:
        return []

    try:
        cursor.execute(
            """
            WITH doc AS (
                SELECT id
                FROM dicom_sr.sr_document
                WHERE study_instance_uid = %s
                ORDER BY COALESCE(processing_finished_at, received_at, created_at) DESC NULLS LAST, id DESC
                LIMIT 1
            )
            SELECT
                ev.id,
                ev.concept_code_value,
                ev.concept_code_scheme,
                ev.concept_code_meaning,
                ev.value_text,
                ev.value_numeric,
                ev.value_unit,
                ev.value_datetime,
                ev.value_json,
                ev.dicom_path,
                ev.sequence_index
            FROM doc d
            JOIN dicom_sr.sr_extracted_variable ev ON ev.sr_document_id = d.id
            ORDER BY ev.id ASC
            """,
            (study_instance_uid,),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []

    items = []
    for row in rows:
        value = _format_sr_value(row[4], row[5], row[6], row[7])
        if value == '':
            continue

        items.append(
            {
                'id': int(row[0]),
                'concept_code_value': str(row[1] or '').strip().lower(),
                'concept_code_scheme': str(row[2] or '').strip().lower(),
                'concept_code_meaning': str(row[3] or '').strip().lower(),
                'value': value,
                'is_user_chosen': _is_user_chosen_value(row[8]),
                'dicom_path': str(row[9] or '').strip(),
                'traza_token': _extract_traza_token_from_path(row[9]),
                'sequence_index': int(row[10] or 0),
            }
        )

    return items


def _resolve_item_value(item, variable_map, extracted_candidates):
    semantic_signature = str(item.get('semantic_signature') or '').strip().lower()
    traza_token = _extract_traza_token_from_signature(semantic_signature)
    concept_code_value, concept_code_scheme = _extract_concept_from_signature(semantic_signature)

    if extracted_candidates:
        contextual = []
        concept_only = []
        for candidate in extracted_candidates:
            if concept_code_value and candidate.get('concept_code_value') != concept_code_value:
                continue
            if concept_code_scheme and candidate.get('concept_code_scheme') != concept_code_scheme:
                continue

            concept_only.append(candidate)
            if traza_token and candidate.get('traza_token') == traza_token:
                contextual.append(candidate)

        active_candidates = contextual if contextual else concept_only
        if active_candidates:
            # Prioridad: User chosen value, luego mayor sequence_index (normalmente best/max), luego id reciente.
            best = sorted(
                active_candidates,
                key=lambda row: (
                    1 if row.get('is_user_chosen') else 0,
                    int(row.get('sequence_index') or 0),
                    int(row.get('id') or 0),
                ),
                reverse=True,
            )[0]
            return str(best.get('value') or '').strip()

    if not variable_map:
        return ''

    candidates = []

    variable_name = str(item.get('variable_name') or '').strip()
    if variable_name:
        candidates.append(variable_name.lower())
        candidates.append(_normalize_placeholder_key(variable_name))

    variable_key = str(item.get('variable_key') or '').strip()
    if variable_key:
        candidates.append(variable_key.lower())
        candidates.append(_normalize_placeholder_key(variable_key))

    seen = set()
    for candidate in candidates:
        key = str(candidate or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if key in variable_map:
            return str(variable_map[key]).strip()

    return ''


def _build_sr_variable_tree(cursor, parser_family, variable_map, study_instance_uid):
    """Construye arbol de variables del parser con valores del estudio (si existen)."""
    items = _list_parser_variable_items_for_family(cursor, parser_family)
    if not items:
        return []

    extracted_candidates = _get_sr_extracted_candidates(cursor, study_instance_uid)

    roots = []
    index = {}

    def ensure_group(parent_children, path_parts, label):
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
        node_path_parts = []

        for segment in segments[:-1]:
            node_path_parts.append(f"grp:{_slug_node_part(segment)}")
            group_node = ensure_group(parent_children, node_path_parts, segment)
            parent_children = group_node['children']

        leaf_label = str(segments[-1])
        leaf_id = '/'.join(node_path_parts + [f"var:{_slug_node_part(item['variable_key'])}"])
        if leaf_id in index:
            continue

        resolved_value = _resolve_item_value(item, variable_map, extracted_candidates)

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
                'value': resolved_value,
                'has_value': bool(resolved_value),
            },
        }
        parent_children.append(leaf_node)
        index[leaf_id] = leaf_node

    def finalize(nodes):
        nodes.sort(key=lambda node: (0 if node['type'] == 'group' else 1, str(node['label']).lower()))
        for node in nodes:
            if node['type'] == 'group':
                finalize(node['children'])
                node['children_count'] = len(node['children'])

    finalize(roots)
    return roots


def _format_sr_value(value_text, value_numeric, value_unit, value_datetime):
    """Construye el valor legible de una variable extraída de SR."""
    if value_text is not None and str(value_text).strip() != '':
        return str(value_text).strip()

    if value_numeric is not None:
        try:
            numeric_decimal = Decimal(str(value_numeric))
            numeric_value = format(numeric_decimal.quantize(Decimal('0.01')), '.2f')
        except (InvalidOperation, ValueError, TypeError):
            try:
                numeric_value = f"{float(value_numeric):.2f}"
            except (ValueError, TypeError):
                numeric_value = str(value_numeric).strip()

        if value_unit and str(value_unit).strip():
            return f"{numeric_value} {str(value_unit).strip()}"
        return numeric_value

    if value_datetime is not None:
        return str(value_datetime)

    return ''


def _is_user_chosen_value(value_json):
    """Detecta si la medicion tiene Selection Status = User chosen value (121410)."""
    if not isinstance(value_json, dict):
        return False

    raw_item_json = value_json.get('raw_item_json')
    if not isinstance(raw_item_json, dict):
        return False

    modifiers = raw_item_json.get('0040A730', {})
    modifier_values = modifiers.get('Value') if isinstance(modifiers, dict) else None
    if not isinstance(modifier_values, list):
        return False

    for modifier in modifier_values:
        if not isinstance(modifier, dict):
            continue
        code_seq = modifier.get('0040A168', {})
        code_values = code_seq.get('Value') if isinstance(code_seq, dict) else None
        if not isinstance(code_values, list):
            continue

        for code_item in code_values:
            if not isinstance(code_item, dict):
                continue
            code_value = (
                ((code_item.get('00080100') or {}).get('Value') or [None])[0]
                if isinstance(code_item.get('00080100'), dict)
                else None
            )
            code_meaning = (
                ((code_item.get('00080104') or {}).get('Value') or [None])[0]
                if isinstance(code_item.get('00080104'), dict)
                else None
            )
            if str(code_value or '').strip() == '121410':
                return True
            if str(code_meaning or '').strip().lower() == 'user chosen value':
                return True

    return False


def _extract_traza_token_from_path(dicom_path):
    """Extrae token traza-x-y desde dicom_path tipo ContentSequence[x].ContentSequence[y]..."""
    path = str(dicom_path or '').strip()
    if not path:
        return ''

    match = re.search(r'ContentSequence\[(\d+)\]\.ContentSequence\[(\d+)\]', path)
    if not match:
        return ''

    return f"traza-{match.group(1)}-{match.group(2)}"


def _extract_traza_token_from_signature(semantic_signature):
    signature = str(semantic_signature or '').strip().lower()
    if not signature:
        return ''

    for part in signature.split('|'):
        token = str(part or '').strip().lower()
        if re.fullmatch(r'traza-\d+-\d+', token):
            return token
    return ''


def _extract_concept_from_signature(semantic_signature):
    """Extrae concept_code_value y concept_code_scheme de semantic_signature cuando exista."""
    parts = [str(part or '').strip().lower() for part in str(semantic_signature or '').split('|')]
    # Estructura esperada: ...|<concept_code_value>|<concept_code_scheme>|<concept_code_meaning>|...
    if len(parts) >= 8:
        code_value = parts[6]
        code_scheme = parts[7]
        if code_value:
            return code_value, code_scheme
    return '', ''


def _get_sr_variable_values(cursor, study_instance_uid):
    """Obtiene un diccionario {nombre_variable: valor} desde dicom_sr para un estudio."""
    if not study_instance_uid:
        return {}

    try:
        cursor.execute("""
            WITH docs AS (
                SELECT id
                FROM dicom_sr.sr_document
                WHERE study_instance_uid = %s
                ORDER BY COALESCE(processing_finished_at, received_at, created_at) DESC NULLS LAST, id DESC
            )
            SELECT
                COALESCE(
                    NULLIF(BTRIM(ev.value_json->>'canonical_name'), ''),
                    NULLIF(BTRIM(fvm_best.canonical_name), ''),
                    NULLIF(BTRIM(sref.resolved_label), ''),
                    NULLIF(BTRIM(vd.canonical_name), ''),
                    NULLIF(BTRIM(ev.concept_code_meaning), ''),
                    NULLIF(BTRIM(ev.concept_code_value), '')
                ) AS variable_name,
                ev.value_text,
                ev.value_numeric,
                ev.value_unit,
                ev.value_datetime,
                ev.sequence_index,
                ev.id,
                ev.value_json
            FROM docs d
            JOIN dicom_sr.sr_extracted_variable ev ON ev.sr_document_id = d.id
            LEFT JOIN dicom_sr.variable_definition vd ON vd.id = ev.canonical_variable_definition_id
            LEFT JOIN dicom_sr.sr_extracted_variable_semantic_map sem_map ON sem_map.sr_extracted_variable_id = ev.id
            LEFT JOIN dicom_sr.sr_variable_semantic_reference sref ON sref.id = sem_map.semantic_reference_id
            LEFT JOIN LATERAL (
                SELECT fvm.canonical_name
                FROM dicom_sr.facility_variable_mapping fvm
                WHERE fvm.semantic_signature = sem_map.semantic_signature
                  AND COALESCE(fvm.active, TRUE) = TRUE
                ORDER BY CASE WHEN fvm.facility_id IS NULL THEN 0 ELSE 1 END, fvm.id DESC
                LIMIT 1
            ) fvm_best ON TRUE
            ORDER BY ev.sr_document_id DESC, ev.sequence_index ASC NULLS LAST, ev.id ASC
        """, (study_instance_uid,))

        rows = cursor.fetchall() or []
    except Exception:
        # En ambientes sin dicom_sr o sin datos SR, no bloquear la carga del redactor.
        return {}

    variable_map = {}
    variable_priority = {}
    for row in rows:
        variable_name = row[0]
        if not variable_name:
            continue

        value = _format_sr_value(row[1], row[2], row[3], row[4])
        if value == '':
            continue

        is_user_chosen = _is_user_chosen_value(row[7])

        exact_key = str(variable_name).strip().lower()
        normalized_key = _normalize_placeholder_key(variable_name)

        if exact_key and (
            exact_key not in variable_map
            or (is_user_chosen and not variable_priority.get(exact_key, False))
        ):
            variable_map[exact_key] = value
            variable_priority[exact_key] = is_user_chosen

        if normalized_key and (
            normalized_key not in variable_map
            or (is_user_chosen and not variable_priority.get(normalized_key, False))
        ):
            variable_map[normalized_key] = value
            variable_priority[normalized_key] = is_user_chosen

    return variable_map


def _build_sr_variables_list(variable_map):
    """Construye lista de variables SR para UI, unificando claves duplicadas (snake/espaciado)."""
    grouped = {}
    for key, value in (variable_map or {}).items():
        normalized = _normalize_placeholder_key(key)
        if not normalized:
            continue

        existing = grouped.get(normalized)
        candidate_name = str(key).strip()

        if not existing:
            grouped[normalized] = {
                'key': normalized,
                'name': candidate_name,
                'value': value,
            }
            continue

        # Preferir etiqueta humana (con espacios) sobre snake_case.
        has_spaces_candidate = ' ' in candidate_name
        has_spaces_existing = ' ' in existing['name']
        if has_spaces_candidate and not has_spaces_existing:
            existing['name'] = candidate_name

    items = list(grouped.values())
    items.sort(key=lambda item: str(item['name']).lower())
    return items


def _replace_sr_placeholders(content, variable_values):
    """Reemplaza placeholders {Variable} y chips HTML por valores extraídos de SR."""
    if not content or not variable_values:
        return content or ''

    def _resolve_value(variable_name):
        if not variable_name:
            return None

        candidate_raw = str(variable_name).strip()
        direct_key = candidate_raw.lower()
        if direct_key in variable_values:
            return variable_values[direct_key]

        # Variantes wrapper frecuentes: (name), [name], {name}
        stripped_key = re.sub(r'^[\[\{\(\s]+', '', candidate_raw)
        stripped_key = re.sub(r'[\]\}\)\s]+$', '', stripped_key)
        stripped_direct = stripped_key.lower()
        if stripped_direct in variable_values:
            return variable_values[stripped_direct]

        normalized_key = _normalize_placeholder_key(stripped_key)
        if normalized_key in variable_values:
            return variable_values[normalized_key]

        # Fallback 1: placeholders largos tipo ruta semántica, usar segmentos por separadores.
        # Ej: Common-Carotid-...-Peak Systolic Velocity -> Peak Systolic Velocity
        segments = [
            segment.strip()
            for segment in re.split(r'[-|>]+', stripped_key)
            if segment and segment.strip()
        ]

        for segment in reversed(segments):
            segment_direct = segment.lower()
            if segment_direct in variable_values:
                return variable_values[segment_direct]

            segment_normalized = _normalize_placeholder_key(segment)
            if segment_normalized in variable_values:
                return variable_values[segment_normalized]

        # Fallback 2: comparar por compactación alfanumérica.
        compact_candidate = re.sub(r'[^a-z0-9]+', '', stripped_direct)
        if compact_candidate:
            for key, val in variable_values.items():
                compact_key = re.sub(r'[^a-z0-9]+', '', str(key).lower())
                if compact_key == compact_candidate:
                    return val

        # Fallback 3: si una variable conocida está contenida en el placeholder normalizado,
        # usar la coincidencia más larga (evita falsas coincidencias genéricas).
        normalized_candidate_text = _normalize_placeholder_key(stripped_key)
        best_match = None
        best_length = 0
        for key, val in variable_values.items():
            key_norm = _normalize_placeholder_key(key)
            if not key_norm or len(key_norm) < 4:
                continue
            if key_norm in normalized_candidate_text and len(key_norm) > best_length:
                best_match = val
                best_length = len(key_norm)

        if best_match is not None:
            return best_match

        return None

    def _extract_chip_variable_name(chip_match):
        attr_name = chip_match.group(1)
        inner_html = chip_match.group(2) or ''

        if attr_name:
            return attr_name

        inner_text = re.sub(r'<[^>]+>', '', inner_html)
        inner_text = html.unescape(inner_text or '').strip()

        # Formatos posibles legacy: {name}, [name], [[name]]
        wrapped_match = re.match(r'^\{(.+)\}$', inner_text) or re.match(r'^\[\[(.+)\]\]$', inner_text) or re.match(r'^\[(.+)\]$', inner_text)
        if wrapped_match:
            return wrapped_match.group(1)

        return inner_text

    def _replace_chip(match):
        variable_name = _extract_chip_variable_name(match)
        resolved_value = _resolve_value(variable_name)
        if resolved_value is None:
            return match.group(0)
        return html.escape(str(resolved_value))

    def _replace_curly(match):
        variable_name = match.group(1)
        resolved_value = _resolve_value(variable_name)
        if resolved_value is None:
            return match.group(0)
        return html.escape(str(resolved_value))

    # Primero reemplazar chips de variable para evitar dejar spans huérfanos en el reporte final.
    resolved_content = re.sub(
        r'<span[^>]*data-variable-chip="true"[^>]*(?:data-variable-name="([^"]+)")?[^>]*>(.*?)</span>',
        _replace_chip,
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Compatibilidad legacy: placeholders tipo [[Variable]].
    resolved_content = re.sub(r'\[\[([^\]]+)\]\]', _replace_curly, resolved_content)

    # Luego placeholders textuales en formato {Variable}.
    return re.sub(r'\{([^{}]+)\}', _replace_curly, resolved_content)


def _collect_placeholder_candidates(content):
    """Extrae placeholders potenciales para diagnóstico."""
    if not content:
        return []

    candidates = set()
    for match in re.finditer(r'\{([^{}]+)\}', content):
        name = (match.group(1) or '').strip()
        if name:
            candidates.add(name)

    for match in re.finditer(r'\[\[([^\]]+)\]\]', content):
        name = (match.group(1) or '').strip()
        if name:
            candidates.add(name)

    for match in re.finditer(r'<span[^>]*data-variable-chip="true"[^>]*(?:data-variable-name="([^"]+)")?[^>]*>(.*?)</span>', content, flags=re.IGNORECASE | re.DOTALL):
        attr_name = (match.group(1) or '').strip()
        if attr_name:
            candidates.add(attr_name)
            continue

        inner = re.sub(r'<[^>]+>', '', match.group(2) or '')
        inner = html.unescape(inner).strip()
        inner = re.sub(r'^[\[\{\(\s]+', '', inner)
        inner = re.sub(r'[\]\}\)\s]+$', '', inner)
        if inner:
            candidates.add(inner)

    return sorted(candidates)


# ====================================================================
# ENDPOINTS PARA REDACCIÓN DE INFORMES
# ====================================================================

@api_blueprint.route('/examinations/for-reporting', methods=['GET'])
@jwt_required()
@require_permission('tabs.worklist.view', include_role_permissions=True)
def get_examinations_for_reporting():
    """
    Obtiene lista de exámenes listos para reportar
    No restringe por ubicación; la ubicación solo se devuelve como información.
    
    Query Parameters:
    - status (optional): Filtrar por estado (default: todos)
    - show_reported (optional): true para incluir exámenes reportados (isreported=1)
    - show_ready (optional): true para incluir exámenes listos para reportar (isreported=0)
    - assigned_to_me (optional): true para mostrar solo exámenes asignados al usuario actual
    - modality_id (optional): GUID de la modalidad o GUIDs separados por coma
    - body_part_id (optional): GUID de la parte del cuerpo
    - study_group_id (optional): GUID del grupo de estudio
    - page (optional): Número de página (default: 1)
    - per_page (optional): Items por página (default: 50, max: 100)
    
    Nota: Si show_reported y show_ready están activos simultáneamente, se muestran ambos tipos.
          Si ninguno está activo, se muestran todos por defecto.
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "patient_name": "nombre completo",
                "patient_id": "Patient ID externo",
                "patient_dni": "dni",
                "study_type": "descripción",
                "admission_number": "ADM001",
                "accession_number": "ACC001",
                "created_on": "datetime",
                "status": "estado",
                "is_reported": false,
                "is_executed": true,
                "is_image": true,
                "study_instance_uid": "1.2.840...",
                "equipment": "equipo",
                "location": "ubicación",
                "assigned_to": "uuid del médico asignado",
                "modality_id": "uuid",
                "modality_description": "CT",
                "study_group_id": "uuid",
                "study_group_description": "Radiología",
                "bodypart_id": "uuid",
                "bodypart_description": "Tórax"
            }
        ],
        "total": 150,
        "page": 1,
        "per_page": 50
    }
    """
    try:
        user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        # Filtros opcionales
        status_filter = request.args.get('status')
        show_reported = request.args.get('show_reported', 'false').lower() == 'true'
        show_ready = request.args.get('show_ready', 'false').lower() == 'true'
        assigned_to_me = request.args.get('assigned_to_me', 'false').lower() == 'true'
        show_no_image = request.args.get('show_no_image', 'false').lower() == 'true'
        show_without_order = request.args.get('show_without_order', 'false').lower() == 'true'
        show_only_with_notes = request.args.get('show_only_with_notes', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        flag_filter = [value.strip().lower() for value in request.args.get('flag_filter', '').split(',') if value.strip()]
        date_range = request.args.get('date_range', 'all').strip().lower()
        date_field = request.args.get('date_field', 'admision').strip().lower()
        sort_column = request.args.get('sort_column', '').strip().lower()
        sort_direction = request.args.get('sort_direction', 'desc').strip().lower()
        modality_ids = parse_filter_values(request.args.get('modality_id'))
        body_part_id = request.args.get('body_part_id')
        study_group_id = request.args.get('study_group_id')
        print(f"[PARAMS] modality_id={modality_ids}, body_part_id={body_part_id}, study_group_id={study_group_id}")
        
        connection = psycopg2.connect(**config)
        ensure_report_type_schema(connection)
        ensure_user_default_schema(connection)
        ensure_applied_template_schema(connection)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        
        # Query base - exámenes ejecutados
        # Lógica de filtrado por estado de reporte:
        # - Si ambos show_reported y show_ready están activos: mostrar ambos (sin filtro)
        # - Si solo show_reported: mostrar solo reportados (isreported=1)
        # - Si solo show_ready: mostrar solo listos/no reportados (isreported=0)
        # - Si ninguno está activo: no mostrar nada
        if show_reported and show_ready:
            # Ambos activos: mostrar todo
            reported_filter = ""
        elif show_reported:
            # Solo reportados
            reported_filter = "AND (e.IsReported = 1 OR e.clinicaparque_workflow_state IN ('cancelled', 'already_read'))"
        elif show_ready:
            # Solo listos (no reportados)
            reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0) AND COALESCE(e.clinicaparque_workflow_state, 'pending') = 'pending'"
        else:
            # Ninguno activo: no mostrar nada
            reported_filter = "AND 1=0"
        
        base_query = f"""
            SELECT e.Guid, 
                   CONCAT_WS(', ', NULLIF(TRIM(dp.Surname), ''), NULLIF(TRIM(dp.Name), '')) as patient_name,
                   dp.patientid,
                   dp.nationalcode,
                   st.Description as study_type,
                   e.AdmisionNumber,
                   e.LocalAcc,
                   e.CreatedOn,
                   e.Status,
                   COALESCE(e.IsReported, 0) as is_reported,
                   COALESCE(e.IsExecuted, 0) as is_executed,
                   COALESCE(e.isimage, 0) as is_image,
                   e.studyinstanceuid,
                   (
                       SELECT COUNT(*)
                       FROM public.instance dicom_instance
                       JOIN public.series dicom_series ON dicom_series.pk = dicom_instance.series_fk
                       JOIN public.study dicom_study ON dicom_study.pk = dicom_series.study_fk
                       WHERE dicom_study.study_iuid = e.studyinstanceuid
                   ) as num_instances,
                   eq.Description as equipment,
                   loc.name as location,
                   e.assignto,
                   COALESCE(
                       NULLIF(TRIM(CONCAT(COALESCE(ua.name, ''), ' ', COALESCE(ua.surname, ''))), ''),
                       ua.username
                   ) as assignto_name,
                   CASE WHEN COALESCE(e.IsReported, 0) = 1 AND rep.Guid IS NOT NULL
                        THEN TRUE ELSE FALSE END AS report_available,
                   st.modality_id,
                   mod.description as modality_description,
                   st.studygroup_id,
                   sg.description as study_group_description,
                   st.bodypart_id,
                   bp.description as bodypart_description,
                   e.blockby,
                   COALESCE(
                       NULLIF(TRIM(CONCAT(COALESCE(ub.name, ''), ' ', COALESCE(ub.surname, ''))), ''),
                       ub.username
                   ) as blocked_by_name,
                   e.reportdate,
                   e.flags,
                   e.tag_ids,
                   (
                       SELECT n.message
                       FROM nextris.tbexaminationnote n
                       WHERE n.examination_id = e.Guid
                       ORDER BY n.created_on DESC, n.guid DESC
                       LIMIT 1
                   ) AS latest_note,
                   COALESCE((
                       SELECT json_agg(json_build_object(
                           'id', recent.guid,
                           'author_id', recent.author_id,
                           'author_username', recent.author_username,
                           'author_display_name', recent.author_display_name,
                           'message', recent.message,
                           'created_on', recent.created_on
                       ) ORDER BY recent.created_on DESC, recent.guid DESC)
                       FROM (
                           SELECT n.guid, n.author_id, n.author_username,
                                  n.author_display_name, n.message, n.created_on
                           FROM nextris.tbexaminationnote n
                           WHERE n.examination_id = e.Guid
                           ORDER BY n.created_on DESC, n.guid DESC
                           LIMIT 3
                       ) recent
                   ), '[]'::json) AS recent_notes,
                    (
                        SELECT COUNT(*)
                        FROM nextris.tbexaminationnote n
                        WHERE n.examination_id = e.Guid
                    ) AS notes_count
                    ,e."w-order" as w_order
                    ,e.idreferringphysician
                    ,e.idrequestingphysician
                    ,e.clinicalquestion
                    ,e.studytype_id
                   ,e.requestingphysician_name
                   ,e.othersdetails
                   ,e.laterality_id
                   ,resolved_template.template_id
                   ,resolved_template.template_name
                   ,resolved_template.template_source
                   ,COALESCE(e.clinicaparque_workflow_state, 'pending')
                   ,e.clinicaparque_workflow_state_at
                   ,e.clinicaparque_workflow_state_source
                   ,e.clinicaparque_workflow_state_user_id
                   ,cr.code AS cancellation_reason_code
                   ,cr.description AS cancellation_reason
                   ,ps.study_date AS study_date
                   ,ps.study_time AS study_time
                   ,ps.created_time AS arrival_time
             FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON COALESCE(e.location_id, eq.location_id) = loc.guid
            LEFT JOIN nextris.tbreport rep ON e.Guid = rep.IdExamination
            LEFT JOIN public.study ps ON ps.study_iuid = e.studyinstanceuid
            LEFT JOIN nextris.ismodality mod ON st.modality_id = mod.guid
            LEFT JOIN nextris.isstudytypegroup sg ON st.studygroup_id = sg.guid
            LEFT JOIN nextris.isanatomicalpart bp ON st.bodypart_id = bp.guid
            LEFT JOIN nextris.tbuser ub ON e.blockby::text = ub.guid
            LEFT JOIN nextris.tbuser ua ON e.assignto::text = ua.guid
            LEFT JOIN nextris.clinicaparque_cancellation_reasons cr
                ON cr.guid = e.clinicaparque_cancellation_reason_id
            LEFT JOIN LATERAL (
                SELECT
                    ip.guid AS template_id,
                    ip.tittle AS template_name,
                    CASE
                        WHEN rep.applied_template_id = ip.guid THEN 'Aplicada'
                        ELSE 'Por defecto'
                    END AS template_source
                FROM nextris.tbinfpredef ip
                WHERE ip.studytype_id = e.studytype_id
                  AND (
                      ip.guid = rep.applied_template_id
                      OR COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = 'simple'
                  )
                ORDER BY
                    CASE
                        WHEN rep.applied_template_id = ip.guid THEN 0
                        WHEN EXISTS (
                            SELECT 1
                            FROM nextris.tbinfpredef_user_default user_default
                            WHERE user_default.user_id = %s
                              AND user_default.study_type_id = e.studytype_id
                              AND user_default.template_id = ip.guid
                        ) THEN 1
                        WHEN ip.guid = st.default_predef_id THEN 2
                        WHEN ip.isdefault = 1 THEN 3
                        ELSE 4
                    END,
                    ip.tittle ASC
                LIMIT 1
            ) resolved_template ON TRUE
             WHERE 1 = 1
            {reported_filter}
        """
        
        # La instalación utiliza una única ubicación. La ubicación se
        # conserva para mostrarla, pero no restringe los resultados.
        params = [user_id]
        
        # Aplicar filtro de estado si se proporciona
        if status_filter:
            base_query += " AND e.Status = %s"
            params.append(status_filter)
        
        # Aplicar filtro de asignación si se solicita
        if assigned_to_me:
            base_query += " AND e.assignto = %s"
            params.append(user_id)

        # Búsqueda libre por paciente, Patient ID, DNI, admisión, accession o estudio.
        if search:
            search_pattern = f"%{search.lower()}%"
            base_query += """
                AND (
                    LOWER(COALESCE(CONCAT(dp.Name, ' ', dp.Surname), '')) LIKE %s
                    OR LOWER(COALESCE(dp.patientid, '')) LIKE %s
                    OR LOWER(COALESCE(dp.nationalcode, '')) LIKE %s
                    OR LOWER(COALESCE(e.LocalAcc, '')) LIKE %s
                    OR LOWER(COALESCE(e.AdmisionNumber, '')) LIKE %s
                    OR LOWER(COALESCE(st.Description, '')) LIKE %s
                )
            """
            params.extend([search_pattern] * 6)

        # Por defecto solo se muestran estudios que tienen imágenes. La opción
        # "Incluir sin imágenes" habilita explícitamente ambos grupos.
        if not show_no_image:
            base_query += " AND COALESCE(e.isimage, 0) = 1"

        # Por defecto se muestran estudios con orden CP. Al activar
        # "Incluir sin orden CP" se incluyen ambos grupos.
        if not show_without_order:
            base_query += ' AND COALESCE(e."w-order", 0) = 1'

        if show_only_with_notes:
            base_query += """
                AND EXISTS (
                    SELECT 1
                    FROM nextris.tbexaminationnote n
                    WHERE n.examination_id = e.Guid
                )
            """

        if flag_filter:
            valid_flags = {'red', 'green', 'blue', 'yellow'}
            flag_filter = [flag for flag in flag_filter if flag in valid_flags]
            if flag_filter:
                base_query += " AND COALESCE(e.flags, ARRAY[]::text[]) && %s::text[]"
                params.append(flag_filter)

        # Los rangos representan el período reciente: desde ahora menos el
        # intervalo hasta el momento actual. Esto evita que "1d" incluya todo
        # el histórico anterior a hace un día.
        date_intervals = {
            '1d': '1 day',
            '3d': '3 days',
            '7d': '7 days',
            '14d': '14 days',
            '1m': '1 month',
            '2m': '2 months',
            '3m': '3 months',
            '1y': '1 year',
        }
        if date_range in date_intervals:
            date_column = 'e.reportdate' if date_field == 'reporte' else 'e.createdon'
            base_query += f" AND {date_column} BETWEEN CURRENT_TIMESTAMP - INTERVAL '{date_intervals[date_range]}' AND CURRENT_TIMESTAMP"
        
        # Aplicar filtro de modalidad por GUID
        if modality_ids:
            print(f"[FILTER] Aplicando filtro modality_id: {modality_ids}")
            modality_placeholders = ','.join(['%s'] * len(modality_ids))
            base_query += f" AND st.modality_id IN ({modality_placeholders})"
            params.extend(modality_ids)
        
        # Aplicar filtro de parte del cuerpo por GUID
        if body_part_id:
            print(f"[FILTER] Aplicando filtro body_part_id: {body_part_id}")
            base_query += " AND st.bodypart_id = %s"
            params.append(body_part_id)
        
        # Aplicar filtro de grupo de estudio
        if study_group_id:
            print(f"[FILTER] Aplicando filtro study_group_id: {study_group_id}")
            base_query += " AND st.studygroup_id = %s"
            params.append(study_group_id)

        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({base_query}) AS count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Query con paginación
        sort_columns = {
            'patient_name': 'patient_name',
            'patient_id': 'dp.patientid',
            'patient_dni': 'dp.nationalcode',
            'assignto_name': 'assignto_name',
            'study_type': 'st.Description',
            'status': 'e.Status',
            'admission_number': 'e.AdmisionNumber',
            'accession_number': 'e.LocalAcc',
            'created_on': 'e.CreatedOn',
            'is_reported': 'e.IsReported',
            'num_instances': 'num_instances',
            'report_date': 'e.reportdate',
            'template_name': 'resolved_template.template_name',
        }
        sort_expression = sort_columns.get(sort_column, 'e.CreatedOn')
        direction = 'ASC' if sort_direction == 'asc' else 'DESC'
        query = base_query + f"""
            ORDER BY {sort_expression} {direction}, e.CreatedOn DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
            'guid': str(row[0]),
            'patient_name': row[1] or '',
                'patient_id': row[2] or '',
                'patient_dni': row[3] or '',
                'study_type': row[4] or '',
                'admission_number': row[5] or '',
                'accession_number': row[6] or '',
                'created_on': _serialize_utc_datetime(row[7]),
                'status': row[8] or '',
                'is_reported': bool(row[9]),
                'is_executed': bool(row[10]),
                'is_image': bool(row[11]),
                'study_instance_uid': row[12] or '',
                'num_instances': row[13] or 0,
                'equipment': row[14] or '',
                'location': row[15] or '',
                'assigned_to': str(row[16]) if row[16] else None,
                'assignto_name': row[17] or '',
                'report_available': bool(row[18]),
                'modality_id': str(row[19]) if row[19] else None,
                'modality_description': row[20] or '',
                'study_group_id': str(row[21]) if row[21] else None,
                'study_group_description': row[22] or '',
                'bodypart_id': str(row[23]) if row[23] else None,
                'bodypart_description': row[24] or '',
                'blocked_by': str(row[25]) if row[25] else None,
                'blocked_by_name': row[26] or '',
                'report_date': row[27].isoformat() if row[27] else None,
                'flags': row[28] or [],
                'tag_ids': [str(value) for value in (row[29] or [])],
                'general_notes': row[30] or None,
                 'recent_notes': row[31] or [],
                 'notes_count': int(row[32] or 0),
                 'w_order': int(row[33] or 0),
                 'referring_physician_id': str(row[34]) if row[34] else None,
                 'requesting_physician_id': str(row[35]) if row[35] else None,
                 'clinical_question': row[36] or '',
                 'study_type_id': str(row[37]) if row[37] else None,
                 'requesting_physician_name': row[38] or '',
                 'other_details': row[39] or '',
                 'laterality_id': row[40] if row[40] else None,
                 'applied_template_id': str(row[41]) if row[41] else None,
                 'template_name': row[42] or '',
                 'template_source': row[43] or '',
                 'workflow_state': row[44] or 'pending',
                 # Los timestamps de workflow se almacenan como UTC naive.
                 # Exponerlos con offset evita que el navegador los interprete
                 # accidentalmente como hora local.
                 'workflow_state_at': _serialize_utc_datetime(row[45]),
                 'workflow_state_source': row[46] or None,
                 'workflow_state_user_id': str(row[47]) if row[47] else None,
                'cancellation_reason_code': row[48] or None,
                'cancellation_reason': row[49] or None,
                'study_date': row[50] or None,
                'study_time': row[51] or None,
                'arrival_time': row[52].isoformat() if row[52] else None,
             })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': results,
                'page': page,
                'per_page': per_page,
                'total': total
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/confirm-study', methods=['POST'])
@jwt_required()
@require_permission('worklist.confirm_execute', include_role_permissions=True)
def confirm_study(exam_id):
    """Confirma los datos clínicos mínimos de un estudio sin crear una orden."""
    connection = None
    cursor = None
    try:
        data = request.get_json(silent=True) or {}
        studytype_id = str(data.get('studytype_id') or '').strip()
        referring_physician_id = data.get('referring_physician_id') or None
        requesting_physician_id = data.get('requesting_physician_id') or None
        requesting_physician_name = str(data.get('requesting_physician_name') or '').strip() or None
        clinical_question = data.get('clinical_question')
        other_details = data.get('other_details')

        if not studytype_id:
            return jsonify({
                'success': False,
                'message': 'El tipo de estudio es obligatorio'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COALESCE(clinicaparque_workflow_state, 'pending'),
                   COALESCE(isreported, 0)
            FROM nextris.tbexamination WHERE guid = %s
            """,
            (exam_id,),
        )
        exam_state = cursor.fetchone()
        if not exam_state:
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        if exam_state[0] == 'already_read':
            return jsonify({'success': False, 'message': 'Este estudio ya fue leído en Info Parque y no puede modificarse', 'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE'}), 409
        if exam_state[0] == 'cancelled':
            return jsonify({'success': False, 'message': 'El estudio está cancelado y no puede modificarse', 'code': 'STUDY_CANCELLED'}), 409
        if exam_state[1]:
            return jsonify({'success': False, 'message': 'El estudio ya fue reportado y no puede modificarse', 'code': 'STUDY_ALREADY_REPORTED'}), 409

        cursor.execute(
            "SELECT 1 FROM nextris.isstudytype WHERE guid = %s",
            (studytype_id,),
        )
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'El tipo de estudio seleccionado no existe'
            }), 400

        if referring_physician_id:
            cursor.execute(
                "SELECT 1 FROM nextris.tbuser WHERE guid = %s",
                (referring_physician_id,),
            )
            if not cursor.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'El médico referente seleccionado no existe'
                }), 400

        if requesting_physician_id:
            cursor.execute(
                "SELECT 1 FROM nextris.isrequestingphysician WHERE guid = %s",
                (requesting_physician_id,),
            )
            if not cursor.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'El médico solicitante seleccionado no existe'
                }), 400

        cursor.execute(
            """
            UPDATE nextris.tbexamination
            SET isexecuted = 1,
                studytype_id = %s,
                idreferringphysician = %s,
                idrequestingphysician = %s,
                requestingphysician_name = %s,
                clinicalquestion = %s,
                othersdetails = %s
            WHERE guid = %s
            """,
            (
                studytype_id,
                referring_physician_id,
                requesting_physician_id,
                requesting_physician_name,
                clinical_question,
                other_details,
                exam_id,
            ),
        )
        connection.commit()

        return jsonify({
            'success': True,
            'message': 'Estudio confirmado correctamente'
        }), 200
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _workflow_action_error(error, action=None):
    if isinstance(error, LookupError):
        return jsonify({'success': False, 'message': str(error)}), 404
    if isinstance(error, (ValueError, TypeError)):
        return jsonify({'success': False, 'message': str(error)}), 400
    if isinstance(error, PermissionError):
        if action == WORKFLOW_CANCELLED and 'reportado' not in str(error).lower():
            code = 'STUDY_CANCELLED'
        elif action == WORKFLOW_ALREADY_READ and 'terminal' in str(error).lower():
            code = 'STUDY_ALREADY_READ_IN_INFOPARQUE'
        else:
            code = 'STUDY_ALREADY_REPORTED'
        return jsonify({'success': False, 'message': str(error), 'code': code}), 409
    return jsonify({'success': False, 'message': f'Error: {error}'}), 500


@api_blueprint.route('/config/cancellation-reasons', methods=['GET'])
@jwt_required()
def get_cancellation_reasons():
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**get_db_config())
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        include_inactive = request.args.get('include_inactive', '').lower() in ('1', 'true', 'yes')
        query = """
            SELECT guid, code, description, sort_order, active
            FROM nextris.clinicaparque_cancellation_reasons
        """
        if not include_inactive:
            query += " WHERE active = TRUE"
        query += " ORDER BY sort_order, description"
        cursor.execute(query)
        return jsonify({'success': True, 'data': [
            {'guid': str(row[0]), 'code': row[1], 'description': row[2],
             'sort_order': row[3], 'active': bool(row[4])}
            for row in cursor.fetchall()
        ]}), 200
    except Exception as error:
        return jsonify({'success': False, 'message': f'Error: {error}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@api_blueprint.route('/config/cancellation-reasons', methods=['POST'])
@jwt_required()
def create_cancellation_reason():
    connection = None
    cursor = None
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get('code') or '').strip().upper()
        description = str(data.get('description') or '').strip()
        if not code or not description:
            return jsonify({'success': False, 'message': 'code y description son obligatorios'}), 400
        connection = psycopg2.connect(**get_db_config())
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        active_value = data.get('active', True)
        if isinstance(active_value, str):
            active_value = active_value.strip().lower() in ('1', 'true', 'yes', 'on')
        cursor.execute(
            """
            INSERT INTO nextris.clinicaparque_cancellation_reasons
                (guid, code, description, sort_order, active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING guid, code, description, sort_order, active
            """,
            (str(uuid.uuid4()), code, description, int(data.get('sort_order') or 0),
             bool(active_value)),
        )
        row = cursor.fetchone()
        connection.commit()
        return jsonify({'success': True, 'data': {
            'guid': str(row[0]), 'code': row[1], 'description': row[2],
            'sort_order': row[3], 'active': bool(row[4]),
        }}), 201
    except psycopg2.errors.UniqueViolation:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': 'El código ya existe'}), 409
    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': f'Error: {error}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@api_blueprint.route('/config/cancellation-reasons/<reason_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def update_cancellation_reason(reason_id):
    connection = None
    cursor = None
    try:
        data = request.get_json(silent=True) or {}
        allowed = {'code', 'description', 'sort_order', 'active'}
        updates = [key for key in allowed if key in data]
        if not updates:
            return jsonify({'success': False, 'message': 'No hay campos para actualizar'}), 400
        connection = psycopg2.connect(**get_db_config())
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        assignments = []
        values = []
        for key in updates:
            column = key
            value = data[key]
            if key == 'code':
                value = str(value or '').strip().upper()
            elif key == 'description':
                value = str(value or '').strip()
            elif key == 'sort_order':
                value = int(value)
            elif key == 'active':
                if isinstance(value, str):
                    value = value.strip().lower() in ('1', 'true', 'yes', 'on')
                else:
                    value = bool(value)
            assignments.append(f'{column} = %s')
            values.append(value)
        assignments.append('updated_at = NOW()')
        values.append(reason_id)
        cursor.execute(
            f"UPDATE nextris.clinicaparque_cancellation_reasons SET {', '.join(assignments)} WHERE guid = %s RETURNING guid, code, description, sort_order, active",
            values,
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Motivo no encontrado'}), 404
        connection.commit()
        return jsonify({'success': True, 'data': {
            'guid': str(row[0]), 'code': row[1], 'description': row[2],
            'sort_order': row[3], 'active': bool(row[4]),
        }}), 200
    except (ValueError, TypeError):
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': 'sort_order inválido'}), 400
    except psycopg2.errors.UniqueViolation:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': 'El código ya existe'}), 409
    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': f'Error: {error}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _execute_local_workflow_action(exam_id, action):
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        actor = normalize_user_id(get_jwt_identity())
        if action == WORKFLOW_CANCELLED:
            data = request.get_json(silent=True) or {}
            result = apply_cancel(connection, exam_id, data.get('reason_code'),
                                  data.get('detail'), source='nextris_ui', user_id=actor)
        else:
            result = apply_already_read(connection, exam_id, source='nextris_ui',
                                        user_id=actor)
        connection.commit()
        return jsonify({'success': True, 'message':
                        'Estudio cancelado correctamente' if action == WORKFLOW_CANCELLED
                        else 'Estudio marcado como ya leído', 'data': result}), 200
    except Exception as error:
        if connection:
            connection.rollback()
        return _workflow_action_error(error, action)
    finally:
        if connection:
            connection.close()


@api_blueprint.route('/examinations/<exam_id>/cancel', methods=['POST'])
@jwt_required()
@require_permission('worklist.confirm_execute', include_role_permissions=True)
def cancel_examination_from_worklist(exam_id):
    return _execute_local_workflow_action(exam_id, WORKFLOW_CANCELLED)


@api_blueprint.route('/examinations/<exam_id>/already-read', methods=['POST'])
@jwt_required()
@require_permission('worklist.confirm_execute', include_role_permissions=True)
def mark_examination_already_read(exam_id):
    return _execute_local_workflow_action(exam_id, WORKFLOW_ALREADY_READ)


@api_blueprint.route('/examinations/<exam_id>/report', methods=['GET'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def get_examination_report(exam_id):
    """
    Obtiene los datos del reporte de un examen específico
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "exam_id": "uuid",
            "patient_id": "uuid",
            "patient_name": "nombre completo",
            "admission_number": "ADM001",
            "findings": "texto hallazgos",
            "impressions": "texto impresiones",
            "techniques": "texto técnicas",
            "conclusions": "texto conclusiones",
            "was_saved": true,
            "report_available": true,
            "updated_on": "datetime",
            "history": "historia clínica",
            "clinical_question": "pregunta clínica",
            "laterality_id": "uuid",
            "stat": "urgencia",
            "others_details": "otros detalles"
        }
    }
    
    Nota: Si was_saved es false, devuelve el informe predefinido del study type.
          Si no existe predefinido, devuelve los campos de informe en blanco.
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_applied_template_schema(connection)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT e.Guid, e.IdPatient, e.AdmisionNumber,
                   CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
                   e.studytype_id, e.history, e.clinicalquestion,
                   e.laterality_id, e.stat, e.othersdetails,
                   dp.Name as first_name,
                   dp.Surname as last_name,
                   EXTRACT(YEAR FROM AGE(CURRENT_DATE, dp.birthdate))::INTEGER as age,
                   dp.sexcode,
                   e.LocalAcc as accession_number,
                   e.StudyInstanceUID,
                   e.location_id,
                   loc.facility_id,
                   st.default_predef_id,
                   st.description as study_type_description,
                   mod.description as modality_description,
                   COALESCE(e.IsReported, 0) AS is_reported,
                   e.CreatedOn AS exam_date,
                   dp.patientid AS patient_identifier,
                   dp.nationalcode AS national_code,
                   st.modality_id,
                   COALESCE(e.clinicaparque_workflow_state, 'pending') AS workflow_state,
                   e.clinicaparque_workflow_state_at,
                   e.clinicaparque_workflow_state_source,
                   e.clinicaparque_cancellation_detail
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
           LEFT JOIN nextris.tblocation loc ON e.location_id = loc.guid
           LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
           LEFT JOIN nextris.ismodality mod ON st.modality_id = mod.guid
            WHERE e.Guid = %s
            """,
            (exam_id,),
        )

        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        current_user_id = normalize_user_id(get_jwt_identity())
        exam_guid = exam[0]
        patient_id = exam[1]
        admission_number = exam[2]
        patient_name = exam[3]
        study_type_id = exam[4]
        history = exam[5]
        clinical_question = exam[6]
        laterality_id = exam[7]
        stat = exam[8]
        others_details = exam[9]
        first_name = exam[10]
        last_name = exam[11]
        age = exam[12]
        sex = exam[13]
        accession_number = exam[14]
        study_instance_uid = exam[15]
        location_id = exam[16]
        facility_id = exam[17]
        default_predef_id = exam[18]
        study_type_description = exam[19]
        modality_description = exam[20]
        is_reported = bool(exam[21])
        exam_date = exam[22]
        patient_identifier = exam[23]
        national_code = exam[24]
        modality_id = exam[25]
        workflow_state = exam[26] or 'pending'
        workflow_state_at = exam[27]
        workflow_state_source = exam[28]
        workflow_detail = exam[29]

        cursor.execute(
            """
            SELECT r.Guid, r.idexamination, r.idpatient, r.admnumber,
                   r.study_reason, r.content, r.conclusion,
                   r.findings, r.impressions, r.techniques, r.conclusions,
                   r.wassaved, r.date, r.applied_template_id
            FROM nextris.tbreport r
            WHERE r.IdExamination = %s
            """,
            (exam_id,),
        )
        report = cursor.fetchone()

        examination_reason = clinical_question or history or ''
        study_reason = examination_reason
        content = ''
        conclusion = ''
        was_saved = False
        report_guid = None
        report_available = False
        updated_on = None
        selected_template_id = None
        selected_template_report_type = None
        selected_template_name = None
        ensure_user_default_schema(connection)

        if report:
            was_saved = bool(report[11])
            report_guid = report[0]
            report_available = is_reported
            updated_on = report[12]
            selected_template_id = str(report[13]) if report[13] else None

            if was_saved:
                fields = canonical_fields_from_row(
                    report[4], report[5], report[6],
                    legacy_findings=report[7],
                    legacy_impressions=report[8],
                    legacy_technique=report[9],
                    legacy_conclusion=report[10],
                    reason_fallback=clinical_question or history,
                )
                study_reason = fields['study_reason']
                content = fields['content']
                conclusion = fields['conclusion']
            else:
                ensure_report_type_schema(connection)
                ensure_template_location_schema(connection)
                structured_enabled = _is_structured_reports_enabled(cursor, facility_id)
                effective_template = _select_predefined_template_for_exam(
                    cursor,
                    study_type_id,
                    location_id,
                    structured_enabled,
                    default_predef_id,
                    current_user_id,
                )
                if effective_template:
                    study_reason = merge_template_study_reason(
                        effective_template['study_reason'],
                        examination_reason,
                    )
                    content = effective_template['content']
                    conclusion = effective_template['conclusion']
                    selected_template_id = effective_template['template_id']
                    selected_template_report_type = effective_template['report_type']
        elif study_type_id and workflow_state == 'pending':
            ensure_report_type_schema(connection)
            ensure_template_location_schema(connection)
            structured_enabled = _is_structured_reports_enabled(cursor, facility_id)
            effective_template = _select_predefined_template_for_exam(
                cursor,
                study_type_id,
                location_id,
                structured_enabled,
                default_predef_id,
                current_user_id,
            )
            if effective_template:
                study_reason = merge_template_study_reason(
                    effective_template['study_reason'],
                    examination_reason,
                )
                content = effective_template['content']
                conclusion = effective_template['conclusion']
                selected_template_id = effective_template['template_id']
                selected_template_report_type = effective_template['report_type']

        structured_enabled = _is_structured_reports_enabled(cursor, facility_id)

        if selected_template_id:
            cursor.execute(
                "SELECT tittle FROM nextris.tbinfpredef WHERE guid = %s LIMIT 1",
                (selected_template_id,),
            )
            selected_template_row = cursor.fetchone()
            selected_template_name = selected_template_row[0] if selected_template_row else None

        debug_requested = request.args.get('debug_sr', '').strip().lower() in ('1', 'true', 'yes')
        debug_before = {
            'study_reason': _collect_placeholder_candidates(study_reason),
            'content': _collect_placeholder_candidates(content),
            'conclusion': _collect_placeholder_candidates(conclusion),
        } if debug_requested else None

        sr_variable_values = _get_sr_variable_values(cursor, study_instance_uid)
        sr_variables_list = _build_sr_variables_list(sr_variable_values)
        sr_parser_context = _get_sr_parser_context(cursor, study_instance_uid)
        sr_variable_tree = _build_sr_variable_tree(
            cursor,
            (sr_parser_context or {}).get('parser_family'),
            sr_variable_values,
            study_instance_uid,
        )
        study_reason = _replace_sr_placeholders(study_reason, sr_variable_values)
        content = _replace_sr_placeholders(content, sr_variable_values)
        conclusion = _replace_sr_placeholders(conclusion, sr_variable_values)

        debug_after = {
            'study_reason': _collect_placeholder_candidates(study_reason),
            'content': _collect_placeholder_candidates(content),
            'conclusion': _collect_placeholder_candidates(conclusion),
        } if debug_requested else None

        cursor.close()
        connection.close()

        response_payload = {
            'success': True,
            'data': {
                'guid': str(report_guid) if report_guid else None,
                'exam_id': str(exam_guid),
                'patient_id': str(patient_id) if patient_id else None,
                'admission_number': admission_number or '',
                'study_type_id': str(study_type_id) if study_type_id else None,
                'study_type_description': study_type_description or '',
                'modality_id': str(modality_id) if modality_id else None,
                'modality_description': modality_description or '',
                'location_id': str(location_id) if location_id else None,
                'facility_id': str(facility_id) if facility_id else None,
                'structured_reports_enabled': bool(structured_enabled),
                'applied_template_id': selected_template_id,
                'applied_template_name': selected_template_name,
                'applied_template_report_type': selected_template_report_type,
                'accession_number': accession_number or '',
                'exam_date': exam_date.isoformat() if exam_date else None,
                'patientid': patient_identifier or '',
                'national_code': national_code or '',
                'patient_name': patient_name or '',
                'first_name': first_name or '',
                'last_name': last_name or '',
                'age': age,
                'sex': sex or '',
                'study_reason': study_reason,
                'content': content,
                'conclusion': conclusion,
                **legacy_aliases({
                    'content': content,
                    'conclusion': conclusion,
                }),
                'was_saved': was_saved,
                'report_available': report_available,
                'workflow_state': workflow_state,
                'workflow_state_at': _serialize_utc_datetime(workflow_state_at),
                'workflow_state_source': workflow_state_source,
                'workflow_detail': workflow_detail or '',
                'report_read_only': workflow_state in ('cancelled', 'already_read'),
                'updated_on': updated_on.isoformat() if updated_on else None,
                'history': history or '',
                'clinical_question': clinical_question or '',
                'laterality_id': str(laterality_id) if laterality_id else None,
                'stat': stat or '',
                'others_details': others_details or '',
                'sr_variables': sr_variables_list,
                'sr_parser_manifest_id': (sr_parser_context or {}).get('parser_manifest_id'),
                'sr_parser_name': (sr_parser_context or {}).get('parser_name'),
                'sr_parser_version': (sr_parser_context or {}).get('parser_version'),
                'sr_parser_family': (sr_parser_context or {}).get('parser_family'),
                'sr_document_status': (sr_parser_context or {}).get('status'),
                'sr_variable_tree': sr_variable_tree,
            }
        }

        if debug_requested:
            response_payload['debug_sr'] = {
                'study_instance_uid': study_instance_uid,
                'sr_variable_keys_count': len(sr_variable_values.keys()),
                'sr_variable_keys_sample': sorted(list(sr_variable_values.keys()))[:80],
                'placeholders_before': debug_before,
                'placeholders_after': debug_after,
            }

        return jsonify(response_payload), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/report', methods=['PUT', 'PATCH'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def update_examination_report(exam_id):
    """
    Actualiza o crea el reporte de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "findings": "texto hallazgos" (optional),
        "impressions": "texto impresiones" (optional),
        "techniques": "texto técnicas" (optional),
        "conclusions": "texto conclusiones" (optional),
        "mark_as_reported": false (optional, default: false)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte actualizado exitosamente",
        "data": {
            "report_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json() or {}
        
        normalized = normalize_report_payload(data)
        if 'study_reason' not in normalized and 'history' in data:
            normalized['study_reason'] = data.get('history') or ''
        study_reason = normalized.get('study_reason')
        content = normalized.get('content')
        conclusion = normalized.get('conclusion')
        applied_template_id = data.get('template_id', data.get('applied_template_id'))
        if applied_template_id is not None:
            applied_template_id = str(applied_template_id).strip() or None
        mark_as_reported = data.get('mark_as_reported', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        ensure_applied_template_schema(connection)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        # Verificar que el examen existe
        cursor.execute("""
            SELECT e.IdPatient,
                   e.AdmisionNumber,
                   COALESCE(e.IsReported, 0) AS is_reported,
                   COALESCE(e.clinicaparque_workflow_state, 'pending') AS workflow_state
            FROM nextris.tbexamination e
            WHERE e.Guid = %s
        """, (exam_id,))
        
        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        patient_id = exam[0]
        admission_number = exam[1]
        already_reported = bool(exam[2])
        workflow_state = exam[3] or 'pending'
        if workflow_state == 'already_read':
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Este estudio ya fue leído en Info Parque y no puede redactarse en NextRIS',
                'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE',
            }), 409
        if workflow_state == 'cancelled':
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El estudio está cancelado y no puede redactarse',
                'code': 'STUDY_CANCELLED',
            }), 409
        
        # Verificar si ya existe un reporte
        cursor.execute("""
            SELECT Guid FROM nextris.tbreport
            WHERE IdExamination = %s
        """, (exam_id,))
        
        existing_report = cursor.fetchone()
        
        if existing_report:
            # Actualizar reporte existente
            report_id = existing_report[0]
            
            updates = []
            params = []
            
            if study_reason is not None:
                updates.append("study_reason = %s")
                params.append(study_reason)
            if content is not None:
                updates.append("content = %s")
                params.append(content)
            if conclusion is not None:
                updates.append("conclusion = %s")
                params.append(conclusion)
            if applied_template_id is not None:
                updates.append("applied_template_id = %s")
                params.append(applied_template_id)
            
            updates.append("WasSaved = true")
            updates.append("Date = NOW()")
            
            if updates:
                params.append(report_id)
                update_query = f"""
                    UPDATE nextris.tbreport
                    SET {', '.join(updates)}
                    WHERE Guid = %s
                """
                cursor.execute(update_query, params)
        else:
            # Crear nuevo reporte
            report_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO nextris.tbreport (
                    Guid, IdExamination, IdPatient, admnumber,
                    study_reason, content, conclusion,
                    applied_template_id,
                    WasSaved, CreatedOn, Date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, true, NOW(), NOW()
                )
            """, (
                report_id, exam_id, patient_id, admission_number,
                study_reason if study_reason is not None else '',
                content if content is not None else '',
                conclusion if conclusion is not None else '',
                applied_template_id,
            ))
        
        # Marcar examen como reportado si se solicita
        if mark_as_reported:
            cursor.execute("""
                UPDATE nextris.tbexamination
                SET IsReported = 1
                WHERE Guid = %s
            """, (exam_id,))

        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte actualizado exitosamente',
            'data': {
                'report_id': str(report_id)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes', methods=['GET'])
@jwt_required()
def get_examination_notes(exam_id):
    """
    Obtiene las notas clínicas de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "data": {
            "history": "historia clínica",
            "clinical_question": "pregunta clínica",
            "others_details": "otros detalles",
            "number_of_views": "número de vistas",
            "laterality": "lateralidad",
            "stat": "urgencia"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT e.history, e.clinicalquestion, e.othersdetails,
                   e.numberofviews, e.stat, l.Description as laterality
            FROM nextris.tbexamination e
            LEFT JOIN nextris.islaterality l ON e.laterality_id = l.Guid
            WHERE e.Guid = %s
        """, (exam_id,))
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        cursor.execute("""
            SELECT guid, author_id, author_username, author_display_name,
                   message, created_on
            FROM nextris.tbexaminationnote
            WHERE examination_id = %s
            ORDER BY created_on DESC, guid DESC
        """, (exam_id,))
        notes = [_serialize_examination_note(row) for row in cursor.fetchall()]

        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'history': result[0] or '',
                'clinical_question': result[1] or '',
                'others_details': result[2] or '',
                'number_of_views': result[3] or '',
                'stat': result[4] or '',
                'laterality': result[5] or '',
                'notes': notes
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes', methods=['POST'])
@jwt_required()
def create_examination_note(exam_id):
    """Append an immutable note to an examination."""
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message')
        if not isinstance(message, str) or not message.strip():
            return jsonify({
                'success': False,
                'message': 'El mensaje de la nota no puede estar vacío'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT Guid FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        author_id, author_username, author_display_name = _resolve_examination_note_author(cursor)
        clean_message = message.strip()
        cursor.execute("""
            INSERT INTO nextris.tbexaminationnote (
                guid, examination_id, author_id, author_username,
                author_display_name, message
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING guid, author_id, author_username, author_display_name,
                      message, created_on
        """, (
            str(uuid.uuid4()), exam_id, author_id, author_username,
            author_display_name, clean_message
        ))
        note = _serialize_examination_note(cursor.fetchone())
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Nota guardada',
            'data': note
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes/<note_id>', methods=['DELETE'])
@jwt_required()
@require_permission('reports.notes.delete', include_role_permissions=True)
def delete_examination_note(exam_id, note_id):
    """Delete one examination note when the authenticated user has permission."""
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("""
            DELETE FROM nextris.tbexaminationnote
            WHERE guid = %s AND examination_id = %s
            RETURNING guid
        """, (note_id, exam_id))
        deleted = cursor.fetchone()

        if not deleted:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Nota no encontrada'
            }), 404

        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({
            'success': True,
            'message': 'Nota eliminada'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes', methods=['PUT', 'PATCH'])
@jwt_required()
def update_examination_notes(exam_id):
    """
    Actualiza las notas clínicas de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "history": "historia clínica" (optional),
        "clinical_question": "pregunta clínica" (optional),
        "others_details": "otros detalles" (optional),
        "number_of_views": "número de vistas" (optional),
        "laterality_id": "uuid lateralidad" (optional),
        "stat": "urgencia" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Notas actualizadas exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el examen existe
        cursor.execute("""
            SELECT Guid FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'history' in data:
            updates.append("history = %s")
            params.append(data['history'])
        if 'clinical_question' in data:
            updates.append("clinicalquestion = %s")
            params.append(data['clinical_question'])
        if 'others_details' in data:
            updates.append("othersdetails = %s")
            params.append(data['others_details'])
        if 'number_of_views' in data:
            updates.append("numberofviews = %s")
            params.append(data['number_of_views'])
        if 'laterality_id' in data:
            updates.append("laterality_id = %s")
            params.append(data['laterality_id'])
        if 'stat' in data:
            updates.append("stat = %s")
            params.append(data['stat'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(exam_id)
        update_query = f"""
            UPDATE nextris.tbexamination
            SET {', '.join(updates)}
            WHERE Guid = %s
        """
        
        cursor.execute(update_query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Notas actualizadas exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# ENDPOINTS EXISTENTES DE PLANTILLAS
# ====================================================================


@jwt_required()
def get_report_template(template_id):
    """
    Obtiene los textos de una plantilla de reporte
    
    Path:
    - template_id: GUID de la plantilla
    
    Returns:
    {
        "success": true,
        "data": {
            "report": "Contenido de la plantilla"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        cursor.execute("SELECT report FROM nextris.isreporttemplate WHERE guid=%s", (template_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            fields = canonical_fields_from_row(
                result[2], result[3], result[4],
                legacy_findings=result[5], legacy_impressions=result[6],
                legacy_technique=result[7], legacy_conclusion=result[4],
            )
            return jsonify({
                'success': True,
                'data': {
                    'report': result[0] or ''
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/study-types/<study_type_id>/default-template', methods=['GET'])
@jwt_required()
def get_default_template_for_study_type(study_type_id):
    """
    Obtiene el ID de plantilla predefinida por defecto para un tipo de estudio
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Returns:
    {
        "success": true,
        "data": {
            "default_template_id": "uuid"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        cursor.execute("SELECT default_predef_id FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'default_template_id': result[0] if result and result[0] else None
            }
        }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['GET'])
@jwt_required()
def get_predefined_reports():
    """
    Obtiene lista de todos los reportes predefinidos
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "title": "Título",
                "study_type": "Descripción del tipo de estudio"
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT ip.guid, ip.tittle, ist.description
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            ORDER BY ip.tittle ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        predefined = []
        for row in results:
            predefined.append({
                'guid': row[0],
                'title': row[1] or '',
                'study_type': row[2] or ''
            })
        
        return jsonify({
            'success': True,
            'data': predefined
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['GET'])
@jwt_required()
def get_predefined_report(predef_id):
    """
    Obtiene datos de un reporte predefinido específico
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "title": "Título",
            "findings": "Hallazgos",
            "impression": "Impresión",
            "technique": "Técnica",
            "conclusion": "Conclusión",
            "study_type_id": "uuid"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, tittle, study_reason, content, conclusion,
                   findings, impression, technique, studytype_id
            FROM nextris.tbinfpredef 
            WHERE guid=%s
        """
        
        cursor.execute(query, (predef_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'guid': result[0],
                    'title': result[1] or '',
                    **fields,
                    **legacy_aliases(fields),
                    'study_type_id': result[8],
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['POST'])
@jwt_required()
def create_predefined_report():
    """
    Crea un nuevo reporte predefinido
    
    Body JSON:
    {
        "title": "string" (required),
        "study_type_id": "uuid" (required),
        "findings": "string" (optional),
        "technique": "string" (optional),
        "impression": "string" (optional),
        "conclusion": "string" (optional),
        "is_default": boolean (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido creado exitosamente",
        "data": {
            "predef_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        title = data.get('title')
        study_type_id = data.get('study_type_id')
        
        if not title or not study_type_id:
            return jsonify({
                'success': False,
                'message': 'title y study_type_id son campos requeridos'
            }), 400
        
        normalized = normalize_report_payload(data)
        study_reason = normalized.get('study_reason', '')
        content = normalized.get('content', '')
        conclusion = normalized.get('conclusion', '')
        is_default = data.get('is_default', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Si este debe ser el predefinido por defecto, actualizar el tipo de estudio
        if is_default:
            update_query = "UPDATE nextris.isstudytype SET default_predef_id=%s WHERE guid=%s"
            cursor.execute(update_query, (new_guid, study_type_id))
        
        # Insertar el nuevo predefinido
        insert_query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, study_reason, content, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            new_guid, title, study_reason, content, conclusion, study_type_id
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido creado exitosamente',
            'data': {
                'predef_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def update_predefined_report(predef_id):
    """
    Actualiza un reporte predefinido existente
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Body JSON (todos opcionales): ``title``, ``study_reason``, ``content`` y
    ``conclusion``. Los nombres legacy siguen siendo aceptados.
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido actualizado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbinfpredef WHERE guid=%s", (predef_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
        
        # Construir query dinámicamente. Sólo se escriben los campos canónicos;
        # las columnas antiguas se conservan como fallback de solo lectura.
        updates = []
        params = []
        
        if 'title' in data:
            updates.append("tittle = %s")
            params.append(data['title'])
        normalized = normalize_report_payload(data)
        for key in ('study_reason', 'content', 'conclusion'):
            if key in normalized:
                updates.append(f"{key} = %s")
                params.append(normalized[key])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(predef_id)
        query = f"UPDATE nextris.tbinfpredef SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>', methods=['PATCH', 'PUT'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def save_report(exam_id):
    """
    Guarda o actualiza los datos de un reporte médico
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "findings": "string" (required),
        "techniques": "string" (required),
        "impressions": "string" (required),
        "conclusions": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte guardado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        normalized = normalize_report_payload(data)
        if any(key not in normalized for key in ('study_reason', 'content', 'conclusion')):
            return jsonify({
                'success': False,
                'message': 'study_reason, content y conclusion son campos requeridos'
            }), 400

        study_reason = normalized['study_reason']
        content = normalized['content']
        conclusion = normalized['conclusion']
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COALESCE(clinicaparque_workflow_state, 'pending')
            FROM nextris.tbexamination WHERE guid = %s
            """,
            (exam_id,),
        )
        workflow = cursor.fetchone()
        if not workflow:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404
        if workflow[0] == 'already_read':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Este estudio ya fue leído en Info Parque y no puede redactarse en NextRIS', 'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE'}), 409
        if workflow[0] == 'cancelled':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'El estudio está cancelado y no puede redactarse', 'code': 'STUDY_CANCELLED'}), 409
        
        query = """
            UPDATE nextris.tbreport 
            SET study_reason=%s, content=%s, conclusion=%s, wassaved=true
            WHERE idexamination=%s
        """
        
        cursor.execute(query, (study_reason, content, conclusion, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte guardado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/next-exam', methods=['POST'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def get_next_exam():
    """
    Obtiene el siguiente examen disponible basado en los filtros configurados
    
    Body JSON:
    {
        "current_exam_id": "uuid",
        "show_ready": true/false,
        "show_reported": true/false,
        "assigned_to_me": true/false,
        "modality_id": "uuid o uuids separados por coma" (optional),
        "body_part_id": "uuid" (optional),
        "study_group_id": "uuid" (optional)
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "study_instance_uid": "...",
            "patient_name": "...",
            ...
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json(force=True, silent=True) or {}
        
        current_exam_id = data.get('current_exam_id')
        if not current_exam_id:
            return jsonify({
                'success': False,
                'message': 'Se requiere current_exam_id para obtener el siguiente examen'
            }), 400

        def as_bool(value, default=False):
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {'true', '1', 'on', 'yes'}

        show_ready = as_bool(data.get('show_ready'), True)
        show_reported = as_bool(data.get('show_reported'), False)
        assigned_to_me = as_bool(data.get('assigned_to_me'), False)
        show_no_image = as_bool(data.get('show_no_image'), False)
        show_without_order = as_bool(data.get('show_without_order'), False)
        sort_direction = 'desc' if str(data.get('sort_direction', 'asc')).lower() == 'desc' else 'asc'
        modality_ids = parse_filter_values(data.get('modality_id'))
        body_part_id = data.get('body_part_id')
        study_group_id = data.get('study_group_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        
        # Obtener la fecha de creación del examen actual para buscar el siguiente
        cursor.execute("""
            SELECT CreatedOn,
                   COALESCE(clinicaparque_workflow_state, 'pending'),
                   COALESCE(isreported, 0)
            FROM nextris.tbexamination WHERE Guid = %s
        """, (current_exam_id,))
        current_exam = cursor.fetchone()
        current_created_on = current_exam[0] if current_exam else None
        if current_exam and current_exam[1] == 'already_read':
            cursor.close(); connection.close()
            return jsonify({'success': False, 'message': 'Este estudio ya fue leído en Info Parque y no puede seleccionar el siguiente examen', 'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE'}), 409
        if current_exam and current_exam[1] == 'cancelled':
            cursor.close(); connection.close()
            return jsonify({'success': False, 'message': 'El estudio está cancelado y no puede seleccionar el siguiente examen', 'code': 'STUDY_CANCELLED'}), 409
        
        # Aplicar el mismo filtro de reportado que en la lista
        if show_reported and show_ready:
            reported_filter = ""
        elif show_reported:
            reported_filter = "AND (e.IsReported = 1 OR e.clinicaparque_workflow_state IN ('cancelled', 'already_read'))"
        elif show_ready:
            reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0) AND COALESCE(e.clinicaparque_workflow_state, 'pending') = 'pending'"
        else:
            reported_filter = "AND 1=0"
        
        # Query para obtener el siguiente examen
        query = f"""
            SELECT e.Guid, 
                   e.studyinstanceuid,
                   CONCAT_WS(', ', NULLIF(TRIM(dp.Surname), ''), NULLIF(TRIM(dp.Name), '')) as patient_name,
                   dp.nationalcode,
                   st.Description as study_type,
                   e.LocalAcc,
                   COALESCE(e.IsReported, 0) as is_reported
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON COALESCE(e.location_id, eq.location_id) = loc.guid
            WHERE e.Guid != %s
            AND (e.blockby IS NULL OR e.blockby::text = %s)
            {reported_filter}
        """
        
        params = [current_exam_id, str(user_id)]

        if not show_no_image:
            query += ' AND COALESCE(e.isimage, 0) = 1'

        if not show_without_order:
            query += ' AND COALESCE(e."w-order", 0) = 1'
        
        # Aplicar filtro de asignación
        if assigned_to_me:
            query += " AND e.assignto = %s"
            params.append(user_id)
        
        # Aplicar filtros adicionales
        if modality_ids:
            modality_placeholders = ','.join(['%s'] * len(modality_ids))
            query += f" AND st.modality_id IN ({modality_placeholders})"
            params.extend(modality_ids)
        
        if body_part_id:
            query += " AND st.bodypart_id = %s"
            params.append(body_part_id)
        
        if study_group_id:
            query += " AND st.studygroup_id = %s"
            params.append(study_group_id)

        # Seguir la misma dirección que la lista de Redacción. La lista por
        # defecto es ascendente; en ese caso el siguiente es posterior al
        # examen actual. Con descendente se busca el anterior.
        if current_created_on:
            if sort_direction == 'desc':
                query += " AND (e.CreatedOn < %s OR (e.CreatedOn = %s AND e.Guid::text < %s))"
            else:
                query += " AND (e.CreatedOn > %s OR (e.CreatedOn = %s AND e.Guid::text > %s))"
            params.extend([current_created_on, current_created_on, str(current_exam_id)])
        
        query += f" ORDER BY e.CreatedOn {sort_direction.upper()}, e.Guid {sort_direction.upper()} LIMIT 1"
        
        cursor.execute(query, params)
        next_exam = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if next_exam:
            return jsonify({
                'success': True,
                'data': {
                    'guid': str(next_exam[0]),
                    'study_instance_uid': next_exam[1] or '',
                    'patient_name': next_exam[2] or '',
                    'patient_dni': next_exam[3] or '',
                    'study_type': next_exam[4] or '',
                    'accession_number': next_exam[5] or '',
                    'is_reported': bool(next_exam[6])
                }
            }), 200
        else:
            return jsonify({
                'success': True,
                'data': None,
                'message': 'No hay más exámenes disponibles'
            }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/sign', methods=['POST'])
@jwt_required()
@require_permission('reports.sign', include_role_permissions=True)
def sign_report(exam_id):
    """
    Firma un reporte médico (marca como reportado) y opcionalmente devuelve el siguiente examen
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON (opcional):
    {
        "reporter_physician_id": "uuid" (opcional, se usa JWT identity si no se provee),
        "get_next": true/false (opcional, default: false),
        "show_ready": true/false (opcional, para obtener siguiente),
        "show_reported": true/false (opcional, para obtener siguiente),
        "assigned_to_me": true/false (opcional, para obtener siguiente),
        "modality_id": "uuid o uuids separados por coma" (opcional, para filtrar siguiente),
        "body_part_id": "uuid" (opcional, para filtrar siguiente),
        "study_group_id": "uuid" (opcional, para filtrar siguiente)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte firmado exitosamente",
        "next_exam": {
            "guid": "uuid",
            "study_instance_uid": "...",
            ...
        } (opcional, solo si get_next=true)
    }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        
        # Obtener ID del médico que firma
        reporter_physician_id = data.get('reporter_physician_id')
        if not reporter_physician_id:
            # Usar el ID del usuario autenticado
            reporter_physician_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        # Obtener datos del examen para el nombre del PDF
        cursor.execute("""
            SELECT e.LocalAcc,
                   p.PatientId,
                   p.Name,
                   p.Surname,
                   e.IdPatient,
                   COALESCE(e.IsReported, 0) AS is_reported,
                   COALESCE(e.clinicaparque_workflow_state, 'pending') AS workflow_state
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON e.IdPatient = p.Guid
            WHERE e.Guid = %s
        """, (exam_id,))
        
        exam_data = cursor.fetchone()
        if not exam_data:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Examen no encontrado: {exam_id}'
            }), 404
        
        accession_number, patient_id, patient_name, patient_surname, patient_guid, is_reported, workflow_state = exam_data
        if workflow_state == 'already_read':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Este estudio ya fue leído en Info Parque y no puede redactarse en NextRIS', 'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE'}), 409
        if workflow_state == 'cancelled':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'El estudio está cancelado y no puede redactarse', 'code': 'STUDY_CANCELLED'}), 409
        already_reported = bool(is_reported)
        
        # Verificar si existe el reporte, si no, crearlo.
        cursor.execute("SELECT guid FROM nextris.tbreport WHERE idexamination = %s", (exam_id,))
        report_exists = cursor.fetchone()

        if report_exists:
            cursor.execute(
                """
                SELECT r.study_reason, r.content, r.conclusion,
                       r.findings, r.impressions, r.techniques, r.conclusions,
                       e.clinicalquestion, e.history
                FROM nextris.tbreport r
                JOIN nextris.tbexamination e ON e.guid = r.idexamination
                WHERE r.idexamination = %s
                LIMIT 1
                """,
                (exam_id,),
            )
            report_fields_row = cursor.fetchone()
            report_fields = canonical_fields_from_row(
                report_fields_row[0], report_fields_row[1], report_fields_row[2],
                legacy_findings=report_fields_row[3],
                legacy_impressions=report_fields_row[4],
                legacy_technique=report_fields_row[5],
                legacy_conclusion=report_fields_row[6],
                reason_fallback=(report_fields_row[7] or report_fields_row[8]) if report_fields_row else '',
            ) if report_fields_row else {'study_reason': '', 'content': '', 'conclusion': ''}
        else:
            report_fields = {'study_reason': '', 'content': '', 'conclusion': ''}

        if not fields_are_complete(report_fields):
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Razón del estudio, contenido y conclusión son obligatorios para firmar el informe',
                'code': 'REPORT_FIELDS_REQUIRED',
            }), 400

        if not report_exists:
            report_guid = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO nextris.tbreport (
                    guid, idexamination, idpatient, admnumber,
                    wassaved, createdon, date, iduser
                ) VALUES (
                    %s, %s, %s, %s, true, NOW(), NOW(), %s
                )
            """, (report_guid, exam_id, patient_guid, accession_number, reporter_physician_id))
        else:
            cursor.execute("""
                UPDATE nextris.tbreport
                SET iduser = %s
                WHERE idexamination = %s
            """, (reporter_physician_id, exam_id))

        # Firmar sólo modifica el estado clínico. El PDF se renderiza bajo demanda.
        query = """
            UPDATE nextris.tbexamination
            SET IsReported=1, assignto=%s, reportdate=CURRENT_TIMESTAMP
            WHERE Guid=%s
        """
        cursor.execute(query, (reporter_physician_id, exam_id))

        if cursor.rowcount == 0:
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Examen no encontrado: {exam_id}'
            }), 404

        # Queue the external transmission in the same transaction as the
        # signature. The queue worker will send it after the configured delay.
        from apps.services.clinicaparque_report_queue import enqueue_report_send
        report_send_schedule = enqueue_report_send(exam_id, connection=connection)

        connection.commit()

        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except Exception:
            pass
        
        # Obtener el siguiente examen si se solicita
        next_exam = None
        get_next = data.get('get_next', False)
        
        if get_next:
            try:
                show_ready = data.get('show_ready', True)
                show_reported = data.get('show_reported', False)
                assigned_to_me = data.get('assigned_to_me', False)
                modality_ids = parse_filter_values(data.get('modality_id'))
                body_part_id = data.get('body_part_id')
                study_group_id = data.get('study_group_id')

                # El flujo de reportes es global: la ubicación y la facility
                # son datos informativos y no limitan el siguiente estudio.
                cursor.execute("""
                    SELECT CreatedOn FROM nextris.tbexamination WHERE Guid = %s
                """, (exam_id,))
                current_exam = cursor.fetchone()
                current_created_on = current_exam[0] if current_exam else None

                if show_reported and show_ready:
                    reported_filter = ""
                elif show_reported:
                    reported_filter = "AND (e.IsReported = 1 OR e.clinicaparque_workflow_state IN ('cancelled', 'already_read'))"
                elif show_ready:
                    reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0) AND COALESCE(e.clinicaparque_workflow_state, 'pending') = 'pending'"
                else:
                    reported_filter = "AND 1=0"

                query = f"""
                    SELECT e.Guid,
                           e.studyinstanceuid,
                           CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
                           dp.nationalcode,
                           st.Description as study_type,
                           e.LocalAcc,
                           COALESCE(e.IsReported, 0) as is_reported
                    FROM nextris.tbexamination e
                    LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
                    LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
                    WHERE e.Guid != %s
                    {reported_filter}
                """

                params = [exam_id]

                if assigned_to_me:
                    query += " AND e.assignto = %s"
                    params.append(reporter_physician_id)

                if modality_ids:
                    modality_placeholders = ','.join(['%s'] * len(modality_ids))
                    query += f" AND st.modality_id IN ({modality_placeholders})"
                    params.extend(modality_ids)

                if body_part_id:
                    query += " AND st.bodypart_id = %s"
                    params.append(body_part_id)

                if study_group_id:
                    query += " AND st.studygroup_id = %s"
                    params.append(study_group_id)

                if current_created_on:
                    query += " AND e.CreatedOn <= %s"
                    params.append(current_created_on)

                query += " ORDER BY e.CreatedOn DESC LIMIT 1"

                cursor.execute(query, params)
                next_exam_row = cursor.fetchone()

                if next_exam_row:
                    next_exam = {
                        'guid': str(next_exam_row[0]),
                        'study_instance_uid': next_exam_row[1] or '',
                        'patient_name': next_exam_row[2] or '',
                        'patient_dni': next_exam_row[3] or '',
                        'study_type': next_exam_row[4] or '',
                        'accession_number': next_exam_row[5] or '',
                        'is_reported': bool(next_exam_row[6])
                    }
            except Exception as next_error:
                print(f"[SIGN] Error al obtener siguiente examen: {str(next_error)}")
                # No fallar si hay error al obtener el siguiente, solo loguearlo
        
        # Cerrar conexión
        cursor.close()
        connection.close()

        response_data = {
            'success': True,
            'message': 'Reporte firmado exitosamente',
            'report_send': {
                'scheduled': True,
                'delay_minutes': report_send_schedule['delay_minutes'],
                'scheduled_at': report_send_schedule['scheduled_at'],
            },
        }

        if next_exam:
            response_data['next_exam'] = next_exam

        return jsonify(response_data), 200
        
    except psycopg2.Error as db_error:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error de base de datos: {str(db_error)}'
        }), 500
    except Exception as e:
        print(f"[SIGN ERROR] Error inesperado al firmar reporte: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/verify-credentials', methods=['POST'])
@jwt_required()
def verify_credentials():
    """
    Compatibilidad con clientes anteriores. La sesión JWT y el permiso
    reports.sign son suficientes; la firma no requiere reingresar contraseña.
    """
    return jsonify({
        'success': True,
        'message': 'Verificación de contraseña omitida'
    }), 200


@api_blueprint.route('/reports/<exam_id>/unsign', methods=['POST'])
@jwt_required()
@require_permission('reports.unsign', include_role_permissions=True)
def unsign_report(exam_id):
    """
    Quita la firma de un reporte (desmarca como reportado)
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Firma removida exitosamente"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbexamination
            SET isreported = 0, reportdate = NULL
            WHERE guid = %s
        """
        cursor.execute(query, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Firma removida exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/pdf', methods=['GET'])
@jwt_required()
def get_report_pdf(exam_id):
    """
    Obtiene el PDF de un reporte
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    - Archivo PDF del reporte
    """
    return _render_report_pdf_response(exam_id)


@api_blueprint.route('/pdfs/by-exam/<exam_id>', methods=['GET'])
def serve_pdf_by_exam(exam_id):
    """
    Ruta canónica para abrir PDFs por GUID de examen.
    Pública para compatibilidad con flujos legacy.
    """
    return _render_report_pdf_response(exam_id)


@api_blueprint.route('/pdfs/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    """
    Compatibilidad histórica para URLs basadas en nombre de archivo.
    
    Path:
    - filename: Nombre del archivo PDF (ej: ACC006_NR00000013_Díaz_Lucía.pdf)
    
    Los PDFs ahora se identifican por GUID de examen y se generan bajo demanda.
    
    Returns:
    - Archivo PDF
    """
    return jsonify({
        'success': False,
        'message': 'Los PDFs por nombre de archivo fueron retirados; use el GUID del examen.',
        'code': 'PDF_FILENAME_ENDPOINT_RETIRED',
    }), 410


@api_blueprint.route('/examinations/<exam_id>/block', methods=['POST'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def block_examination(exam_id):
    """
    Bloquea un examen para edición exclusiva del usuario actual
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Examen bloqueado exitosamente",
        "blocked_by": "uuid del usuario"
    }
    """
    try:
        user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        ensure_workflow_schema(connection)
        cursor = connection.cursor()
        
        # Verificar si el examen existe y si ya está bloqueado
        cursor.execute("""
            SELECT blockby, COALESCE(clinicaparque_workflow_state, 'pending')
            FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        current_block = result[0]
        workflow_state = result[1]
        if workflow_state == 'already_read':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Este estudio ya fue leído en Info Parque y no puede redactarse en NextRIS', 'code': 'STUDY_ALREADY_READ_IN_INFOPARQUE'}), 409
        if workflow_state == 'cancelled':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'El estudio está cancelado y no puede redactarse', 'code': 'STUDY_CANCELLED'}), 409
        
        # Si ya está bloqueado por otro usuario, no permitir
        if current_block and str(current_block) != str(user_id):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El examen está bloqueado por otro usuario',
                'blocked_by': str(current_block)
            }), 409
        
        # Bloquear el examen
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET blockby = %s
            WHERE Guid = %s
        """, (user_id, exam_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Examen bloqueado exitosamente',
            'blocked_by': str(user_id)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/unblock', methods=['POST'])
@jwt_required()
@require_permission('reports.write', include_role_permissions=True)
def unblock_examination(exam_id):
    """
    Desbloquea un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Examen desbloqueado exitosamente"
    }
    """
    try:
        user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el examen existe y quién lo bloqueó
        cursor.execute("""
            SELECT blockby FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        current_block = result[0]

        # El usuario que tomó el estudio puede desbloquearlo. El sysadmin
        # también puede hacerlo para resolver bloqueos abandonados o erróneos.
        user_permissions = get_user_permission_codes(
            user_id,
            connection=connection,
            include_role_permissions=True,
        )
        is_sysadmin = '*' in user_permissions

        if current_block and str(current_block) != str(user_id) and not is_sysadmin:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Solo el usuario que bloqueó el examen puede desbloquearlo'
            }), 403
        
        # Desbloquear el examen
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET blockby = NULL
            WHERE Guid = %s
        """, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Examen desbloqueado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/filters/body-parts', methods=['GET'])
@jwt_required()
def get_body_parts_filter():
    """Obtiene lista de partes anatómicas disponibles"""
    try:
        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT guid, description FROM nextris.isanatomicalpart ORDER BY description")
        results = [{'guid': str(row[0]), 'description': row[1] or ''} for row in cursor.fetchall()]
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'data': results}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@api_blueprint.route('/filters/modalities', methods=['GET'])
@jwt_required()
def get_modalities_filter():
    """Obtiene lista de modalidades disponibles"""
    try:
        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT guid, description FROM nextris.ismodality ORDER BY description")
        results = [{'guid': str(row[0]), 'description': row[1] or ''} for row in cursor.fetchall()]
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'data': results}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@api_blueprint.route('/filters/study-groups', methods=['GET'])
@jwt_required()
def get_study_groups_filter():
    """Obtiene lista de grupos de estudio disponibles"""
    try:
        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT guid, description FROM nextris.isstudytypegroup ORDER BY description")
        results = [{'guid': str(row[0]), 'description': row[1] or ''} for row in cursor.fetchall()]
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'data': results}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@api_blueprint.route('/reports/<exam_id>/assign', methods=['POST'])
@jwt_required()
@require_permission('reports.assign', include_role_permissions=True)
def assign_exam_to_user(exam_id):
    """
    Asigna un examen a un usuario (radiólogo).

    Body:
        user_id: GUID del usuario radiólogo

    Returns:
        {"success": true, "message": "..."}
    """
    try:
        data = request.get_json()
        if not data or not data.get('user_id'):
            return jsonify({'success': False, 'message': 'user_id es requerido'}), 400

        user_id = data['user_id']

        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbexamination WHERE guid = %s", (exam_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid = %s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404

        cursor.execute(
            """
            UPDATE nextris.tbexamination
            SET assignto = %s
            WHERE guid = %s
            """,
            (user_id, exam_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Estudio asignado correctamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
