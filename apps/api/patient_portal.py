# -*- encoding: utf-8 -*-
"""
API del Portal de Pacientes - Endpoints para pacientes autenticados
Permite a los pacientes gestionar su perfil y acceder a su información
"""

from flask import jsonify, request, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from datetime import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from urllib.parse import urlparse
from apps.api import api_blueprint


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


# ====================================================================
# MIS DATOS - PERFIL DEL PACIENTE
# ====================================================================

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
                dp.healthcard
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
            'health_card': result[12]
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
        "email": "nuevo.email@example.com"
    }
    
    NOTA: Campos como nombre, apellido, DNI, fecha de nacimiento, sexo, 
    dirección, ciudad, estado y código postal NO se pueden modificar 
    desde el portal del paciente por seguridad.
    Deben ser actualizados por personal administrativo.
    
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
        
        # Campos permitidos para actualizar desde el portal
        # Solo phone y email están disponibles en la tabla datapatient
        allowed_fields = {
            'phone': 'phone',
            'email': 'email'
        }
        
        # Construir query de actualización solo con campos permitidos
        updates = []
        params = []
        
        for json_field, db_field in allowed_fields.items():
            if json_field in data:
                updates.append(f"{db_field} = %s")
                params.append(data[json_field])
        
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
            "UPDATE nextris.tbuser_patient SET password = %s WHERE guid = %s",
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
            SELECT dp.guid 
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
                    WHEN ex.studyinstanceuid IS NOT NULL AND ex.studyinstanceuid != '' THEN true
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
                ex.studyinstanceuid,
                ps.study_date,
                ps.study_time
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.ismodality m ON st.modality_id = m.guid
            LEFT JOIN public.study ps ON ex.studyinstanceuid = ps.study_iuid
            LEFT JOIN LATERAL (
                SELECT psr.modality
                FROM public.series psr
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
# VER INFORME - Descarga del PDF del informe del paciente
# ====================================================================

@api_blueprint.route('/patient-portal/examinations/<exam_id>/report', methods=['GET'])
@jwt_required()
def get_patient_report(exam_id):
    """
    Devuelve el PDF del informe de un estudio.
    Solo el paciente dueño del estudio puede descargarlo.
    """
    try:
        patient_user_id = get_jwt_identity()

        config = get_db_config()
        if not config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Verificar que el paciente existe
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

        # Obtener el PDF verificando que el examen pertenece al paciente
        cursor.execute("""
            SELECT r.pdfpath, ex.localacc
            FROM nextris.tbexamination ex
            INNER JOIN nextris.tbreport r ON r.idexamination = ex.guid
            WHERE ex.guid = %s
                AND ex.idpatient = %s
                AND ex.isreported = 1
        """, (exam_id, patient_data_id))
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if not result:
            return jsonify({'success': False, 'message': 'Informe no encontrado'}), 404

        pdf_path = result[0]
        accession_number = result[1]

        # Resolver a ruta absoluta (la DB guarda rutas relativas al raíz del proyecto)
        abs_pdf_path = os.path.abspath(pdf_path)

        if not pdf_path or not os.path.exists(abs_pdf_path):
            return jsonify({'success': False, 'message': 'Archivo PDF no encontrado'}), 404

        return send_file(
            abs_pdf_path,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'informe_{accession_number}.pdf'
        )

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


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
                            AND ex.idpatient = %s
                            AND ex.isreported = 1
                            AND EXISTS (
                                        SELECT 1
                                        FROM nextris.rel_facility_module rel
                                        INNER JOIN nextris.ismodule mod ON mod.guid = rel.module_id
                                        WHERE rel.facility_id = l.facility_id
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

        pdf_path = result[0]
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

        if not pdf_path or not os.path.exists(pdf_path):
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'PDF del informe no encontrado'}), 404

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
            viewer_url_cfg = current_app.config.get('DICOM_VIEWER_URL', 'https://clinicacp.ddns.net:3000/viewer')
            parsed = urlparse(viewer_url_cfg)
            viewer_base = f"{parsed.scheme}://{parsed.netloc}"
            viewer_link = f"\n\nPara visualizar las imágenes médicas acceda al siguiente enlace:\n{viewer_base}/viewer?StudyInstanceUIDs={study_uid}\n"

        body = f"""
Estimado/a {recipient_label},

El/la paciente {patient_name} le comparte el informe médico correspondiente al siguiente estudio:

  Estudio: {study_type}
  Número de acceso: {accession_number}
{viewer_link}
El informe se encuentra adjunto en formato PDF.

Este es un mensaje automático generado desde el portal de pacientes NextRIS.

Saludos cordiales,
{smtp_from_name}
        """

        msg.attach(MIMEText(body, 'plain'))

        with open(pdf_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=informe_{accession_number}.pdf')
        msg.attach(part)

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
