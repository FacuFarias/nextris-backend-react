# -*- encoding: utf-8 -*-
"""
API REST para gestión de reportes médicos y plantillas predefinidas
Endpoints para CRUD de reportes, plantillas y generación de PDFs
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
import uuid
import os
import re
import html
from decimal import Decimal, InvalidOperation


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


def get_user_locations(user_id, connection):
    """Obtener ubicaciones del usuario"""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT location_id FROM nextris.rel_user_location WHERE user_id = %s",
        (user_id,)
    )
    locations = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return locations


PDF_OUTPUT_DIR = '/var/www/nextris-dev-react/output_pdfs'


def _get_report_pdfpath_from_exam(exam_id):
    """Obtiene la ruta de PDF asociada a un examen."""
    config = get_db_config()
    if not config:
        return None, 'Error de configuración de base de datos', 500

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    try:
        query = "SELECT pdfpath FROM nextris.tbreport WHERE idexamination = %s"
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
    finally:
        cursor.close()
        connection.close()

    if not result or not result[0]:
        return None, 'PDF no disponible', 404

    return str(result[0]), None, None


def _send_pdf_response_from_path(pdf_path):
    """Valida y devuelve el PDF de forma consistente."""
    normalized = os.path.normpath(str(pdf_path))
    absolute_path = os.path.abspath(normalized)

    if not os.path.exists(absolute_path):
        return jsonify({
            'success': False,
            'message': 'Archivo PDF no encontrado en el sistema'
        }), 404

    if not absolute_path.lower().endswith('.pdf'):
        return jsonify({
            'success': False,
            'message': 'Archivo no válido'
        }), 400

    return send_file(absolute_path, as_attachment=False, mimetype='application/pdf')


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
                ev.id
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
    for row in rows:
        variable_name = row[0]
        if not variable_name:
            continue

        value = _format_sr_value(row[1], row[2], row[3], row[4])
        if value == '':
            continue

        exact_key = str(variable_name).strip().lower()
        normalized_key = _normalize_placeholder_key(variable_name)

        if exact_key and exact_key not in variable_map:
            variable_map[exact_key] = value
        if normalized_key and normalized_key not in variable_map:
            variable_map[normalized_key] = value

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
def get_examinations_for_reporting():
    """
    Obtiene lista de exámenes listos para reportar
    Filtra por ubicaciones del usuario
    
    Query Parameters:
    - status (optional): Filtrar por estado (default: todos)
    - show_reported (optional): true para incluir exámenes reportados (isreported=1)
    - show_ready (optional): true para incluir exámenes listos para reportar (isreported=0)
    - assigned_to_me (optional): true para mostrar solo exámenes asignados al usuario actual
    - modality_id (optional): GUID de la modalidad
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
        modality_id = request.args.get('modality_id')
        body_part_id = request.args.get('body_part_id')
        study_group_id = request.args.get('study_group_id')
        
        print(f"[PARAMS] modality_id={modality_id}, body_part_id={body_part_id}, study_group_id={study_group_id}")
        
        connection = psycopg2.connect(**config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({
                'success': True,
                'data': {
                    'data': [],
                    'page': page,
                    'per_page': per_page,
                    'total': 0
                }
            }), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
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
            reported_filter = "AND e.IsReported = 1"
        elif show_ready:
            # Solo listos (no reportados)
            reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0)"
        else:
            # Ninguno activo: no mostrar nada
            reported_filter = "AND 1=0"
        
        base_query = f"""
            SELECT e.Guid, 
                   CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
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
                   eq.Description as equipment,
                   loc.name as location,
                   e.assignto,
                   rep.pdfpath,
                   st.modality_id,
                   mod.description as modality_description,
                   st.studygroup_id,
                   sg.description as study_group_description,
                   st.bodypart_id,
                   bp.description as bodypart_description,
                   e.blockby
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON eq.location_id = loc.guid
            LEFT JOIN nextris.tbreport rep ON e.Guid = rep.IdExamination
            LEFT JOIN nextris.ismodality mod ON st.modality_id = mod.guid
            LEFT JOIN nextris.isstudytypegroup sg ON st.studygroup_id = sg.guid
            LEFT JOIN nextris.isanatomicalpart bp ON st.bodypart_id = bp.guid
            WHERE eq.location_id IN ({location_placeholders})
            AND e.IsExecuted = 1
            {reported_filter}
        """
        
        params = list(user_locations)
        
        # Aplicar filtro de estado si se proporciona
        if status_filter:
            base_query += " AND e.Status = %s"
            params.append(status_filter)
        
        # Aplicar filtro de asignación si se solicita
        if assigned_to_me:
            base_query += " AND e.assignto = %s"
            params.append(user_id)
        
        # Aplicar filtro de modalidad por GUID
        if modality_id:
            print(f"[FILTER] Aplicando filtro modality_id: {modality_id}")
            base_query += " AND st.modality_id = %s"
            params.append(modality_id)
        
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
        query = base_query + """
            ORDER BY e.CreatedOn DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': str(row[0]),
                'patient_name': row[1] or '',
                'patient_dni': row[2] or '',
                'study_type': row[3] or '',
                'admission_number': row[4] or '',
                'accession_number': row[5] or '',
                'created_on': row[6].isoformat() if row[6] else None,
                'status': row[7] or '',
                'is_reported': bool(row[8]),
                'is_executed': bool(row[9]),
                'is_image': bool(row[10]),
                'study_instance_uid': row[11] or '',
                'equipment': row[12] or '',
                'location': row[13] or '',
                'assigned_to': str(row[14]) if row[14] else None,
                'pdf_path': row[15] or None,
                'modality_id': str(row[16]) if row[16] else None,
                'modality_description': row[17] or '',
                'study_group_id': str(row[18]) if row[18] else None,
                'study_group_description': row[19] or '',
                'bodypart_id': str(row[20]) if row[20] else None,
                'bodypart_description': row[21] or '',
                'blocked_by': str(row[22]) if row[22] else None
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


@api_blueprint.route('/examinations/<exam_id>/report', methods=['GET'])
@jwt_required()
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
            "pdf_path": "ruta/al/archivo.pdf",
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
        cursor = connection.cursor()
        
        # Verificar que el examen existe y obtener datos adicionales
        cursor.execute("""
            SELECT e.Guid, e.IdPatient, e.AdmisionNumber,
                   CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
                   e.studytype_id, e.history, e.clinicalquestion,
                   e.laterality_id, e.stat, e.othersdetails,
                   dp.Name as first_name,
                   dp.Surname as last_name,
                   EXTRACT(YEAR FROM AGE(CURRENT_DATE, dp.birthdate))::INTEGER as age,
                   dp.sexcode,
                   e.LocalAcc as accession_number,
                   e.StudyInstanceUID
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
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
        
        # Obtener reporte
        cursor.execute("""
            SELECT r.Guid, r.idexamination, r.idpatient, r.admnumber,
                   r.findings, r.impressions, r.techniques, r.conclusions,
                   r.wassaved, r.pdfpath, r.date
            FROM nextris.tbreport r
            WHERE r.IdExamination = %s
        """, (exam_id,))
        
        report = cursor.fetchone()
        
        # Determinar si usar datos guardados o predefinidos
        findings = ''
        impressions = ''
        techniques = ''
        conclusions = ''
        was_saved = False
        report_guid = None
        pdf_path = None
        updated_on = None
        
        if report:
            was_saved = bool(report[8])
            report_guid = report[0]
            pdf_path = report[9]
            updated_on = report[10]
            
            if was_saved:
                # Si está guardado, usar datos de tbreport
                findings = report[4] or ''
                impressions = report[5] or ''
                techniques = report[6] or ''
                conclusions = report[7] or ''
            else:
                # Si no está guardado, buscar informe predefinido
                cursor.execute("""
                    SELECT default_predef_id 
                    FROM nextris.isstudytype 
                    WHERE guid = %s
                """, (study_type_id,))
                
                study_type_result = cursor.fetchone()
                default_predef_id = study_type_result[0] if study_type_result else None
                
                if default_predef_id:
                    # Obtener datos del predefinido
                    cursor.execute("""
                        SELECT findings, impression, technique, conclusion
                        FROM nextris.tbinfpredef
                        WHERE guid = %s
                    """, (default_predef_id,))
                    
                    predef = cursor.fetchone()
                    if predef:
                        findings = predef[0] or ''
                        impressions = predef[1] or ''
                        techniques = predef[2] or ''
                        conclusions = predef[3] or ''
        else:
            # Si no existe reporte, buscar predefinido
            if study_type_id:
                cursor.execute("""
                    SELECT default_predef_id 
                    FROM nextris.isstudytype 
                    WHERE guid = %s
                """, (study_type_id,))
                
                study_type_result = cursor.fetchone()
                default_predef_id = study_type_result[0] if study_type_result else None
                
                if default_predef_id:
                    cursor.execute("""
                        SELECT findings, impression, technique, conclusion
                        FROM nextris.tbinfpredef
                        WHERE guid = %s
                    """, (default_predef_id,))
                    
                    predef = cursor.fetchone()
                    if predef:
                        findings = predef[0] or ''
                        impressions = predef[1] or ''
                        techniques = predef[2] or ''
                        conclusions = predef[3] or ''

        debug_requested = request.args.get('debug_sr', '').strip().lower() in ('1', 'true', 'yes')
        debug_before = {
            'findings': _collect_placeholder_candidates(findings),
            'impressions': _collect_placeholder_candidates(impressions),
            'techniques': _collect_placeholder_candidates(techniques),
            'conclusions': _collect_placeholder_candidates(conclusions),
        } if debug_requested else None

        # Reemplazar placeholders {Variable} con valores SR del estudio, cuando existan.
        sr_variable_values = _get_sr_variable_values(cursor, study_instance_uid)
        sr_variables_list = _build_sr_variables_list(sr_variable_values)
        findings = _replace_sr_placeholders(findings, sr_variable_values)
        impressions = _replace_sr_placeholders(impressions, sr_variable_values)
        techniques = _replace_sr_placeholders(techniques, sr_variable_values)
        conclusions = _replace_sr_placeholders(conclusions, sr_variable_values)

        debug_after = {
            'findings': _collect_placeholder_candidates(findings),
            'impressions': _collect_placeholder_candidates(impressions),
            'techniques': _collect_placeholder_candidates(techniques),
            'conclusions': _collect_placeholder_candidates(conclusions),
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
                'accession_number': accession_number or '',
                'patient_name': patient_name or '',
                'first_name': first_name or '',
                'last_name': last_name or '',
                'age': age,
                'sex': sex or '',
                'findings': findings,
                'impressions': impressions,
                'techniques': techniques,
                'conclusions': conclusions,
                'was_saved': was_saved,
                'pdf_path': pdf_path or None,
                'updated_on': updated_on.isoformat() if updated_on else None,
                'history': history or '',
                'clinical_question': clinical_question or '',
                'laterality_id': str(laterality_id) if laterality_id else None,
                'stat': stat or '',
                'others_details': others_details or '',
                'sr_variables': sr_variables_list,
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
        
        findings = data.get('findings')
        impressions = data.get('impressions')
        techniques = data.get('techniques')
        conclusions = data.get('conclusions')
        mark_as_reported = data.get('mark_as_reported', False)
        
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
            SELECT IdPatient, AdmisionNumber
            FROM nextris.tbexamination
            WHERE Guid = %s
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
            
            if findings is not None:
                updates.append("Findings = %s")
                params.append(findings)
            if impressions is not None:
                updates.append("Impressions = %s")
                params.append(impressions)
            if techniques is not None:
                updates.append("Techniques = %s")
                params.append(techniques)
            if conclusions is not None:
                updates.append("Conclusions = %s")
                params.append(conclusions)
            
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
                    Findings, Impressions, Techniques, Conclusions,
                    WasSaved, CreatedOn, Date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, true, NOW(), NOW()
                )
            """, (
                report_id, exam_id, patient_id, admission_number,
                findings or '', impressions or '', techniques or '', conclusions or ''
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
        
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'history': result[0] or '',
                'clinical_question': result[1] or '',
                'others_details': result[2] or '',
                'number_of_views': result[3] or '',
                'stat': result[4] or '',
                'laterality': result[5] or ''
            }
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
            SELECT guid, tittle, findings, impression, technique, conclusion, studytype_id
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
                    'findings': result[2] or '',
                    'impression': result[3] or '',
                    'technique': result[4] or '',
                    'conclusion': result[5] or '',
                    'study_type_id': result[6]
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
        
        findings = data.get('findings', '')
        technique = data.get('technique', '')
        impression = data.get('impression', '')
        conclusion = data.get('conclusion', '')
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
            (guid, tittle, findings, impression, technique, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            new_guid, title, findings, impression, technique, conclusion, study_type_id
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
    
    Body JSON (todos opcionales):
    {
        "title": "string",
        "findings": "string",
        "technique": "string",
        "impression": "string",
        "conclusion": "string"
    }
    
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
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'title' in data:
            updates.append("tittle = %s")
            params.append(data['title'])
        if 'findings' in data:
            updates.append("findings = %s")
            params.append(data['findings'])
        if 'technique' in data:
            updates.append("technique = %s")
            params.append(data['technique'])
        if 'impression' in data:
            updates.append("impression = %s")
            params.append(data['impression'])
        if 'conclusion' in data:
            updates.append("conclusion = %s")
            params.append(data['conclusion'])
        
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
        
        findings = data.get('findings')
        techniques = data.get('techniques')
        impressions = data.get('impressions')
        conclusions = data.get('conclusions')
        
        if findings is None or techniques is None or impressions is None or conclusions is None:
            return jsonify({
                'success': False,
                'message': 'findings, techniques, impressions y conclusions son campos requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbreport 
            SET findings=%s, techniques=%s, impressions=%s, conclusions=%s, wassaved=true 
            WHERE idexamination=%s
        """
        
        cursor.execute(query, (findings, techniques, impressions, conclusions, exam_id))
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
def get_next_exam():
    """
    Obtiene el siguiente examen disponible basado en los filtros configurados
    
    Body JSON:
    {
        "current_exam_id": "uuid",
        "show_ready": true/false,
        "show_reported": true/false,
        "assigned_to_me": true/false,
        "modality_id": "uuid" (optional),
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
        show_ready = data.get('show_ready', True)
        show_reported = data.get('show_reported', False)
        assigned_to_me = data.get('assigned_to_me', False)
        modality_id = data.get('modality_id')
        body_part_id = data.get('body_part_id')
        study_group_id = data.get('study_group_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({
                'success': True,
                'data': None
            }), 200
        
        cursor = connection.cursor()
        
        # Obtener la fecha de creación del examen actual para buscar el siguiente
        cursor.execute("""
            SELECT CreatedOn FROM nextris.tbexamination WHERE Guid = %s
        """, (current_exam_id,))
        current_exam = cursor.fetchone()
        current_created_on = current_exam[0] if current_exam else None
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        # Aplicar el mismo filtro de reportado que en la lista
        if show_reported and show_ready:
            reported_filter = ""
        elif show_reported:
            reported_filter = "AND e.IsReported = 1"
        elif show_ready:
            reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0)"
        else:
            reported_filter = "AND 1=0"
        
        # Query para obtener el siguiente examen
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
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE eq.location_id IN ({location_placeholders})
            AND e.IsExecuted = 1
            AND e.Guid != %s
            {reported_filter}
        """
        
        params = list(user_locations)
        params.append(current_exam_id)
        
        # Aplicar filtro de asignación
        if assigned_to_me:
            query += " AND e.assignto = %s"
            params.append(user_id)
        
        # Aplicar filtros adicionales
        if modality_id:
            query += " AND st.modality_id = %s"
            params.append(modality_id)
        
        if body_part_id:
            query += " AND st.bodypart_id = %s"
            params.append(body_part_id)
        
        if study_group_id:
            query += " AND st.studygroup_id = %s"
            params.append(study_group_id)
        
        # Ordenar y limitar a 1
        if current_created_on:
            query += " AND e.CreatedOn <= %s"
            params.append(current_created_on)
        
        query += " ORDER BY e.CreatedOn DESC LIMIT 1"
        
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
        "modality_id": "uuid" (opcional, para filtrar siguiente),
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
        cursor = connection.cursor()
        
        # Obtener datos del examen para el nombre del PDF
        cursor.execute("""
            SELECT e.LocalAcc, p.PatientId, p.Name, p.Surname, e.IdPatient
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
        
        accession_number, patient_id, patient_name, patient_surname, patient_guid = exam_data
        
        # Crear nombre del PDF: <acc_number>_<patient_id>_<patient_name>.pdf
        # Limpiar caracteres especiales del nombre y manejar valores None
        clean_surname = (patient_surname or '').strip().replace(' ', '_')
        clean_name = (patient_name or '').strip().replace(' ', '_')
        full_name = f"{clean_surname}_{clean_name}".strip('_')
        full_name = ''.join(c for c in full_name if c.isalnum() or c == '_') or 'SinNombre'
        
        acc_num = accession_number or 'SinACC'
        pat_id = patient_id or 'SinID'
        
        pdf_filename = f"{acc_num}_{pat_id}_{full_name}.pdf"
        pdf_relative_path = f"output_pdfs/{pdf_filename}"
        
        # Marcar el examen como reportado, asignar médico y registrar fecha
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
        
        # Verificar si existe el reporte, si no, crearlo
        cursor.execute("SELECT guid FROM nextris.tbreport WHERE idexamination = %s", (exam_id,))
        report_exists = cursor.fetchone()
        
        if not report_exists:
            # Crear el reporte si no existe
            report_guid = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO nextris.tbreport (
                    guid, idexamination, idpatient, admnumber, 
                    pdfpath, wassaved, createdon, date, iduser
                ) VALUES (
                    %s, %s, %s, %s, %s, true, NOW(), NOW(), %s
                )
            """, (report_guid, exam_id, patient_guid, accession_number, 
                  pdf_relative_path, reporter_physician_id))
        else:
            # Actualizar pdfpath en tbreport existente
            cursor.execute("""
                UPDATE nextris.tbreport
                SET pdfpath = %s, iduser = %s
                WHERE idexamination = %s
            """, (pdf_relative_path, reporter_physician_id, exam_id))
        
        connection.commit()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except Exception:
            pass
        
        # Generar PDF del reporte
        print(f"[SIGN] Generando PDF para exam_id: {exam_id}, filename: {pdf_filename}")
        try:
            from apps.home.controllers.report_controller import generate_report_pdf_with_signature
            pdf_path = generate_report_pdf_with_signature(exam_id, pdf_filename=pdf_filename)
            
            print(f"[SIGN] PDF generado, ruta retornada: {pdf_path}")
            print(f"[SIGN] ¿Existe el archivo?: {os.path.exists(pdf_path) if pdf_path else 'pdf_path es None'}")
            
            if not pdf_path or not os.path.exists(pdf_path):
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Error: El PDF no se pudo generar. Ruta: {pdf_path}'
                }), 500
                
        except Exception as pdf_error:
            # FALLAR si no se puede generar el PDF
            import traceback
            traceback.print_exc()
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Error al generar PDF: {str(pdf_error)}'
            }), 500
        
        # Obtener el siguiente examen si se solicita
        next_exam = None
        get_next = data.get('get_next', False)
        
        if get_next:
            try:
                show_ready = data.get('show_ready', True)
                show_reported = data.get('show_reported', False)
                assigned_to_me = data.get('assigned_to_me', False)
                modality_id = data.get('modality_id')
                body_part_id = data.get('body_part_id')
                study_group_id = data.get('study_group_id')
                
                user_locations = get_user_locations(reporter_physician_id, connection)
                
                if user_locations:
                    cursor = connection.cursor()
                    
                    # Obtener la fecha de creación del examen actual
                    cursor.execute("""
                        SELECT CreatedOn FROM nextris.tbexamination WHERE Guid = %s
                    """, (exam_id,))
                    current_exam = cursor.fetchone()
                    current_created_on = current_exam[0] if current_exam else None
                    
                    location_placeholders = ','.join(['%s'] * len(user_locations))
                    
                    # Aplicar el mismo filtro de reportado que en la lista
                    if show_reported and show_ready:
                        reported_filter = ""
                    elif show_reported:
                        reported_filter = "AND e.IsReported = 1"
                    elif show_ready:
                        reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0)"
                    else:
                        reported_filter = "AND 1=0"
                    
                    # Query para obtener el siguiente examen
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
                        LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
                        WHERE eq.location_id IN ({location_placeholders})
                        AND e.IsExecuted = 1
                        AND e.Guid != %s
                        {reported_filter}
                    """
                    
                    params = list(user_locations)
                    params.append(exam_id)
                    
                    # Aplicar filtro de asignación
                    if assigned_to_me:
                        query += " AND e.assignto = %s"
                        params.append(reporter_physician_id)
                    
                    # Aplicar filtros adicionales
                    if modality_id:
                        query += " AND st.modality_id = %s"
                        params.append(modality_id)
                    
                    if body_part_id:
                        query += " AND st.bodypart_id = %s"
                        params.append(body_part_id)
                    
                    if study_group_id:
                        query += " AND st.studygroup_id = %s"
                        params.append(study_group_id)
                    
                    # Ordenar y limitar a 1
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
                    
                    cursor.close()
            except Exception as next_error:
                print(f"[SIGN] Error al obtener siguiente examen: {str(next_error)}")
                # No fallar si hay error al obtener el siguiente, solo loguearlo
        
        # Cerrar conexión
        cursor.close()
        connection.close()
        
        response_data = {
            'success': True,
            'message': 'Reporte firmado exitosamente'
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
    Verifica las credenciales del usuario actual
    Útil para acciones críticas como firmar reportes
    
    Headers:
    - Authorization: Bearer <token>
    
    Body JSON:
    {
        "password": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Credenciales válidas"
    }
    
    Error Response:
    {
        "success": false,
        "message": "Credenciales inválidas"
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        
        if not data or 'password' not in data:
            return jsonify({
                'success': False,
                'message': 'La contraseña es requerida'
            }), 400
        
        password = data.get('password')
        user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener hash de contraseña del usuario
        cursor.execute("""
            SELECT password FROM nextris.tbuser 
            WHERE guid = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        stored_password = result[0]
        
        # Verificar contraseña (asumiendo que está hasheada con bcrypt o similar)
        try:
            from werkzeug.security import check_password_hash
            
            if check_password_hash(stored_password, password):
                return jsonify({
                    'success': True,
                    'message': 'Credenciales válidas'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }), 401
        except:
            # Si no está hasheada, comparar directamente (no recomendado en producción)
            if stored_password == password:
                return jsonify({
                    'success': True,
                    'message': 'Credenciales válidas'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }), 401
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/unsign', methods=['POST'])
@jwt_required()
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
        
        query = "UPDATE nextris.tbexamination SET isreported=0 WHERE guid=%s"
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
    try:
        pdf_path, error_message, status_code = _get_report_pdfpath_from_exam(exam_id)
        if error_message:
            return jsonify({
                'success': False,
                'message': error_message
            }), status_code

        return _send_pdf_response_from_path(pdf_path)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/pdfs/by-exam/<exam_id>', methods=['GET'])
