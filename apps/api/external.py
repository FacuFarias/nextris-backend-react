# -*- encoding: utf-8 -*-
"""
API Externa para NextRIS
Endpoints para recibir pacientes, reportes e imágenes desde sistemas externos.
No requiere autenticación JWT.
"""

from flask import jsonify, request
import psycopg2
import uuid
import json
from datetime import datetime
from apps.api import api_blueprint
from apps.authentication.util import hash_pass
from apps.home.controllers.report_controller import generate_report_pdf_with_signature


def get_db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def generate_patient_id(cursor):
    """Genera un PatientID con formato NR00000001, NR00000002, etc."""
    cursor.execute("""
        SELECT patientid FROM nextris.datapatient
        WHERE patientid LIKE 'NR%%'
        ORDER BY patientid DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    if result and result[0]:
        try:
            last_number = int(result[0][2:])
            new_number = last_number + 1
        except (ValueError, IndexError):
            new_number = 1
    else:
        new_number = 1
    return f"NR{new_number:08d}"


def generate_adm_number(cursor):
    """Genera un número de admisión: ADM001, ADM002, ..."""
    cursor.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(admisionnumber FROM 4) AS INTEGER)), 0) + 1
        FROM nextris.tbexamination
        WHERE admisionnumber LIKE 'ADM%'
    """)
    return f"ADM{cursor.fetchone()[0]:03d}"


def generate_local_acc(cursor):
    """Genera un LocalAcc: ACC001, ACC002, ..."""
    cursor.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(LocalAcc FROM 4) AS INTEGER)), 0) + 1
        FROM nextris.tbexamination
        WHERE LocalAcc LIKE 'ACC%%'
    """)
    return f"ACC{cursor.fetchone()[0]:03d}"


def find_or_create_patient(cursor, patient_data):
    """
    Busca paciente por nationalcode (DNI). Si no existe, lo crea.
    Retorna (patient_guid, is_new).
    """
    nationalcode = patient_data.get('nationalcode', '').strip()
    name = patient_data.get('name', '').strip()
    surname = patient_data.get('surname', '').strip()
    birthdate = patient_data.get('birthdate')
    sexcode = patient_data.get('sexcode', 'I')
    email = patient_data.get('email')
    phone = patient_data.get('phone')

    if nationalcode:
        cursor.execute(
            "SELECT guid FROM nextris.datapatient WHERE nationalcode = %s LIMIT 1",
            (nationalcode,)
        )
        existing = cursor.fetchone()
        if existing:
            return existing[0], False

    patient_guid = str(uuid.uuid4())
    patient_id = generate_patient_id(cursor)

    cursor.execute("""
        INSERT INTO nextris.datapatient
        (guid, name, surname, patientid, nationalcode, email, phone, birthdate, sexcode,
         isanonymous, ismerged)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::bit, %s::bit)
        RETURNING guid
    """, (
        patient_guid, name, surname, patient_id,
        nationalcode or None, email or None, phone or None,
        birthdate, sexcode, 0, 0
    ))
    cursor.fetchone()
    return patient_guid, True


def ensure_portal_user(cursor, patient_guid, nationalcode):
    """
    Asegura que el paciente tenga un usuario en el portal.
    Username = DNI, Password = últimos 3 dígitos del DNI.
    firstlogin = 0 (no pide cambio de contraseña).
    Si ya tiene usuario, no hace nada.
    """
    if not nationalcode:
        return None

    cursor.execute(
        "SELECT guid FROM nextris.tbuser_patient WHERE datapatient_id = %s LIMIT 1",
        (patient_guid,)
    )
    if cursor.fetchone():
        return None

    username = nationalcode.strip()
    last3 = username[-3:] if len(username) >= 3 else username
    hashed_password = hash_pass(last3)

    user_guid = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO nextris.tbuser_patient
        (guid, username, password, datapatient_id, status, firstlogin)
        VALUES (%s, %s, %s, %s, 'Active', 0)
    """, (user_guid, username, hashed_password, patient_guid))
    return user_guid


