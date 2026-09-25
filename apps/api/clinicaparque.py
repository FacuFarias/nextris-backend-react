# -*- encoding: utf-8 -*-
"""
API Clínica Parque - Recepción de pacientes y órdenes desde sistemas externos
Endpoints:
  - POST /api/clinicaparque/patients           → Crear paciente
  - POST /api/clinicaparque/patients/update    → Actualizar paciente
  - POST /api/clinicaparque/orders             → Crear exámenes
  - POST /api/clinicaparque/orders/<order_id>/confirm-study → Confirmar estudio
  - POST /api/clinicaparque/reports            → Recibir reportes
  - POST /api/clinicaparque/reports/send       → Enviar reportes a externo
Autenticación: Bearer Token estático en header Authorization
"""

import uuid
import os
import json
import requests
from datetime import datetime
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import jwt_required
import psycopg2
from psycopg2 import OperationalError
from apps.api import api_blueprint
from apps.api.permissions import require_permission
from apps.authentication.util import hash_pass
from apps.home.services.hl7_service import HL7Service
from apps.api.viewer_share_service import create_for_exam
from apps.services.report_fields import canonical_fields_from_row, normalize_report_payload
from apps.services.clinicaparque_workflow import (
    WORKFLOW_ALREADY_READ,
    WORKFLOW_CANCELLED,
    apply_already_read,
    apply_cancel,
    ensure_workflow_schema,
)


CLINICAPARQUE_TOKEN = os.environ.get(
    'CLINICAPARQUE_TOKEN',
    'Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s='
)


def require_clinicaparque_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        workflow_endpoint = None
        if '/cancel-study' in request.path:
            workflow_endpoint = '/clinicaparque/cancel-study'
        elif '/already-read' in request.path:
            workflow_endpoint = '/clinicaparque/already-read'
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            if workflow_endpoint:
                _log_communication(workflow_endpoint,
                                   request_body=json.dumps(request.get_json(silent=True), ensure_ascii=False, default=str),
                                   response_status=401,
                                   response_body=json.dumps({'success': False, 'message': 'Token de autenticación requerido'}),
                                   success=False, error_message='Token de autenticación requerido',
                                   start_time=datetime.now())
            return jsonify({'success': False, 'message': 'Token de autenticación requerido'}), 401
        token = auth_header[7:].strip()
        if token != CLINICAPARQUE_TOKEN:
            if workflow_endpoint:
                _log_communication(workflow_endpoint,
                                   request_body=json.dumps(request.get_json(silent=True), ensure_ascii=False, default=str),
                                   response_status=401,
                                   response_body=json.dumps({'success': False, 'message': 'Token de autenticación inválido'}),
                                   success=False, error_message='Token de autenticación inválido',
                                   start_time=datetime.now())
            return jsonify({'success': False, 'message': 'Token de autenticación inválido'}), 401
        return f(*args, **kwargs)
    return decorated