def serve_pdf_by_exam(exam_id):
    """
    Ruta canónica para abrir PDFs por GUID de examen.
    Pública para compatibilidad con flujos legacy.
    """
    try:
        pdf_path, error_message, status_code = _get_report_pdfpath_from_exam(exam_id)
        if error_message:
            return jsonify({
                'success': False,
                'message': error_message
            }), status_code

        return _send_pdf_response_from_path(pdf_path)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/pdfs/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    """
    Sirve archivos PDF directamente desde output_pdfs
    Endpoint público sin autenticación para abrir PDFs en nueva pestaña
    
    Path:
    - filename: Nombre del archivo PDF (ej: ACC006_NR00000013_Díaz_Lucía.pdf)
    
    URL completa desde pdf_path:
    - Si pdf_path = "output_pdfs/ACC006_NR00000013_Díaz_Lucía.pdf"
    - URL = "/api/pdfs/ACC006_NR00000013_Díaz_Lucía.pdf"
    
    Returns:
    - Archivo PDF
    """
    try:
        # Sanitizar el nombre del archivo para evitar path traversal
        safe_filename = os.path.basename(filename)

        if not safe_filename:
            return jsonify({
                'success': False,
                'message': 'PDF no encontrado'
            }), 404

        pdf_path = os.path.join(PDF_OUTPUT_DIR, safe_filename)
        return _send_pdf_response_from_path(pdf_path)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/block', methods=['POST'])
@jwt_required()
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
        cursor = connection.cursor()
        
        # Verificar si el examen existe y si ya está bloqueado
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
        
        # Solo el usuario que bloqueó puede desbloquear (o si no está bloqueado)
        if current_block and str(current_block) != str(user_id):
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
