# -*- encoding: utf-8 -*-
"""
API REST para Distribución de Informes
Endpoints para gestión y envío de informes médicos finalizados
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
from apps.api.permissions import require_permission
import uuid
import os
import smtplib
import requests
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
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener ubicaciones del usuario
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            cursor.close()
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
        
        # Query base
        query = """
            SELECT 
                e.guid,
                TO_CHAR(e.createdon, 'DD/MM/YYYY HH24:MI') as fecha,
                st.description as examen,
                CONCAT(dp.name, ' ', dp.surname) as paciente,
                COALESCE(dp.email, '') as mail,
                CASE 
                    WHEN COALESCE(e.ispublicated, 0) = 1 THEN 'E'
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
                COALESCE(dp.phone, '') as phone
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
            LEFT JOIN nextris.isequipment eq ON e.idequipment = eq.guid
            LEFT JOIN nextris.isrequestingphysician rp ON e.idrequestingphysician = rp.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            LEFT JOIN nextris.tbuser u ON r.iduser = u.guid
            WHERE eq.location_id = ANY(%s)
            AND e.isreported = 1
        """
        
        params = [user_locations]
        
        # Si no se quieren los ya enviados, filtrar
        if not all_reported:
            query += " AND (e.ispublicated IS NULL OR e.ispublicated = 0)"
        
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
                'phone': row[14] or ''
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
                r.pdfpath,
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
                COALESCE(ex.isimage, 0) as has_images
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
        
        pdf_path = result[0]
        patient_name = result[1]
        study_type = result[2]
        accession_number = result[3]
        
        # Configuración SMTP con valores por defecto
        smtp_server = result[4] or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = result[5] or int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = result[6] or os.environ.get('SMTP_USER')
        smtp_password = result[7] or os.environ.get('SMTP_PASSWORD')
        smtp_from = result[8] or smtp_user or os.environ.get('SMTP_FROM')
        smtp_from_name = result[9] or os.environ.get('SMTP_FROM_NAME', 'NextRIS')
        use_tls = result[10] if result[10] is not None else True
        
        study_uid = result[11]
        has_images = bool(result[12])
        
        if not pdf_path or not os.path.exists(pdf_path):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'PDF del informe no encontrado'
            }), 404
        
        if not smtp_user or not smtp_password:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Configuración SMTP incompleta. Configure SMTP_USER y SMTP_PASSWORD en las variables de entorno o en la base de datos.',
                'data': {
                    'smtp_configured': False,
                    'smtp_server': smtp_server,
                    'smtp_port': smtp_port,
                    'smtp_user_exists': bool(smtp_user),
                    'smtp_password_exists': bool(smtp_password)
                }
            }), 500
        
        # Crear mensaje de email
        msg = MIMEMultipart()
        msg['From'] = f"{smtp_from_name} <{smtp_from}>"
        msg['To'] = email
        msg['Subject'] = f'Informe Médico - {study_type}'
        
        # Generar link del visor DICOM si hay imágenes
        viewer_link = ""
        if has_images and study_uid:
            viewer_link = f"\n\nPara visualizar las imágenes médicas, acceda al siguiente enlace:\nhttps://viewer.nextris.cloud/viewer?StudyInstanceUIDs={study_uid}\n"
        
        body = f"""
Estimado/a {patient_name},

Adjunto encontrará el informe médico correspondiente al estudio: {study_type}
Número de acceso: {accession_number}
{viewer_link}
Este es un mensaje automático, por favor no responder.

Saludos cordiales,
{smtp_from_name}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Adjuntar PDF
        with open(pdf_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= informe_{accession_number}.pdf'
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
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_from, email, text)
        server.quit()
        
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
        
        # Obtener ruta del PDF
        query = """
            SELECT r.pdfpath
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
        
        pdf_path = result[0]
        
        # Normalizar y verificar que el archivo existe
        absolute_path = os.path.abspath(os.path.normpath(pdf_path))
        
        if not os.path.exists(absolute_path):
            return jsonify({
                'success': False,
                'message': 'Archivo PDF no encontrado en el sistema'
            }), 404
        
        # Enviar el PDF para visualizar en el navegador (no como descarga)
        return send_file(
            absolute_path,
            mimetype='application/pdf'
        )
        
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
        viewer_url = f"/viewer?studyUID={study_uid}"

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
                           pdf_path, caption, document_filename):
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

    with open(pdf_path, 'rb') as pdf_file:
        upload_response = requests.post(
            upload_url,
            headers=headers_auth,
            files={'file': (document_filename, pdf_file, 'application/pdf')},
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
                r.pdfpath,
                CONCAT(dp.name, ' ', dp.surname) as patient_name,
                st.description as study_type,
                ex.localacc as accession_number,
                f.whatsapp_api_url,
                f.whatsapp_api_token,
                f.whatsapp_phone_number_id,
                f.whatsapp_is_active,
                ex.studyinstanceuid,
                COALESCE(ex.isimage, 0) as has_images,
                COALESCE(f.smtp_from_name, f.name, 'NextRIS') as sender_name
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

        pdf_path = result[0]
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

        if not pdf_path or not os.path.exists(pdf_path):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'PDF del informe no encontrado'
            }), 404

        # Construir caption del documento
        caption = (
            f"Estimado/a {patient_name},\n\n"
            f"Adjunto el informe médico correspondiente al estudio: {study_type}\n"
            f"Número de acceso: {accession_number}\n\n"
            f"Este es un mensaje automático.\n"
            f"- {sender_name}"
        )

        document_filename = f"informe_{accession_number}.pdf"

        # Enviar documento PDF por WhatsApp
        success, message = send_whatsapp_document(
            wa_api_url, wa_api_token, wa_phone_number_id,
            clean_phone, pdf_path, caption, document_filename
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
            viewer_url = f"https://viewer.nextris.cloud/viewer?StudyInstanceUIDs={study_uid}"
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
