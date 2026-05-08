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
from apps.api.facility_plan_usage import ensure_plan_management_schema, increment_usage_counter, check_limit_before_action

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


def _normalize_dicom_value(value):
    """Normaliza identificadores DICOM para validación/agrupación."""
    normalized = (str(value or '')).strip()
    if normalized.lower() in {'', 'unknown', 'n/a', 'none', 'null'}:
        return ''
    return normalized


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

        # Validar límite mensual de recepción por facility antes de guardar/transferir.
        try:
            conn_limit = psycopg2.connect(**config)
            ensure_plan_management_schema(conn_limit)
            cursor_limit = conn_limit.cursor()
            cursor_limit.execute(
                """
                SELECT facility_id
                FROM nextris.tblocation
                WHERE guid = %s
                LIMIT 1
                """,
                (location_id,),
            )
            facility_row = cursor_limit.fetchone()
            facility_id_for_limit = facility_row[0] if facility_row else None

            if facility_id_for_limit:
                is_allowed, limit_payload = check_limit_before_action(conn_limit, facility_id_for_limit, 'receive')
                if not is_allowed:
                    cursor_limit.close()
                    conn_limit.close()
                    return jsonify({
                        'success': False,
                        'error': limit_payload.get('message', 'Límite mensual de carga DICOM alcanzado'),
                        'error_code': limit_payload.get('reason', 'RECEIVE_LIMIT_REACHED'),
                        'data': limit_payload,
                    }), 409

            cursor_limit.close()
            conn_limit.close()
        except Exception as limit_error:
            print(f"[WARN] No se pudo validar límite de carga DICOM: {str(limit_error)}")
        
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
        auto_link_data = {
            'matched': False,
            'linked': False,
            'examination_guid': None,
            'reason': None,
        }
        try:
            # Sin autenticación - usuario por defecto
            user_guid = None
            username = 'Manual Upload'
            facility_id = None
            
            conn = psycopg2.connect(**config)
            ensure_plan_management_schema(conn)
            cursor = conn.cursor()

            # Resolver facility para contabilizar uso mensual por plan.
            cursor.execute(
                """
                SELECT facility_id
                FROM nextris.tblocation
                WHERE guid = %s
                LIMIT 1
                """,
                (location_id,),
            )
            facility_row = cursor.fetchone()
            facility_id = facility_row[0] if facility_row else None
            
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

            # Commit inmediato del registro base; garantiza que siempre queda guardado
            # independientemente del resultado del auto-link.
            conn.commit()
            print(f"[DB] Registro creado en tbmanual_uploads: {upload_guid}")

            # Contabilizar carga DICOM por ESTUDIO (no por instancia/archivo).
            if facility_id:
                study_uid_key = _normalize_dicom_value(dicom_info.get('study_instance_uid'))
                accession_key = _normalize_dicom_value(dicom_info.get('accession_number'))

                should_increment_received = False

                if study_uid_key:
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM nextris.tbmanual_uploads mu
                        JOIN nextris.tblocation l ON l.guid = mu.location_id
                        WHERE l.facility_id = %s
                          AND date_trunc('month', mu.created_at) = date_trunc('month', NOW())
                          AND UPPER(TRIM(COALESCE(mu.study_instance_uid, ''))) = UPPER(TRIM(%s))
                        """,
                        (facility_id, study_uid_key),
                    )
                    same_study_count = int(cursor.fetchone()[0] or 0)
                    should_increment_received = same_study_count == 1
                elif accession_key:
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM nextris.tbmanual_uploads mu
                        JOIN nextris.tblocation l ON l.guid = mu.location_id
                        WHERE l.facility_id = %s
                          AND date_trunc('month', mu.created_at) = date_trunc('month', NOW())
                          AND UPPER(TRIM(COALESCE(mu.accession_number, ''))) = UPPER(TRIM(%s))
                        """,
                        (facility_id, accession_key),
                    )
                    same_accession_count = int(cursor.fetchone()[0] or 0)
                    should_increment_received = same_accession_count == 1

                if should_increment_received:
                    increment_usage_counter(conn, facility_id, 'received', 1)
                    conn.commit()

            # Auto-vinculación: accession + (patientid o nationalcode)
            # Bloque aislado: un fallo aquí no revierte el registro de upload.
            try:
                dicom_accession = (dicom_info.get('accession_number') or '').strip()
                dicom_patient_id = (dicom_info.get('patient_id') or '').strip()
                invalid_values = {'', 'unknown', 'n/a', 'none', 'null'}

                can_match = (
                    dicom_accession.lower() not in invalid_values
                    and dicom_patient_id.lower() not in invalid_values
                )

                if can_match:
                    cursor.execute(
                        """
                        SELECT e.guid, e.studyinstanceuid
                        FROM nextris.tbexamination e
                        INNER JOIN nextris.datapatient dp ON dp.guid = e.idpatient
                        WHERE COALESCE(e.localacc, '') <> ''
                          AND UPPER(TRIM(e.localacc)) = UPPER(TRIM(%s))
                          AND (
                                UPPER(TRIM(COALESCE(dp.patientid, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(dp.nationalcode, ''))) = UPPER(TRIM(%s))
                          )
                          AND (e.isimage IS NULL OR e.isimage = 0)
                          AND (%s = '' OR COALESCE(e.location_id::text, '') = %s)
                        ORDER BY e.createdon DESC
                        LIMIT 1
                        """,
                        (dicom_accession, dicom_patient_id, dicom_patient_id, location_id, location_id)
                    )
                    exam_match = cursor.fetchone()

                    if exam_match:
                        examination_guid = str(exam_match[0])
                        auto_link_data['matched'] = True
                        auto_link_data['examination_guid'] = examination_guid

                        # Marca todas las instancias del estudio cargado como vinculadas.
                        cursor.execute(
                            """
                            UPDATE nextris.tbmanual_uploads
                            SET islinked = 1,
                                linked_examination_guid = %s,
                                linked_date = CURRENT_TIMESTAMP
                            WHERE study_instance_uid = %s
                              AND COALESCE(islinked, 0) = 0
                            """,
                            (examination_guid, dicom_info.get('study_instance_uid'))
                        )

                        # Actualiza la orden RIS para reflejar imagen vinculada.
                        cursor.execute(
                            """
                            UPDATE nextris.tbexamination
                            SET isimage = 1,
                                studyinstanceuid = %s
                            WHERE guid = %s
                            """,
                            (dicom_info.get('study_instance_uid'), examination_guid)
                        )

                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT 1
                                FROM information_schema.tables
                                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
                            )
                        """)
                        has_pacs_link_table = cursor.fetchone()[0]

                        if has_pacs_link_table:
                            cursor.execute(
                                """
                                SELECT pk, study_iuid
                                FROM public.study
                                WHERE study_iuid = %s
                                ORDER BY updated_time DESC NULLS LAST, pk DESC
                                LIMIT 1
                                """,
                                (dicom_info.get('study_instance_uid'),)
                            )
                            pacs_row = cursor.fetchone()
                            if pacs_row:
                                pacs_study_pk = pacs_row[0]
                                pacs_study_iuid = pacs_row[1]

                                cursor.execute(
                                    """
                                    SELECT studyinstanceuid
                                    FROM nextris.tbexamination
                                    WHERE guid = %s
                                    """,
                                    (examination_guid,)
                                )
                                order_row = cursor.fetchone()
                                order_study_uuid = order_row[0] if order_row else None

                                cursor.execute(
                                    """
                                    UPDATE nextris.tbpacs_study_link
                                    SET link_status = 'unlinked',
                                        unlinked_at = CURRENT_TIMESTAMP,
                                        unlinked_reason = 'Relink automático desde /api/manual/upload',
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE link_status = 'linked'
                                      AND (order_guid = %s OR pacs_study_pk = %s OR pacs_study_iuid = %s)
                                    """,
                                    (examination_guid, pacs_study_pk, pacs_study_iuid)
                                )

                                cursor.execute(
                                    """
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
                                        'linked', 'auto', CURRENT_TIMESTAMP,
                                        NULL, 'Auto Upload',
                                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                                    )
                                    """,
                                    (
                                        pacs_study_pk,
                                        pacs_study_iuid,
                                        examination_guid,
                                        order_study_uuid,
                                        upload_guid,
                                    )
                                )

                        auto_link_data['linked'] = True
                    else:
                        auto_link_data['reason'] = (
                            'No se encontró una orden sin imagen con accession y patientid/nationalcode coincidentes'
                        )
                else:
                    auto_link_data['reason'] = 'DICOM sin accession number o patient id válidos para auto-vinculación'

                conn.commit()
                if auto_link_data['linked']:
                    print(
                        f"[AUTO-LINK] Upload {upload_guid} vinculado automáticamente a examen {auto_link_data['examination_guid']}"
                    )

            except Exception as link_error:
                print(f"[ERROR] Auto-link falló (registro de upload preservado): {str(link_error)}")
                try:
                    conn.rollback()
                except Exception:
                    pass

            cursor.close()
            conn.close()

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
                'uploaded_by': username,
                'auto_link': auto_link_data
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
    Lista estudios DICOM cargados manualmente.
    Por defecto devuelve solo NO vinculados, pero permite incluir vinculados y excluir PACS.
    Acepta location_id como parámetro opcional para filtrar por ubicación
    """
    try:
        location_id = request.args.get('location_id', '')
        all_locations = str(location_id).strip().lower() == 'all'
        include_linked_param = str(request.args.get('include_linked', '0')).strip().lower()
        include_linked = include_linked_param in ('1', 'true', 'yes')
        include_pacs_param = str(request.args.get('include_pacs', '1')).strip().lower()
        include_pacs = include_pacs_param not in ('0', 'false', 'no')
        
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # Agrupar por study_instance_uid para mostrar un estudio por fila
        query = """
            SELECT
                MIN(mu.guid) as guid,
                mu.patient_name,
                mu.patient_id,
                mu.study_date,
                mu.study_time,
                mu.study_description,
                STRING_AGG(DISTINCT mu.modality, ',') as modalities,
                mu.study_instance_uid,
                mu.accession_number,
                MAX(mu.upload_date) as upload_date,
                MIN(mu.pacs_status) as pacs_status,
                SUM(mu.file_size) as total_size,
                mu.location_id,
                COUNT(*) as instance_count,
                MAX(CASE WHEN COALESCE(mu.islinked, 0) = 1 THEN 1 ELSE 0 END) as islinked,
                MAX(mu.linked_date) as linked_date,
                MAX(mu.linked_examination_guid::text) as linked_examination_guid,
                MAX(e.localacc) as linked_order_accession
            FROM nextris.tbmanual_uploads mu
            LEFT JOIN nextris.tbexamination e ON e.guid::text = mu.linked_examination_guid::text
            WHERE 1 = 1
        """

        params = []
        if not include_linked:
            query += " AND COALESCE(mu.islinked, 0) = 0"

        if location_id and not all_locations:
            query += " AND mu.location_id = %s"
            params.append(location_id)

        query += """
            GROUP BY mu.patient_name, mu.patient_id, mu.study_date, mu.study_time,
                     mu.study_description, mu.study_instance_uid, mu.accession_number, mu.location_id
            ORDER BY MAX(mu.upload_date) DESC
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
                'islinked': bool(row[14]),
                'linked_date': row[15].isoformat() if row[15] else None,
                'linked_examination_guid': str(row[16]) if row[16] else None,
                'linked_order_accession': row[17] if row[17] else None,
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
        if include_pacs and has_pacs_link_table:
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


# ==================== IMAGES / STUDIES BY LOCATION ====================

@api_blueprint.route('/dicom/studies-by-location/<location_id>', methods=['GET'])
@jwt_required()
def get_studies_by_location(location_id):
    """
    Obtiene estudios DICOM (de public.study) por location_id
    
    GET /api/dicom/studies-by-location/<location_id>?page=1&per_page=10&search=<term>&sort_column=<col>&sort_direction=asc
    
    Response:
    {
        "success": true,
        "data": {
            "data": [
                {
                    "pk": 25,
                    "study_iuid": "1.2.840.113619.2.323...",
                    "study_desc": "CHEST",
                    "study_datetime": "2024-03-20T10:30:00",
                    "location_id": "c7168384-3c3d-4cb9-ad9f-41bbb5083be6",
                    "patient_name": "DOE, JOHN",
                    "accession_no": "ACC001",
                    "modality": "CX",
                    "sending_aet": "FF001",
                    "num_series": 3,
                    "num_instances": 45
                }
            ],
            "total": 150
        }
    }
    """
    try:
        db_config = ConfigService.get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Parámetros de query
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            per_page = max(1, min(100, int(request.args.get('per_page', 10))))
        except (TypeError, ValueError):
            per_page = 10

        search_term = request.args.get('search', '').strip()
        filter_patient_name = request.args.get('filter_patient_name', '').strip()
        filter_study_desc = request.args.get('filter_study_desc', '').strip()
        filter_accession_no = request.args.get('filter_accession_no', '').strip()
        filter_modality = request.args.get('filter_modality', '').strip()
        date_range = request.args.get('date_range', 'all').strip()
        date_field = request.args.get('date_field', 'arrival').strip()
        sort_column = request.args.get('sort_column', 'study_datetime')
        sort_direction = request.args.get('sort_direction', 'desc').lower()
        
        # Validar sort_direction
        if sort_direction not in ('asc', 'desc'):
            sort_direction = 'desc'
        
        # Permitir columnas ordenables (mapeadas a SQL seguro)
        sort_column_map = {
            'study_datetime': "s.study_date {dir} NULLS LAST, s.study_time {dir} NULLS LAST, s.created_time {dir} NULLS LAST",
            'updated_time': "s.updated_time {dir} NULLS LAST",
            'study_date': "s.study_date {dir} NULLS LAST",
            'study_time': "s.study_time {dir} NULLS LAST",
            'study_desc': "s.study_desc {dir} NULLS LAST",
            'patient_name': "COALESCE(pn.alphabetic_name, 'Unknown') {dir}",
            'accession_no': "s.accession_no {dir} NULLS LAST",
            'modality': "modality {dir} NULLS LAST",
            'is_linked': "is_linked {dir} NULLS LAST",
            'num_series': "num_series {dir} NULLS LAST"
        }
        if sort_column not in sort_column_map:
            sort_column = 'study_datetime'
        
        offset = (page - 1) * per_page
        
        # Query base
        base_query = """
            SELECT 
                s.pk,
                s.study_iuid,
                s.study_desc,
                s.study_date,
                s.study_time,
                s.created_time,
                s.updated_time,
                s.location_id as location_id,
                COALESCE(pn.alphabetic_name, 'Unknown') as patient_name,
                s.accession_no,
                                (
                                        EXISTS (
                                                SELECT 1
                                                FROM nextris.tbpacs_study_link lnk
                                                WHERE lnk.link_status = 'linked'
                                                    AND (lnk.pacs_study_pk = s.pk OR lnk.pacs_study_iuid = s.study_iuid)
                                        )
                                        OR EXISTS (
                                                SELECT 1
                                                FROM nextris.tbexamination exam
                                                WHERE exam.studyinstanceuid = s.study_iuid
                                                    AND COALESCE(exam.isimage, 0) = 1
                                        )
                                ) as is_linked,
                (SELECT MAX(sr.modality) FROM public.series sr WHERE sr.study_fk = s.pk) as modality,
                (SELECT MAX(sr.sending_aet) FROM public.series sr WHERE sr.study_fk = s.pk) as sending_aet,
                (SELECT COUNT(*) FROM public.series sr WHERE sr.study_fk = s.pk) as num_series,
                (SELECT COUNT(*) FROM public.instance i 
                 JOIN public.series sr ON sr.pk = i.series_fk 
                 WHERE sr.study_fk = s.pk) as num_instances
            FROM public.study s
            LEFT JOIN public.patient p ON p.pk = s.patient_fk
            LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
            WHERE s.location_id = %s
        """
        
        params = [location_id]

        date_interval_map = {
            '1d': '1 day',
            '3d': '3 days',
            '7d': '7 days',
            '14d': '14 days',
            '1m': '1 month',
            '2m': '2 months',
            '3m': '3 months',
            '1y': '1 year',
        }

        date_field_map = {
            'arrival': 'COALESCE(s.updated_time, s.created_time)',
            'study': "CASE WHEN s.study_date ~ '^\\d{8}$' THEN TO_DATE(s.study_date, 'YYYYMMDD')::timestamp END",
        }
        
        # Aplicar búsqueda
        if search_term:
            base_query += """
                AND (
                    COALESCE(pn.alphabetic_name, 'Unknown') ILIKE %s
                    OR s.accession_no ILIKE %s
                    OR s.study_iuid ILIKE %s
                    OR s.study_desc ILIKE %s
                )
            """
            search_param = f"%{search_term}%"
            params.extend([search_param, search_param, search_param, search_param])

        if filter_patient_name:
            base_query += """
                AND COALESCE(pn.alphabetic_name, 'Unknown') ILIKE %s
            """
            params.append(f"%{filter_patient_name}%")

        if filter_study_desc:
            base_query += """
                AND COALESCE(s.study_desc, '') ILIKE %s
            """
            params.append(f"%{filter_study_desc}%")

        if filter_accession_no:
            base_query += """
                AND COALESCE(s.accession_no, '') ILIKE %s
            """
            params.append(f"%{filter_accession_no}%")

        if filter_modality:
            base_query += """
                AND EXISTS (
                    SELECT 1
                    FROM public.series sr_mod
                    WHERE sr_mod.study_fk = s.pk
                      AND COALESCE(sr_mod.modality, '') ILIKE %s
                )
            """
            params.append(f"%{filter_modality}%")

        if date_range in date_interval_map:
            date_expression = date_field_map.get(date_field, date_field_map['arrival'])
            base_query += f"""
                AND {date_expression} >= NOW() - INTERVAL %s
            """
            params.append(date_interval_map[date_range])
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({base_query}) as count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Agregar ordenamiento y paginación
        order_clause = sort_column_map[sort_column].format(dir=sort_direction.upper())
        query = base_query + f" ORDER BY {order_clause} LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        studies = []
        for row in rows:
            study_date = row[3]
            study_time = row[4]
            created_time = row[5]
            updated_time = row[6]

            if study_date and study_time:
                date_str = str(study_date)
                time_str = str(study_time)
                if len(date_str) == 8 and date_str.isdigit():
                    formatted_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    formatted_date = date_str

                time_digits = ''.join(ch for ch in time_str if ch.isdigit())
                hh = time_digits[0:2] if len(time_digits) >= 2 else '00'
                mm = time_digits[2:4] if len(time_digits) >= 4 else '00'
                ss = time_digits[4:6] if len(time_digits) >= 6 else '00'
                study_datetime = f"{formatted_date}T{hh}:{mm}:{ss}"
            elif study_date:
                date_str = str(study_date)
                if len(date_str) == 8 and date_str.isdigit():
                    study_datetime = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    study_datetime = date_str
            else:
                study_datetime = created_time.isoformat() if created_time else None

            studies.append({
                'pk': row[0],
                'study_iuid': row[1],
                'study_desc': row[2],
                'study_datetime': study_datetime,
                'updated_time': updated_time.isoformat() if updated_time else None,
                'study_date': str(study_date) if study_date else None,
                'study_time': str(study_time) if study_time else None,
                'location_id': row[7] if row[7] else None,
                'patient_name': row[8],
                'accession_no': row[9],
                'is_linked': bool(row[10]),
                'modality': row[11],
                'sending_aet': row[12],
                'num_series': row[13] or 0,
                'num_instances': row[14] or 0
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': studies,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Error obteniendo estudios por location: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