def get_db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def _ensure_patient_type_columns(cursor):
    """Agregar columnas patient_type y healthcard_type si no existen."""
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'nextris' AND table_name = 'datapatient'
          AND column_name IN ('patient_type', 'healthcard_type')
    """)
    existing = {row[0] for row in cursor.fetchall()}
    if 'patient_type' not in existing:
        cursor.execute("ALTER TABLE nextris.datapatient ADD COLUMN patient_type VARCHAR(50)")
    if 'healthcard_type' not in existing:
        cursor.execute("ALTER TABLE nextris.datapatient ADD COLUMN healthcard_type VARCHAR(10)")


def _generate_guid():
    return str(uuid.uuid4())


def _ensure_clinicaparque_order_links(cursor):
    """Ensure the external Clínica Parque order mapping exists.

    GUIDs remain database-only.  The integration identifies an order with the
    source orderId and the mapping resolves it to the internal examination and
    report rows.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nextris.clinicaparque_order_links (
            guid                    VARCHAR(50) PRIMARY KEY,
            source                  VARCHAR(50) NOT NULL DEFAULT 'clinicaparque',
            external_order_id       VARCHAR(100) NOT NULL,
            external_patient_id     VARCHAR(50),
            examination_guid        VARCHAR(50) NOT NULL,
            report_guid             VARCHAR(50),
            accession_number        VARCHAR(50),
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clinicaparque_order_links_order
        ON nextris.clinicaparque_order_links (source, external_order_id)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clinicaparque_order_links_accession
        ON nextris.clinicaparque_order_links (source, accession_number)
        WHERE accession_number IS NOT NULL AND accession_number <> ''
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_clinicaparque_order_links_exam
        ON nextris.clinicaparque_order_links (examination_guid)
        """
    )


def _upsert_clinicaparque_order_link(
    cursor, external_order_id, external_patient_id, examination_guid,
    report_guid=None, accession_number=None,
):
    """Create/update an external order mapping without exposing its internals."""
    if not external_order_id:
        return
    cursor.execute(
        """
        SELECT examination_guid
        FROM nextris.clinicaparque_order_links
        WHERE source = 'clinicaparque' AND external_order_id = %s
        LIMIT 1
        """,
        (external_order_id,),
    )
    existing = cursor.fetchone()
    if existing and str(existing[0]) != str(examination_guid):
        raise ValueError('orderId ya está asociado a otra orden')
    cursor.execute(
        """
        INSERT INTO nextris.clinicaparque_order_links (
            guid, source, external_order_id, external_patient_id,
            examination_guid, report_guid, accession_number, updated_at
        ) VALUES (%s, 'clinicaparque', %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (source, external_order_id) DO UPDATE SET
            external_patient_id = EXCLUDED.external_patient_id,
            examination_guid = EXCLUDED.examination_guid,
            report_guid = COALESCE(EXCLUDED.report_guid,
                                   nextris.clinicaparque_order_links.report_guid),
            accession_number = COALESCE(EXCLUDED.accession_number,
                                        nextris.clinicaparque_order_links.accession_number),
            updated_at = NOW()
        """,
        (
            _generate_guid(), external_order_id, external_patient_id,
            examination_guid, report_guid, accession_number,
        ),
    )


def _find_clinicaparque_order(cursor, order_id=None, accession=None, study_uid=None):
    """Resolve an external order to internal rows.

    The returned GUIDs are intentionally only used by server-side SQL; they
    must never be returned to the integration or accepted from it.
    """
    if order_id:
        cursor.execute(
            """
            SELECT examination_guid, report_guid, accession_number
            FROM nextris.clinicaparque_order_links
            WHERE source = 'clinicaparque' AND external_order_id = %s
            LIMIT 1
            """,
            (order_id,),
        )
        row = cursor.fetchone()
        if row:
            return row

    if accession:
        cursor.execute(
            """
            SELECT e.guid, r.guid, e.localacc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            WHERE e.localacc = %s
            ORDER BY e.createdon DESC NULLS LAST
            LIMIT 1
            """,
            (accession,),
        )
        row = cursor.fetchone()
        if row:
            return row

    if study_uid:
        cursor.execute(
            """
            SELECT e.guid, r.guid, e.localacc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            WHERE e.studyinstanceuid = %s
            ORDER BY e.createdon DESC NULLS LAST
            LIMIT 1
            """,
            (study_uid,),
        )
        row = cursor.fetchone()
        if row:
            return row

    return None


def _workflow_callback_response(status, message, code=None):
    body = {'success': False, 'message': message}
    if code:
        body['code'] = code
    return jsonify(body), status


def _clinicaparque_workflow_callback(action, path_order_id=None):
    """Process a cancellation/already-read callback from Clínica Parque."""
    start_time = datetime.now()
    canonical_endpoint = (
        '/clinicaparque/cancel-study'
        if action == WORKFLOW_CANCELLED
        else '/clinicaparque/already-read'
    )
    payload = request.get_json(silent=True)
    request_body = json.dumps(payload, ensure_ascii=False, default=str)
    order_data = payload.get('order') if isinstance(payload, dict) else {}
    if not isinstance(order_data, dict):
        order_data = {}
    order_id = str(
        path_order_id
        or (payload or {}).get('orderId')
        or (payload or {}).get('order_id')
        or order_data.get('orderId')
        or order_data.get('order_id')
        or ''
    ).strip() or None
    accession = str(
        (payload or {}).get('accessionNumber')
        or (payload or {}).get('accession_number')
        or order_data.get('accessionNumber')
        or order_data.get('accession_number')
        or ''
    ).strip() or None
    connection = None
    cursor = None
    patient_id = None
    patient_name = None
    try:
        if not isinstance(payload, dict):
            _log_communication(canonical_endpoint, order_id=order_id,
                               accession_number=accession, request_body=request_body,
                               response_status=400, response_body=json.dumps({'success': False}),
                               success=False, error_message='JSON inválido o vacío',
                               start_time=start_time)
            return _workflow_callback_response(400, 'JSON inválido o vacío')
        if not order_id and not accession:
            _log_communication(canonical_endpoint, request_body=request_body,
                               response_status=400, response_body=json.dumps({'success': False}),
                               success=False, error_message='orderId o accessionNumber es requerido',
                               start_time=start_time)
            return _workflow_callback_response(400, 'orderId o accessionNumber es requerido')

        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        ensure_workflow_schema(connection)
        _ensure_clinicaparque_order_links(cursor)
        order_row = _find_clinicaparque_order(cursor, order_id=order_id, accession=accession)
        if not order_row:
            _log_communication(canonical_endpoint, accession_number=accession, order_id=order_id,
                               request_body=request_body, response_status=404,
                               response_body=json.dumps({'success': False}), success=False,
                               error_message='No se encontró la orden', start_time=start_time)
            return _workflow_callback_response(404, 'No se encontró la orden')
        exam_id = order_row[0]
        cursor.execute(
            """
            SELECT dp.patientid,
                   CONCAT_WS(', ', NULLIF(TRIM(dp.surname), ''), NULLIF(TRIM(dp.name), '')),
                   e.localacc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON dp.guid = e.idpatient
            WHERE e.guid = %s
            LIMIT 1
            """,
            (exam_id,),
        )
        exam_data = cursor.fetchone()
        if exam_data:
            patient_id, patient_name, accession = exam_data[0], exam_data[1], accession or exam_data[2]

        if action == WORKFLOW_CANCELLED:
            cancellation = payload.get('cancellation')
            if not isinstance(cancellation, dict):
                cancellation = payload
            result = apply_cancel(
                connection,
                exam_id,
                cancellation.get('reason_code') or cancellation.get('cancellation_reason_code'),
                cancellation.get('detail') or cancellation.get('cancellation_reason_detail'),
                source='clinicaparque_api',
            )
        else:
            report = payload.get('report')
            report = report if isinstance(report, dict) else None
            rad_id = payload.get('rad_id') or (report or {}).get('rad_id')
            read_at = payload.get('read_at') or payload.get('readAt')
            result = apply_already_read(
                connection,
                exam_id,
                report_payload=report,
                rad_id=rad_id,
                read_at=read_at,
                source='clinicaparque_api',
            )
        connection.commit()
        response = {
            'success': True,
            'message': ('Estudio cancelado correctamente'
                        if action == WORKFLOW_CANCELLED
                        else 'Estudio marcado como ya leído'),
            'orderId': order_id,
            'accessionNumber': accession,
            'state': result['state'],
            'idempotent': result['idempotent'],
        }
        _log_communication(canonical_endpoint, patient_id=patient_id,
                           patient_name=patient_name, accession_number=accession,
                           order_id=order_id, request_body=request_body,
                           response_status=200,
                           response_body=json.dumps(response, ensure_ascii=False),
                           success=True, start_time=start_time)
        return jsonify(response), 200
    except LookupError as error:
        if connection:
            connection.rollback()
        _log_communication(canonical_endpoint, patient_id=patient_id,
                           patient_name=patient_name, accession_number=accession,
                           order_id=order_id, request_body=request_body,
                           response_status=404, response_body=json.dumps({'success': False}),
                           success=False, error_message=str(error), start_time=start_time)
        return _workflow_callback_response(404, str(error))
    except PermissionError as error:
        if connection:
            connection.rollback()
        code = 'STUDY_CANCELLED' if action == WORKFLOW_CANCELLED else 'STUDY_ALREADY_READ_IN_INFOPARQUE'
        _log_communication(canonical_endpoint, patient_id=patient_id,
                           patient_name=patient_name, accession_number=accession,
                           order_id=order_id, request_body=request_body,
                           response_status=409, response_body=json.dumps({'success': False, 'code': code}),
                           success=False, error_message=str(error), start_time=start_time)
        return _workflow_callback_response(409, str(error), code)
    except (ValueError, TypeError) as error:
        if connection:
            connection.rollback()
        _log_communication(canonical_endpoint, patient_id=patient_id,
                           patient_name=patient_name, accession_number=accession,
                           order_id=order_id, request_body=request_body,
                           response_status=400, response_body=json.dumps({'success': False}),
                           success=False, error_message=str(error), start_time=start_time)
        return _workflow_callback_response(400, str(error))
    except Exception as error:
        if connection:
            connection.rollback()
        _log_communication(canonical_endpoint, patient_id=patient_id,
                           patient_name=patient_name, accession_number=accession,
                           order_id=order_id, request_body=request_body,
                           response_status=500, response_body=json.dumps({'success': False}),
                           success=False, error_message=str(error), start_time=start_time)
        return _workflow_callback_response(500, 'Error procesando la notificación')
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@api_blueprint.route('/clinicaparque/cancel-study', methods=['POST'])
@api_blueprint.route('/clinicaparque/orders/<order_id>/cancel', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_cancel_study(order_id=None):
    return _clinicaparque_workflow_callback(WORKFLOW_CANCELLED, order_id)


@api_blueprint.route('/clinicaparque/already-read', methods=['POST'])
@api_blueprint.route('/clinicaparque/orders/<order_id>/already-read', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_already_read(order_id=None):
    return _clinicaparque_workflow_callback(WORKFLOW_ALREADY_READ, order_id)


def _resolve_external_laterality(cursor, value):
    """Resolve a description/code supplied by the external system."""
    if value is None or str(value).strip() == '':
        return None
    value = str(value).strip()
    cursor.execute(
        """
        SELECT guid
        FROM nextris.islaterality
        WHERE LOWER(TRIM(description)) = LOWER(TRIM(%s))
        LIMIT 1
        """,
        (value,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError(
            'laterality debe ser una descripción existente, por ejemplo IZQUIERDA, DERECHA o BILATERAL'
        )
    return row[0]


def _resolve_external_physician(cursor, value):
    """Resolve an external username/national number, never a GUID input."""
    if value is None or str(value).strip() == '':
        return None
    value = str(value).strip()
    cursor.execute(
        """
        SELECT guid
        FROM nextris.tbuser
        WHERE username = %s OR nationalnumber = %s
        LIMIT 1
        """,
        (value, value),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _log_communication(endpoint, patient_id=None, patient_name=None,
                       accession_number=None, order_id=None,
                       request_body=None, response_status=200,
                       response_body=None, success=True, error_message=None,
                       start_time=None):
    """Registra un log de comunicación en la tabla communication_logs."""
    try:
        db_config = get_db_config()
        if not db_config:
            return
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        duration_ms = None
        if start_time:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        cursor.execute(
            """
            INSERT INTO nextris.communication_logs (
                guid, received_at, api_endpoint, http_method,
                patient_id, patient_name, accession_number, order_id,
                request_body, response_status, response_body,
                success, error_message, source_ip, duration_ms
            ) VALUES (
                %s, NOW(), %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            """,
            (
                str(uuid.uuid4()), endpoint, 'POST',
                patient_id, patient_name, accession_number, order_id,
                request_body, response_status, response_body,
                success, error_message, request.remote_addr, duration_ms,
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"[LOG] Error logging communication: {str(e)}")


def _communication_direction(endpoint):
    """Clasifica el sentido del mensaje para la vista de monitoreo."""
    return 'Enviado' if endpoint in (
        '/clinicaparque/reports/send',
        '/clinicaparque/reports/send-test',
    ) else 'Recibido'


def _serialize_communication_log(row, include_body=False):
    data = {
        'guid': row[0],
        # communication_logs.received_at is stored as UTC without timezone.
        # The suffix makes the contract explicit so clients can render it in
        # America/Argentina/Buenos_Aires instead of using browser local time.
        'received_at': f'{row[1].isoformat()}Z' if row[1] else None,
        'api_endpoint': row[2],
        'http_method': row[3],
        'patient_id': row[4],
        'patient_name': row[5],
        'accession_number': row[6],
        'order_id': row[7],
        'response_status': row[8],
        'success': row[9],
        'error_message': row[10],
        'source_ip': row[11],
        'duration_ms': row[12],
        'direction': _communication_direction(row[2]),
    }
    if include_body:
        data['request_body'] = row[13]
        data['response_body'] = row[14]
    return data


@api_blueprint.route('/clinicaparque/logs', methods=['GET'])
@jwt_required()
@require_permission('tabs.gestion.view', include_role_permissions=True)
def clinicaparque_communication_logs():
    """Consulta el historial de mensajes de la integración Clínica Parque."""
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(max(per_page, 1), 100)
    search = request.args.get('search', '').strip()
    endpoint_filter = request.args.get('api_endpoint', '').strip()
    success_filter = request.args.get('success', '').strip().lower()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if success_filter not in ('', 'true', 'false'):
        return jsonify({'success': False, 'message': 'El filtro success debe ser true o false'}), 400

    conditions = []
    params = []
    if search:
        conditions.append("""(
            api_endpoint ILIKE %s OR patient_id ILIKE %s OR patient_name ILIKE %s
            OR accession_number ILIKE %s OR order_id ILIKE %s
        )""")
        search_value = f'%{search}%'
        params.extend([search_value] * 5)
    if endpoint_filter:
        conditions.append('api_endpoint = %s')
        params.append(endpoint_filter)
    if success_filter:
        conditions.append('success = %s')
        params.append(success_filter == 'true')
    if date_from:
        conditions.append('received_at >= %s::date')
        params.append(date_from)
    if date_to:
        conditions.append("received_at < %s::date + interval '1 day'")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    offset = (page - 1) * per_page

    connection = None
    cursor = None
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT DISTINCT api_endpoint
            FROM nextris.communication_logs
            WHERE api_endpoint IS NOT NULL
            ORDER BY api_endpoint
            """
        )
        available_endpoints = sorted({
            *(row[0] for row in cursor.fetchall()),
            '/clinicaparque/cancel-study',
            '/clinicaparque/already-read',
        })
        cursor.execute(f"SELECT COUNT(*) FROM nextris.communication_logs {where_clause}", params)
        total = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT guid, received_at, api_endpoint, http_method,
                   patient_id, patient_name, accession_number, order_id,
                   response_status, success, error_message, source_ip,
                   duration_ms, NULL, NULL
            FROM nextris.communication_logs
            {where_clause}
            ORDER BY received_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        logs = [_serialize_communication_log(row) for row in cursor.fetchall()]
        return jsonify({
            'success': True,
            'data': {
                'items': logs,
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if total else 0,
                'available_endpoints': available_endpoints,
            },
        }), 200
    except Exception as e:
        print(f"[LOG] Error consultando communication_logs: {str(e)}")
        return jsonify({'success': False, 'message': 'No se pudo consultar el log de Clínica Parque'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@api_blueprint.route('/clinicaparque/logs/<log_guid>', methods=['GET'])
@jwt_required()
@require_permission('tabs.gestion.view', include_role_permissions=True)
def clinicaparque_communication_log_detail(log_guid):
    """Obtiene el contenido de un mensaje recibido/enviado."""
    connection = None
    cursor = None
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT guid, received_at, api_endpoint, http_method,
                   patient_id, patient_name, accession_number, order_id,
                   response_status, success, error_message, source_ip,
                   duration_ms, request_body, response_body
            FROM nextris.communication_logs
            WHERE guid = %s
            LIMIT 1
            """,
            (log_guid,),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Registro no encontrado'}), 404
        return jsonify({'success': True, 'data': _serialize_communication_log(row, include_body=True)}), 200
    except Exception as e:
        print(f"[LOG] Error consultando detalle de communication_logs: {str(e)}")
        return jsonify({'success': False, 'message': 'No se pudo consultar el detalle del registro'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _sanitize_error(e, endpoint_name):
    """Devuelve un mensaje genérico para el cliente, sin filtrar detalles internos."""
    print(f"[API CLINICAPARQUE {endpoint_name}] Error: {str(e)}")
    if isinstance(e, OperationalError):
        return 'Error de conexión a la base de datos. Intente nuevamente en unos segundos.'
    return 'Error interno del servidor. Contacte al administrador.'


@api_blueprint.route('/clinicaparque/confirm-study', methods=['POST'])
@api_blueprint.route('/clinicaparque/orders/<order_id>/confirm-study', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_confirm_study(order_id=None):
    """Confirma los datos clínicos de un estudio desde Clínica Parque.

    El cuerpo usa identificadores externos de la orden y del procedimiento.
    Los GUID de NextRIS no forman parte de este contrato.
    """
    connection = None
    cursor = None
    start_time = datetime.now()
    payload = request.get_json(silent=True)
    endpoint = '/clinicaparque/orders/<order_id>/confirm-study'

    try:
        if not isinstance(payload, dict):
            _log_communication(
                endpoint,
                request_body=str(payload),
                response_status=400,
                success=False,
                error_message='JSON inválido o vacío',
                start_time=start_time,
            )
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        # La variante plana recibe el identificador externo dentro del JSON.
        order_id = str(order_id or payload.get('orderId') or '').strip()
        accession = str(payload.get('accessionNumber') or '').strip() or None
        if not order_id and not accession:
            return jsonify({'success': False, 'message': 'orderId o accessionNumber es requerido'}), 400

        procedure_code = str(payload.get('procedure_code') or '').strip()
        if not procedure_code:
            return jsonify({'success': False, 'message': 'procedure_code es requerido'}), 400

        forbidden_fields = (
            'guid', 'exam_id', 'examination_guid', 'report_guid', 'patient_guid',
            'studytype_id', 'laterality_id', 'referring_physician_id',
            'requesting_physician_id',
        )
        received_forbidden = [field for field in forbidden_fields if field in payload]
        if received_forbidden:
            return jsonify({
                'success': False,
                'message': (
                    'Los identificadores internos no forman parte del contrato externo: '
                    + ', '.join(received_forbidden)
                ),
            }), 400

        referring_physician = str(
            payload.get('referring_physician')
            or payload.get('rad_id')
            or ''
        ).strip() or None
        requesting_physician_name = str(payload.get('requesting_physician_name') or '').strip() or None
        clinical_question = str(payload.get('clinical_question') or '').strip() or None
        other_details = str(payload.get('other_details') or '').strip() or None

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        _ensure_clinicaparque_order_links(cursor)

        order_row = _find_clinicaparque_order(cursor, order_id=order_id, accession=accession)
        if not order_row:
            return jsonify({'success': False, 'message': 'No se encontró la orden'}), 404
        exam_id = order_row[0]
        if accession and order_row[2] != accession:
            cursor.execute(
                "UPDATE nextris.tbexamination SET localacc = %s WHERE guid = %s",
                (accession, exam_id),
            )

        cursor.execute(
            """
            SELECT e.localacc, dp.patientid,
                   CONCAT(COALESCE(dp.name, ''), ' ', COALESCE(dp.surname, '')),
                   e.laterality_id
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON dp.guid = e.idpatient
            WHERE e.guid = %s
            LIMIT 1
            """,
            (exam_id,),
        )
        exam_row = cursor.fetchone()
        if not exam_row:
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404

        cursor.execute(
            "SELECT guid, description FROM nextris.isstudytype WHERE code = %s LIMIT 1",
            (procedure_code,),
        )
        studytype_row = cursor.fetchone()
        if not studytype_row:
            return jsonify({'success': False, 'message': 'procedure_code no existe'}), 400
        studytype_id = studytype_row[0]

        referring_physician_provided = 'referring_physician' in payload or 'rad_id' in payload
        referring_physician_id = _resolve_external_physician(cursor, referring_physician)
        requesting_physician_provided = any(
            key in payload for key in ('requesting_physician', 'req_doctor')
        )
        requesting_physician_id = _resolve_external_physician(
            cursor,
            payload.get('requesting_physician') or payload.get('req_doctor'),
        )
        laterality_provided = any(key in payload for key in ('laterality', 'lateralidad'))
        laterality_value = payload.get('laterality', payload.get('lateralidad'))
        laterality_id = _resolve_external_laterality(cursor, laterality_value) if laterality_provided else None

        update_parts = [
            '"w-order" = 1',
            'isexecuted = 1',
            'studytype_id = %s',
        ]
        update_values = [studytype_id]
        if referring_physician_provided:
            update_parts.append('idreferringphysician = %s')
            update_values.append(referring_physician_id)
        if requesting_physician_provided:
            update_parts.append('idrequestingphysician = %s')
            update_values.append(requesting_physician_id)
        if 'requesting_physician_name' in payload:
            update_parts.append('requestingphysician_name = %s')
            update_values.append(requesting_physician_name)
        if 'clinical_question' in payload:
            update_parts.append('clinicalquestion = %s')
            update_values.append(clinical_question)
        if 'other_details' in payload:
            update_parts.append('othersdetails = %s')
            update_values.append(other_details)
        if laterality_provided:
            update_parts.append('laterality_id = %s')
            update_values.append(laterality_id)

        update_values.append(exam_id)
        cursor.execute(
            f"UPDATE nextris.tbexamination SET {', '.join(update_parts)} WHERE guid = %s",
            update_values,
        )
        response = {
            'success': True,
            'message': 'Estudio confirmado correctamente',
            'orderId': order_id,
            'accessionNumber': accession or exam_row[0],
            'procedure_code': procedure_code,
            'lateralidad': laterality_value if laterality_provided else None,
        }
        _upsert_clinicaparque_order_link(
            cursor, order_id, None, exam_id, order_row[1], accession or exam_row[0]
        )
        connection.commit()
        _log_communication(
            endpoint,
            patient_id=exam_row[1],
            patient_name=(exam_row[2] or '').strip(),
            accession_number=exam_row[0],
            request_body=str(payload),
            response_status=200,
            response_body=str(response),
            success=True,
            start_time=start_time,
        )
        return jsonify(response), 200

    except ValueError as error:
        if connection:
            connection.rollback()
        _log_communication(
            endpoint,
            request_body=str(payload),
            response_status=400,
            success=False,
            error_message=str(error),
            start_time=start_time,
        )
        return jsonify({'success': False, 'message': str(error)}), 400
    except Exception as error:
        if connection:
            connection.rollback()
        user_message = _sanitize_error(error, 'CONFIRM STUDY')
        _log_communication(
            endpoint,
            request_body=str(payload),
            response_status=500,
            success=False,
            error_message=str(error),
            start_time=start_time,
        )
        return jsonify({'success': False, 'message': user_message}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _split_patient_name(full_name):
    parts = (full_name or '').strip().split(',', 1)
    surname = parts[0].strip() if parts else ''
    name = parts[1].strip() if len(parts) > 1 else ''
    return name, surname


def _find_or_create_patient(cursor, patient_id, patient_name):
    cursor.execute(
        "SELECT guid, name, surname FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
        (patient_id,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    name, surname = _split_patient_name(patient_name)
    guid = _generate_guid()
    cursor.execute(
        """
        INSERT INTO nextris.datapatient (guid, patientid, name, surname)
        VALUES (%s, %s, %s, %s)
        """,
        (guid, patient_id, name, surname),
    )
    return guid


def _extract_patient_id_from_dicomattrs(cursor, patient_pk):
    """Extract PatientID (0010,0020) from dcm4chee binary dicomattrs."""
    cursor.execute(
        "SELECT attrs FROM public.dicomattrs WHERE pk = "
        "(SELECT dicomattrs_fk FROM public.patient WHERE pk = %s)",
        (patient_pk,),
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return None

    raw = bytes(row[0])
    idx = 0
    while idx <= len(raw) - 8:
        if raw[idx:idx + 4] == b'\x10\x00\x20\x00':
            vr = raw[idx + 4:idx + 6].decode('ascii', errors='replace')
            if vr in ('LO', 'SH', 'PN'):
                val_len = raw[idx + 6] + raw[idx + 7] * 256
                if val_len > 0 and idx + 8 + val_len <= len(raw):
                    patient_id = raw[idx + 8:idx + 8 + val_len].decode(
                        'ascii', errors='replace',
                    ).strip()
                    if patient_id:
                        return patient_id
        idx += 1
    return None


def _parse_dicom_name(alphabetic_name):
    """Parse DICOM person name: LASTNAME^FIRSTNAME^MIDDLENAME^PREFIX^SUFFIX."""
    if not alphabetic_name:
        return '', ''
    parts = alphabetic_name.split('^')
    surname = parts[0].strip() if len(parts) > 0 else ''
    firstname = parts[1].strip() if len(parts) > 1 else ''
    return surname, firstname


def _format_dicom_date(dicom_date):
    """Convert DICOM date YYYYMMDD to YYYY-MM-DD."""
    if not dicom_date or dicom_date == '*' or len(dicom_date) != 8:
        return None
    try:
        datetime.strptime(dicom_date, '%Y%m%d')
        return f'{dicom_date[:4]}-{dicom_date[4:6]}-{dicom_date[6:8]}'
    except ValueError:
        return None


def _clean_study_desc(study_desc):
    """Clean PACS study descriptions, including the RES prefix used by MR studies."""
    if not study_desc or study_desc == '*':
        return None
    import re
    cleaned = re.sub(r'^(ECO\s+\d+\s*:\s*|ECO\s*:\s*|MAMO\s*:\s*|END\s*:\s*|RES\s*:\s*)', '', study_desc, flags=re.IGNORECASE).strip()
    return cleaned if cleaned and cleaned != '*' else None


def _match_studytype(cursor, study_desc):
    """Match a PACS study description to nextris.isstudytype. Returns guid or None."""
    cleaned = _clean_study_desc(study_desc)
    if not cleaned:
        return None

    # Exact match (case insensitive)
    cursor.execute(
        "SELECT guid FROM nextris.isstudytype WHERE UPPER(description) = UPPER(%s) LIMIT 1",
        (cleaned,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Substring match: cleaned desc contains studytype description
    cursor.execute(
        """SELECT guid FROM nextris.isstudytype
           WHERE UPPER(%s) LIKE '%%' || UPPER(description) || '%%'
           ORDER BY LENGTH(description) DESC LIMIT 1""",
        (cleaned,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _resolve_external_studytype(cursor, procedure_code, study_description=None):
    """Resolve an external procedure by code, falling back to its description.

    Procedure codes are the preferred identifier. The description fallback is
    needed for orders whose code was added in the external system after the
    local procedure catalog was synchronized.
    """
    if procedure_code:
        cursor.execute(
            "SELECT guid FROM nextris.isstudytype WHERE code = %s LIMIT 1",
            (procedure_code,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    return _match_studytype(cursor, study_description)


def _get_external_study_description(order_data):
    """Read the study description using the supported external field names."""
    for field in ('study_description', 'StudyDescription', 'studyDescription',
                  'procedure_description', 'procedure_name'):
        value = order_data.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _link_existing_pacs_studies(cursor, patient_guid, dicom_patient_id):
    """
    Search PACS for existing studies belonging to this patient and create
    nextris.tbexamination + tbreport for each one that doesn't already exist.

    Returns list of created examination dicts.
    """
    created = []

    # Find all PACS studies for this PatientID
    cursor.execute(
        """
        SELECT s.pk, s.study_iuid, s.accession_no, s.study_desc, s.study_date
        FROM public.study s
        JOIN public.patient p ON p.pk = s.patient_fk
        JOIN public.dicomattrs da ON da.pk = p.dicomattrs_fk
        WHERE public._parse_dicom_patient_id(da.attrs) = %s
        ORDER BY s.created_time DESC
        """,
        (dicom_patient_id,),
    )
    pacs_studies = cursor.fetchall()

    for study_row in pacs_studies:
        pacs_study_pk = study_row[0]
        study_iuid = study_row[1]
        accession_no = study_row[2]
        study_desc = study_row[3]

        # Skip if examination already exists
        exists = False
        if accession_no and accession_no != '*':
            cursor.execute(
                "SELECT guid FROM nextris.tbexamination WHERE localacc = %s LIMIT 1",
                (accession_no,),
            )
            exists = cursor.fetchone() is not None

        if not exists and study_iuid and study_iuid != '*':
            cursor.execute(
                "SELECT guid FROM nextris.tbexamination WHERE studyinstanceuid = %s LIMIT 1",
                (study_iuid,),
            )
            exists = cursor.fetchone() is not None

        if exists:
            continue

        # Match study type
        studytype_id = _match_studytype(cursor, study_desc)

        # Generate ADM number
        cursor.execute("SELECT nextval('nextris.seq_adm_number')")
        nr = cursor.fetchone()[0]
        adm_number = f'ADM{nr:06d}'

        # Create examination
        exam_guid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO nextris.tbexamination (
                guid, idpatient, studytype_id,
                admisionnumber, localacc, studyinstanceuid,
                status, isexecuted, isreported, isimage,
                createdon, executedon, "w-order"
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, 0, 1,
                NOW(), %s, %s
            )
            """,
            (
                exam_guid, patient_guid, studytype_id,
                adm_number,
                accession_no if accession_no and accession_no != '*' else None,
                study_iuid if study_iuid and study_iuid != '*' else None,
                'Scheduled',
                0,
                None,
                0,
            ),
        )

        # Create empty report
        report_guid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO nextris.tbreport (
                guid, idexamination, idpatient, admnumber, createdon, wassaved
            ) VALUES (
                %s, %s, %s, %s, NOW(), FALSE
            )
            """,
            (report_guid, exam_guid, patient_guid, adm_number),
        )

        created.append({
            'accession_number': accession_no,
            'study_uid': study_iuid,
            'admision_number': adm_number,
        })

    return created


def _find_equipment(cursor, machine):
    cursor.execute(
        "SELECT guid FROM nextris.isequipment WHERE UPPER(aetitle) = UPPER(%s) LIMIT 1",
        (machine,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "SELECT guid FROM nextris.isequipment WHERE UPPER(description) = UPPER(%s) LIMIT 1",
        (machine,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _next_sequence(cursor, prefix, column='admisionnumber'):
    cursor.execute(f"""
        SELECT COALESCE(MAX(CAST(SUBSTRING({column} FROM {len(prefix)+1}) AS INTEGER)), 0) + 1
        FROM nextris.tbexamination
        WHERE {column} LIKE %s
    """, (f'{prefix}%',))
    return cursor.fetchone()[0]


@api_blueprint.route('/clinicaparque/patients', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_create_patient():
    """
    Crear un nuevo paciente desde sistema externo (Clínica Parque).

    POST /api/clinicaparque/patients
    Authorization: Bearer <token>
    Content-Type: application/json

    Body para paciente Final (F):
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

    Body para paciente Temporal (T) o Neonatal (N):
    {
        "patient": {
            "id": "ID_INTERNO_123",
            "patient_type": "T"
        }
    }

    Campos:
      - id              (requerido siempre) - Identificador único en el sistema origen
      - patient_type    (requerido siempre) - Tipo de paciente (T=Temporal, F=Final, N=Neonatal)
      - dni             (requerido solo si F) - Documento Nacional de Identidad
      - name            (requerido solo si F) - Nombre completo del paciente
      - birthdate       (requerido solo si F) - Fecha de nacimiento (YYYY-MM-DD)
      - sex             (requerido solo si F) - Sexo (M, F, O)
      - healthcard_type (requerido solo si F) - Tipo de cobertura (Particular, Obra Social, Prepaga)
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload or 'patient' not in payload:
            _log_communication('/clinicaparque/patients', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='JSON inválido: se requiere nodo "patient"')
            return jsonify({'success': False, 'message': 'JSON inválido: se requiere nodo "patient"'}), 400

        patient = payload['patient']
        if not isinstance(patient, dict):
            _log_communication('/clinicaparque/patients', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='El nodo "patient" debe ser un objeto JSON')
            return jsonify({'success': False, 'message': 'El nodo "patient" debe ser un objeto JSON'}), 400

        if not patient.get('id'):
            _log_communication('/clinicaparque/patients', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='id es requerido', start_time=start_time)
            return jsonify({'success': False, 'message': 'id es requerido'}), 400

        ptype = patient.get('patient_type', '').strip()
        if ptype not in ('T', 'F', 'N'):
            _log_communication('/clinicaparque/patients', patient_id=patient.get('id'),
                             request_body=str(payload), response_status=400,
                             success=False, error_message='patient_type debe ser T, F o N',
                             start_time=start_time)
            return jsonify({'success': False, 'message': 'patient_type debe ser T, F o N'}), 400

        is_temporal_or_neonatal = ptype in ('T', 'N')
        complex_fields = ['dni', 'name', 'birthdate', 'sex', 'healthcard_type']
        if is_temporal_or_neonatal:
            missing = []
        else:
            required_fields = ['id', 'patient_type'] + complex_fields
            missing = [f for f in required_fields if not patient.get(f)]
        if missing:
            msg = f'Campos faltantes: {", ".join(missing)}'
            _log_communication('/clinicaparque/patients', patient_id=patient.get('id'),
                             patient_name=patient.get('name'), request_body=str(payload),
                             response_status=400, success=False, error_message=msg,
                             start_time=start_time)
            return jsonify({'success': False, 'message': msg}), 400

        if patient.get('sex') and patient['sex'] not in ('M', 'F', 'O'):
            _log_communication('/clinicaparque/patients', patient_id=patient.get('id'),
                             request_body=str(payload), response_status=400,
                             success=False, error_message='sex debe ser M, F u O',
                             start_time=start_time)
            return jsonify({'success': False, 'message': 'sex debe ser M, F u O'}), 400

        if patient.get('birthdate'):
            try:
                datetime.strptime(patient['birthdate'], '%Y-%m-%d')
            except ValueError:
                _log_communication('/clinicaparque/patients', patient_id=patient.get('id'),
                                 request_body=str(payload), response_status=400,
                                 success=False, error_message='birthdate debe tener formato YYYY-MM-DD',
                                 start_time=start_time)
                return jsonify({'success': False, 'message': 'birthdate debe tener formato YYYY-MM-DD'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        _ensure_patient_type_columns(cursor)
        _ensure_clinicaparque_order_links(cursor)

        external_id = patient['id'].strip()
        cursor.execute(
            "SELECT guid FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (external_id,),
        )
        existing = cursor.fetchone()
        if existing:
            existing_guid = existing[0]
            cursor.execute(
                "SELECT guid FROM nextris.tbuser_patient WHERE datapatient_id = %s LIMIT 1",
                (existing_guid,),
            )
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Ya existe un paciente con id: {external_id}'
                }), 400

            # Update patient data if existing record has incomplete data (e.g., from PACS)
            if not is_temporal_or_neonatal and ptype == 'F':
                cursor.execute(
                    "SELECT nationalcode, name, surname FROM nextris.datapatient WHERE guid = %s",
                    (existing_guid,),
                )
                row = cursor.fetchone()
                if row:
                    cur_nc = row[0] or ''
                    cur_name = row[1] or ''
                    cur_surname = row[2] or ''
                    # Detect PACS-created patients: nationalcode == patientid, or name empty
                    is_pacs = (cur_nc == external_id) or (cur_name == '') or (cur_name == cur_surname)

                    if is_pacs:
                        full_name = patient.get('name', '').strip()
                        parts = full_name.split(',', 1) if full_name else ['', '']
                        new_surname = parts[0].strip()
                        new_name = parts[1].strip() if len(parts) > 1 else ''
                        new_dni = patient.get('dni', '').strip()
                        birthdate = patient.get('birthdate')
                        if birthdate is not None and str(birthdate).strip() == '':
                            birthdate = None

                        if new_name and new_surname:
                            cursor.execute(
                                """
                                UPDATE nextris.datapatient
                                SET name = %s, surname = %s, nationalcode = %s,
                                    birthdate = COALESCE(%s, birthdate),
                                    sexcode = COALESCE(%s, sexcode)
                                WHERE guid = %s
                                """,
                                (new_name, new_surname, new_dni,
                                 birthdate, patient.get('sex'), existing_guid),
                            )

            dni = patient.get('dni', '').strip()
            password_raw = dni[-3:] if len(dni) >= 3 else external_id[-3:] if len(external_id) >= 3 else external_id
            hashed_password = hash_pass(password_raw)

            cursor.execute(
                """
                INSERT INTO nextris.tbuser_patient
                    (guid, username, password, datapatient_id, status, firstlogin)
                VALUES (%s, %s, %s, %s, 'Active', 0)
                """,
                (str(uuid.uuid4()), external_id, hashed_password, existing_guid),
            )
            connection.commit()
            cursor.close()
            connection.close()

            response = {
                'success': True,
                'message': 'Paciente actualizado y usuario portal creado',
                'patientid': external_id,
                'username': external_id,
            }
            _log_communication('/clinicaparque/patients', patient_id=external_id,
                             patient_name=patient.get('name'), request_body=str(payload),
                             response_status=200, response_body=str(response),
                             success=True, start_time=start_time)
            return jsonify(response), 200

        full_name = patient.get('name', '').strip()
        parts = full_name.split(',', 1) if full_name else ['', '']
        surname = parts[0].strip() if parts else ''
        patient_name = parts[1].strip() if len(parts) > 1 else ''

        patient_guid = str(uuid.uuid4())

        birthdate = patient.get('birthdate')
        if birthdate is not None and str(birthdate).strip() == '':
            birthdate = None

        cursor.execute(
            """
            INSERT INTO nextris.datapatient
                (guid, patientid, nationalcode, name, surname, birthdate, sexcode,
                 patient_type, healthcard_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_guid,
                external_id,
                patient.get('dni', '').strip(),
                patient_name,
                surname,
                birthdate,
                patient.get('sex'),
                patient.get('patient_type', '').strip(),
                patient.get('healthcard_type', ''),
            ),
        )

        dni = patient.get('dni', '').strip()
        password_raw = dni[-3:] if len(dni) >= 3 else external_id[-3:] if len(external_id) >= 3 else external_id
        hashed_password = hash_pass(password_raw)

        cursor.execute(
            """
            INSERT INTO nextris.tbuser_patient
                (guid, username, password, datapatient_id, status, firstlogin)
            VALUES (%s, %s, %s, %s, 'Active', 0)
            """,
            (str(uuid.uuid4()), external_id, hashed_password, patient_guid),
        )

        # Link existing PACS studies for this patient
        linked_studies = []
        try:
            linked_studies = _link_existing_pacs_studies(cursor, patient_guid, external_id)
        except Exception as link_err:
            print(f"[API CLINICAPARQUE] Error linking PACS studies: {link_err}")

        connection.commit()
        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Paciente creado exitosamente',
            'patientid': external_id,
            'username': external_id,
        }
        if linked_studies:
            response['linked_studies'] = linked_studies
            response['message'] = f'Paciente creado exitosamente. {len(linked_studies)} estudio(s) vinculado(s).'
        _log_communication('/clinicaparque/patients', patient_id=external_id,
                         patient_name=patient.get('name'), request_body=str(payload),
                         response_status=200, response_body=str(response),
                         success=True, start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'CREATE PATIENT')
        try:
            _patient_id = patient.get('id') if ('patient' in dir() and isinstance(patient, dict)) else None
        except Exception:
            _patient_id = None
        _log_communication('/clinicaparque/patients', patient_id=_patient_id,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


@api_blueprint.route('/clinicaparque/patients/update', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_update_patient():
    """
    Actualizar datos de un paciente existente desde sistema externo.

    POST /api/clinicaparque/patients/update
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
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

    Campos:
      - old_id          (requerido) - Identificador actual del paciente (clave de búsqueda)
      - id              (requerido) - Identificador nuevo o definitivo
      - dni             (requerido) - DNI corregido
      - name            (requerido) - Nombre completo corregido
      - birthdate       (requerido) - Fecha de nacimiento corregida (YYYY-MM-DD)
      - sex             (requerido) - Sexo (M, F, O)
      - patient_type    (requerido) - Tipo de paciente (T=Temporal, F=Final, N=Neonatal)
      - healthcard_type (requerido) - Tipo de cobertura (Particular, Obra Social, Prepaga)
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload or 'patient' not in payload:
            _log_communication('/clinicaparque/patients/update', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='JSON inválido: se requiere nodo "patient"')
            return jsonify({'success': False, 'message': 'JSON inválido: se requiere nodo "patient"'}), 400

        patient = payload['patient']
        if not isinstance(patient, dict):
            _log_communication('/clinicaparque/patients/update', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='El nodo "patient" debe ser un objeto JSON')
            return jsonify({'success': False, 'message': 'El nodo "patient" debe ser un objeto JSON'}), 400

        required_fields = ['old_id', 'id', 'dni', 'name', 'birthdate', 'sex', 'patient_type', 'healthcard_type']
        missing = [f for f in required_fields if not patient.get(f)]
        if missing:
            msg = f'Campos faltantes: {", ".join(missing)}'
            _log_communication('/clinicaparque/patients/update', patient_id=patient.get('old_id'),
                             request_body=str(payload), response_status=400,
                             success=False, error_message=msg, start_time=start_time)
            return jsonify({'success': False, 'message': msg}), 400

        if patient['sex'] not in ('M', 'F', 'O'):
            return jsonify({'success': False, 'message': 'sex debe ser M, F u O'}), 400

        if patient['patient_type'] not in ('T', 'F', 'N'):
            return jsonify({'success': False, 'message': 'patient_type debe ser T, F o N'}), 400

        try:
            datetime.strptime(patient['birthdate'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'birthdate debe tener formato YYYY-MM-DD'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        _ensure_patient_type_columns(cursor)

        old_id = patient['old_id'].strip()
        cursor.execute(
            "SELECT guid FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (old_id,),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'No se encontró paciente con old_id: {old_id}'
            }), 400

        patient_guid = row[0]
        new_id = patient['id'].strip()

        if new_id != old_id:
            cursor.execute(
                "SELECT guid FROM nextris.datapatient WHERE patientid = %s AND guid != %s LIMIT 1",
                (new_id, patient_guid),
            )
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Ya existe otro paciente con id: {new_id}'
                }), 400

        full_name = patient['name'].strip()
        parts = full_name.split(',', 1)
        surname = parts[0].strip() if parts else ''
        name = parts[1].strip() if len(parts) > 1 else ''

        cursor.execute(
            """
            UPDATE nextris.datapatient
            SET patientid       = %s,
                nationalcode    = %s,
                name            = %s,
                surname         = %s,
                birthdate       = %s,
                sexcode         = %s,
                patient_type    = %s,
                healthcard_type = %s
            WHERE guid = %s
            """,
            (
                new_id,
                patient['dni'].strip(),
                name,
                surname,
                patient['birthdate'],
                patient['sex'],
                patient['patient_type'].strip(),
                patient['healthcard_type'],
                patient_guid,
            ),
        )

        connection.commit()

        # Ensure portal user exists for this patient
        # Username is always synced to patient_id (not name+surname)
        cursor.execute(
            "SELECT guid FROM nextris.tbuser_patient WHERE datapatient_id = %s LIMIT 1",
            (patient_guid,),
        )
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.execute(
                "UPDATE nextris.tbuser_patient SET username = %s WHERE guid = %s",
                (new_id, existing_user[0]),
            )
            connection.commit()
        else:
            username = new_id
            dni = patient['dni'].strip()
            password_raw = dni[-3:] if len(dni) >= 3 else dni
            hashed_password = hash_pass(password_raw)
            cursor.execute(
                """
                INSERT INTO nextris.tbuser_patient
                    (guid, username, password, datapatient_id, status, firstlogin)
                VALUES (%s, %s, %s, %s, 'Active', 0)
                """,
                (str(uuid.uuid4()), username, hashed_password, patient_guid),
            )
            connection.commit()

        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Paciente actualizado exitosamente',
            'patientid': new_id,
        }
        _log_communication('/clinicaparque/patients/update', patient_id=patient.get('old_id'),
                         patient_name=patient['name'], request_body=str(payload),
                         response_status=200, response_body=str(response),
                         success=True, start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'UPDATE PATIENT')
        try:
            _patient_id = patient.get('old_id') if ('patient' in dir() and isinstance(patient, dict)) else None
        except Exception:
            _patient_id = None
        _log_communication('/clinicaparque/patients/update',
                         patient_id=_patient_id,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


@api_blueprint.route('/clinicaparque/orders', methods=['POST'])
def receive_clinicaparque_orders():
    """
    Recibe órdenes de Clínica Parque y crea exámenes listos para redactar.

    POST /api/clinicaparque/orders
    Content-Type: application/json

    Body (una orden):
    {
        "patient_id": "12345",
        "patient_name": "Juan Pérez",
        "accession_number": "ACC-001",
        "machine": "CT-01"
        "procedure_code": "RX-01"
    }

    Body (múltiples órdenes):
    [
        { "orderId": "...", "patient_id": "...", "patient_name": "...", "accession_number": "...", "machine": "...", "procedure_code": "..." },
        { "orderId": "...", "patient_id": "...", "patient_name": "...", "accession_number": "...", "machine": "...", "procedure_code": "..." }
    ]

    Campos:
      - patient_id          (requerido) - ID del paciente en el sistema externo
      - patient_name        (requerido) - Nombre completo del paciente
      - accession_number    (requerido) - Número de acceso / estudio
      - machine             (opcional) - AE Title o descripción del equipo
      - procedure_code      (requerido) - Código externo del tipo de estudio, por ejemplo `3153`

    Response 200:
    {
        "success": true,
        "created": 2,
        "failed": 0,
        "results": [
            { "orderId": "ORD-001", "accession_number": "ACC-001", "admision_number": "ADM000001", "status": "created" },
            { "orderId": "ORD-002", "accession_number": "ACC-002", "admision_number": "ADM000002", "status": "created" }
        ],
        "errors": []
    }
    """
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        orders = payload if isinstance(payload, list) else [payload]

        if not orders:
            return jsonify({'success': False, 'message': 'Se requiere al menos una orden'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        _ensure_clinicaparque_order_links(cursor)

        created = []
        errors = []

        for idx, order in enumerate(orders):
            forbidden_fields = [
                field for field in (
                    'guid', 'exam_id', 'examination_guid', 'report_guid',
                    'patient_guid', 'procedure_id', 'studytype_id',
                    'location_id', 'equipment_id',
                ) if field in order
            ]
            if forbidden_fields:
                errors.append({
                    'index': idx,
                    'accession_number': order.get('accession_number'),
                    'error': (
                        'Los identificadores internos no forman parte del contrato externo: '
                        + ', '.join(forbidden_fields)
                    ),
                })
                continue

            accession = (order.get('accession_number') or '').strip()
            patient_id = (order.get('patient_id') or '').strip()
            patient_name = (order.get('patient_name') or '').strip()
            machine = (order.get('machine') or '').strip()
            procedure_code = (order.get('procedure_code') or '').strip()

            missing = []
            if not patient_id:
                missing.append('patient_id')
            if not patient_name:
                missing.append('patient_name')
            if not accession:
                missing.append('accession_number')
            if not procedure_code:
                missing.append('procedure_code')

            if missing:
                errors.append({
                    'index': idx,
                    'accession_number': accession or None,
                    'error': f'Campos faltantes: {", ".join(missing)}',
                })
                continue

            try:
                cursor.execute(
                    "SELECT guid FROM nextris.tbexamination WHERE localacc = %s LIMIT 1",
                    (accession,),
                )
                existing_exam_row = cursor.fetchone()
                existing_exam_guid = existing_exam_row[0] if existing_exam_row else None

                patient_guid = _find_or_create_patient(cursor, patient_id, patient_name)

                # El equipo es opcional. Si se informa, se valida contra
                # isequipment; si se omite, el examen queda sin equipo.
                equipment_guid = _find_equipment(cursor, machine) if machine else None
                if machine and not equipment_guid:
                    errors.append({
                        'index': idx,
                        'accession_number': accession,
                        'error': f'Equipo no encontrado: {machine}',
                    })
                    continue

                cursor.execute(
                    """
                    SELECT guid FROM nextris.isstudytype
                    WHERE code = %s
                    LIMIT 1
                    """,
                    (procedure_code,),
                )
                study_type_row = cursor.fetchone()
                if not study_type_row:
                    errors.append({
                        'index': idx,
                        'accession_number': accession,
                        'error': f'Tipo de estudio no encontrado: {procedure_code}',
                    })
                    continue
                procedure_id = study_type_row[0]

                if equipment_guid:
                    cursor.execute(
                        "SELECT location_id FROM nextris.isequipment WHERE guid = %s LIMIT 1",
                        (equipment_guid,),
                    )
                    loc_row = cursor.fetchone()
                    location_id = loc_row[0] if loc_row else None
                else:
                    cursor.execute(
                        """
                        SELECT guid FROM nextris.tblocation
                        WHERE facility_id = '1'
                        ORDER BY name
                        LIMIT 1
                        """
                    )
                    loc_row = cursor.fetchone()
                    location_id = loc_row[0] if loc_row else None

                if existing_exam_guid:
                    # La imagen pudo haber creado primero el examen. La
                    # llegada de la orden lo habilita para Redacción.
                    cursor.execute(
                        """
                        UPDATE nextris.tbexamination
                        SET "w-order" = 1,
                            studytype_id = %s,
                            idequipment = COALESCE(%s, idequipment),
                            location_id = COALESCE(location_id, %s),
                            isexecuted = 1,
                            status = 'Executed',
                            executedon = COALESCE(executedon, NOW())
                        WHERE guid = %s
                        """,
                        (procedure_id, equipment_guid, location_id, existing_exam_guid),
                    )
                    cursor.execute(
                        "SELECT guid FROM nextris.tbreport WHERE idexamination = %s LIMIT 1",
                        (existing_exam_guid,),
                    )
                    existing_report_row = cursor.fetchone()
                    order_ref = (order.get('orderId') or order.get('order_id') or accession).strip()
                    _upsert_clinicaparque_order_link(
                        cursor, order_ref, patient_id, existing_exam_guid,
                        existing_report_row[0] if existing_report_row else None, accession,
                    )
                    created.append({
                        'index': idx,
                        'accession_number': accession,
                        'orderId': order_ref,
                        'status': 'updated',
                    })
                    continue

                next_adm = _next_sequence(cursor, 'ADM', 'admisionnumber')
                adm_number = f'ADM{next_adm:06d}'

                exam_guid = _generate_guid()
                report_guid = _generate_guid()

                cursor.execute(
                    """
                    INSERT INTO nextris.tbexamination (
                        guid, idpatient, studytype_id, idequipment,
                        admisionnumber, localacc,
                        status, isexecuted, createdon, executedon,
                        location_id, "w-order"
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s,
                        'Executed', 1, NOW(), NOW(),
                        %s, 1
                    )
                    """,
                    (
                        exam_guid, patient_guid, procedure_id, equipment_guid,
                        adm_number, accession,
                        location_id,
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO nextris.tbreport (
                        guid, idexamination, idpatient, admnumber, createdon, wassaved
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), FALSE
                    )
                    """,
                    (report_guid, exam_guid, patient_guid, adm_number),
                )

                order_ref = (order.get('orderId') or order.get('order_id') or accession).strip()
                _upsert_clinicaparque_order_link(
                    cursor, order_ref, patient_id, exam_guid, report_guid, accession,
                )

                created.append({
                    'index': idx,
                    'accession_number': accession,
                    'orderId': order_ref,
                    'admision_number': adm_number,
                    'status': 'created',
                })

            except Exception as order_err:
                errors.append({
                    'index': idx,
                    'accession_number': accession,
                    'error': str(order_err),
                })
                continue

        if created:
            connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'created': len(created),
            'failed': len(errors),
            'results': created,
            'errors': errors,
        }), 200 if created else 400

    except Exception as e:
        user_msg = _sanitize_error(e, 'ORDERS')
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Recepción de Reportes Finalizados
# =============================================================================
@api_blueprint.route('/clinicaparque/reports', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_receive_report():
    """
    Recibe reportes finalizados desde sistema externo (Clínica Parque).
    Crea o actualiza paciente, examen y reporte en la base de datos.

    POST /api/clinicaparque/reports
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
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
            "study_reason": "...",
            "technique": "...",
            "narrative": "...",
            "findings": "...",
            "impressions": "...",
            "conclusions": "...",
            "study_uid": "1.2.840.113619..."
        }
    }

    report_type: NR=Nuevo Reporte, NV=Nueva Versión, A=Addenda
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload:
            _log_communication('/clinicaparque/reports', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='JSON inválido o vacío')
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        patient_data = payload.get('patient')
        order_data = payload.get('order')
        report_data = payload.get('report')

        if not patient_data or not order_data or not report_data:
            _log_communication('/clinicaparque/reports',
                             patient_id=patient_data.get('id') if patient_data else None,
                             accession_number=order_data.get('accessionNumber') if order_data else None,
                             request_body=str(payload), response_status=400, success=False,
                             error_message='Se requieren los nodos: patient, order, report',
                             start_time=start_time)
            return jsonify({
                'success': False,
                'message': 'Se requieren los nodos: patient, order, report'
            }), 400

        patient_required = ['id', 'dni', 'name', 'birthdate', 'sex']
        order_required = ['orderId', 'accessionNumber', 'procedure_code', 'report_type', 'modality']
        report_required = ['study_uid']

        missing = []
        for f in patient_required:
            if not patient_data.get(f):
                missing.append(f'patient.{f}')
        for f in order_required:
            if not order_data.get(f):
                missing.append(f'order.{f}')
        for f in report_required:
            if not report_data.get(f):
                missing.append(f'report.{f}')

        if missing:
            return jsonify({
                'success': False,
                'message': f'Campos faltantes: {", ".join(missing)}'
            }), 400

        report_type = order_data['report_type'].strip().upper()
        if report_type not in ('NR', 'NV', 'A'):
            return jsonify({
                'success': False,
                'message': 'report_type debe ser NR, NV o A'
            }), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        _ensure_patient_type_columns(cursor)
        _ensure_clinicaparque_order_links(cursor)

        external_id = patient_data['id'].strip()
        cursor.execute(
            "SELECT guid FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (external_id,),
        )
        row = cursor.fetchone()
        if row:
            patient_guid = row[0]
        else:
            full_name = patient_data['name'].strip()
            parts = full_name.split(',', 1)
            surname = parts[0].strip() if parts else ''
            name = parts[1].strip() if len(parts) > 1 else ''
            patient_guid = _generate_guid()
            birthdate = patient_data['birthdate']
            if birthdate is not None and str(birthdate).strip() == '':
                birthdate = None
            cursor.execute(
                """
                INSERT INTO nextris.datapatient
                    (guid, patientid, nationalcode, name, surname, birthdate, sexcode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (patient_guid, external_id, patient_data['dni'].strip(),
                 name, surname, birthdate, patient_data['sex']),
            )

        accession = order_data['accessionNumber'].strip()
        order_id = order_data['orderId'].strip()
        procedure_code = order_data['procedure_code'].strip()

        cursor.execute(
            "SELECT guid FROM nextris.isstudytype WHERE code = %s LIMIT 1",
            (procedure_code,),
        )
        st_row = cursor.fetchone()
        if st_row:
            studytype_id = st_row[0]
        else:
            studytype_id = None

        mapped_order = _find_clinicaparque_order(
            cursor, order_id=order_id, accession=accession,
        )
        exam_row = (mapped_order[0],) if mapped_order else None

        if exam_row:
            exam_guid = exam_row[0]
            if mapped_order[2] != accession:
                cursor.execute(
                    "UPDATE nextris.tbexamination SET localacc = %s WHERE guid = %s",
                    (accession, exam_guid),
                )
        else:
            exam_guid = _generate_guid()
            next_adm = _next_sequence(cursor, 'ADM', 'admisionnumber')
            adm_number = f'ADM{next_adm:06d}'

            modality = order_data['modality'].strip()
            cursor.execute(
                "SELECT guid FROM nextris.isequipment WHERE UPPER(aetitle) = UPPER(%s) LIMIT 1",
                (modality,),
            )
            eq_row = cursor.fetchone()
            equipment_guid = eq_row[0] if eq_row else None

            cursor.execute(
                """
                INSERT INTO nextris.tbexamination (
                    guid, idpatient, studytype_id, idequipment,
                    admisionnumber, localacc, studyinstanceuid,
                    status, isexecuted, isreported, createdon, executedon, reportdate
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    'Reported', 1, 1, NOW(), NOW(), NOW()
                )
                """,
                (
                    exam_guid, patient_guid, studytype_id, equipment_guid,
                    adm_number, accession, report_data['study_uid'],
                ),
            )

        rad_id = order_data.get('rad_id', '').strip() or None
        if rad_id:
            rad_guid = _resolve_external_physician(cursor, rad_id)
        else:
            rad_guid = None

        report_date_str = order_data.get('report_date', '').strip()
        report_date = None
        if report_date_str:
            try:
                report_date = datetime.strptime(report_date_str, '%Y-%m-%d')
            except ValueError:
                report_date = None

        if report_type in ('NR', 'NV'):
            report_fields = normalize_report_payload(
                report_data,
                reason_fallback=report_data.get('study_reason')
                    or order_data.get('clinicalquestion') or order_data.get('history')
            )
            cursor.execute(
                "SELECT guid FROM nextris.tbreport WHERE idexamination = %s LIMIT 1",
                (exam_guid,),
            )
            existing_report = cursor.fetchone()

            if existing_report:
                report_guid = existing_report[0]
                cursor.execute(
                    """
                    UPDATE nextris.tbreport SET
                        study_reason = %s,
                        content = %s,
                        conclusion = %s,
                        iduser = %s,
                        date = %s,
                        wassaved = TRUE
                    WHERE guid = %s
                    """,
                    (
                        report_fields.get('study_reason', ''),
                        report_fields.get('content', ''),
                        report_fields.get('conclusion', ''),
                        rad_guid,
                        report_date,
                        report_guid,
                    ),
                )
            else:
                report_guid = _generate_guid()
                adm_number = accession
                cursor.execute(
                    """
                    INSERT INTO nextris.tbreport (
                        guid, idexamination, idpatient, admnumber,
                        study_reason, content, conclusion,
                        iduser, date, createdon, wassaved
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, NOW(), TRUE
                    )
                    """,
                    (
                        report_guid, exam_guid, patient_guid, adm_number,
                        report_fields.get('study_reason', ''),
                        report_fields.get('content', ''),
                        report_fields.get('conclusion', ''),
                        rad_guid,
                        report_date,
                    ),
                )

            cursor.execute(
                """
                UPDATE nextris.tbexamination SET
                    isreported = 1,
                    status = 'Reported',
                    reportdate = COALESCE(%s, NOW()),
                    studyinstanceuid = COALESCE(%s, studyinstanceuid)
                WHERE guid = %s
                """,
                (report_date, report_data.get('study_uid'), exam_guid),
            )

        elif report_type == 'A':
            cursor.execute(
                """SELECT guid, study_reason, content, conclusion,
                          findings, techniques, impressions, conclusions
                   FROM nextris.tbreport WHERE idexamination = %s LIMIT 1""",
                (exam_guid,),
            )
            existing_report = cursor.fetchone()

            if not existing_report:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'No se encontró reporte existente para addenda. accessionNumber: {accession}'
                }), 400

            report_guid = existing_report[0]
            fields = canonical_fields_from_row(
                existing_report[1], existing_report[2], existing_report[3],
                legacy_findings=existing_report[4], legacy_technique=existing_report[5],
                legacy_impressions=existing_report[6], legacy_conclusion=existing_report[7],
            )
            new_fields = normalize_report_payload(report_data)

            addenda_date = datetime.now().strftime('%d/%m/%Y')
            addenda_tag = f'[ADDENDA {addenda_date}]'

            new_content = new_fields.get('content', '')
            new_conclusion = new_fields.get('conclusion', '')
            combined_content = (
                f"{fields['content']}<p><strong>{addenda_tag} Contenido:</strong></p>{new_content}"
            ).strip() if new_content else fields['content']
            combined_conclusion = (
                f"{fields['conclusion']}<p><strong>{addenda_tag} Conclusión:</strong></p>{new_conclusion}"
            ).strip() if new_conclusion else fields['conclusion']

            cursor.execute(
                """
                UPDATE nextris.tbreport SET
                    content = %s,
                    conclusion = %s,
                    iduser = COALESCE(%s, iduser),
                    date = %s,
                    wassaved = TRUE
                WHERE guid = %s
                """,
                (
                    combined_content,
                    combined_conclusion,
                    rad_guid,
                    report_date,
                    report_guid,
                ),
            )

        _upsert_clinicaparque_order_link(
            cursor, order_id, external_id, exam_guid, report_guid, accession,
        )
        connection.commit()
        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': f'Reporte ({report_type}) procesado exitosamente',
            'orderId': order_id,
            'accession_number': accession,
            'report_type': report_type,
        }
        _log_communication('/clinicaparque/reports',
                         patient_id=patient_data.get('id'),
                         patient_name=patient_data.get('name'),
                         accession_number=accession,
                         order_id=order_data.get('orderId'),
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'REPORT')
        try:
            _pid = patient_data.get('id') if ('patient_data' in dir() and isinstance(patient_data, dict)) else None
        except Exception:
            _pid = None
        try:
            _acc = order_data.get('accessionNumber') if ('order_data' in dir() and isinstance(order_data, dict)) else None
        except Exception:
            _acc = None
        _log_communication('/clinicaparque/reports',
                         patient_id=_pid,
                         accession_number=_acc,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Notificación de Apertura de Estudio (Paciente)
# =============================================================================
@api_blueprint.route('/clinicaparque/study-open', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_study_open():
    """
    Registra evento cuando un paciente abre/visualiza su estudio/reporte.

    POST /api/clinicaparque/study-open
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
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
            "study_uid": "1.2.840.113619..."
        }
    }
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload:
            _log_communication('/clinicaparque/study-open', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='JSON inválido o vacío')
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        event_data = payload.get('event', {})
        patient_data = payload.get('patient', {})
        order_data = payload.get('order', {})
        study_data = payload.get('study', {})

        if event_data.get('eventType') != 'PATIENT_VIEW':
            _log_communication('/clinicaparque/study-open',
                             patient_id=patient_data.get('id'),
                             accession_number=order_data.get('accessionNumber'),
                             request_body=str(payload), response_status=400,
                             success=False, error_message='eventType debe ser PATIENT_VIEW',
                             start_time=start_time)
            return jsonify({
                'success': False,
                'message': 'eventType debe ser PATIENT_VIEW'
            }), 400

        accession = order_data.get('accessionNumber', '').strip()
        order_id = order_data.get('orderId', '').strip()
        study_uid = study_data.get('study_uid', '').strip()
        patient_id = patient_data.get('id', '').strip()

        if not accession and not study_uid:
            _log_communication('/clinicaparque/study-open',
                             patient_id=patient_id,
                             request_body=str(payload), response_status=400,
                             success=False, error_message='Se requiere al menos accessionNumber o study_uid',
                             start_time=start_time)
            return jsonify({
                'success': False,
                'message': 'Se requiere al menos accessionNumber o study_uid'
            }), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        _ensure_clinicaparque_order_links(cursor)

        order_row = _find_clinicaparque_order(
            cursor, order_id=order_id, accession=accession, study_uid=study_uid,
        )
        exam_guid = order_row[0] if order_row else None
        if order_id and order_row:
            _upsert_clinicaparque_order_link(
                cursor, order_id, patient_id, exam_guid,
                order_row[1], accession or order_row[2],
            )

        timestamp = event_data.get('timestamp', '')
        event_log = f"[PATIENT_VIEW {timestamp}] Patient: {patient_id}, Accession: {accession}, StudyUID: {study_uid}"

        if exam_guid:
            cursor.execute(
                "UPDATE nextris.tbexamination SET history = COALESCE(history, '') || %s WHERE guid = %s",
                (f"\n{event_log}", exam_guid),
            )
            connection.commit()

        cursor.close()
        connection.close()

        response = {
            'status': 'success',
            'message': 'Event processed successfully',
            'examination_found': exam_guid is not None,
        }
        _log_communication('/clinicaparque/study-open',
                         patient_id=patient_id,
                         accession_number=accession,
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'STUDY-OPEN')
        try:
            _pid = patient_data.get('id') if ('patient_data' in dir() and isinstance(patient_data, dict)) else None
        except Exception:
            _pid = None
        try:
            _acc = order_data.get('accessionNumber') if ('order_data' in dir() and isinstance(order_data, dict)) else None
        except Exception:
            _acc = None
        _log_communication('/clinicaparque/study-open',
                         patient_id=_pid,
                         accession_number=_acc,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Envío de Addendas
# =============================================================================
@api_blueprint.route('/clinicaparque/addenda', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_addenda():
    """
    Recibe una addenda para un reporte existente.

    POST /api/clinicaparque/addenda
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
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
            "study_reason": "...",
            "technique": "...",
            "narrative": "...",
            "findings": "...",
            "impressions": "...",
            "conclusions": "...",
            "study_uid": "1.2.840.113619..."
        }
    }
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload:
            _log_communication('/clinicaparque/addenda', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='JSON inválido o vacío')
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        patient_data = payload.get('patient')
        order_data = payload.get('order')
        report_data = payload.get('report')

        if not patient_data or not order_data or not report_data:
            _log_communication('/clinicaparque/addenda',
                             patient_id=patient_data.get('id') if patient_data else None,
                             accession_number=order_data.get('accessionNumber') if order_data else None,
                             request_body=str(payload), response_status=400, success=False,
                             error_message='Se requieren los nodos: patient, order, report',
                             start_time=start_time)
            return jsonify({
                'success': False,
                'message': 'Se requieren los nodos: patient, order, report'
            }), 400

        accession = order_data.get('accessionNumber', '').strip()
        study_uid = report_data.get('study_uid', '').strip()
        order_id = order_data.get('orderId', '').strip()

        if not accession:
            return jsonify({'success': False, 'message': 'accessionNumber es requerido'}), 400
        if not study_uid:
            return jsonify({'success': False, 'message': 'study_uid es requerido'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        _ensure_clinicaparque_order_links(cursor)

        row = _find_clinicaparque_order(
            cursor, order_id=order_id, accession=accession, study_uid=study_uid,
        )
        if row:
            cursor.execute(
                """
                SELECT e.guid, r.guid, r.study_reason, r.content, r.conclusion,
                       r.findings, r.techniques, r.impressions, r.conclusions,
                       e.clinicalquestion, e.history
                FROM nextris.tbexamination e
                INNER JOIN nextris.tbreport r ON r.idexamination = e.guid
                WHERE e.guid = %s
                LIMIT 1
                """,
                (row[0],),
            )
            row = cursor.fetchone()

        if not row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'No se encontró estudio con accessionNumber={accession} y study_uid={study_uid}'
            }), 400

        exam_guid = row[0]
        report_guid = row[1]
        fields = canonical_fields_from_row(
            row[2], row[3], row[4], legacy_findings=row[5], legacy_technique=row[6],
            legacy_impressions=row[7], legacy_conclusion=row[8],
            reason_fallback=row[9] or row[10],
        )

        rad_id = order_data.get('rad_id', '').strip() or None
        if rad_id:
            rad_guid = _resolve_external_physician(cursor, rad_id)
        else:
            rad_guid = None

        report_date_str = order_data.get('report_date', '').strip()
        report_date = None
        if report_date_str:
            try:
                report_date = datetime.strptime(report_date_str, '%Y-%m-%d')
            except ValueError:
                report_date = None

        addenda_date = datetime.now().strftime('%d/%m/%Y')
        addenda_tag = f'[ADDENDA {addenda_date}]'

        new_fields = normalize_report_payload(report_data)

        new_content = new_fields.get('content', '')
        new_conclusion = new_fields.get('conclusion', '')
        combined_content = (
            f"{fields['content']}<p><strong>{addenda_tag} Contenido:</strong></p>{new_content}"
        ).strip() if new_content else fields['content']
        combined_conclusion = (
            f"{fields['conclusion']}<p><strong>{addenda_tag} Conclusión:</strong></p>{new_conclusion}"
        ).strip() if new_conclusion else fields['conclusion']

        cursor.execute(
            """
            UPDATE nextris.tbreport SET
                content = %s,
                conclusion = %s,
                iduser = COALESCE(%s, iduser),
                date = %s,
                wassaved = TRUE
            WHERE guid = %s
            """,
            (
                combined_content,
                combined_conclusion,
                rad_guid,
                report_date,
                report_guid,
            ),
        )

        _upsert_clinicaparque_order_link(
            cursor, order_id or accession, patient_data.get('id'),
            exam_guid, report_guid, accession,
        )
        connection.commit()
        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Addenda anexada correctamente',
            'orderId': order_id,
            'accession_number': accession,
        }
        _log_communication('/clinicaparque/addenda',
                         patient_id=patient_data.get('id'),
                         patient_name=patient_data.get('name'),
                         accession_number=accession,
                         order_id=order_data.get('orderId'),
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'ADDENDA')
        try:
            _pid = patient_data.get('id') if ('patient_data' in dir() and isinstance(patient_data, dict)) else None
        except Exception:
            _pid = None
        try:
            _acc = order_data.get('accessionNumber') if ('order_data' in dir() and isinstance(order_data, dict)) else None
        except Exception:
            _acc = None
        _log_communication('/clinicaparque/addenda',
                         patient_id=_pid,
                         accession_number=_acc,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Crear orden para ejecutar y leer (Worklist)
# =============================================================================
@api_blueprint.route('/clinicaparque/orders_to_execute_and_read', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_orders_to_execute_and_read():
    """
    Recibe datos de paciente y orden (sin reporte).
    Crea paciente si no existe, crea examen con isexecuted=0 e isreported=0,
    y genera un item de worklist DICOM.

    POST /api/clinicaparque/orders_to_execute_and_read
    Authorization: Bearer <token>
    Content-Type: application/json

    Body para paciente Final (F):
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
            "rad_id": "ID_MEDICO",
            "priority_id": 1
        }
    }

    Body para paciente Temporal (T) o Neonatal (N):
    {
        "patient": {
            "id": "ID_INTERNO_123",
            "patient_type": "T"
        },
        "order": { ... }
    }

    Campos patient (tipo F):
      - id              (requerido) - Identificador único del paciente en el sistema origen
      - patient_type    (requerido) - Tipo de paciente (T=Temporal, F=Final, N=Neonatal)
      - dni             (requerido) - Documento Nacional de Identidad
      - name            (requerido) - Nombre completo del paciente
      - birthdate       (requerido) - Fecha de nacimiento (YYYY-MM-DD)
      - sex             (requerido) - Sexo (M, F, O)
      - healthcard_type (requerido) - Tipo de cobertura (Particular, Obra Social, Prepaga)

    Campos patient (tipo T o N):
      - id              (requerido) - Identificador único del paciente en el sistema origen
      - patient_type    (requerido) - Tipo de paciente (T=Temporal, N=Neonatal)

    Campos order:
      - orderId              (requerido) - Número de orden o solicitud
      - accessionNumber      (requerido) - Número de acceso (clave DICOM)
      - procedure_code       (requerido) - Código del estudio/procedimiento
      - procedure_name       (requerido) - Descripción del estudio
      - study_description    (opcional) - Descripción del estudio para resolver
                                          el tipo local cuando el código aún no
                                          existe en el catálogo de NextRIS
      - modality             (requerido) - Modalidad (CR, CT, MR, DX, etc.)
      - AET                  (requerido) - AE Title del equipo
      - rad_id               (opcional) - Identificador del radiólogo; si se omite se guarda vacío/NULL
      - priority_id          (opcional) - Prioridad: 0=Rutina, 1=Urgente (por defecto 0)
      - lateralidad          (opcional) - Descripción externa de la lateralidad
      - study_reason         (opcional) - Razón o motivo del estudio
      - req_doctor           (opcional) - Nombre del médico referente

    La fecha de recepción del examen se genera internamente con NOW() en UTC.
    No es necesario enviar una fecha externa; los clientes antiguos que aún
    envíen scheduledTime serán compatibles, pero el campo se ignora.
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload:
            _log_communication('/clinicaparque/orders_to_execute_and_read',
                             request_body=str(payload), response_status=400,
                             success=False, error_message='JSON inválido o vacío')
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        patient_data = payload.get('patient')
        order_data = payload.get('order')

        if not patient_data or not order_data:
            _log_communication('/clinicaparque/orders_to_execute_and_read',
                             patient_id=patient_data.get('id') if patient_data else None,
                             request_body=str(payload), response_status=400,
                             success=False, error_message='Se requieren los nodos: patient, order',
                             start_time=start_time)
            return jsonify({
                'success': False,
                'message': 'Se requieren los nodos: patient, order'
            }), 400

        patient_required_base = ['id', 'patient_type']
        ptype = patient_data.get('patient_type', '').strip()
        if ptype not in ('T', 'F', 'N'):
            return jsonify({'success': False, 'message': 'patient_type debe ser T, F o N'}), 400

        is_temporal_or_neonatal = ptype in ('T', 'N')
        complex_fields = ['dni', 'name', 'birthdate', 'sex', 'healthcard_type']
        if is_temporal_or_neonatal:
            patient_required = patient_required_base
        else:
            patient_required = patient_required_base + complex_fields

        order_required = ['orderId', 'accessionNumber', 'procedure_code',
                         'modality', 'AET']

        missing = []
        for f in patient_required:
            if not patient_data.get(f):
                missing.append(f'patient.{f}')
        for f in order_required:
            if not order_data.get(f):
                missing.append(f'order.{f}')
        if not _get_external_study_description(order_data):
            missing.append('order.procedure_name o order.study_description')

        if missing:
            return jsonify({
                'success': False,
                'message': f'Campos faltantes: {", ".join(missing)}'
            }), 400

        if patient_data.get('sex') and patient_data['sex'] not in ('M', 'F', 'O'):
            return jsonify({'success': False, 'message': 'sex debe ser M, F u O'}), 400

        if patient_data.get('birthdate'):
            try:
                datetime.strptime(patient_data['birthdate'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'message': 'birthdate debe tener formato YYYY-MM-DD'}), 400

        # Los campos de integración opcionales se normalizan antes de tocar la
        # base de datos para que los defaults sean consistentes en creación y
        # actualización de órdenes existentes.
        rad_id = str(order_data.get('rad_id') or '').strip()

        raw_priority_id = order_data.get('priority_id', 0)
        if raw_priority_id is None or raw_priority_id == '':
            raw_priority_id = 0
        if isinstance(raw_priority_id, bool):
            return jsonify({'success': False, 'message': 'priority_id debe ser 0 o 1'}), 400
        if isinstance(raw_priority_id, int):
            priority_id = raw_priority_id
        elif isinstance(raw_priority_id, str) and raw_priority_id.strip() in ('0', '1'):
            priority_id = int(raw_priority_id.strip())
        else:
            return jsonify({'success': False, 'message': 'priority_id debe ser 0 o 1'}), 400
        if priority_id not in (0, 1):
            return jsonify({'success': False, 'message': 'priority_id debe ser 0 o 1'}), 400

        if 'laterality_id' in order_data:
            return jsonify({
                'success': False,
                'message': 'laterality_id no forma parte del contrato externo; use laterality o lateralidad'
            }), 400
        raw_laterality = order_data.get('laterality', order_data.get('lateralidad'))

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        _ensure_patient_type_columns(cursor)
        _ensure_clinicaparque_order_links(cursor)
        laterality_id = _resolve_external_laterality(cursor, raw_laterality)

        severity_guid = None
        if priority_id == 1:
            cursor.execute(
                "SELECT guid FROM nextris.isseverity WHERE description ILIKE '%urgente%' LIMIT 1"
            )
            severity_row = cursor.fetchone()
            if not severity_row:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'No está configurada la severidad urgente'
                }), 500
            severity_guid = severity_row[0]

        # === CREAR PACIENTE SI NO EXISTE ===
        external_id = patient_data['id'].strip()
        cursor.execute(
            "SELECT guid FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (external_id,),
        )
        row = cursor.fetchone()

        if row:
            patient_guid = row[0]
        else:
            full_name = patient_data.get('name', '').strip()
            parts = full_name.split(',', 1)
            surname = parts[0].strip() if parts else ''
            name = parts[1].strip() if len(parts) > 1 else ''
            patient_guid = str(uuid.uuid4())

            birthdate = patient_data.get('birthdate')
            if birthdate is not None and str(birthdate).strip() == '':
                birthdate = None
            cursor.execute(
                """
                INSERT INTO nextris.datapatient
                    (guid, patientid, nationalcode, name, surname, birthdate, sexcode,
                     patient_type, healthcard_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (patient_guid, external_id, patient_data.get('dni', '').strip(),
                 name, surname, birthdate, patient_data.get('sex'),
                 patient_data.get('patient_type', '').strip(),
                 patient_data.get('healthcard_type', '')),
            )

            username = external_id
            dni = patient_data.get('dni', '').strip()
            password_raw = dni[-3:] if len(dni) >= 3 else external_id[-3:] if len(external_id) >= 3 else external_id
            hashed_password = hash_pass(password_raw)

            cursor.execute(
                """
                INSERT INTO nextris.tbuser_patient
                    (guid, username, password, datapatient_id, status, firstlogin)
                VALUES (%s, %s, %s, %s, 'Active', 0)
                """,
                (str(uuid.uuid4()), username, hashed_password, patient_guid),
            )

        # === BUSCAR TIPO DE ESTUDIO ===
        procedure_code = order_data['procedure_code'].strip()
        study_description = _get_external_study_description(order_data)
        studytype_id = _resolve_external_studytype(
            cursor, procedure_code, study_description,
        )

        # === BUSCAR EQUIPO POR AET ===
        aet = order_data['AET'].strip()
        cursor.execute(
            "SELECT guid, location_id FROM nextris.isequipment WHERE UPPER(aetitle) = UPPER(%s) LIMIT 1",
            (aet,),
        )
        eq_row = cursor.fetchone()
        equipment_guid = eq_row[0] if eq_row else None
        location_id = eq_row[1] if eq_row else None

        # === BUSCAR RADIOLOGO ===
        # idreferringphysician es una referencia UUID; por eso un rad_id vacío
        # se representa en la base como NULL.
        rad_guid = None
        if rad_id:
            rad_guid = _resolve_external_physician(cursor, rad_id)

        # === EXTRAER RAZON DEL ESTUDIO Y DOCTOR REFERENTE ===
        study_reason = (order_data.get('study_reason') or '').strip()
        req_doctor = (order_data.get('req_doctor') or '').strip()

        exam_history_parts = []
        if study_reason:
            exam_history_parts.append(f"Razón del estudio: {study_reason}")
        if req_doctor:
            exam_history_parts.append(f"Doctor Referente: {req_doctor}")
        exam_history = ' | '.join(exam_history_parts) if exam_history_parts else None

        # === GENERAR NUMERO DE ADMISION ===
        order_id = order_data['orderId'].strip()
        accession = order_data['accessionNumber'].strip()

        mapped_order = _find_clinicaparque_order(cursor, order_id=order_id)
        if mapped_order:
            existing_exam_row = (mapped_order[0],)
            cursor.execute(
                "SELECT guid FROM nextris.tbexamination WHERE localacc = %s LIMIT 1",
                (accession,),
            )
            accession_exam = cursor.fetchone()
            if accession_exam and str(accession_exam[0]) != str(mapped_order[0]):
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'accessionNumber ya pertenece a otra orden'
                }), 409
            if mapped_order[2] != accession:
                cursor.execute(
                    "UPDATE nextris.tbexamination SET localacc = %s WHERE guid = %s",
                    (accession, mapped_order[0]),
                )
        else:
            cursor.execute(
                "SELECT guid FROM nextris.tbexamination WHERE localacc = %s LIMIT 1",
                (accession,),
            )
            existing_exam_row = cursor.fetchone()
        if existing_exam_row:
            existing_exam_guid = existing_exam_row[0]
            if exam_history:
                cursor.execute(
                    """
                    UPDATE nextris.tbexamination
                    SET "w-order" = 1,
                        studytype_id = COALESCE(%s, studytype_id),
                        idequipment = COALESCE(%s, idequipment),
                        location_id = COALESCE(location_id, %s),
                        idreferringphysician = %s,
                        idseverity = %s,
                        laterality_id = %s,
                        requestingphysician_name = COALESCE(%s, requestingphysician_name),
                        history = COALESCE(history, '') || E'\n' || %s
                    WHERE guid = %s
                    """,
                    (studytype_id, equipment_guid, location_id, rad_guid, severity_guid,
                     laterality_id, req_doctor or None, exam_history, existing_exam_guid),
                )
            else:
                cursor.execute(
                    """
                    UPDATE nextris.tbexamination
                    SET "w-order" = 1,
                        studytype_id = COALESCE(%s, studytype_id),
                        idequipment = COALESCE(%s, idequipment),
                        location_id = COALESCE(location_id, %s),
                        idreferringphysician = %s,
                        idseverity = %s,
                        laterality_id = %s,
                        requestingphysician_name = COALESCE(%s, requestingphysician_name)
                    WHERE guid = %s
                    """,
                    (studytype_id, equipment_guid, location_id, rad_guid, severity_guid,
                     laterality_id, req_doctor or None, existing_exam_guid),
                )
            cursor.execute(
                "SELECT guid FROM nextris.tbreport WHERE idexamination = %s LIMIT 1",
                (existing_exam_guid,),
            )
            existing_report_row = cursor.fetchone()
            _upsert_clinicaparque_order_link(
                cursor, order_id, external_id, existing_exam_guid,
                existing_report_row[0] if existing_report_row else None, accession,
            )
            connection.commit()
            cursor.close()
            connection.close()
            response = {
                'success': True,
                'message': 'Orden asociada al examen existente',
                'orderId': order_id,
                'accession_number': accession,
                'updated': True,
                'worklist_created': False,
            }
            _log_communication('/clinicaparque/orders_to_execute_and_read',
                             patient_id=patient_data.get('id'),
                             patient_name=patient_data.get('name'),
                             accession_number=accession,
                             order_id=order_data.get('orderId'),
                             request_body=str(payload), response_status=200,
                             response_body=str(response), success=True,
                             start_time=start_time)
            return jsonify(response), 200

        next_adm = _next_sequence(cursor, 'ADM', 'admisionnumber')
        adm_number = f'ADM{next_adm:06d}'

        # === CREAR EXAMEN ===
        exam_guid = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO nextris.tbexamination (
                guid, idpatient, studytype_id, idequipment,
                admisionnumber, localacc, studyinstanceuid,
                idreferringphysician,
                idseverity, laterality_id,
                status, isexecuted, isreported, createdon,
                location_id, "w-order", history, requestingphysician_name
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s,
                %s, %s,
                'Scheduled', 0, 0, NOW(),
                %s, 1, %s, %s
            )
            """,
            (
                exam_guid, patient_guid, studytype_id, equipment_guid,
                adm_number, accession, None,
                rad_guid,
                severity_guid, laterality_id,
                location_id,
                exam_history,
                req_doctor or None,
            ),
        )

        # === CREAR REPORTE VACIO ===
        report_guid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO nextris.tbreport (
                guid, idexamination, idpatient, admnumber, createdon, wassaved
            ) VALUES (
                %s, %s, %s, %s, NOW(), FALSE
            )
            """,
            (report_guid, exam_guid, patient_guid, adm_number),
        )
        _upsert_clinicaparque_order_link(
            cursor, order_id, external_id, exam_guid, report_guid, accession,
        )

        # === ENVIAR A WORKLIST HL7 ===
        worklist_success = False
        study_instance_uid = None

        patient_tuple = (
            patient_guid,
            patient_data['name'].split()[0] if patient_data['name'] else '',
            ' '.join(patient_data['name'].split()[1:]) if len(patient_data['name'].split()) > 1 else '',
            patient_data['dni'],
            patient_data['sex'],
        )

        try:
            study_instance_uid, worklist_success = HL7Service.send_exam_to_worklist(
                patient_data=patient_tuple,
                exam_data=study_description or '',
                equipment_data=aet,
                modality_data=order_data['modality'],
                admission_number=adm_number,
                accession_number=accession,
            )

            if study_instance_uid:
                cursor.execute(
                    "UPDATE nextris.tbexamination SET studyinstanceuid = %s WHERE guid = %s",
                    (str(study_instance_uid), exam_guid),
                )

        except Exception as hl7_err:
            print(f"[API CLINICAPARQUE WORKLIST] HL7 Error: {str(hl7_err)}")

        connection.commit()
        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Orden creada exitosamente',
            'orderId': order_id,
            'admision_number': adm_number,
            'accession_number': accession,
            'worklist_created': worklist_success,
            'study_instance_uid': str(study_instance_uid) if study_instance_uid else None,
        }
        _log_communication('/clinicaparque/orders_to_execute_and_read',
                         patient_id=patient_data.get('id'),
                         patient_name=patient_data.get('name'),
                         accession_number=accession,
                         order_id=order_data.get('orderId'),
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'ORDERS_TO_EXECUTE')
        try:
            _pid = patient_data.get('id') if ('patient_data' in dir() and isinstance(patient_data, dict)) else None
        except Exception:
            _pid = None
        try:
            _acc = order_data.get('accessionNumber') if ('order_data' in dir() and isinstance(order_data, dict)) else None
        except Exception:
            _acc = None
        _log_communication('/clinicaparque/orders_to_execute_and_read',
                         patient_id=_pid,
                         accession_number=_acc,
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Crear paciente desde DICOM tags (PACS dcm4chee)
# =============================================================================
@api_blueprint.route('/clinicaparque/patients/from-dicom', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_create_patient_from_dicom():
    """
    Crear paciente en NextRIS usando datos DICOM del PACS (dcm4chee).
    Busca el estudio en public.study por study_uid o accession_no,
    obtiene los datos del paciente desde las tablas del PACS y crea
    el paciente + usuario portal en nextris.

    POST /api/clinicaparque/patients/from-dicom
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
    {
        "study_uid": "1.2.840.113619.2.55.3.1234"
    }
    O alternativamente:
    {
        "accession_no": "3310260_2739"
    }

    Response 200:
    {
        "success": true,
        "message": "Paciente creado exitosamente",
        "patientid": "NR00000001",
        "username": "57458",
        "dicom_patient_id": "57458",
        "source": "dicom"
    }
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload:
            _log_communication('/clinicaparque/patients/from-dicom',
                             request_body=str(payload), response_status=400,
                             success=False, error_message='JSON inválido o vacío')
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        study_uid = (payload.get('study_uid') or '').strip()
        accession_no = (payload.get('accession_no') or '').strip()

        if not study_uid and not accession_no:
            _log_communication('/clinicaparque/patients/from-dicom',
                             request_body=str(payload), response_status=400,
                             success=False,
                             error_message='Se requiere study_uid o accession_no')
            return jsonify({
                'success': False,
                'message': 'Se requiere study_uid o accession_no',
            }), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        _ensure_patient_type_columns(cursor)

        # 1. Find study in PACS
        if study_uid:
            cursor.execute(
                """
                SELECT s.pk, s.patient_fk, s.accession_no
                FROM public.study s
                WHERE s.study_iuid = %s
                LIMIT 1
                """,
                (study_uid,),
            )
        else:
            cursor.execute(
                """
                SELECT s.pk, s.patient_fk, s.accession_no
                FROM public.study s
                WHERE s.accession_no = %s
                LIMIT 1
                """,
                (accession_no,),
            )

        study_row = cursor.fetchone()
        if not study_row:
            cursor.close()
            connection.close()
            msg = f'Estudio no encontrado en PACS: {"study_uid=" + study_uid if study_uid else "accession_no=" + accession_no}'
            _log_communication('/clinicaparque/patients/from-dicom',
                             request_body=str(payload), response_status=404,
                             success=False, error_message=msg)
            return jsonify({'success': False, 'message': msg}), 404

        pacs_patient_fk = study_row[1]
        if not pacs_patient_fk:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El estudio no tiene paciente asociado en PACS',
            }), 400

        # 2. Get patient data from PACS
        cursor.execute(
            """
            SELECT p.pk, p.pat_birthdate, p.pat_sex, p.dicomattrs_fk,
                   pn.alphabetic_name
            FROM public.patient p
            LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
            WHERE p.pk = %s
            LIMIT 1
            """,
            (pacs_patient_fk,),
        )
        patient_row = cursor.fetchone()
        if not patient_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado en PACS',
            }), 404

        pacs_pk = patient_row[0]
        pat_birthdate = patient_row[1]
        pat_sex = patient_row[2]
        alphabetic_name = patient_row[4]

        # 3. Extract PatientID from dicomattrs binary
        dicom_patient_id = _extract_patient_id_from_dicomattrs(cursor, pacs_pk)
        if not dicom_patient_id:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se pudo extraer PatientID del DICOM',
            }), 400

        # 4. Check if patient already exists in nextris
        cursor.execute(
            "SELECT guid, patientid FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (dicom_patient_id,),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Ya existe un paciente con PatientID DICOM: {dicom_patient_id}',
                'patientid': existing[1],
            }), 400

        cursor.execute(
            "SELECT guid, patientid FROM nextris.datapatient WHERE nationalcode = %s LIMIT 1",
            (dicom_patient_id,),
        )
        existing_nc = cursor.fetchone()
        if existing_nc:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Ya existe un paciente con nationalcode: {dicom_patient_id}',
                'patientid': existing_nc[1],
            }), 400

        # 5. Parse DICOM data
        surname, firstname = _parse_dicom_name(alphabetic_name)
        if not surname and not firstname:
            surname = 'SIN NOMBRE'

        birthdate = _format_dicom_date(pat_birthdate)
        sexcode = pat_sex if pat_sex in ('M', 'F') else 'I'

        # 6. Generate patient GUID
        # patientid = DICOM PatientID (tag 0010,0020)
        patient_guid = str(uuid.uuid4())

        # 7. Insert patient
        cursor.execute(
            """
            INSERT INTO nextris.datapatient
                (guid, patientid, nationalcode, name, surname, birthdate, sexcode,
                 patient_type, healthcard_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_guid, dicom_patient_id, dicom_patient_id,
                firstname, surname, birthdate, sexcode,
                'F', 'Particular',
            ),
        )

        # 8. Create portal user
        username = dicom_patient_id
        password_raw = username[-3:] if len(username) >= 3 else username
        hashed_password = hash_pass(password_raw)

        cursor.execute(
            """
            INSERT INTO nextris.tbuser_patient
                (guid, username, password, datapatient_id, status, firstlogin)
            VALUES (%s, %s, %s, %s, 'Active', 0)
            """,
            (str(uuid.uuid4()), username, hashed_password, patient_guid),
        )

        # Link existing PACS studies for this patient (beyond the one being created)
        linked_studies = []
        try:
            linked_studies = _link_existing_pacs_studies(cursor, patient_guid, dicom_patient_id)
        except Exception as link_err:
            print(f"[API CLINICAPARQUE FROM-DICOM] Error linking PACS studies: {link_err}")

        connection.commit()
        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Paciente creado exitosamente desde DICOM',
            'patientid': dicom_patient_id,
            'username': username,
            'source': 'dicom',
        }
        if linked_studies:
            response['linked_studies'] = linked_studies
            response['message'] = f'Paciente creado exitosamente desde DICOM. {len(linked_studies)} estudio(s) adicional(es) vinculado(s).'
        _log_communication('/clinicaparque/patients/from-dicom',
                         patient_id=dicom_patient_id,
                         patient_name=f'{firstname} {surname}',
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'FROM-DICOM')
        _log_communication('/clinicaparque/patients/from-dicom',
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e))
        return jsonify({'success': False, 'message': user_msg}), 500


@api_blueprint.route('/clinicaparque/resetpassword', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_reset_password():
    """
    Resetea la contraseña del usuario portal de un paciente.

    POST /api/clinicaparque/resetpassword
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
    {
        "patient_id": "82416",        // requerido
        "password": "nuevapass"       // opcional (default: últimos 3 dígitos del DNI)
    }
    """
    try:
        start_time = datetime.now()
        payload = request.get_json(silent=True)
        if not payload or 'patient_id' not in payload:
            _log_communication('/clinicaparque/resetpassword', request_body=str(payload),
                             response_status=400, success=False,
                             error_message='patient_id es requerido')
            return jsonify({'success': False, 'message': 'patient_id es requerido'}), 400

        patient_id = str(payload['patient_id']).strip()
        new_password = payload.get('password')

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT guid, patientid, nationalcode, name, surname FROM nextris.datapatient WHERE patientid = %s LIMIT 1",
            (patient_id,),
        )
        patient_row = cursor.fetchone()
        if not patient_row:
            cursor.close()
            connection.close()
            _log_communication('/clinicaparque/resetpassword', patient_id=patient_id,
                             request_body=str(payload), response_status=404, success=False,
                             error_message=f'Paciente con id {patient_id} no encontrado',
                             start_time=start_time)
            return jsonify({'success': False, 'message': f'Paciente con id {patient_id} no encontrado'}), 404

        patient_guid, pat_id, nationalcode, name, surname = patient_row

        cursor.execute(
            "SELECT guid, username FROM nextris.tbuser_patient WHERE datapatient_id = %s LIMIT 1",
            (patient_guid,),
        )
        user_row = cursor.fetchone()

        if user_row:
            user_guid, username = user_row
        else:
            username = patient_id
            if not new_password:
                if not nationalcode or len(nationalcode) < 3:
                    cursor.close()
                    connection.close()
                    _log_communication('/clinicaparque/resetpassword', patient_id=patient_id,
                                     request_body=str(payload), response_status=400, success=False,
                                     error_message='DNI no disponible para generar password por defecto',
                                     start_time=start_time)
                    return jsonify({'success': False, 'message': 'DNI no disponible para generar password por defecto'}), 400
                new_password = nationalcode[-3:]

            hashed_password = hash_pass(str(new_password))
            user_guid = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO nextris.tbuser_patient
                    (guid, username, password, datapatient_id, status, firstlogin)
                VALUES (%s, %s, %s, %s, 'Active', 0)
                """,
                (user_guid, username, hashed_password, patient_guid),
            )
            connection.commit()

            cursor.close()
            connection.close()

            response = {
                'success': True,
                'message': 'Usuario portal creado y contraseña establecida exitosamente',
                'patient_id': patient_id,
                'username': username,
            }
            _log_communication('/clinicaparque/resetpassword', patient_id=patient_id,
                             patient_name=f'{name} {surname}'.strip(),
                             request_body=str(payload), response_status=200,
                             response_body=str(response), success=True,
                             start_time=start_time)
            return jsonify(response), 200

        if not new_password:
            if not nationalcode or len(nationalcode) < 3:
                cursor.close()
                connection.close()
                _log_communication('/clinicaparque/resetpassword', patient_id=patient_id,
                                 request_body=str(payload), response_status=400, success=False,
                                 error_message='DNI no disponible para generar password por defecto',
                                 start_time=start_time)
                return jsonify({'success': False, 'message': 'DNI no disponible para generar password por defecto'}), 400
            new_password = nationalcode[-3:]

        hashed_password = hash_pass(str(new_password))

        cursor.execute(
            "UPDATE nextris.tbuser_patient SET username = %s, password = %s WHERE guid = %s",
            (patient_id, hashed_password, user_guid),
        )
        connection.commit()

        cursor.close()
        connection.close()

        response = {
            'success': True,
            'message': 'Contraseña actualizada exitosamente',
            'patient_id': patient_id,
            'username': patient_id,
        }
        _log_communication('/clinicaparque/resetpassword', patient_id=patient_id,
                         patient_name=f'{name} {surname}'.strip(),
                         request_body=str(payload), response_status=200,
                         response_body=str(response), success=True,
                         start_time=start_time)
        return jsonify(response), 200

    except Exception as e:
        user_msg = _sanitize_error(e, 'RESET PASSWORD')
        _log_communication('/clinicaparque/resetpassword',
                         request_body=str(payload) if 'payload' in dir() else None,
                         response_status=500, success=False, error_message=str(e),
                         start_time=start_time if 'start_time' in dir() else None)
        return jsonify({'success': False, 'message': user_msg}), 500


