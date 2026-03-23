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
        all_locations = str(location_id).strip().lower() == 'all'
        
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
        if location_id and not all_locations:
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
                'source': 'manual',
                'pacs_study_pk': None,
            })

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
            )
        """)
        has_pacs_link_table = cursor.fetchone()[0]

        # Complementa el panel con estudios PACS sin vínculo activo.
        if has_pacs_link_table:
            if all_locations:
                cursor.execute("""
                    SELECT
                        s.pk,
                        s.study_iuid,
                        s.accession_no,
                        s.study_date,
                        s.study_time,
                        s.study_desc,
                        COALESCE(pn.alphabetic_name, 'PACS SIN NOMBRE') AS patient_name,
                        s.updated_time,
                        STRING_AGG(DISTINCT sr.modality, ',') AS modalities
                    FROM public.study s
                    LEFT JOIN public.patient p ON p.pk = s.patient_fk
                    LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
                    LEFT JOIN nextris.tbpacs_study_link l
                        ON l.pacs_study_pk = s.pk
                       AND l.link_status = 'linked'
                    LEFT JOIN public.series sr ON sr.study_fk = s.pk
                    WHERE l.id IS NULL
                    GROUP BY s.pk, s.study_iuid, s.accession_no, s.study_date, s.study_time,
                             s.study_desc, pn.alphabetic_name, s.updated_time
                    ORDER BY s.updated_time DESC NULLS LAST, s.pk DESC
                    LIMIT 500
                """)
            elif location_id:
                cursor.execute("""
                    SELECT
                        s.pk,
                        s.study_iuid,
                        s.accession_no,
                        s.study_date,
                        s.study_time,
                        s.study_desc,
                        COALESCE(pn.alphabetic_name, 'PACS SIN NOMBRE') AS patient_name,
                        s.updated_time,
                        STRING_AGG(DISTINCT sr.modality, ',') AS modalities
                    FROM public.study s
                    LEFT JOIN public.patient p ON p.pk = s.patient_fk
                    LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
                    LEFT JOIN nextris.tbpacs_study_link l
                        ON l.pacs_study_pk = s.pk
                       AND l.link_status = 'linked'
                    LEFT JOIN public.series sr ON sr.study_fk = s.pk
                    WHERE l.id IS NULL
                      AND s.location_id = %s
                    GROUP BY s.pk, s.study_iuid, s.accession_no, s.study_date, s.study_time,
                             s.study_desc, pn.alphabetic_name, s.updated_time
                    ORDER BY s.updated_time DESC NULLS LAST, s.pk DESC
                    LIMIT 500
                """, (location_id,))
            else:
                cursor.execute("""
                    SELECT
                        s.pk,
                        s.study_iuid,
                        s.accession_no,
                        s.study_date,
                        s.study_time,
                        s.study_desc,
                        COALESCE(pn.alphabetic_name, 'PACS SIN NOMBRE') AS patient_name,
                        s.updated_time,
                        STRING_AGG(DISTINCT sr.modality, ',') AS modalities
                    FROM public.study s
                    LEFT JOIN public.patient p ON p.pk = s.patient_fk
                    LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
                    LEFT JOIN nextris.tbpacs_study_link l
                        ON l.pacs_study_pk = s.pk
                       AND l.link_status = 'linked'
                    LEFT JOIN public.series sr ON sr.study_fk = s.pk
                    WHERE l.id IS NULL
                    GROUP BY s.pk, s.study_iuid, s.accession_no, s.study_date, s.study_time,
                             s.study_desc, pn.alphabetic_name, s.updated_time
                    ORDER BY s.updated_time DESC NULLS LAST, s.pk DESC
                    LIMIT 500
                """)

            pacs_rows = cursor.fetchall()

            for pacs_row in pacs_rows:
                pacs_pk = pacs_row[0]
                pacs_iuid = pacs_row[1]
                accession_no = pacs_row[2]
                study_date = pacs_row[3]
                study_time = pacs_row[4]
                study_desc = pacs_row[5]
                patient_name = pacs_row[6]
                updated_time = pacs_row[7]
                series_modalities = pacs_row[8] if pacs_row[8] else 'PACS'

                studies.append({
                    'guid': f'pacs:{pacs_pk}',
                    'filename': None,
                    'patient_name': patient_name,
                    'patient_id': accession_no if accession_no else 'N/A',
                    'study_date': study_date,
                    'study_time': study_time,
                    'study_description': study_desc if study_desc else 'PACS Study',
                    'modality': series_modalities,
                    'study_instance_uid': pacs_iuid,
                    'accession_number': accession_no,
                    'upload_date': updated_time.isoformat() if updated_time else None,
                    'uploaded_by': 'PACS',
                    'pacs_status': 'available',
                    'file_size_mb': 0,
                    'location_id': str(location_id) if (location_id and not all_locations) else None,
                    'instance_count': 1,
                    'source': 'pacs',
                    'pacs_study_pk': pacs_pk,
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
        all_locations = str(location_id).strip().lower() == 'all'

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
        if location_id and location_id.strip() and not all_locations:
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
        current_user = get_jwt_identity()
        
        upload_guid = data.get('upload_guid')
        pacs_study_pk = data.get('pacs_study_pk')
        request_study_instance_uid = data.get('study_instance_uid')
        examination_guid = data.get('examination_guid')
        link_source = 'manual' if upload_guid else 'reconcile'
        
        if not examination_guid:
            return jsonify({
                'success': False,
                'error': 'Se requiere examination_guid'
            }), 400

        if not upload_guid and not pacs_study_pk and not request_study_instance_uid:
            return jsonify({
                'success': False,
                'error': 'Se requiere upload_guid o pacs_study_pk o study_instance_uid'
            }), 400
        
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT guid, localacc, studyinstanceuid FROM nextris.tbexamination WHERE guid = %s",
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
        
        study_instance_uid = None
        patient_name = None
        manual_upload_guid = None

        if upload_guid:
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
            manual_upload_guid = upload_guid
        elif pacs_study_pk:
            cursor.execute(
                "SELECT pk, study_iuid FROM public.study WHERE pk = %s",
                (pacs_study_pk,)
            )
            pacs_row = cursor.fetchone()
            if not pacs_row:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'No se encontró el estudio PACS especificado'
                }), 404
            pacs_study_pk = pacs_row[0]
            study_instance_uid = pacs_row[1]
            patient_name = 'PACS Study'
        else:
            cursor.execute(
                """
                SELECT pk, study_iuid
                FROM public.study
                WHERE study_iuid = %s
                ORDER BY updated_time DESC NULLS LAST, pk DESC
                LIMIT 1
                """,
                (request_study_instance_uid,)
            )
            pacs_row = cursor.fetchone()
            if not pacs_row:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'No se encontró el estudio PACS para study_instance_uid'
                }), 404
            pacs_study_pk = pacs_row[0]
            study_instance_uid = pacs_row[1]
            patient_name = 'PACS Study'

        order_study_uuid = exam_result[2]

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
            )
        """)
        has_pacs_link_table = cursor.fetchone()[0]

        resolved_pacs_study_pk = pacs_study_pk
        pacs_study_iuid = study_instance_uid
        if has_pacs_link_table and not resolved_pacs_study_pk:
            cursor.execute("""
                SELECT pk, study_iuid
                FROM public.study
                WHERE study_iuid = %s
                ORDER BY updated_time DESC NULLS LAST, pk DESC
                LIMIT 1
            """, (study_instance_uid,))
            pacs_study_row = cursor.fetchone()
            if not pacs_study_row:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'El estudio no existe en PACS (public.study) para el StudyInstanceUID indicado'
                }), 404
            resolved_pacs_study_pk, pacs_study_iuid = pacs_study_row

        linked_by_user_guid = str(current_user) if current_user else None
        linked_by_username = None
        if linked_by_user_guid:
            cursor.execute(
                "SELECT username FROM nextris.tbuser WHERE guid = %s",
                (linked_by_user_guid,)
            )
            user_row = cursor.fetchone()
            linked_by_username = user_row[0] if user_row else None

        result = None
        if upload_guid:
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

        if has_pacs_link_table:
            # Si existe un vínculo activo previo del estudio o la orden, se cierra para dejar historial consistente.
            cursor.execute("""
                UPDATE nextris.tbpacs_study_link
                SET link_status = 'unlinked',
                    unlinked_at = CURRENT_TIMESTAMP,
                    unlinked_reason = 'Relink manual desde /api/dicom/link-study',
                    updated_at = CURRENT_TIMESTAMP
                WHERE link_status = 'linked'
                  AND (order_guid = %s OR pacs_study_pk = %s OR pacs_study_iuid = %s)
            """, (examination_guid, resolved_pacs_study_pk, pacs_study_iuid))

            cursor.execute("""
                INSERT INTO nextris.tbpacs_study_link (
                    pacs_study_pk,
                    pacs_study_iuid,
                    order_guid,
                    order_study_uuid,
                    manual_upload_guid,
                    link_status,
                    source,
                    linked_at,
                    linked_by_user_guid,
                    linked_by_username,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    'linked', %s, CURRENT_TIMESTAMP,
                    %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                resolved_pacs_study_pk,
                pacs_study_iuid,
                examination_guid,
                order_study_uuid,
                manual_upload_guid,
                link_source,
                linked_by_user_guid,
                linked_by_username
            ))
        
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
        
        log_name = result[1] if result else f"PACS:{resolved_pacs_study_pk or 'unknown'}"
        print(f"[LINK] Estudio {log_name} vinculado a examen {examination_guid}")
        
        return jsonify({
            'success': True,
            'message': 'Estudio vinculado exitosamente',
            'data': {
                'upload_guid': str(result[0]) if result else None,
                'filename': result[1] if result else None,
                'patient_name': result[2] if result else patient_name,
                'study_instance_uid': result[3] if result else study_instance_uid,
                'pacs_study_pk': resolved_pacs_study_pk,
                'linked_to': examination_guid,
                'source': link_source
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error vinculando estudio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_blueprint.route('/dicom/linked-studies', methods=['GET'])
@jwt_required()
def dicom_linked_studies():
    """
    Lista vínculos activos entre estudios PACS/DICOM y órdenes RIS.
    Soporta filtro opcional por location_id y el valor especial all.
    """
    try:
        location_id = request.args.get('location_id', '')
        all_locations = str(location_id).strip().lower() == 'all'

        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
            )
        """)
        has_pacs_link_table = cursor.fetchone()[0]

        links = []

        if has_pacs_link_table:
            query = """
                SELECT
                    l.id,
                    l.order_guid,
                    l.order_study_uuid,
                    l.pacs_study_pk,
                    l.pacs_study_iuid,
                    l.manual_upload_guid,
                    l.source,
                    l.linked_at,
                    l.linked_by_username,
                    e.localacc,
                    e.createdon,
                    COALESCE(e.location_id::text, '') as exam_location_id,
                    p.name as patient_name,
                    p.nationalcode as patient_id,
                    COALESCE(st.description, 'N/A') as study_type,
                    s.accession_no,
                    s.study_desc,
                    COALESCE(pn.alphabetic_name, p.name, 'N/A') as pacs_patient_name
                FROM nextris.tbpacs_study_link l
                LEFT JOIN nextris.tbexamination e ON e.guid = l.order_guid
                LEFT JOIN nextris.datapatient p ON p.guid = e.idpatient
                LEFT JOIN nextris.isstudytype st ON st.guid = e.studytype_id
                LEFT JOIN public.study s ON s.pk = l.pacs_study_pk
                LEFT JOIN public.patient pp ON pp.pk = s.patient_fk
                LEFT JOIN public.person_name pn ON pn.pk = pp.pat_name_fk
                WHERE l.link_status = 'linked'
            """

            params = []
            if location_id and not all_locations:
                query += " AND e.location_id = %s"
                params.append(location_id)

            query += " ORDER BY l.linked_at DESC LIMIT 500"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                links.append({
                    'link_id': row[0],
                    'examination_guid': str(row[1]) if row[1] else None,
                    'order_study_uuid': str(row[2]) if row[2] else None,
                    'pacs_study_pk': row[3],
                    'study_instance_uid': row[4],
                    'manual_upload_guid': str(row[5]) if row[5] else None,
                    'source': row[6],
                    'linked_at': row[7].isoformat() if row[7] else None,
                    'linked_by': row[8],
                    'order_accession': row[9] if row[9] else 'N/A',
                    'order_date': row[10].isoformat() if row[10] else None,
                    'location_id': row[11] if row[11] else None,
                    'patient_name': row[12] if row[12] else 'N/A',
                    'patient_id': row[13] if row[13] else 'N/A',
                    'study_type': row[14] if row[14] else 'N/A',
                    'pacs_accession': row[15] if row[15] else None,
                    'pacs_study_description': row[16] if row[16] else None,
                    'pacs_patient_name': row[17] if row[17] else 'N/A',
                })
        else:
            query = """
                SELECT
                    MIN(mu.guid) as manual_upload_guid,
                    mu.study_instance_uid,
                    mu.linked_examination_guid,
                    MAX(mu.linked_date) as linked_at,
                    e.localacc,
                    e.createdon,
                    COALESCE(e.location_id::text, '') as exam_location_id,
                    p.name as patient_name,
                    p.nationalcode as patient_id,
                    COALESCE(st.description, 'N/A') as study_type
                FROM nextris.tbmanual_uploads mu
                JOIN nextris.tbexamination e ON e.guid = mu.linked_examination_guid
                LEFT JOIN nextris.datapatient p ON p.guid = e.idpatient
                LEFT JOIN nextris.isstudytype st ON st.guid = e.studytype_id
                WHERE mu.islinked = 1
            """

            params = []
            if location_id and not all_locations:
                query += " AND e.location_id = %s"
                params.append(location_id)

            query += """
                GROUP BY mu.study_instance_uid, mu.linked_examination_guid,
                         e.localacc, e.createdon, e.location_id,
                         p.name, p.nationalcode, st.description
                ORDER BY MAX(mu.linked_date) DESC
                LIMIT 500
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                links.append({
                    'link_id': None,
                    'examination_guid': str(row[2]) if row[2] else None,
                    'order_study_uuid': None,
                    'pacs_study_pk': None,
                    'study_instance_uid': row[1],
                    'manual_upload_guid': str(row[0]) if row[0] else None,
                    'source': 'manual',
                    'linked_at': row[3].isoformat() if row[3] else None,
                    'linked_by': None,
                    'order_accession': row[4] if row[4] else 'N/A',
                    'order_date': row[5].isoformat() if row[5] else None,
                    'location_id': row[6] if row[6] else None,
                    'patient_name': row[7] if row[7] else 'N/A',
                    'patient_id': row[8] if row[8] else 'N/A',
                    'study_type': row[9] if row[9] else 'N/A',
                    'pacs_accession': None,
                    'pacs_study_description': None,
                    'pacs_patient_name': row[7] if row[7] else 'N/A',
                })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'data': links,
                'total': len(links)
            }
        }), 200

    except Exception as e:
        print(f"[ERROR] Error obteniendo estudios vinculados: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_blueprint.route('/dicom/unlink-study', methods=['POST'])
@jwt_required()
def dicom_unlink_study():
    """
    Desvincula un estudio de una orden.
    Acepta link_id (tbpacs_study_link) o combinación de examination_guid + pacs_study_pk/study_instance_uid.
    """
    try:
        data = request.get_json() or {}
        link_id = data.get('link_id')
        examination_guid = data.get('examination_guid')
        pacs_study_pk = data.get('pacs_study_pk')
        study_instance_uid = data.get('study_instance_uid')
        reason = data.get('reason', 'Desvinculación manual desde UI')

        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
            )
        """)
        has_pacs_link_table = cursor.fetchone()[0]

        unlinked_order_guid = None
        unlinked_study_iuid = None

        if has_pacs_link_table:
            if link_id is not None:
                cursor.execute("""
                    UPDATE nextris.tbpacs_study_link
                    SET link_status = 'unlinked',
                        unlinked_at = CURRENT_TIMESTAMP,
                        unlinked_reason = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND link_status = 'linked'
                    RETURNING order_guid, pacs_study_iuid
                """, (reason, link_id))
            else:
                if not examination_guid:
                    cursor.close()
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Se requiere link_id o examination_guid'
                    }), 400

                query = """
                    UPDATE nextris.tbpacs_study_link
                    SET link_status = 'unlinked',
                        unlinked_at = CURRENT_TIMESTAMP,
                        unlinked_reason = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE link_status = 'linked'
                      AND order_guid = %s
                """
                params = [reason, examination_guid]

                if pacs_study_pk is not None:
                    query += " AND pacs_study_pk = %s"
                    params.append(pacs_study_pk)
                elif study_instance_uid:
                    query += " AND pacs_study_iuid = %s"
                    params.append(study_instance_uid)

                query += " RETURNING order_guid, pacs_study_iuid"
                cursor.execute(query, tuple(params))

            updated_rows = cursor.fetchall()
            if not updated_rows:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'No se encontró un vínculo activo para desvincular'
                }), 404

            unlinked_order_guid = updated_rows[0][0]
            unlinked_study_iuid = updated_rows[0][1]
        else:
            if not examination_guid:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Se requiere examination_guid cuando no existe tbpacs_study_link'
                }), 400

            manual_query = """
                UPDATE nextris.tbmanual_uploads
                SET islinked = 0,
                    linked_examination_guid = NULL,
                    linked_date = NULL
                WHERE islinked = 1
                  AND linked_examination_guid = %s
            """
            manual_params = [examination_guid]

            if study_instance_uid:
                manual_query += " AND study_instance_uid = %s"
                manual_params.append(study_instance_uid)

            manual_query += " RETURNING linked_examination_guid, study_instance_uid"
            cursor.execute(manual_query, tuple(manual_params))
            updated_rows = cursor.fetchall()

            if not updated_rows:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'No se encontró un vínculo manual activo para desvincular'
                }), 404

            unlinked_order_guid = updated_rows[0][0]
            unlinked_study_iuid = updated_rows[0][1]

        if unlinked_order_guid and unlinked_study_iuid:
            # Limpia legacy manual_uploads para todos los archivos de ese estudio/orden.
            cursor.execute("""
                UPDATE nextris.tbmanual_uploads
                SET islinked = 0,
                    linked_examination_guid = NULL,
                    linked_date = NULL
                WHERE linked_examination_guid = %s
                  AND study_instance_uid = %s
                  AND islinked = 1
            """, (unlinked_order_guid, unlinked_study_iuid))

        active_link_count = 0
        if has_pacs_link_table and unlinked_order_guid:
            cursor.execute("""
                SELECT COUNT(*)
                FROM nextris.tbpacs_study_link
                WHERE order_guid = %s
                  AND link_status = 'linked'
            """, (unlinked_order_guid,))
            active_link_count = cursor.fetchone()[0]

        active_manual_count = 0
        if unlinked_order_guid:
            cursor.execute("""
                SELECT COUNT(*)
                FROM nextris.tbmanual_uploads
                WHERE linked_examination_guid = %s
                  AND islinked = 1
            """, (unlinked_order_guid,))
            active_manual_count = cursor.fetchone()[0]

        if unlinked_order_guid and active_link_count == 0 and active_manual_count == 0:
            cursor.execute("""
                UPDATE nextris.tbexamination
                SET isimage = 0
                WHERE guid = %s
            """, (unlinked_order_guid,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Estudio desvinculado exitosamente',
            'data': {
                'examination_guid': str(unlinked_order_guid) if unlinked_order_guid else None,
                'study_instance_uid': unlinked_study_iuid,
                'remaining_active_links': active_link_count,
                'remaining_active_manual_links': active_manual_count
            }
        }), 200

    except Exception as e:
        print(f"[ERROR] Error desvinculando estudio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