def resolve_rad_id(cursor, rad_id):
    """
    Resuelve el rad_id (username) al GUID del usuario en tbuser.
    Retorna el GUID o None si no se encuentra.
    """
    if not rad_id:
        return None
    cursor.execute(
        "SELECT guid FROM nextris.tbuser WHERE username = %s LIMIT 1",
        (rad_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def create_examination(cursor, patient_guid, exam_data, report_data, study_uid=None, rad_id=None):
    """
    Crea el examen (tbexamination) y su reporte asociado (tbreport).
    Retorna (examination_guid, report_guid, adm_number).
    """
    adm_number = generate_adm_number(cursor)
    local_acc = generate_local_acc(cursor)
    exam_guid = str(uuid.uuid4())

    # Resolver rad_id (username) a GUID
    rad_user_guid = resolve_rad_id(cursor, rad_id)

    cursor.execute("""
        INSERT INTO nextris.tbexamination (
            guid, idpatient, studytype_id,
            admisionnumber, localacc, status, createdon, isexecuted,
            studyinstanceuid, history
        ) VALUES (
            %s, %s, %s,
            %s, %s, 'Scheduled', NOW(), 0,
            %s, %s
        )
    """, (
        exam_guid, patient_guid,
        exam_data.get('studytype_id'),
        adm_number, local_acc,
        study_uid,
        exam_data.get('history')
    ))

    report_guid = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO nextris.tbreport (
            guid, idexamination, idpatient, admnumber, iduser,
            findings, impressions, techniques, conclusions,
            wassaved, createdon, date
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            true, NOW(), NOW()
        )
    """, (
        report_guid, exam_guid, patient_guid, adm_number, rad_user_guid,
        report_data.get('findings', ''),
        report_data.get('impressions', ''),
        report_data.get('techniques', ''),
        report_data.get('conclusions', '')
    ))

    return exam_guid, report_guid, adm_number


def try_link_pacs_study(cursor, exam_guid, study_uid):
    """
    Intenta vincular un estudio del PACS al examen.
    Retorna (linked: bool, error_message: str|None).
    """
    if not study_uid:
        return False, "study_uid no proporcionado"

    cursor.execute(
        "SELECT pk, study_iuid, accession_no FROM public.study WHERE study_iuid = %s LIMIT 1",
        (study_uid,)
    )
    pacs_study = cursor.fetchone()
    if not pacs_study:
        return False, f"study_uid '{study_uid}' no encontrado en PACS"

    pacs_study_pk = pacs_study[0]
    pacs_study_iuid = pacs_study[1]

    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
        )
    """)
    has_link_table = cursor.fetchone()[0]

    if has_link_table:
        cursor.execute("""
            UPDATE nextris.tbpacs_study_link
            SET link_status = 'unlinked',
                unlinked_at = CURRENT_TIMESTAMP,
                unlinked_reason = 'Reemplazo desde API externa',
                updated_at = CURRENT_TIMESTAMP
            WHERE link_status = 'linked'
              AND (order_guid = %s OR pacs_study_pk = %s OR pacs_study_iuid = %s)
        """, (exam_guid, pacs_study_pk, pacs_study_iuid))

        cursor.execute("""
            INSERT INTO nextris.tbpacs_study_link (
                pacs_study_pk, pacs_study_iuid, order_guid,
                link_status, source, linked_at,
                linked_by_user_guid, linked_by_username,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s,
                'linked', 'external', CURRENT_TIMESTAMP,
                NULL, 'external-api',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """, (pacs_study_pk, pacs_study_iuid, exam_guid))

    cursor.execute("""
        UPDATE nextris.tbexamination
        SET isimage = 1, studyinstanceuid = %s
        WHERE guid = %s
    """, (pacs_study_iuid, exam_guid))

    return True, None


def log_external_call(cursor, endpoint, method, payload, patient_guid,
                      nationalcode, exam_guid, report_guid, study_uid,
                      pacs_linked, pacs_link_error, status, error_message):
    """Registra la llamada externa en la tabla de log."""
    cursor.execute("""
        INSERT INTO nextris.tbexternal_api_log (
            endpoint, method, payload,
            patient_guid, patient_nationalcode,
            examination_guid, report_guid, study_uid,
            pacs_linked, pacs_link_error,
            status, error_message,
            ip_address, user_agent
        ) VALUES (
            %s, %s, %s::jsonb,
            %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s
        ) RETURNING request_id
    """, (
        endpoint, method, json.dumps(payload) if payload else None,
        patient_guid, nationalcode,
        exam_guid, report_guid, study_uid,
        pacs_linked, pacs_link_error,
        status, error_message,
        request.remote_addr,
        request.headers.get('User-Agent', '')
    ))
    result = cursor.fetchone()
    return result[0] if result else None


# =============================================================
# ENDPOINT PRINCIPAL: POST /api/external/receive-study
# =============================================================

@api_blueprint.route('/external/receive-study', methods=['POST'])
def external_receive_study():
    """
    Recibe un paciente, examen, reporte y opcionalmente un study_uid
    desde un sistema externo.

    Body JSON:
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
            "findings": "Hallazgos...",
            "impressions": "Impresión...",
            "techniques": "Técnica...",
            "conclusions": "Conclusión..."
        },
        "study_uid": "1.2.840.113619.2.55.3.1234"
    }
    """
    request_id = None
    connection = None

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        # --- Validaciones ---
        patient_data = data.get('patient', {})
        exam_data = data.get('examination', {})
        report_data = data.get('report', {})
        study_uid = data.get('study_uid')
        rad_id = data.get('rad_id')

        # Mapear dni a nationalcode
        if 'dni' in patient_data and 'nationalcode' not in patient_data:
            patient_data['nationalcode'] = patient_data.pop('dni')

        missing = []
        if not patient_data.get('name'):
            missing.append('patient.name')
        if not patient_data.get('surname'):
            missing.append('patient.surname')
        if not patient_data.get('nationalcode'):
            missing.append('patient.dni')
        if not exam_data.get('studytype_id'):
            missing.append('examination.studytype_id')
        if not report_data.get('findings'):
            missing.append('report.findings')
        if not report_data.get('impressions'):
            missing.append('report.impressions')
        if not report_data.get('techniques'):
            missing.append('report.techniques')
        if not report_data.get('conclusions'):
            missing.append('report.conclusions')

        if missing:
            return jsonify({
                'success': False,
                'message': f'Campos requeridos faltantes: {", ".join(missing)}'
            }), 400

        # --- Conexión a BD ---
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # --- Paso 1: Buscar o crear paciente ---
        patient_guid, patient_is_new = find_or_create_patient(cursor, patient_data)

        # --- Paso 2: Crear usuario portal ---
        portal_user_created = ensure_portal_user(
            cursor, patient_guid, patient_data.get('nationalcode')
        )

        # --- Paso 3: Crear examen + reporte ---
        exam_guid, report_guid, adm_number = create_examination(
            cursor, patient_guid, exam_data, report_data, study_uid, rad_id
        )

        # --- Paso 4: Vincular PACS ---
        pacs_linked = False
        pacs_link_error = None
        if study_uid:
            pacs_linked, pacs_link_error = try_link_pacs_study(
                cursor, exam_guid, study_uid
            )

        # --- Paso 5: Firmar reporte automáticamente ---
        # Resolver rad_id a GUID para asignar
        rad_user_guid = resolve_rad_id(cursor, rad_id)
        
        # Marcar examen como reportado
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET isreported = 1, reportdate = NOW(), assignto = %s
            WHERE guid = %s
        """, (rad_user_guid, exam_guid))

        # Generar PDF
        pdf_filename = f"{adm_number}_{patient_data.get('nationalcode', 'unknown')}.pdf"
        pdf_relative_path = f"output_pdfs/{pdf_filename}"
        
        connection.commit()  # Commit antes de generar PDF
        
        try:
            pdf_path = generate_report_pdf_with_signature(
                exam_guid, 
                output_dir='output_pdfs', 
                pdf_filename=pdf_filename
            )
            if pdf_path:
                cursor.execute("""
                    UPDATE nextris.tbreport
                    SET pdfpath = %s
                    WHERE guid = %s
                """, (pdf_relative_path, report_guid))
                connection.commit()
        except Exception as pdf_error:
            print(f"[WARNING] Error generando PDF: {pdf_error}")

        # --- Paso 6: Log ---
        request_id = log_external_call(
            cursor,
            endpoint='/api/external/receive-study',
            method='POST',
            payload=data,
            patient_guid=patient_guid,
            nationalcode=patient_data.get('nationalcode'),
            exam_guid=exam_guid,
            report_guid=report_guid,
            study_uid=study_uid,
            pacs_linked=pacs_linked,
            pacs_link_error=pacs_link_error,
            status='success',
            error_message=None
        )

        connection.commit()
        cursor.close()
        connection.close()

        # --- Respuesta ---
        response = {
            'success': True,
            'request_id': request_id,
            'patient': {
                'guid': patient_guid,
                'nationalcode': patient_data.get('nationalcode'),
                'username': patient_data.get('nationalcode'),
                'is_new': patient_is_new
            },
            'examination': {
                'guid': exam_guid,
                'admisionnumber': adm_number,
                'studytype_id': exam_data.get('studytype_id')
            },
            'report': {
                'guid': report_guid, 'rad_id': rad_id
            },
            'pacs_link': {
                'linked': pacs_linked,
                'study_uid': study_uid,
                'error': pacs_link_error
            }
        }
        if portal_user_created:
            response['patient']['portal_user_created'] = True

        return jsonify(response), 201

    except Exception as e:
        if connection:
            try:
                connection.rollback()
                cursor = connection.cursor()
                log_external_call(
                    cursor,
                    endpoint='/api/external/receive-study',
                    method='POST',
                    payload=data if 'data' in dir() else None,
                    patient_guid=None,
                    nationalcode=data.get('patient', {}).get('nationalcode') if 'data' in dir() else None,
                    exam_guid=None,
                    report_guid=None,
                    study_uid=data.get('study_uid') if 'data' in dir() else None,
                    pacs_linked=False,
                    pacs_link_error=None,
                    status='error',
                    error_message=str(e)
                )
                connection.commit()
                cursor.close()
            except Exception:
                pass
            connection.close()

        return jsonify({
            'success': False,
            'request_id': request_id,
            'message': f'Error interno: {str(e)}'
        }), 500


# =============================================================
# ENDPOINT AUXILIAR: GET /api/external/logs
# =============================================================

@api_blueprint.route('/external/logs', methods=['GET'])
def external_logs():
    """
    Consulta el historial de llamadas a la API externa.

    Query params:
    - nationalcode: filtrar por DNI
    - status: filtrar por status (success/error/partial)
    - date_from: fecha desde (YYYY-MM-DD)
    - date_to: fecha hasta (YYYY-MM-DD)
    - page: número de página (default: 1)
    - per_page: resultados por página (default: 50, max: 200)
    """
    try:
        nationalcode = request.args.get('nationalcode', '').strip()
        status_filter = request.args.get('status', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 200:
            per_page = 50

        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        conditions = []
        params = []

        if nationalcode:
            conditions.append("patient_nationalcode = %s")
            params.append(nationalcode)
        if status_filter:
            conditions.append("status = %s")
            params.append(status_filter)
        if date_from:
            conditions.append("created_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("created_at < %s::date + interval '1 day'")
            params.append(date_to)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Contar total
        cursor.execute(f"""
            SELECT COUNT(*) FROM nextris.tbexternal_api_log {where_clause}
        """, params)
        total = cursor.fetchone()[0]

        # Obtener datos
        offset = (page - 1) * per_page
        query_params = params + [per_page, offset]

        cursor.execute(f"""
            SELECT
                request_id, endpoint, method,
                patient_guid, patient_nationalcode,
                examination_guid, report_guid, study_uid,
                pacs_linked, pacs_link_error,
                status, error_message,
                ip_address, created_at
            FROM nextris.tbexternal_api_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, query_params)

        rows = cursor.fetchall()
        logs = []
        for row in rows:
            logs.append({
                'request_id': row[0],
                'endpoint': row[1],
                'method': row[2],
                'patient_guid': row[3],
                'patient_nationalcode': row[4],
                'examination_guid': row[5],
                'report_guid': row[6],
                'study_uid': row[7],
                'pacs_linked': row[8],
                'pacs_link_error': row[9],
                'status': row[10],
                'error_message': row[11],
                'ip_address': row[12],
                'created_at': row[13].isoformat() if row[13] else None
            })

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'data': logs,
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# =============================================================
# ENDPOINT AUXILIAR: GET /api/external/logs/<request_id>
# =============================================================

@api_blueprint.route('/external/logs/<request_id>', methods=['GET'])
def external_log_detail(request_id):
    """
    Obtiene el detalle de una llamada específica por request_id.
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                request_id, endpoint, method, payload,
                patient_guid, patient_nationalcode,
                examination_guid, report_guid, study_uid,
                pacs_linked, pacs_link_error,
                status, error_message,
                ip_address, user_agent, created_at
            FROM nextris.tbexternal_api_log
            WHERE request_id = %s
        """, (request_id,))

        row = cursor.fetchone()
        cursor.close()
        connection.close()

        if not row:
            return jsonify({
                'success': False,
                'message': 'Log no encontrado'
            }), 404

        return jsonify({
            'success': True,
            'data': {
                'request_id': row[0],
                'endpoint': row[1],
                'method': row[2],
                'payload': row[3],
                'patient_guid': row[4],
                'patient_nationalcode': row[5],
                'examination_guid': row[6],
                'report_guid': row[7],
                'study_uid': row[8],
                'pacs_linked': row[9],
                'pacs_link_error': row[10],
                'status': row[11],
                'error_message': row[12],
                'ip_address': row[13],
                'user_agent': row[14],
                'created_at': row[15].isoformat() if row[15] else None
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
