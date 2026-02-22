"""
DICOM API Routes
Endpoints para carga y vinculación de estudios DICOM
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import psycopg2
import pydicom
import requests as http_requests
from datetime import datetime
from werkzeug.utils import secure_filename
from apps.api import api_blueprint
from apps.home.services import DatabaseService, ConfigService

# TEST: Ruta sin autenticación para pruebas
@api_blueprint.route('/test-no-auth', methods=['GET'])
def test_no_auth():
    """Ruta de prueba sin autenticación"""
    return jsonify({'success': True, 'message': 'Ruta sin autenticación funciona!'})

# TEST: Ruta CON autenticación para pruebas
@api_blueprint.route('/test-with-auth', methods=['GET'])
@jwt_required()
def test_with_auth():
    """Ruta de prueba CON autenticación JWT"""
    current_user = get_jwt_identity()
    return jsonify({'success': True, 'message': 'Auth funciona!', 'user_id': current_user})

# Obtener configuración de BD
config = ConfigService.get_db_config()

# Configuración DICOM / PACS (STOW-RS vía HTTP)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../uploads_dicom')
ALLOWED_EXTENSIONS = {'dcm', 'dicom', 'dic'}
PACS_STOW_URL = 'http://localhost:8080/dcm4chee-arc/aets/DCM4CHEE/rs/studies'
KEYCLOAK_TOKEN_URL = 'http://localhost:8090/auth/realms/dcm4che/protocol/openid-connect/token'
KEYCLOAK_CLIENT_ID = 'dcm4chee-arc-rs'
KEYCLOAK_CLIENT_SECRET = 'changeit'

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_dicom_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_dicom(filepath):
    """Valida que el archivo sea un DICOM válido y extrae información"""
    try:
        ds = pydicom.dcmread(filepath)
        info = {
            'patient_name': str(getattr(ds, 'PatientName', 'Unknown')),
            'patient_id': str(getattr(ds, 'PatientID', 'Unknown')),
            'study_date': str(getattr(ds, 'StudyDate', 'Unknown')),
            'study_time': str(getattr(ds, 'StudyTime', '')),
            'study_description': str(getattr(ds, 'StudyDescription', 'Unknown')),
            'modality': str(getattr(ds, 'Modality', 'Unknown')),
            'study_instance_uid': str(getattr(ds, 'StudyInstanceUID', 'Unknown')),
            'series_instance_uid': str(getattr(ds, 'SeriesInstanceUID', 'Unknown')),
            'sop_instance_uid': str(getattr(ds, 'SOPInstanceUID', 'Unknown')),
            'accession_number': str(getattr(ds, 'AccessionNumber', 'Unknown')),
        }
        return True, info
    except Exception as e:
        print(f"[ERROR] Error validando DICOM: {str(e)}")
        return False, str(e)


def get_pacs_token():
    """Obtiene token de acceso para PACS via Keycloak service account"""
    resp = http_requests.post(
        KEYCLOAK_TOKEN_URL,
        data={
            'grant_type': 'client_credentials',
            'client_id': KEYCLOAK_CLIENT_ID,
            'client_secret': KEYCLOAK_CLIENT_SECRET,
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()['access_token']


def send_to_pacs(filepath):
    """Envía un archivo DICOM al PACS usando STOW-RS (HTTP)"""
    try:
        print(f"[INFO] Enviando archivo al PACS via STOW-RS: {filepath}")

        token = get_pacs_token()

        with open(filepath, 'rb') as f:
            dicom_data = f.read()

        boundary = 'DICOMboundary'
        body = (
            f'--{boundary}\r\nContent-Type: application/dicom\r\n\r\n'
        ).encode() + dicom_data + f'\r\n--{boundary}--\r\n'.encode()

        resp = http_requests.post(
            PACS_STOW_URL,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': f'multipart/related; type="application/dicom"; boundary={boundary}',
            },
            data=body,
            timeout=60
        )

        if resp.status_code in (200, 409):
            print(f"[SUCCESS] Archivo enviado al PACS: {filepath}")
            return True, "Enviado al PACS exitosamente"
        else:
            error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            print(f"[ERROR] Error enviando al PACS: {error_msg}")
            return False, f"Error al enviar al PACS: HTTP {resp.status_code}"

    except Exception as e:
        print(f"[ERROR] Error en send_to_pacs: {str(e)}")
        return False, str(e)


@api_blueprint.route('/manual/upload', methods=['POST'])
def manual_upload():
    """
    Endpoint para subir archivos DICOM
    Recibe archivos, los valida y envía al PACS
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No se encontró ningún archivo'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No se seleccionó ningún archivo'
            }), 400
        
        if not allowed_dicom_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'Tipo de archivo no permitido. Extensiones válidas: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Validar location_id obligatorio
        location_id = request.form.get('location_id')
        if not location_id or location_id.strip() == '':
            return jsonify({
                'success': False,
                'error': 'El parámetro location_id es obligatorio'
            }), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_with_timestamp = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename_with_timestamp)
        
        file.save(filepath)
        print(f"[INFO] Archivo guardado: {filepath}")
        
        is_valid, dicom_info = validate_dicom(filepath)
        
        if not is_valid:
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': f'El archivo no es un DICOM válido: {dicom_info}'
            }), 400
        
        file_size = os.path.getsize(filepath)
        pacs_success, pacs_message = send_to_pacs(filepath)
        
        # Registrar en base de datos
        upload_guid = None
        try:
            # Sin autenticación - usuario por defecto
            user_guid = None
            username = 'Manual Upload'
            
            conn = psycopg2.connect(**config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO nextris.tbmanual_uploads (
                    filename, filepath, file_size,
                    patient_name, patient_id, study_date, study_time,
                    study_description, modality, study_instance_uid,
                    series_instance_uid, sop_instance_uid, accession_number,
                    uploaded_by_user_guid, uploaded_by_username,
                    pacs_status, pacs_message, pacs_sent_date,
                    location_id,
                    islinked
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s,
                    0
                ) RETURNING guid
            """, (
                filename_with_timestamp, filepath, file_size,
                dicom_info.get('patient_name'), dicom_info.get('patient_id'),
                dicom_info.get('study_date'), dicom_info.get('study_time', ''),
                dicom_info.get('study_description'), dicom_info.get('modality'),
                dicom_info.get('study_instance_uid'),
                dicom_info.get('series_instance_uid'), dicom_info.get('sop_instance_uid'),
                dicom_info.get('accession_number'),
                user_guid, username,
                'success' if pacs_success else 'error', pacs_message,
                datetime.now() if pacs_success else None,
                location_id
            ))
            
            upload_guid = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"[DB] Registro creado en tbmanual_uploads: {upload_guid}")
            
        except Exception as db_error:
            print(f"[ERROR] Error registrando en BD: {str(db_error)}")
        
        print(f"[UPLOAD] Usuario: {username} | Archivo: {filename_with_timestamp}")
        print(f"[DICOM INFO] Patient: {dicom_info['patient_name']} | ID: {dicom_info['patient_id']}")
        print(f"[PACS] Status: {'SUCCESS' if pacs_success else 'ERROR'} | {pacs_message}")
        
        response = {
            'success': True,
            'message': 'Archivo DICOM procesado exitosamente',
            'data': {
                'guid': str(upload_guid) if upload_guid else None,
                'filename': filename_with_timestamp,
                'original_filename': file.filename,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'upload_time': datetime.now().isoformat(),
                'dicom_info': dicom_info,
                'pacs_status': 'success' if pacs_success else 'error',
                'pacs_message': pacs_message,
                'uploaded_by': username
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"[ERROR] Error en upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error al procesar el archivo: {str(e)}'
        }), 500


@api_blueprint.route('/manual/unlinked-studies', methods=['GET'])
def manual_unlinked_studies():
    """
    Lista todos los estudios DICOM cargados manualmente que NO están vinculados a ninguna orden
    Acepta location_id como parámetro opcional para filtrar por ubicación
    """
    try:
        location_id = request.args.get('location_id', '')
        
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # Agrupar por study_instance_uid para mostrar un estudio por fila
        query = """
            SELECT
                MIN(guid) as guid,
                patient_name,
                patient_id,
                study_date,
                study_time,
                study_description,
                STRING_AGG(DISTINCT modality, ',') as modalities,
                study_instance_uid,
                accession_number,
                MAX(upload_date) as upload_date,
                MIN(pacs_status) as pacs_status,
                SUM(file_size) as total_size,
                location_id,
                COUNT(*) as instance_count
            FROM nextris.tbmanual_uploads
            WHERE islinked = 0
        """

        params = []
        if location_id:
            query += " AND location_id = %s"
            params.append(location_id)

        query += """
            GROUP BY patient_name, patient_id, study_date, study_time,
                     study_description, study_instance_uid, accession_number, location_id
            ORDER BY MAX(upload_date) DESC
        """

        cursor.execute(query, params)

        rows = cursor.fetchall()

        studies = []
        for row in rows:
            studies.append({
                'guid': str(row[0]),
                'patient_name': row[1],
                'patient_id': row[2],
                'study_date': row[3],
                'study_time': row[4],
                'study_description': row[5],
                'modality': row[6],
                'study_instance_uid': row[7],
                'accession_number': row[8],
                'upload_date': row[9].isoformat() if row[9] else None,
                'pacs_status': row[10],
                'file_size_mb': round(row[11] / (1024 * 1024), 2) if row[11] else 0,
                'location_id': str(row[12]) if row[12] else None,
                'instance_count': row[13],
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': studies,
                'total': len(studies)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error obteniendo estudios no vinculados: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_blueprint.route('/dicom/search-examinations', methods=['GET'])
@jwt_required()
def dicom_search_examinations():
    """
    Busca exámenes existentes para vincular con estudios DICOM
    Filtra por isimage = 0 (sin imagen asociada)
    Requiere location_id como parámetro obligatorio
    """
    try:
        # location_id opcional - puede buscar con location_id específico, NULL o todos
        location_id = request.args.get('location_id', '')

        patient_name = request.args.get('patient_name', '')
        patient_id = request.args.get('patient_id', '')
        accession = request.args.get('accession', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        query = """
            SELECT
                e.guid,
                e.localacc,
                p.name as patient_name,
                p.nationalcode as patient_id,
                e.createdon,
                st.description as study_type,
                COALESCE(e.isimage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON e.idpatient = p.guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
            WHERE (e.isimage IS NULL OR e.isimage = 0)
        """

        params = []

        # Filtrar por location_id si se proporciona
        if location_id and location_id.strip():
            query += " AND e.location_id = %s"
            params.append(location_id)
        
        if patient_name:
            query += " AND LOWER(p.name) LIKE LOWER(%s)"
            params.append(f'%{patient_name}%')
        
        if patient_id:
            query += " AND p.nationalcode LIKE %s"
            params.append(f'%{patient_id}%')
        
        if accession:
            query += " AND e.localacc LIKE %s"
            params.append(f'%{accession}%')
        
        if date_from:
            query += " AND e.createdon >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND e.createdon <= %s"
            params.append(date_to)
        
        query += " ORDER BY e.createdon DESC LIMIT 100"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        examinations = []
        for row in rows:
            examinations.append({
                'guid': str(row[0]),
                'accession': row[1] if row[1] else 'N/A',
                'patient_name': row[2] if row[2] else 'N/A',
                'patient_id': row[3] if row[3] else 'N/A',
                'date': row[4].isoformat() if row[4] else None,
                'study_type': row[5] if row[5] else 'N/A',
                'is_image': row[6]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': examinations,
                'total': len(examinations)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error buscando exámenes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_blueprint.route('/dicom/link-study', methods=['POST'])
@jwt_required()
def dicom_link_study():
    """
    Vincula un estudio DICOM cargado manualmente con una orden/examen existente
    """
    try:
        data = request.get_json()
        
        upload_guid = data.get('upload_guid')
        examination_guid = data.get('examination_guid')
        
        if not upload_guid or not examination_guid:
            return jsonify({
                'success': False,
                'error': 'Se requieren upload_guid y examination_guid'
            }), 400
        
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT guid, localacc FROM nextris.tbexamination WHERE guid = %s",
            (examination_guid,)
        )
        
        exam_result = cursor.fetchone()
        if not exam_result:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'El examen especificado no existe'
            }), 404
        
        # Obtener el study_instance_uid del registro seleccionado
        cursor.execute(
            "SELECT study_instance_uid, patient_name FROM nextris.tbmanual_uploads WHERE guid = %s",
            (upload_guid,)
        )
        upload_row = cursor.fetchone()
        if not upload_row:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No se encontró el estudio cargado'
            }), 404

        study_instance_uid, patient_name = upload_row

        # Marcar TODAS las instancias del mismo estudio como vinculadas
        cursor.execute("""
            UPDATE nextris.tbmanual_uploads
            SET
                islinked = 1,
                linked_examination_guid = %s,
                linked_date = CURRENT_TIMESTAMP
            WHERE study_instance_uid = %s AND islinked = 0
            RETURNING guid, filename, patient_name, study_instance_uid
        """, (examination_guid, study_instance_uid))

        results = cursor.fetchall()
        result = results[0] if results else None

        if not result:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No se encontró el estudio cargado'
            }), 404
        
        # Actualizar tbexamination con el UID real del DICOM y marcar con imagen
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET isimage = 1,
                studyinstanceuid = %s
            WHERE guid = %s
        """, (study_instance_uid, examination_guid,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[LINK] Estudio {result[1]} vinculado a examen {examination_guid}")
        
        return jsonify({
            'success': True,
            'message': 'Estudio vinculado exitosamente',
            'data': {
                'upload_guid': str(result[0]),
                'filename': result[1],
                'patient_name': result[2],
                'study_instance_uid': result[3],
                'linked_to': examination_guid
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error vinculando estudio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
