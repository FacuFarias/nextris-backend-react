# -*- encoding: utf-8 -*-
"""
API del Portal de Pacientes - Endpoints para pacientes autenticados
Permite a los pacientes gestionar su perfil y acceder a su información
"""

from flask import jsonify, request, send_file, current_app, Response
from io import BytesIO
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import psycopg2
import requests
from datetime import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse
from apps.services.patient_email_verification import (
    VerificationError, normalize_email, require_password_change_email, email_verification_enabled,
    send_verification, confirm_verification,
)
from apps.api import api_blueprint
from apps.api.viewer_share_service import create_for_exam as create_share_for_exam


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


# ====================================================================
# MIS DATOS - PERFIL DEL PACIENTE
# ====================================================================

def _can_change_patient_password(email, verified):
    if email_verification_enabled():
        return verified
    try:
        normalize_email(email)
        return True
    except VerificationError:
        return False


@api_blueprint.route('/patient-portal/my-profile', methods=['GET'])
@jwt_required()
def get_my_profile():
    """
    Obtiene los datos del perfil del paciente autenticado
    
    Headers:
    - Authorization: Bearer <patient_jwt_token>
    
    Returns:
    {
        "success": true,
        "data": {
            "patient_id": "uuid",
            "username": "jperez",
            "name": "Juan",
            "surname": "Pérez",
            "full_name": "Pérez, Juan",
            "national_code": "12345678",
            "patient_id_number": "20-12345678-9",
            "birthdate": "1990-01-15",
            "age": 36,
            "sex_code": "M",
            "sex": "Masculino",
            "phone": "+5491112345678",
            "email": "juan.perez@email.com",
            "address": "Calle Falsa 123",
            "city": "Buenos Aires",
            "state": "CABA",
            "zip_code": "1000",
            "health_card": "123456789",
            "last_login": "2026-01-10T15:30:00",
            "account_status": "Active"
        }
    }
    """
    try:
        patient_user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener datos del usuario paciente y su información personal
        query = """
            SELECT 
                up.guid as patient_id,
                up.username,
                up.status,
                up.lastlogin,
                dp.name,
                dp.surname,
                dp.nationalcode,
                dp.patientid,
                dp.birthdate,
                dp.sexcode,
                dp.phone,
                dp.email,
                dp.healthcard,
                dp.address,
                dp.city,
                dp.state,
                dp.zip_code,
                (up.verified_email IS NOT NULL AND
                 up.verified_email = lower(btrim(dp.email))) AS email_verified
            FROM nextris.tbuser_patient up
            INNER JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
            WHERE up.guid = %s
        """
        
        cursor.execute(query, (patient_user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        # Calcular edad
        age = None
        if result[8]:  # birthdate
            today = datetime.now().date()
            birthdate = result[8]
            age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        
        # Determinar sexo en texto
        sex_text = None
        if result[9]:  # sexcode
            sex_map = {
                'M': 'Masculino',
                'F': 'Femenino',
                'O': 'Otro'
            }
            sex_text = sex_map.get(result[9], result[9])
        
        patient_data = {
            'patient_id': result[0],
            'username': result[1],
            'account_status': result[2],
            'last_login': result[3].isoformat() if result[3] else None,
            'name': result[4],
            'surname': result[5],
            'full_name': f"{result[5]}, {result[4]}" if result[5] and result[4] else None,
            'national_code': result[6],
            'patient_id_number': result[7],
            'birthdate': result[8].strftime('%Y-%m-%d') if result[8] else None,
            'age': age,
            'sex_code': result[9],
            'sex': sex_text,
            'phone': result[10],
            'email': result[11],
            'health_card': result[12],
            'address': result[13],
            'city': result[14],
            'state': result[15],
            'zip_code': result[16],
            'email_verified': bool(result[17]),
            'email_verification_enabled': email_verification_enabled(),
            'can_change_password': _can_change_patient_password(result[11], bool(result[17]))
        }
        
        return jsonify({
            'success': True,
            'data': patient_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patient-portal/my-profile', methods=['PUT', 'PATCH'])
@jwt_required()
def update_my_profile():
    """
    Actualiza los datos del perfil del paciente autenticado
    
    Headers:
    - Authorization: Bearer <patient_jwt_token>
    
    Body JSON (todos opcionales):
    {
        "phone": "+5491112345678",
        "email": "nuevo.email@example.com",
        "address": "Calle Falsa 123",
        "city": "Buenos Aires",
        "state": "CABA",
        "zip_code": "1000"
    }
    
    Nombre, apellido, DNI, fecha de nacimiento y sexo deben ser actualizados
    por personal administrativo.
    
    Returns:
    {
        "success": true,
        "message": "Perfil actualizado exitosamente",
        "data": { ... datos actualizados ... }
    }
    """
    try:
        patient_user_id = get_jwt_identity()
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
        
        # Obtener el datapatient_id
        cursor.execute(
            "SELECT datapatient_id FROM nextris.tbuser_patient WHERE guid = %s",
            (patient_user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        datapatient_id = result[0]
        
        # Solo los datos de contacto pueden ser modificados por el paciente.
        allowed_fields = {
            'phone': 50,
            'email': 150,
            'address': 255,
            'city': 100,
            'state': 100,
            'zip_code': 20,
        }
        
        # Construir query de actualización solo con campos permitidos
        updates = []
        params = []
        
        for json_field, max_length in allowed_fields.items():
            if json_field in data:
                value = data[json_field]
                if not isinstance(value, str) or len(value.strip()) > max_length:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': f'Valor inválido para {json_field}'
                    }), 400
                if json_field == 'email' and value.strip():
                    try:
                        value = normalize_email(value)
                    except VerificationError as exc:
                        cursor.close()
                        connection.close()
                        return jsonify(success=False, message=str(exc)), exc.status
                updates.append(f"{json_field} = %s")
                params.append(value.strip() or None)
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos válidos para actualizar'
            }), 400
        
        params.append(datapatient_id)
        query = f"UPDATE nextris.datapatient SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        # Obtener los datos actualizados usando el endpoint GET
        return get_my_profile()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patient-portal/email-verification/send', methods=['POST'])
@jwt_required()
def send_patient_email_verification():
    return _patient_email_verification(confirm=False)


@api_blueprint.route('/patient-portal/email-verification/confirm', methods=['POST'])
@jwt_required()
def confirm_patient_email_verification():
    return _patient_email_verification(confirm=True)


def _patient_email_verification(confirm):
    if get_jwt().get('user_type') != 'patient':
        return jsonify(success=False, message='Acceso exclusivo para pacientes'), 403
    if not email_verification_enabled():
        return jsonify(success=False, message='La validación de email está deshabilitada'), 403
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        with connection.cursor() as cursor:
            try:
                if confirm:
                    data = request.get_json(silent=True) or {}
                    confirm_verification(cursor, get_jwt_identity(), data.get('code'))
                else:
                    from apps.api.auth import _send_code_email
                    smtp_config = None
                    if not (os.getenv('RESEND_API_KEY')) and not (os.getenv('SMTP_USER') and os.getenv('SMTP_PASSWORD')):
                        cursor.execute("""SELECT smtp_server, smtp_port, smtp_user, smtp_password,
                            smtp_from, smtp_from_name, use_tls FROM nextris.app_config WHERE id = 1""")
                        row = cursor.fetchone()
                        if row and row[2] and row[3]:
                            smtp_config = dict(zip(('smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from', 'smtp_from_name', 'use_tls'), row))
                    send_verification(cursor, get_jwt_identity(),
                                      lambda email, code: _send_code_email(email, code, smtp_config))
            except VerificationError as exc:
                connection.commit()
                return jsonify(success=False, message=str(exc)), exc.status
        connection.commit()
        message = 'Email validado correctamente' if confirm else 'Enviamos un código a su email. Vence en 30 minutos'
        return jsonify(success=True, message=message), 200
    except Exception:
        if connection:
            connection.rollback()
        current_app.logger.exception('Error en verificación de email del paciente')
        return jsonify(success=False, message='No se pudo completar la validación. Intente nuevamente'), 503
    finally:
        if connection:
            connection.close()


@api_blueprint.route('/patient-portal/change-password', methods=['POST'])
@jwt_required()
def patient_change_password():
    """
    Permite al paciente cambiar su propia contraseña
    
    Headers:
    - Authorization: Bearer <patient_jwt_token>
    
    Body JSON:
    {
        "current_password": "contraseña_actual",
        "new_password": "nueva_contraseña",
        "confirm_password": "nueva_contraseña"
    }
    
    Returns:
    {
        "success": true,
        "message": "Contraseña actualizada exitosamente"
    }
    """
    try:
        patient_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            return jsonify({
                'success': False,
                'message': 'Se requieren current_password, new_password y confirm_password'
            }), 400
        
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': 'La nueva contraseña y su confirmación no coinciden'
            }), 400
        
        if len(new_password) < 4:
            return jsonify({
                'success': False,
                'message': 'La nueva contraseña debe tener al menos 4 caracteres'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        try:
            require_password_change_email(cursor, patient_user_id)
        except VerificationError as exc:
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify(success=False, message=str(exc)), exc.status

        # Verificar la contraseña actual
        cursor.execute(
            "SELECT password FROM nextris.tbuser_patient WHERE guid = %s",
            (patient_user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        stored_password = result[0]
        
        # Verificar contraseña actual
        from werkzeug.security import check_password_hash, generate_password_hash
        
        if not check_password_hash(stored_password, current_password):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La contraseña actual es incorrecta'
            }), 401
        
        # Actualizar contraseña
        new_password_hash = generate_password_hash(new_password)
        
        cursor.execute(
            "UPDATE nextris.tbuser_patient SET password = %s, firstlogin = 0 WHERE guid = %s",
            (new_password_hash, patient_user_id)
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# MIS ESTUDIOS - LISTADO DE ESTUDIOS DEL PACIENTE
# ====================================================================

@api_blueprint.route('/patient-portal/my-studies', methods=['GET'])
@jwt_required()
def get_my_studies():
    """
    Obtiene los estudios médicos del paciente autenticado
    
    Headers:
    - Authorization: Bearer <patient_jwt_token>
    
    Query Parameters:
    - page (optional): Número de página (default: 1)
    - per_page (optional): Items por página (default: 20, max: 100)
    - status (optional): Filtrar por estado - 'reported' (con informe), 'pending' (sin informe)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "examination_id": "uuid",
                "order_id": "uuid",
                "accession_number": "ACC001234",
                "patient_name": "Juan Pérez",
                "patient_id": "NR00000001",
                "study_type": "TOMOGRAFIA DE TORAX",
                "modality": "CT",
                "study_date": "2026-01-10",
                "study_time": "14:30:00",
                "status": "Reportado",
                "has_report": true,
                "has_images": true,
                "referring_physician": "Dr. García",
                "location": "Sede Central",
                "urgency": "Normal",
                "report_date": "2026-01-10T16:00:00"
            }
        ],
        "total": 10,
        "page": 1,
        "per_page": 20
    }
    """
    try:
        patient_user_id = get_jwt_identity()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', None)
        
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener el patient_id del datapatient
        cursor.execute("""
            SELECT dp.guid, dp.name, dp.surname, dp.patientid
            FROM nextris.tbuser_patient up
            INNER JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
            WHERE up.guid = %s
        """, (patient_user_id,))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        patient_data_id = result[0]
        patient_name = ' '.join(filter(None, (result[1], result[2])))
        patient_id = result[3]
        
        # Query base - usar tbexamination directamente sin tborder
        base_query = """
            SELECT 
                ex.guid as examination_id,
                ex.localacc as accession_number,
                COALESCE(st.description, ps.study_desc) as study_type,
                COALESCE(m.description, first_series.modality) as modality,
                ex.createdon as created_datetime,
                CASE 
                    WHEN ex.isreported = 1 THEN 'Reportado'
                    ELSE 'Pendiente'
                END as status,
                COALESCE(ex.isreported, 0) as isreported,
                CASE
                    WHEN COALESCE(ex.isimage, 0) = 1
                         AND ex.studyinstanceuid IS NOT NULL
                         AND ex.studyinstanceuid != ''
                         AND nextris.available_study_for_exam(ex.guid) IS NOT NULL
                    THEN true
                    ELSE false
                END as has_images,
                CONCAT(COALESCE(u_ref.name, ''), ' ', COALESCE(u_ref.surname, '')) as referring_physician,
                rp.description as requesting_physician,
                CONCAT(COALESCE(u_auth.name, ''), ' ', COALESCE(u_auth.surname, '')) as author_physician,
                CASE
                    WHEN CAST(ex.stat AS TEXT) = 'S' THEN 'Urgente'
                    ELSE 'Normal'
                END as urgency,
                r.date as report_date,
                nextris.available_study_for_exam(ex.guid) AS studyinstanceuid,
                ps.study_date,
                ps.study_time
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.ismodality m ON st.modality_id = m.guid
            LEFT JOIN public.study ps ON ex.studyinstanceuid = ps.study_iuid
            LEFT JOIN LATERAL (
                SELECT psr.modality
                FROM nextris.available_pacs_series psr
                WHERE psr.study_fk = ps.pk
                LIMIT 1
            ) first_series ON true
            LEFT JOIN nextris.tbuser u_ref ON u_ref.guid = ex.idreferringphysician
            LEFT JOIN nextris.isrequestingphysician rp ON ex.idrequestingphysician = rp.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = ex.guid
            LEFT JOIN nextris.tbuser u_auth ON u_auth.guid = r.iduser
            WHERE ex.idpatient = %s
                AND (ex.hidden_in_portal = 0 OR ex.hidden_in_portal IS NULL)
        """
        
        params = [patient_data_id]
        
        # Aplicar filtro de estado si se proporciona
        if status_filter == 'reported':
            base_query += " AND ex.isreported = 1"
        elif status_filter == 'pending':
            base_query += " AND (ex.isreported = 0 OR ex.isreported IS NULL)"
        
        # Aplicar filtro de fecha
        date_from = request.args.get('date_from', None)
        date_to = request.args.get('date_to', None)
        if date_from:
            base_query += " AND (ps.study_date >= %s OR (ps.study_date IS NULL AND ex.createdon::date >= %s))"
            params.append(date_from.replace('-', ''))
            params.append(date_from)
        if date_to:
            base_query += " AND (ps.study_date <= %s OR (ps.study_date IS NULL AND ex.createdon::date <= %s))"
            params.append(date_to.replace('-', ''))
            params.append(date_to)
        
        # Aplicar búsqueda por texto (busca en múltiples campos)
        search = request.args.get('search', None)
        if search:
            search_param = f"%{search}%"
            base_query += """ AND (
                ex.localacc ILIKE %s
                OR st.description ILIKE %s
                OR m.description ILIKE %s
                OR ps.study_desc ILIKE %s
                OR u_ref.name ILIKE %s
                OR u_ref.surname ILIKE %s
                OR rp.description ILIKE %s
                OR u_auth.name ILIKE %s
                OR u_auth.surname ILIKE %s
                OR CASE WHEN CAST(ex.stat AS TEXT) = 'S' THEN 'Urgente' ELSE 'Normal' END ILIKE %s
                OR CASE WHEN ex.isreported = 1 THEN 'Reportado' ELSE 'Pendiente' END ILIKE %s
            )"""
            params.extend([search_param] * 11)
        
        base_query += " ORDER BY COALESCE(ps.study_date, TO_CHAR(ex.createdon, 'YYYYMMDD')) DESC NULLS LAST, COALESCE(ps.study_time, TO_CHAR(ex.createdon, 'HH24MISS')) DESC NULLS LAST"
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({base_query}) as count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Agregar paginación
        paginated_query = base_query + f" LIMIT {per_page} OFFSET {offset}"
        
        cursor.execute(paginated_query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        studies = []
        for row in results:
            created_datetime = row[4]
            pacs_study_date = row[14]
            pacs_study_time = row[15]

            if pacs_study_date:
                date_str = str(pacs_study_date)
                if len(date_str) == 8:
                    study_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    study_date = date_str

                if pacs_study_time:
                    time_str = str(pacs_study_time)
                    hh = time_str[0:2] if len(time_str) >= 2 else '00'
                    mm = time_str[2:4] if len(time_str) >= 4 else '00'
                    ss = time_str[4:6] if len(time_str) >= 6 else '00'
                    study_time = f"{hh}:{mm}:{ss}"
                else:
                    study_time = None
            elif created_datetime:
                study_date = created_datetime.strftime('%Y-%m-%d')
                study_time = created_datetime.strftime('%H:%M:%S')
            else:
                study_date = None
                study_time = None

            studies.append({
                'examination_id': row[0],
                'accession_number': row[1],
                'patient_name': patient_name,
                'patient_id': patient_id,
                'study_type': row[2],
                'modality': row[3],
                'study_date': study_date,
                'study_time': study_time,
                'status': row[5],
                'has_report': bool(row[6]),
                'has_images': row[7],
                'referring_physician': row[8].strip() if row[8] else None,
                'requesting_physician': row[9],
                'author_physician': row[10].strip() if row[10] else None,
                'urgency': row[11],
                'report_date': row[12].isoformat() if row[12] else None,
                'study_uid': row[13]
            })
        
        return jsonify({
            'success': True,
            'data': {
                'data': studies,
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


# ====================================================================
# CASE LINK - ENLACE PÚBLICO DEL ESTUDIO DEL PACIENTE
# ====================================================================

@api_blueprint.route('/patient-portal/examinations/<exam_id>/case-link', methods=['POST'])
@jwt_required()
def create_patient_case_link(exam_id):
    """Genera un enlace público temporal para un examen del paciente."""
    connection = None
    try:
        patient_user_id = get_jwt_identity()
        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        cursor.execute("""
            SELECT ex.guid, nextris.available_study_for_exam(ex.guid) AS studyinstanceuid,
                   COALESCE(ex.isimage, 0) = 1
                   AND ex.studyinstanceuid IS NOT NULL
                   AND ex.studyinstanceuid <> ''
                   AND EXISTS (
                       SELECT 1
                       FROM nextris.available_pacs_study ps
                       WHERE ps.study_iuid = nextris.available_study_for_exam(ex.guid)
                   ) AS has_images
            FROM nextris.tbuser_patient up
            INNER JOIN nextris.tbexamination ex ON ex.idpatient = up.datapatient_id
            WHERE up.guid = %s
              AND ex.guid = %s
              AND (ex.hidden_in_portal = 0 OR ex.hidden_in_portal IS NULL)
        """, (patient_user_id, exam_id))
        study = cursor.fetchone()
        cursor.close()

        if not study:
            connection.close()
            return jsonify({'success': False, 'message': 'Estudio no encontrado'}), 404
        if not study[1] or not study[2]:
            connection.close()
            return jsonify({'success': False, 'message': 'El estudio no tiene imágenes disponibles'}), 400

        share_data = create_share_for_exam(
            exam_id,
            created_by=patient_user_id,
            connection=connection,
            share_type='case_link',
        )
        connection.commit()
        connection.close()
        connection = None

        public_base = current_app.config.get('PUBLIC_API_URL', '').strip().rstrip('/')
        if not public_base:
            public_base = f"{request.headers.get('X-Forwarded-Proto', request.scheme)}://{request.headers.get('X-Forwarded-Host', request.host)}"

        short_code = share_data['short_code']
        return jsonify({
            'success': True,
            'data': {
                'case_url': f'{public_base}/case/{short_code}',
                'share_url': share_data['share_url'],
                'expires_at': share_data['expires_at'].isoformat() + 'Z',
                'expires_hours': share_data['expires_hours'],
            },
        }), 201
    except Exception as error:
        if connection:
            connection.rollback()
            connection.close()
        print(f'[PATIENT CASE LINK] Error creando enlace: {error}')
        return jsonify({'success': False, 'message': 'No se pudo generar el enlace del caso'}), 500


# ====================================================================
# DESCARGAR IMÁGENES - ESTUDIO DICOM DEL PACIENTE
# ====================================================================

@api_blueprint.route('/patient-portal/examinations/<exam_id>/images/download', methods=['GET'])
@jwt_required()
def download_study_images(exam_id):
    """Descarga todas las imágenes DICOM del estudio como archivo ZIP."""
    pacs_response = None
    try:
        patient_user_id = get_jwt_identity()
        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT nextris.available_study_for_exam(ex.guid) AS studyinstanceuid, ex.localacc,
                   COALESCE(ex.isimage, 0) = 1
                   AND ex.studyinstanceuid IS NOT NULL
                   AND ex.studyinstanceuid <> ''
                   AND EXISTS (
                       SELECT 1
                       FROM nextris.available_pacs_study ps
                       WHERE ps.study_iuid = nextris.available_study_for_exam(ex.guid)
                   ) AS has_images
            FROM nextris.tbuser_patient up
            INNER JOIN nextris.tbexamination ex ON ex.idpatient = up.datapatient_id
            WHERE up.guid = %s
              AND ex.guid = %s
              AND (ex.hidden_in_portal = 0 OR ex.hidden_in_portal IS NULL)
        """, (patient_user_id, exam_id))
        study = cursor.fetchone()
        cursor.close()
        connection.close()

        if not study or not study[0] or not study[2]:
            return jsonify({'success': False, 'message': 'Imágenes no encontradas para este estudio'}), 404

        # Reutiliza la configuración y autenticación PACS ya usada por la carga DICOM.
        from apps.api.dicom_routes import PACS_STOW_URL, get_pacs_token
        from urllib.parse import quote

        study_uid, accession_number = str(study[0]), study[1] or exam_id
        pacs_url = f"{PACS_STOW_URL.rstrip('/')}/{quote(study_uid, safe='')}"
        pacs_token = get_pacs_token()
        pacs_response = requests.get(
            pacs_url,
            params={'accept': 'application/zip'},
            headers={
                'Authorization': f'Bearer {pacs_token}',
                'Accept': 'application/zip',
            },
            stream=True,
            timeout=300,
            verify=False,
        )

        if pacs_response.status_code != 200:
            message = pacs_response.text[:300] if pacs_response.text else 'No se pudieron descargar las imágenes'
            pacs_response.close()
            pacs_response = None
            return jsonify({'success': False, 'message': message}), 502

        safe_accession = ''.join(char if char.isalnum() or char in '-_' else '_' for char in str(accession_number))
        headers = {
            'Content-Disposition': f'attachment; filename="estudio_{safe_accession}.zip"',
            'Content-Type': 'application/zip',
        }
        if pacs_response.headers.get('Content-Length'):
            headers['Content-Length'] = pacs_response.headers['Content-Length']

        stream_response = pacs_response

        def stream_content():
            try:
                for chunk in stream_response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        yield chunk
            finally:
                stream_response.close()

        response = Response(stream_content(), status=200, headers=headers)
        pacs_response = None
        return response

    except requests.RequestException as error:
        if pacs_response:
            pacs_response.close()
        return jsonify({'success': False, 'message': f'Error conectando con el PACS: {str(error)}'}), 502
    except Exception as error:
        if pacs_response:
            pacs_response.close()
        return jsonify({'success': False, 'message': f'Error descargando imágenes: {str(error)}'}), 500


# ====================================================================
# VER INFORME - Consulta del informe del paciente en NextRIS
# ====================================================================

@api_blueprint.route('/patient-portal/examinations/<exam_id>/report', methods=['GET'])
@jwt_required()
def get_patient_report(exam_id):
    """
    Devuelve el informe de NextRIS de un estudio.
    Solo el paciente dueño del estudio puede consultarlo.
    """
    from apps.services.patient_report_document import resolve_patient_report_view
    from apps.services.report_view_service import ReportViewUnavailable

    try:
        data = resolve_patient_report_view(exam_id, get_jwt_identity())
        response = jsonify({'success': True, 'data': data})
    except ReportViewUnavailable as error:
        payload = {'success': False, 'message': str(error), 'code': error.code}
        if error.alternatives is not None:
            payload['alternatives'] = error.alternatives
        response = jsonify(payload)
        response.status_code = error.status
    except Exception:
        current_app.logger.exception('No se pudo abrir el informe del portal')
        response = jsonify({'success': False, 'message': 'No se pudo abrir el informe'})
        response.status_code = 500
    response.headers['Cache-Control'] = 'no-store'
    return response


# ====================================================================
# COMPARTIR INFORME - Envío por email a médico de referencia externa
# ====================================================================

@api_blueprint.route('/patient-portal/examinations/<exam_id>/share', methods=['POST'])
@jwt_required()
def share_examination(exam_id):
    """
    Envía el informe de un estudio por email a un médico de referencia externo.
    Solo el paciente dueño del estudio puede compartirlo.

    Body JSON:
    {
        "email": "medico@ejemplo.com",   (required)
        "doctor_name": "Dr. García"      (optional)
    }
    """
    try:
        patient_user_id = get_jwt_identity()

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Se requiere un cuerpo JSON'}), 400

        email = data.get('email', '').strip()
        doctor_name = data.get('doctor_name', '').strip()

        if not email:
            return jsonify({'success': False, 'message': 'El email es requerido'}), 400

        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Obtener patient_data_id del usuario autenticado
        cursor.execute("""
            SELECT dp.guid
            FROM nextris.tbuser_patient up
            INNER JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
            WHERE up.guid = %s
        """, (patient_user_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Paciente no encontrado'}), 404

        patient_data_id = result[0]

        # Verificar que el examen pertenece al paciente y tiene informe
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
                nextris.available_study_for_exam(ex.guid) AS studyinstanceuid,
                COALESCE(ex.isimage, 0) as has_images
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.datapatient dp ON ex.idpatient = dp.guid
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = ex.guid
            LEFT JOIN nextris.isequipment eq ON ex.idequipment = eq.guid
            LEFT JOIN nextris.tblocation l ON l.guid = COALESCE(ex.location_id, eq.location_id)
            LEFT JOIN nextris.app_config f ON f.id = 1
                        WHERE ex.guid = %s
                            AND ex.idpatient = %s
                            AND ex.isreported = 1
                            AND EXISTS (
                                        SELECT 1
                                        FROM nextris.app_modules rel
                                        INNER JOIN nextris.ismodule mod ON mod.guid = rel.module_id
                                        WHERE TRUE
                                            AND rel.is_active = TRUE
                                            AND mod.is_active = TRUE
                                            AND mod.code = 'patient_portal'
                                )
        """
        cursor.execute(query, (exam_id, patient_data_id))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Estudio no encontrado o sin informe disponible'}), 404

        patient_name = result[1]
        study_type = result[2]
        accession_number = result[3]

        smtp_server = result[4] or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = result[5] or int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = result[6] or os.environ.get('SMTP_USER')
        smtp_password = result[7] or os.environ.get('SMTP_PASSWORD')
        smtp_from = result[8] or smtp_user or os.environ.get('SMTP_FROM')
        smtp_from_name = result[9] or os.environ.get('SMTP_FROM_NAME', 'NextRIS')
        use_tls = result[10] if result[10] is not None else True
        study_uid = result[11]
        has_images = bool(result[12])

        from apps.services.report_view_service import ReportViewUnavailable, resolve_report_view, report_view_text
        try:
            external_text = report_view_text(resolve_report_view(exam_id)['report'])
        except ReportViewUnavailable as error:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': str(error), 'code': error.code}), error.status

        if not smtp_user or not smtp_password:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Configuración SMTP incompleta'}), 500

        # Construir email
        recipient_label = f"Dr./Dra. {doctor_name}" if doctor_name else "Médico/a"

        msg = MIMEMultipart()
        msg['From'] = f"{smtp_from_name} <{smtp_from}>"
        msg['To'] = email
        msg['Subject'] = f'Informe Médico compartido por {patient_name} - {study_type}'

        viewer_link = ""
        if has_images and study_uid:
            viewer_url_cfg = current_app.config.get('DICOM_VIEWER_URL', 'http://localhost:3000/viewer')
            parsed = urlparse(viewer_url_cfg)
            viewer_base = f"{parsed.scheme}://{parsed.netloc}"
            viewer_link = f"\n\nPara visualizar las imágenes médicas acceda al siguiente enlace:\n{viewer_base}/viewer?StudyInstanceUIDs={study_uid}\n"

        body = f"""
Estimado/a {recipient_label},

El/la paciente {patient_name} le comparte el informe médico correspondiente al siguiente estudio:

  Estudio: {study_type}
  Número de acceso: {accession_number}
{viewer_link}
{external_text}

Este es un mensaje automático generado desde el portal de pacientes NextRIS.

Saludos cordiales,
{smtp_from_name}
        """

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, email, msg.as_string())
        server.quit()

        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Informe compartido correctamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al compartir: {str(e)}'}), 500
