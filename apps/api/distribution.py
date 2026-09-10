# -*- encoding: utf-8 -*-
"""
API REST para Distribución de Informes
Endpoints para gestión y envío de informes médicos finalizados
"""

from flask import request, jsonify, send_file, current_app
from io import BytesIO
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
from apps.api.permissions import require_permission
import uuid
import os
import smtplib
import requests
from urllib.parse import urlparse, urlunparse
import html
from apps.api.facility_plan_usage import (
    ensure_plan_management_schema,
    check_limit_before_action,
)
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None


def _build_viewer_url(study_uid):
    """Construye URL absoluta del visor DICOM usando config."""
    viewer_url_cfg = current_app.config.get(
        'DICOM_VIEWER_URL',
        'https://clinicacp.ddns.net:3000/viewer'
    )
    parsed = urlparse(viewer_url_cfg)
    viewer_base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{viewer_base}/viewer?StudyInstanceUIDs={study_uid}"


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


def get_smtp_fallback_from_any_facility(connection):
    """Obtiene una configuración SMTP válida desde cualquier facility activa como fallback."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT smtp_server,
                   smtp_port,
                   smtp_user,
                   smtp_password,
                   smtp_from,
                   smtp_from_name,
                   use_tls
            FROM nextris.tbfacility
            WHERE COALESCE(TRIM(smtp_user), '') <> ''
              AND COALESCE(TRIM(smtp_password), '') <> ''
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'smtp_server': row[0],
            'smtp_port': row[1],
            'smtp_user': row[2],
            'smtp_password': row[3],
            'smtp_from': row[4],
            'smtp_from_name': row[5],
            'use_tls': row[6],
        }
    finally:
        cursor.close()


# ====================================================================
# ENDPOINTS PARA DISTRIBUCIÓN DE INFORMES
# ====================================================================

@api_blueprint.route('/examinations/distribution', methods=['GET'])
@jwt_required()
def get_examinations_for_distribution():
    """
    Obtiene exámenes listos para distribuir (informes finalizados)
    
    Query Parameters:
    - all_reported (optional): true para incluir todos los reportados, false solo pendientes (default: false)
    - page (optional): Número de página (default: 1)
    - per_page (optional): Items por página (default: 50, max: 100)
    
    Returns:
    {
        "success": true,
        "data": {
            "data": [
                {
                    "guid": "uuid",
                    "fecha": "2025-01-07",
                    "examen": "ANGIOTOMOGRAFIA",
                    "paciente": "García Ana",
                    "mail": "ana@email.com",
                    "estado": "R" o "E",
                    "medico_autor": "Dr. Smith",
                    "medico_solicitante": "Dr. Jones",
                    "urgencia": "N"
                }
            ],
            "page": 1,
            "per_page": 50,
            "total": 25
        }
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

        # Parámetros
        all_reported = request.args.get('all_reported', 'false').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        date_range = request.args.get('date_range', 'all').strip().lower()
        date_field = request.args.get('date_field', 'admision').strip().lower()
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        ensure_plan_management_schema(connection)
        
        # Query base
        query = """
            SELECT
                e.guid,
                TO_CHAR(e.createdon, 'DD/MM/YYYY HH24:MI') as fecha,
                st.description as examen,
                CONCAT(dp.name, ' ', dp.surname) as paciente,
                COALESCE(dp.email, '') as mail,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM nextris.communication_logs cl
                        WHERE cl.accession_number = e.localacc
                        AND cl.api_endpoint = '/clinicaparque/reports/send'
                        AND cl.success = TRUE
                    ) THEN 'E'
                    ELSE 'R'
                END as estado,
                COALESCE(u.name || ' ' || COALESCE(u.surname, ''), u.username, '') as medico_autor,
                COALESCE(rp.description, '') as medico_solicitante,
                COALESCE(e.stat, 'N') as urgencia,
                COALESCE(e.isimage, 0) as isimage,
                COALESCE(e.isreported, 0) as isreported,
                COALESCE(e.isexecuted, 0) as isexecuted,
                COALESCE(e.ispublicated, 0) as ispublicated,
                e.localacc as accession_number,
                COALESCE(dp.phone, '') as phone,
                CASE
                    WHEN cl_sent.success = TRUE THEN
                        TO_CHAR(cl_sent.received_at, 'DD/MM/YYYY HH24:MI')
                    ELSE NULL
                END as sent_at,
                CASE
                    WHEN cl_sent.success = FALSE THEN cl_sent.error_message
                    ELSE NULL
                END as send_error
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
            LEFT JOIN nextris.isequipment eq ON e.idequipment = eq.guid
            LEFT JOIN nextris.tblocation loc ON COALESCE(e.location_id, eq.location_id) = loc.guid
            LEFT JOIN nextris.isrequestingphysician rp ON e.idrequestingphysician = rp.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            LEFT JOIN nextris.tbuser u ON r.iduser = u.guid
            LEFT JOIN LATERAL (
                SELECT cl2.success, cl2.received_at, cl2.error_message
                FROM nextris.communication_logs cl2
                WHERE cl2.accession_number = e.localacc
                AND cl2.api_endpoint = '/clinicaparque/reports/send'
                ORDER BY cl2.received_at DESC
                LIMIT 1
            ) cl_sent ON TRUE
            WHERE e.isreported = 1
        """

        params = []

        # Si no se quieren los ya enviados, filtrar
        if not all_reported:
            query += " AND NOT EXISTS ("
            query += " SELECT 1 FROM nextris.communication_logs cl"
            query += " WHERE cl.accession_number = e.localacc"
            query += " AND cl.api_endpoint = '/clinicaparque/reports/send'"
            query += " AND cl.success = TRUE)"

        # Filtro de fechas
        date_intervals = {
            '1d': '1 day',
            '3d': '3 days',
            '7d': '7 days',
            '14d': '14 days',
            '1m': '1 month',
            '2m': '2 months',
            '3m': '3 months',
            '1y': '1 year'
        }
        if date_range in date_intervals:
            if date_field == 'estudio':
                date_column = 'e.reportdate'
            elif date_field == 'enviado':
                date_column = 'cl_sent.received_at'
            else:  # admision
                date_column = 'e.createdon'
            query += f" AND {date_column} BETWEEN CURRENT_TIMESTAMP - INTERVAL '{date_intervals[date_range]}' AND CURRENT_TIMESTAMP"

        query += " ORDER BY e.createdon DESC"
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({query}) as count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Agregar paginación
        query += f" LIMIT {per_page} OFFSET {offset}"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        examinations = []
        for row in results:
            examinations.append({
                'guid': row[0],
                'fecha': row[1],
                'examen': row[2],
                'paciente': row[3],
                'mail': row[4],
                'estado': row[5],
                'medico_autor': row[6],
                'medico_solicitante': row[7],
                'urgencia': row[8],
                'isimage': bool(row[9]),
                'isreported': bool(row[10]),
                'isexecuted': bool(row[11]),
                'ispublicated': bool(row[12]),
                'accession_number': row[13] or '',
                'phone': row[14] or '',
                'sent_at': row[15] or None,
                'send_error': row[16] or None
            })
        
        return jsonify({
            'success': True,
            'data': {
                'data': examinations,
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


@api_blueprint.route('/examinations/<exam_id>/send-report', methods=['POST'])
@jwt_required()
@require_permission('distribution.send_report', include_role_permissions=False)
def send_report_email(exam_id):
    """
    Envía un informe por email
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "email": "paciente@email.com" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Informe enviado correctamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'message': 'El email es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener información del reporte y examen
        query = """
            SELECT 
                r.guid,
                CONCAT(dp.name, ' ', dp.surname) as patient_name,
                st.description as study_type,
                ex.localacc as accession_number,
                f.smtp_server,
                f.smtp_port,
                f.smtp_user,
                f.smtp_password,
                f.smtp_from,
                f.smtp_from_name,
                f.use_tls,
                ex.studyinstanceuid,
                COALESCE(ex.isimage, 0) as has_images,
                f.guid as facility_id,
                COALESCE(ex.ispublicated, 0) as is_publicated
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.datapatient dp ON ex.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = ex.guid
            LEFT JOIN nextris.isequipment eq ON ex.idequipment = eq.guid
            LEFT JOIN nextris.tblocation l ON COALESCE(ex.location_id, eq.location_id) = l.guid
            LEFT JOIN nextris.tbfacility f ON l.facility_id = f.guid
            WHERE ex.guid = %s
        """
        
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        patient_name = result[1]
        study_type = result[2]
        accession_number = result[3]
        
        # Configuración SMTP (primero por facility, con fallback a variables globales)
        env_smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        env_smtp_port_raw = os.environ.get('SMTP_PORT', '587')
        env_smtp_user = os.environ.get('SMTP_USER')
        env_smtp_password = os.environ.get('SMTP_PASSWORD')
        env_smtp_from = os.environ.get('SMTP_FROM')
        env_smtp_from_name = os.environ.get('SMTP_FROM_NAME', 'NextRIS')

        def _safe_port(value, default=587):
            try:
                return int(value)
            except Exception:
                return int(default)

        smtp_server = result[4] or env_smtp_server
        smtp_port = _safe_port(result[5] or env_smtp_port_raw, 587)
        smtp_user = result[6] or env_smtp_user
        smtp_password = result[7] or env_smtp_password
        smtp_from = result[8] or smtp_user or env_smtp_from
        smtp_from_name = result[9] or env_smtp_from_name
        use_tls = result[10] if result[10] is not None else True
        
        study_uid = result[11]
        has_images = bool(result[12])
        facility_id = result[13]
        already_publicated = bool(result[14])

        if facility_id:
            is_allowed, limit_payload = check_limit_before_action(connection, facility_id, 'distribute')
            if not is_allowed:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': limit_payload.get('message', 'Límite de distribución alcanzado para el plan actual'),
                    'code': limit_payload.get('reason', 'DISTRIBUTE_LIMIT_REACHED'),
                    'data': {
                        'limits': limit_payload.get('limits'),
                        'usage': limit_payload.get('usage'),
                    }
                }), 409
        
        from apps.services.report_pdf_service import ReportPdfNotAvailable, render_report_pdf
        try:
            rendered = render_report_pdf(exam_id)
        except ReportPdfNotAvailable:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Informe PDF no disponible',
                'code': 'REPORT_NOT_AVAILABLE',
            }), 404
        except Exception as render_error:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': f'Error generando PDF: {render_error}'}), 500
        
        if not smtp_user or not smtp_password:
            smtp_fallback = get_smtp_fallback_from_any_facility(connection)
            if smtp_fallback:
                smtp_server = smtp_fallback.get('smtp_server') or smtp_server
                smtp_port = _safe_port(smtp_fallback.get('smtp_port') or smtp_port, 587)
                smtp_user = smtp_fallback.get('smtp_user') or smtp_user
                smtp_password = smtp_fallback.get('smtp_password') or smtp_password
                smtp_from = smtp_fallback.get('smtp_from') or smtp_user or smtp_from
                smtp_from_name = smtp_fallback.get('smtp_from_name') or smtp_from_name
                if smtp_fallback.get('use_tls') is not None:
                    use_tls = bool(smtp_fallback.get('use_tls'))

        if not smtp_user or not smtp_password:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Configuración SMTP incompleta. Configure SMTP_USER y SMTP_PASSWORD en la institución activa o en variables de entorno.',
                'data': {
                    'smtp_configured': False,
                    'smtp_server': smtp_server,
                    'smtp_port': smtp_port,
                    'smtp_user_exists': bool(smtp_user),
                    'smtp_password_exists': bool(smtp_password)
                }
            }), 500
        
        # Crear mensaje de email
        msg = MIMEMultipart('mixed')
        msg['From'] = f"{smtp_from_name} <{smtp_from}>"
        msg['To'] = email
        msg['Subject'] = f'Informe Médico - {study_type}'

        # Generar link del visor DICOM si hay imágenes
        viewer_url = ""
        viewer_text_block = ""
        viewer_html_block = ""
        if has_images and study_uid:
            viewer_url = _build_viewer_url(study_uid)
            viewer_text_block = (
                "\n\nPuede visualizar las imágenes médicas en el siguiente enlace:\n"
                f"{viewer_url}\n"
            )
            viewer_html_block = f"""
            <div style=\"margin: 20px 0 0 0;\">
                <a href=\"{viewer_url}\" style=\"display:inline-block; background:#6f2cff; color:#ffffff; text-decoration:none; font-weight:600; font-size:14px; padding:12px 18px; border-radius:8px;\" target=\"_blank\" rel=\"noopener noreferrer\">Ver Imágenes Médicas</a>
            </div>
            """

        patient_name_safe = html.escape(patient_name or "Paciente")
        study_type_safe = html.escape(study_type or "Estudio")
        accession_safe = html.escape(accession_number or "N/A")
        sender_name_safe = html.escape(smtp_from_name or "NextRIS")

        body_text = (
            f"Estimado/a {patient_name or 'Paciente'},\n\n"
            "Le enviamos adjunto su informe médico en formato PDF.\n\n"
            f"Estudio: {study_type or 'Estudio'}\n"
            f"Número de acceso: {accession_number or 'N/A'}"
            f"{viewer_text_block}\n"
            "Este es un mensaje automático. Por favor, no responder a este correo.\n\n"
            f"Atentamente,\n{smtp_from_name or 'NextRIS'}"
        )

        body_html = f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Informe Médico - NextRIS</title>
</head>
<body style=\"margin:0; padding:0; background:#0f1226; font-family:Arial, Helvetica, sans-serif;\">
    <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"background:#0f1226; padding:24px 12px;\">
        <tr>
            <td align=\"center\">
                <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"max-width:640px; background:#161a33; border:1px solid #2a2f57; border-radius:14px; overflow:hidden;\">
                    <tr>
                        <td style=\"padding:20px 24px; background:linear-gradient(135deg,#7b2cff 0%,#4e1cd2 100%); color:#ffffff;\">
                            <div style=\"font-size:22px; font-weight:700; letter-spacing:0.2px;\">NextRIS</div>
                            <div style=\"font-size:13px; opacity:0.9; margin-top:4px;\">Distribución de Informes Médicos</div>
                        </td>
                    </tr>
                    <tr>
                        <td style=\"padding:24px; color:#e8ebff;\">
                            <p style=\"margin:0 0 14px 0; font-size:16px; line-height:1.5;\">Estimado/a <strong>{patient_name_safe}</strong>:</p>
                            <p style=\"margin:0 0 18px 0; font-size:15px; line-height:1.6; color:#cdd3ff;\">Le enviamos adjunto su informe médico en formato PDF.</p>

                            <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"background:#11152d; border:1px solid #2b325f; border-radius:10px;\">
                                <tr>
                                    <td style=\"padding:14px 16px; font-size:14px; color:#dbe1ff;\">
                                        <div style=\"margin-bottom:6px;\"><strong>Estudio:</strong> {study_type_safe}</div>
                                        <div><strong>Número de acceso:</strong> {accession_safe}</div>
                                    </td>
                                </tr>
                            </table>

                            {viewer_html_block}

                            <p style=\"margin:24px 0 0 0; font-size:12px; color:#97a0d6; line-height:1.5;\">Este es un mensaje automático generado por NextRIS. Por favor, no responder a este correo.</p>
                        </td>
                    </tr>
                    <tr>
                        <td style=\"padding:14px 24px; border-top:1px solid #2a2f57; background:#131731; color:#9aa3da; font-size:12px;\">
                            Atentamente, {sender_name_safe}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """

        alternative_part = MIMEMultipart('alternative')
        alternative_part.attach(MIMEText(body_text, 'plain', 'utf-8'))
        alternative_part.attach(MIMEText(body_html, 'html', 'utf-8'))
        msg.attach(alternative_part)
        
        # Adjuntar PDF
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(rendered.content)
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {rendered.filename}'
        )
        msg.attach(part)
        
        # Enviar email
        if not smtp_user or not smtp_password:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Configuración SMTP incompleta'
            }), 500

        text = msg.as_string()

        def _send_with_smtp(server_host, server_port, user_name, password_value, sender_email, sender_name, tls_enabled):
            smtp_client = smtplib.SMTP(server_host, server_port)
            sent_ok = False
            try:
                if tls_enabled:
                    smtp_client.starttls()
                smtp_client.login(user_name, password_value)
                smtp_client.sendmail(sender_email, email, text)
                sent_ok = True
            finally:
                try:
                    smtp_client.quit()
                except Exception:
                    # Evita reintentos/doble envío cuando el correo ya salió pero falló el cierre SMTP.
                    if not sent_ok:
                        raise

        send_error = None
        try:
            _send_with_smtp(smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls)
        except Exception as smtp_error:
            send_error = smtp_error

            # Fallback: reintentar con SMTP global si el principal era configuración de facility.
            fallback_server = env_smtp_server
            fallback_port = _safe_port(env_smtp_port_raw, 587)
            fallback_user = env_smtp_user
            fallback_password = env_smtp_password
            fallback_from = env_smtp_from or fallback_user
            fallback_name = env_smtp_from_name

            can_retry_with_env = bool(fallback_user and fallback_password)
            primary_is_different = (
                str(smtp_server or '') != str(fallback_server or '')
                or str(smtp_user or '') != str(fallback_user or '')
                or int(smtp_port or 0) != int(fallback_port or 0)
            )

            if can_retry_with_env and primary_is_different:
                _send_with_smtp(
                    fallback_server,
                    fallback_port,
                    fallback_user,
                    fallback_password,
                    fallback_from,
                    fallback_name,
                    True,
                )
                send_error = None

        if send_error is not None:
            raise send_error
        
        # Registrar envío en cola de emails
        # Nota: tbemailqueue table doesn't exist yet, so we skip this for now
        # queue_query = """
        #     INSERT INTO nextris.tbemailqueue (
        #         guid, examination_id, recipient_email, status, sent_at
        #     ) VALUES (%s, %s, %s, 'sent', NOW())
        # """
        # cursor.execute(queue_query, (str(uuid.uuid4()), exam_id, email))
        # connection.commit()
        
        # Mark examination as published/sent
        update_query = """
            UPDATE nextris.tbexamination 
            SET ispublicated = 1
            WHERE guid = %s
        """
        cursor.execute(update_query, (exam_id,))


        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Informe enviado correctamente'
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error al enviar email: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/update-email', methods=['PATCH', 'PUT'])
@jwt_required()
@require_permission('distribution.update_email', include_role_permissions=False)
def update_examination_email(exam_id):
    """
    Actualiza el email de un examen/orden
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "email": "nuevo@email.com" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Email actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'message': 'El email es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener el patient_id del examen
        cursor.execute(
            "SELECT idpatient FROM nextris.tbexamination WHERE guid = %s",
            (exam_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        patient_id = result[0]
        
        # Actualizar email del paciente
        cursor.execute(
            "UPDATE nextris.datapatient SET email = %s WHERE guid = %s",
            (email, patient_id)
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Email actualizado correctamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/report/view', methods=['GET'])
@jwt_required()
def view_examination_report(exam_id):
    """
    Visualiza el PDF del informe de un examen en el navegador
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    - Archivo PDF del reporte para visualizar en el navegador
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
        
        # El PDF se renderiza bajo demanda desde el reporte vigente.
        query = """
            SELECT r.guid
            FROM nextris.tbreport r
            INNER JOIN nextris.tbexamination e ON r.idexamination = e.guid
            WHERE e.guid = %s
        """
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result or not result[0]:
            return jsonify({
                'success': False,
                'message': 'Informe PDF no disponible para este examen'
            }), 404

        from apps.services.report_pdf_service import ReportPdfNotAvailable, render_report_pdf
        try:
            rendered = render_report_pdf(exam_id)
        except ReportPdfNotAvailable:
            return jsonify({'success': False, 'message': 'Informe PDF no disponible', 'code': 'REPORT_NOT_AVAILABLE'}), 404

        response = send_file(
            BytesIO(rendered.content),
            as_attachment=request.args.get('download', '').lower() in ('1', 'true', 'yes', 'on'),
            download_name=rendered.filename,
            mimetype='application/pdf',
            max_age=0,
        )
        response.headers['Cache-Control'] = 'no-store'
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/dicom-viewer', methods=['GET'])
@jwt_required()
def get_dicom_viewer_info(exam_id):
    """
    Obtiene la información necesaria para abrir el visor DICOM

    Path:
    - exam_id: GUID del examen

    Returns:
    {
        "success": true,
        "data": {
            "exam_id": "uuid",
            "study_uid": "1.2.840...",
            "patient_name": "García, Ana",
            "study_description": "ANGIOTOMOGRAFIA",
            "study_date": "07/12/2025",
            "viewer_url": "/viewer?studyUID=1.2.840...",
            "has_images": true
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

        # Obtener información del examen para el visor DICOM
        query = """
            SELECT
                e.guid,
                e.studyinstanceuid,
                CONCAT(dp.surname, ', ', dp.name) as patient_name,
                st.description as study_description,
                TO_CHAR(e.createdon, 'DD/MM/YYYY') as study_date,
                e.localacc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
            WHERE e.guid = %s
        """

        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if not result:
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        study_uid = result[1]

        if not study_uid:
            return jsonify({
                'success': False,
                'message': 'Este examen no tiene Study UID asociado'
            }), 404

        # Construir URL del visor
        viewer_url_cfg = current_app.config.get('DICOM_VIEWER_URL', 'https://clinicacp.ddns.net:3000/viewer')
        parsed = urlparse(viewer_url_cfg)
        viewer_base = f"{parsed.scheme}://{parsed.netloc}"
        viewer_url = f"{viewer_base}/viewer?StudyInstanceUIDs={study_uid}"

        # Verificar si existen imágenes (opcional, basado en la existencia de archivos)
        has_images = True  # Por defecto asumimos que sí hay imágenes si tiene study_uid

        return jsonify({
            'success': True,
            'data': {
                'exam_id': result[0],
                'study_uid': study_uid,
                'patient_name': result[2] or '',
                'study_description': result[3] or '',
                'study_date': result[4] or '',
                'accession_number': result[5] or '',
                'viewer_url': viewer_url,
                'has_images': has_images
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# FUNCIONES AUXILIARES PARA WHATSAPP
# ====================================================================

def send_whatsapp_document(api_url, api_token, phone_number_id, recipient_phone,
                           pdf_content, caption, document_filename):
    """
    Envía un documento PDF por WhatsApp usando la Meta Cloud API.

    1. Sube el PDF como media
    2. Envía el documento con caption al destinatario

    Returns: (success: bool, message: str)
    """
    headers_auth = {
        'Authorization': f'Bearer {api_token}'
    }

    # Paso 1: Subir el PDF como media
    upload_url = f"{api_url}/{phone_number_id}/media"

    upload_response = requests.post(
        upload_url,
        headers=headers_auth,
        files={'file': (document_filename, pdf_content, 'application/pdf')},
        data={'messaging_product': 'whatsapp', 'type': 'application/pdf'},
        timeout=30
    )

    if upload_response.status_code != 200:
        return False, f"Error al subir media: {upload_response.status_code} - {upload_response.text}"

    media_id = upload_response.json().get('id')
    if not media_id:
        return False, f"No se obtuvo media_id de la respuesta: {upload_response.text}"

    # Paso 2: Enviar mensaje con el documento
    message_url = f"{api_url}/{phone_number_id}/messages"

    message_payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "document",
        "document": {
            "id": media_id,
            "caption": caption,
            "filename": document_filename
        }
    }

    msg_response = requests.post(
        message_url,
        headers={**headers_auth, 'Content-Type': 'application/json'},
        json=message_payload,
        timeout=30
    )

    if msg_response.status_code not in (200, 201):
        return False, f"Error al enviar documento: {msg_response.status_code} - {msg_response.text}"

    return True, "Documento enviado correctamente"


def send_whatsapp_text(api_url, api_token, phone_number_id, recipient_phone, text_body):
    """
    Envía un mensaje de texto por WhatsApp usando la Meta Cloud API.

    Returns: (success: bool, message: str)
    """
    message_url = f"{api_url}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text_body}
    }

    response = requests.post(
        message_url,
        headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        },
        json=payload,
        timeout=30
    )

    if response.status_code not in (200, 201):
        return False, f"Error al enviar texto: {response.status_code} - {response.text}"

    return True, "Mensaje enviado correctamente"


# ====================================================================
# ENDPOINTS PARA DISTRIBUCIÓN POR WHATSAPP
# ====================================================================

@api_blueprint.route('/examinations/<exam_id>/send-report-whatsapp', methods=['POST'])
@jwt_required()
@require_permission('distribution.send_report_whatsapp', include_role_permissions=False)
def send_report_whatsapp(exam_id):
    """
    Envía un informe por WhatsApp

    Path:
    - exam_id: GUID del examen

    Body JSON:
    {
        "phone": "+521234567890" (required)
    }

    Returns:
    {
        "success": true,
        "message": "Informe enviado por WhatsApp correctamente"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        phone = data.get('phone', '').strip()

        if not phone:
            return jsonify({
                'success': False,
                'message': 'El número de teléfono es requerido'
            }), 400

        # Limpiar el número: solo dígitos
        clean_phone = phone.lstrip('+')
        clean_phone = ''.join(c for c in clean_phone if c.isdigit())

        if not clean_phone or len(clean_phone) < 10:
            return jsonify({
                'success': False,
                'message': 'Número de teléfono inválido. Debe incluir código de país (ej: +521234567890)'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Obtener información del reporte, examen y config WhatsApp de la facility
        query = """
            SELECT
                r.guid,
                CONCAT(dp.name, ' ', dp.surname) as patient_name,
                st.description as study_type,
                ex.localacc as accession_number,
                f.whatsapp_api_url,
                f.whatsapp_api_token,
                f.whatsapp_phone_number_id,
                f.whatsapp_is_active,
                ex.studyinstanceuid,
                COALESCE(ex.isimage, 0) as has_images,
                COALESCE(f.smtp_from_name, f.name, 'NextRIS') as sender_name,
                f.guid as facility_id,
                COALESCE(ex.ispublicated, 0) as is_publicated
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.datapatient dp ON ex.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = ex.guid
            LEFT JOIN nextris.isequipment eq ON ex.idequipment = eq.guid
            LEFT JOIN nextris.tblocation l ON eq.location_id = l.guid
            LEFT JOIN nextris.tbfacility f ON l.facility_id = f.guid
            WHERE ex.guid = %s
        """

        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        patient_name = result[1]
        study_type = result[2]
        accession_number = result[3]
        wa_api_url = result[4]
        wa_api_token = result[5]
        wa_phone_number_id = result[6]
        wa_is_active = result[7]
        study_uid = result[8]
        has_images = bool(result[9])
        sender_name = result[10]
        facility_id = result[11]
        already_publicated = bool(result[12])

        if facility_id and not already_publicated:
            is_allowed, limit_payload = check_limit_before_action(connection, facility_id, 'distribute')
            if not is_allowed:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': limit_payload.get('message', 'Límite de distribución alcanzado para el plan actual'),
                    'code': limit_payload.get('reason', 'DISTRIBUTE_LIMIT_REACHED'),
                    'data': {
                        'limits': limit_payload.get('limits'),
                        'usage': limit_payload.get('usage'),
                    }
                }), 409

        # Validar configuración WhatsApp
        if not wa_is_active:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'WhatsApp no está activo para esta facility. Active la configuración de WhatsApp en la configuración de la facility.'
            }), 400

        if not wa_api_url or not wa_api_token or not wa_phone_number_id:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Configuración de WhatsApp incompleta. Verifique API URL, Token y Phone Number ID en la configuración de la facility.',
                'data': {
                    'whatsapp_configured': False,
                    'api_url_exists': bool(wa_api_url),
                    'api_token_exists': bool(wa_api_token),
                    'phone_number_id_exists': bool(wa_phone_number_id)
                }
            }), 500

        from apps.services.report_pdf_service import ReportPdfNotAvailable, render_report_pdf
        try:
            rendered = render_report_pdf(exam_id)
        except ReportPdfNotAvailable:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Informe PDF no disponible',
                'code': 'REPORT_NOT_AVAILABLE',
            }), 404
        except Exception as render_error:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': f'Error generando PDF: {render_error}'}), 500

        # Construir caption del documento
        caption = (
            f"Estimado/a {patient_name},\n\n"
            f"Adjunto el informe médico correspondiente al estudio: {study_type}\n"
            f"Número de acceso: {accession_number}\n\n"
            f"Este es un mensaje automático.\n"
            f"- {sender_name}"
        )

        document_filename = rendered.filename

        # Enviar documento PDF por WhatsApp
        success, message = send_whatsapp_document(
            wa_api_url, wa_api_token, wa_phone_number_id,
            clean_phone, rendered.content, caption, document_filename
        )

        if not success:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Error al enviar por WhatsApp: {message}'
            }), 500

        # Si hay imágenes DICOM, enviar link del visor en un segundo mensaje
        if has_images and study_uid:
            viewer_url = _build_viewer_url(study_uid)
            viewer_text = (
                f"Para visualizar las imágenes médicas de su estudio ({study_type}), "
                f"acceda al siguiente enlace:\n\n{viewer_url}"
            )
            send_whatsapp_text(
                wa_api_url, wa_api_token, wa_phone_number_id,
                clean_phone, viewer_text
            )

        # Marcar examen como publicado/enviado
        update_query = """
            UPDATE nextris.tbexamination
            SET ispublicated = 1
            WHERE guid = %s
        """
        cursor.execute(update_query, (exam_id,))


        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Informe enviado por WhatsApp correctamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al enviar por WhatsApp: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/update-phone', methods=['PATCH', 'PUT'])
@jwt_required()
def update_examination_phone(exam_id):
    """
    Actualiza el teléfono de un paciente asociado a un examen

    Path:
    - exam_id: GUID del examen

    Body JSON:
    {
        "phone": "+521234567890" (required)
    }

    Returns:
    {
        "success": true,
        "message": "Teléfono actualizado correctamente"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        phone = data.get('phone', '').strip()

        if not phone:
            return jsonify({
                'success': False,
                'message': 'El teléfono es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Obtener el patient_id del examen
        cursor.execute(
            "SELECT idpatient FROM nextris.tbexamination WHERE guid = %s",
            (exam_id,)
        )
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404

        patient_id = result[0]

        # Actualizar teléfono del paciente
        cursor.execute(
            "UPDATE nextris.datapatient SET phone = %s WHERE guid = %s",
            (phone, patient_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Teléfono actualizado correctamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
