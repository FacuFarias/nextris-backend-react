# -*- encoding: utf-8 -*-
"""
API REST para Distribución de Informes
Endpoints para gestión y envío de informes médicos finalizados
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
import uuid
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


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
                COALESCE(e.stat, 'N') as urgencia
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.patientid
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
                'urgencia': row[8]
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
                p.name as patient_name,
                st.description as study_type,
                o.accession_number,
                f.smtp_server,
                f.smtp_port,
                f.smtp_user,
                f.smtp_password,
                f.smtp_from,
                f.smtp_from_name,
                f.use_tls
            FROM nextris.tbexamination ex
            INNER JOIN nextris.tborder o ON ex.order_id = o.guid
            INNER JOIN nextris.tbpatient p ON o.patient_id = p.guid
            INNER JOIN nextris.isstudytype st ON o.studytype_id = st.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = ex.guid
            LEFT JOIN nextris.tblocation l ON o.location_id = l.guid
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
        smtp_server = result[4] or 'smtp.gmail.com'
        smtp_port = result[5] or 587
        smtp_user = result[6]
        smtp_password = result[7]
        smtp_from = result[8] or smtp_user
        smtp_from_name = result[9] or 'NextRIS'
        use_tls = result[10] if result[10] is not None else True
        
        if not pdf_path or not os.path.exists(pdf_path):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'PDF del informe no encontrado'
            }), 404
        
        # Crear mensaje de email
        msg = MIMEMultipart()
        msg['From'] = f"{smtp_from_name} <{smtp_from}>"
        msg['To'] = email
        msg['Subject'] = f'Informe Médico - {study_type}'
        
        body = f"""
Estimado/a {patient_name},

Adjunto encontrará el informe médico correspondiente al estudio: {study_type}
Número de acceso: {accession_number}

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
        queue_query = """
            INSERT INTO nextris.tbemailqueue (
                guid, examination_id, recipient_email, status, sent_at
            ) VALUES (%s, %s, %s, 'sent', NOW())
        """
        cursor.execute(queue_query, (str(uuid.uuid4()), exam_id, email))
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
        
        # Obtener el order_id del examen
        cursor.execute(
            "SELECT order_id FROM nextris.tbexamination WHERE guid = %s",
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
        
        order_id = result[0]
        
        # Actualizar email en la orden
        cursor.execute(
            "UPDATE nextris.tborder SET patient_email = %s WHERE guid = %s",
            (email, order_id)
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
    Visualiza o descarga el PDF del informe de un examen
    
    Path:
    - exam_id: GUID del examen
    
    Query Parameters:
    - download (optional): 'true' para forzar descarga, 'false' para visualizar en navegador (default: false)
    
    Returns:
    - Archivo PDF del reporte
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
        
        # Obtener ruta del PDF y nombre del paciente para el filename
        query = """
            SELECT 
                r.pdfpath,
                CONCAT(dp.name, '_', dp.surname, '_', st.description) as filename_base
            FROM nextris.tbreport r
            INNER JOIN nextris.tbexamination e ON r.idexamination = e.guid
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.patientid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
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
        filename_base = result[1] if result[1] else 'informe'
        
        # Normalizar y verificar que el archivo existe
        absolute_path = os.path.abspath(os.path.normpath(pdf_path))
        
        if not os.path.exists(absolute_path):
            return jsonify({
                'success': False,
                'message': 'Archivo PDF no encontrado en el sistema'
            }), 404
        
        # Verificar si se solicita descarga
        download = request.args.get('download', 'false').lower() == 'true'
        
        # Limpiar filename_base de caracteres no permitidos
        filename = f"{filename_base.replace(' ', '_').replace('/', '_')}.pdf"
        
        return send_file(
            absolute_path,
            as_attachment=download,
            download_name=filename if download else None,
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
            LEFT JOIN nextris.datapatient dp ON e.idpatient = dp.patientid
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