# =============================================================================
# ENDPOINT: Envío de Reportes a Sistema Externo
# =============================================================================
CLINICAPARQUE_REPORTS_URL = os.environ.get(
    'CLINICAPARQUE_REPORTS_URL',
    'http://192.168.0.76:9292/receive/'
)


def _send_report_to_external(exam_id, connection=None, created_by='system'):
    """
    Función helper para enviar un reporte al sistema externo.
    Puede usarse tanto desde el endpoint manual como desde hooks automáticos (sign).

    Returns:
        dict con claves: success (bool), external_status (int), viewer_link (str), error (str)
    """
    db_config = get_db_config()
    if not db_config:
        return {'success': False, 'external_status': 0, 'viewer_link': '', 'error': 'Error de configuración de base de datos'}

    owns_connection = connection is None
    if owns_connection:
        connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    _ensure_clinicaparque_order_links(cursor)

    try:
        cursor.execute("""
            SELECT
                ex.guid,
                ex.localacc,
                ex.studyinstanceuid,
                dp.patientid,
                dp.nationalcode,
                CONCAT(dp.name, ' ', dp.surname) as patient_name,
                dp.birthdate,
                dp.sexcode,
                st.description as study_description,
                l.external_order_id,
                ex.clinicalquestion,
                ex.history
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.datapatient dp ON ex.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.clinicaparque_order_links l
                ON l.examination_guid = ex.guid AND l.source = 'clinicaparque'
            WHERE ex.guid = %s
            LIMIT 1
        """, (exam_id,))
        exam_row = cursor.fetchone()

        if not exam_row:
            return {'success': False, 'external_status': 404, 'viewer_link': '', 'error': 'Examen no encontrado'}

        exam_guid, accession_number, study_uid, patient_id, patient_dni, patient_name, birthdate, sexcode, study_description, external_order_id, clinical_question, history = exam_row

        cursor.execute("""
            SELECT
                r.study_reason,
                r.content,
                r.conclusion,
                r.findings,
                r.techniques,
                r.impressions,
                r.conclusions,
                r.date,
                r.createdon,
                r.iduser
            FROM nextris.tbreport r
            WHERE r.idexamination = %s
            LIMIT 1
        """, (exam_id,))
        report_row = cursor.fetchone()

        fields = canonical_fields_from_row(
            report_row[0] if report_row else None,
            report_row[1] if report_row else None,
            report_row[2] if report_row else None,
            legacy_findings=report_row[3] if report_row else None,
            legacy_technique=report_row[4] if report_row else None,
            legacy_impressions=report_row[5] if report_row else None,
            legacy_conclusion=report_row[6] if report_row else None,
            reason_fallback=clinical_question or history or study_description,
        )
        report_date = report_row[7].isoformat() if report_row and report_row[7] else None
        report_created = report_row[8].isoformat() if report_row and report_row[8] else None
        rad_guid = report_row[9] if report_row else None

        rad_id = ''
        if rad_guid:
            cursor.execute("""
                SELECT username FROM nextris.tbuser WHERE guid = %s LIMIT 1
            """, (rad_guid,))
            rad_row = cursor.fetchone()
            rad_id = rad_row[0] if rad_row else str(rad_guid)

        try:
            share_data = create_for_exam(exam_id, created_by=created_by, connection=connection)
            viewer_link = share_data.get('share_url', '')
        except Exception as share_err:
            print(f"[SEND REPORT] Error generando share link: {share_err}")
            viewer_link = ''

        if owns_connection:
            connection.commit()
        cursor.close()
        if owns_connection:
            connection.close()

        external_payload = {
            'patient': {
                'id': patient_id or '',
                'dni': patient_dni or '',
                'name': patient_name or '',
                'accession_number': accession_number or ''
            },
            'report': {
                'study_reason': fields['study_reason'] or '',
                'technique': '',
                'findings': fields['content'] or '',
                'impressions': '',
                'conclusions': fields['conclusion'] or '',
                'report_date': report_date or report_created or '',
                'study_uid': study_uid or ''
            },
            'order': {
                'orderId': external_order_id or '',
                'accessionNumber': accession_number or '',
            },
            'rad_id': rad_id,
            'viewer_link': viewer_link
        }

        external_url = CLINICAPARQUE_REPORTS_URL
        try:
            external_response = requests.post(
                external_url,
                json=external_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            ext_status = external_response.status_code
            ext_body = external_response.text[:500] if external_response.text else ''
            ext_success = ext_status >= 200 and ext_status < 300
        except requests.exceptions.RequestException as req_err:
            ext_status = 0
            ext_body = str(req_err)
            ext_success = False
            print(f"[SEND REPORT] Error conectando con sistema externo: {req_err}")

        start_time = datetime.now()
        _log_communication('/clinicaparque/reports/send',
                          patient_id=patient_id,
                          patient_name=patient_name,
                          accession_number=accession_number,
                          request_body=str({
                              'orderId': external_order_id,
                              'accessionNumber': accession_number,
                          }),
                          response_status=ext_status,
                          response_body=ext_body,
                          success=ext_success,
                          error_message=None if ext_success else 'Error en comunicación externa',
                          start_time=start_time)

        if not ext_success:
            return {'success': False, 'external_status': ext_status, 'viewer_link': viewer_link, 'error': f'Error externo: {ext_status}'}

        return {'success': True, 'external_status': ext_status, 'viewer_link': viewer_link, 'error': None}

    except Exception as e:
        if owns_connection and connection:
            connection.rollback()
            if cursor:
                cursor.close()
            connection.close()
        return {'success': False, 'external_status': 500, 'viewer_link': '', 'error': str(e)}


@api_blueprint.route('/clinicaparque/reports/send', methods=['POST'])
@require_clinicaparque_token
def clinicaparque_send_report():
    """
    Envía datos del reporte a sistema externo (Clínica Parque).
    Incluye datos del paciente, examen, reporte y link corto del visor.

    POST /api/clinicaparque/reports/send
    Authorization: Bearer <token>
    Content-Type: application/json

    Body:
    {
        "orderId": "ORD-2026-001",
        "accessionNumber": "ACC123456"
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({'success': False, 'message': 'JSON inválido o vacío'}), 400

        order_id = str(payload.get('orderId') or '').strip()
        accession = str(payload.get('accessionNumber') or '').strip()
        if not order_id and not accession:
            return jsonify({'success': False, 'message': 'orderId o accessionNumber es requerido'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        _ensure_clinicaparque_order_links(cursor)
        order_row = _find_clinicaparque_order(
            cursor, order_id=order_id, accession=accession,
        )
        cursor.close()
        connection.close()
        if not order_row:
            return jsonify({'success': False, 'message': 'No se encontró la orden'}), 404
        exam_id = order_row[0]

        result = _send_report_to_external(exam_id)

        if not result['success']:
            return jsonify({
                'success': False,
                'message': 'Error al enviar reporte al sistema externo',
                'error': result['error'],
                'external_status': result['external_status']
            }), 502

        return jsonify({
            'success': True,
            'message': 'Reporte enviado exitosamente',
            'external_status': result['external_status'],
            'viewer_link': result['viewer_link']
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/clinicaparque/reports/send-test', methods=['POST'])
def clinicaparque_send_report_test():
    """
    Endpoint de testing sin autenticación para probar envío a sistema externo.
    Envía un reporte mock al destino configurado en CLINICAPARQUE_REPORTS_URL.
    """
    try:
        start_time = datetime.now()

        external_payload = {
            'patient': {
                'id': 'NR-TEST-001',
                'dni': '12345678',
                'name': 'Juan Pérez TEST',
                'accession_number': 'ACC-TEST-001'
            },
            'report': {
                'study_reason': 'Dolor torácico',
                'technique': 'Radiografía de tórax frontal y lateral',
                'findings': 'Campos pulmonares simétricos, sin hallazgos agudos.',
                'impressions': 'Estudio dentro de parámetros normales.',
                'conclusions': 'No se observan anormalidades.',
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'study_uid': '1.2.840.113619.2.55.3.123456'
            },
            'viewer_link': 'https://clinicacp.ddns.net/api/s/test123'
        }

        external_url = CLINICAPARQUE_REPORTS_URL
        try:
            external_response = requests.post(
                external_url,
                json=external_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            ext_status = external_response.status_code
            ext_body = external_response.text[:500] if external_response.text else ''
            ext_success = ext_status >= 200 and ext_status < 300
            print(f"[SEND TEST] Response status: {ext_status}, body: {ext_body[:200]}")
        except requests.exceptions.RequestException as req_err:
            ext_status = 0
            ext_body = str(req_err)
            ext_success = False
            print(f"[SEND TEST] Error conectando: {req_err}")

        _log_communication('/clinicaparque/reports/send-test',
                          patient_id='NR-TEST-001',
                          patient_name='Juan Pérez TEST',
                          accession_number='ACC-TEST-001',
                          request_body=str(external_payload),
                          response_status=ext_status,
                          response_body=ext_body,
                          success=ext_success,
                          error_message=None if ext_success else 'Error en comunicación externa',
                          start_time=start_time)

        if ext_success:
            return jsonify({
                'success': True,
                'message': 'Reporte de prueba enviado exitosamente',
                'external_status': ext_status,
                'payload_sent': external_payload
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Error al enviar reporte de prueba',
                'external_status': ext_status,
                'external_response': ext_body
            }), 502

    except Exception as e:
        user_msg = _sanitize_error(e, 'SEND TEST')
        return jsonify({'success': False, 'message': user_msg}), 500
