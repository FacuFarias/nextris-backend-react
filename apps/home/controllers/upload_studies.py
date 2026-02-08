"""
Controlador para carga de estudios DICOM
Maneja la carga de archivos DICOM y su envío al PACS
"""

from flask import jsonify, request, session
from flask_login import login_required
import os
import psycopg2
import pydicom
import subprocess
from datetime import datetime
from werkzeug.utils import secure_filename
from apps.home import blueprint
from apps.home.services import DatabaseService, ConfigService

# Obtener configuración de BD
config = ConfigService.get_db_config()

# Configuración DICOM
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../uploads_dicom')
ALLOWED_EXTENSIONS = {'dcm', 'dicom', 'dic'}
PACS_HOST = '148.230.72.8'
PACS_PORT = 11112
PACS_AET = 'DCM4CHEE'
LOCAL_AET = 'NEXTRIS_UPLOADER'

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


def send_to_pacs(filepath):
    """Envía un archivo DICOM al PACS usando storescu"""
    try:
        print(f"[INFO] Enviando archivo al PACS: {filepath}")
        
        cmd = [
            'storescu',
            '-aec', PACS_AET,      # AE Title del PACS destino
            '-aet', LOCAL_AET,      # AE Title local
            PACS_HOST,              # Host del PACS
            str(PACS_PORT),         # Puerto del PACS
            filepath                # Archivo DICOM
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"[SUCCESS] Archivo enviado exitosamente al PACS: {filepath}")
            return True, "Enviado al PACS exitosamente"
        else:
            error_msg = result.stderr or result.stdout or "Error desconocido"
            print(f"[ERROR] Error enviando al PACS: {error_msg}")
            return False, f"Error al enviar al PACS: {error_msg}"
            
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout enviando al PACS: {filepath}")
        return False, "Timeout al conectar con el PACS"
    except Exception as e:
        print(f"[ERROR] Error en send_to_pacs: {str(e)}")
        return False, str(e)


@blueprint.route('/api/dicom/upload', methods=['POST'])
@login_required
def dicom_upload():
    """
    Endpoint para subir archivos DICOM
    Recibe archivos, los valida y envía al PACS
    """
    try:
        # Verificar que hay un archivo
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No se encontró ningún archivo'
            }), 400
        
        file = request.files['file']
        
        # Verificar que el archivo tiene nombre
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No se seleccionó ningún archivo'
            }), 400
        
        # Verificar extensión
        if not allowed_dicom_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'Tipo de archivo no permitido. Extensiones válidas: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Guardar archivo de forma segura
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_with_timestamp = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename_with_timestamp)
        
        file.save(filepath)
        print(f"[INFO] Archivo guardado: {filepath}")
        
        # Validar que es un DICOM válido
        is_valid, dicom_info = validate_dicom(filepath)
        
        if not is_valid:
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': f'El archivo no es un DICOM válido: {dicom_info}'
            }), 400
        
        # Obtener tamaño del archivo
        file_size = os.path.getsize(filepath)
        
        # Enviar al PACS
        pacs_success, pacs_message = send_to_pacs(filepath)
        
        # Registrar en base de datos
        upload_guid = None
        try:
            conn = psycopg2.connect(**config)
            cursor = conn.cursor()
            
            # Obtener GUID del usuario actual
            cursor.execute(
                "SELECT guid FROM nextris.tbuser WHERE username = %s",
                (session.get('username'),)
            )
            user_result = cursor.fetchone()
            user_guid = user_result[0] if user_result else None
            
            # Insertar en tbmanual_uploads
            cursor.execute("""
                INSERT INTO nextris.tbmanual_uploads (
                    filename, filepath, file_size,
                    patient_name, patient_id, study_date, study_time,
                    study_description, modality, study_instance_uid,
                    series_instance_uid, sop_instance_uid, accession_number,
                    uploaded_by_user_guid, uploaded_by_username,
                    pacs_status, pacs_message, pacs_sent_date,
                    islinked
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
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
                user_guid, session.get('username'),
                'success' if pacs_success else 'error', pacs_message,
                datetime.now() if pacs_success else None
            ))
            
            upload_guid = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"[DB] Registro creado en tbmanual_uploads: {upload_guid}")
            
        except Exception as db_error:
            print(f"[ERROR] Error registrando en BD: {str(db_error)}")
            # No fallar el upload si falla el registro en BD
        
        # Log de la operación
        print(f"[UPLOAD] Usuario: {session.get('username')} | Archivo: {filename_with_timestamp}")
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
                'uploaded_by': session.get('username', 'Unknown')
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"[ERROR] Error en upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error al procesar el archivo: {str(e)}'
        }), 500


@blueprint.route('/api/dicom/files', methods=['GET'])
@login_required
def dicom_list_files():
    """
    Lista todos los archivos DICOM subidos
    """
    try:
        files = []
        
        # Verificar que la carpeta existe
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({
                'success': True,
                'data': {
                    'files': [],
                    'total': 0
                }
            }), 200
        
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                
                # Intentar obtener información DICOM
                dicom_info = None
                try:
                    is_valid, info = validate_dicom(filepath)
                    if is_valid:
                        dicom_info = info
                except:
                    pass
                
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'upload_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'dicom_info': dicom_info
                })
        
        # Ordenar por fecha de subida (más recientes primero)
        files.sort(key=lambda x: x['upload_time'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': {
                'files': files,
                'total': len(files)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error listando archivos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@blueprint.route('/api/dicom/delete/<filename>', methods=['DELETE'])
@login_required
def dicom_delete_file(filename):
    """
    Elimina un archivo DICOM subido
    Solo disponible para administradores
    """
    try:
        # Verificar permisos (solo Sysadmin puede eliminar)
        if session.get('user_type') != 'Sysadmin':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para eliminar archivos'
            }), 403
        
        # Sanitizar nombre de archivo
        filename = secure_filename(filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': 'Archivo no encontrado'
            }), 404
        
        # Eliminar archivo
        os.remove(filepath)
        
        print(f"[DELETE] Usuario: {session.get('username')} eliminó archivo: {filename}")
        
        return jsonify({
            'success': True,
            'message': 'Archivo eliminado exitosamente'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error eliminando archivo: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@blueprint.route('/api/dicom/scan-path', methods=['POST'])
@login_required
def dicom_scan_path():
    """
    Escanea un directorio buscando archivos DICOM
    Útil para cargar estudios desde una carpeta del servidor
    """
    try:
        data = request.get_json()
        
        if not data or 'path' not in data:
            return jsonify({
                'success': False,
                'error': 'No se proporcionó una ruta'
            }), 400
        
        scan_path = data['path']
        
        # Verificar que la ruta existe
        if not os.path.exists(scan_path):
            return jsonify({
                'success': False,
                'error': f'La ruta no existe: {scan_path}'
            }), 404
        
        # Verificar que es un directorio
        if not os.path.isdir(scan_path):
            return jsonify({
                'success': False,
                'error': f'La ruta no es un directorio: {scan_path}'
            }), 400
        
        print(f"[SCAN] Escaneando ruta: {scan_path}")
        
        # Escanear recursivamente buscando archivos DICOM
        dicom_files = []
        errors = []
        total_size = 0
        
        for root, dirs, files in os.walk(scan_path):
            for filename in files:
                # Verificar extensión
                if allowed_dicom_file(filename):
                    filepath = os.path.join(root, filename)
                    
                    try:
                        # Validar DICOM
                        is_valid, dicom_info = validate_dicom(filepath)
                        
                        if is_valid:
                            file_size = os.path.getsize(filepath)
                            total_size += file_size
                            
                            dicom_files.append({
                                'filepath': filepath,
                                'filename': filename,
                                'size': file_size,
                                'size_mb': round(file_size / (1024 * 1024), 2),
                                'dicom_info': dicom_info
                            })
                        else:
                            errors.append({
                                'file': filepath,
                                'error': dicom_info
                            })
                    except Exception as e:
                        errors.append({
                            'file': filepath,
                            'error': str(e)
                        })
        
        response = {
            'success': True,
            'message': f'Escaneo completado',
            'data': {
                'scan_path': scan_path,
                'total_files': len(dicom_files),
                'total_errors': len(errors),
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'files': dicom_files,
                'errors': errors[:10] if errors else []  # Limitar errores mostrados
            }
        }
        
        print(f"[SCAN] Completado: {len(dicom_files)} archivos DICOM encontrados")
        return jsonify(response), 200
        
    except Exception as e:
        print(f"[ERROR] Error en scan-path: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error al escanear la ruta: {str(e)}'
        }), 500


@blueprint.route('/api/dicom/batch-upload', methods=['POST'])
@login_required
def dicom_batch_upload():
    """
    Envía múltiples archivos DICOM al PACS desde una ruta escaneada
    """
    try:
        data = request.get_json()
        
        if not data or 'files' not in data:
            return jsonify({
                'success': False,
                'error': 'No se proporcionaron archivos'
            }), 400
        
        files_to_upload = data['files']
        results = {
            'success': 0,
            'errors': 0,
            'details': []
        }
        
        for file_path in files_to_upload:
            try:
                # Validar que el archivo existe
                if not os.path.exists(file_path):
                    results['errors'] += 1
                    results['details'].append({
                        'file': file_path,
                        'status': 'error',
                        'message': 'Archivo no encontrado'
                    })
                    continue
                
                # Enviar al PACS
                pacs_success, pacs_message = send_to_pacs(file_path)
                
                if pacs_success:
                    results['success'] += 1
                    results['details'].append({
                        'file': file_path,
                        'status': 'success',
                        'message': pacs_message
                    })
                else:
                    results['errors'] += 1
                    results['details'].append({
                        'file': file_path,
                        'status': 'error',
                        'message': pacs_message
                    })
                    
            except Exception as e:
                results['errors'] += 1
                results['details'].append({
                    'file': file_path,
                    'status': 'error',
                    'message': str(e)
                })
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error en batch-upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@blueprint.route('/api/dicom/unlinked-studies', methods=['GET'])
@login_required
def dicom_unlinked_studies():
    """
    Lista todos los estudios DICOM cargados manualmente que NO están vinculados a ninguna orden
    """
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # Consultar estudios no vinculados (islinked = 0)
        cursor.execute("""
            SELECT 
                guid,
                filename,
                patient_name,
                patient_id,
                study_date,
                study_time,
                study_description,
                modality,
                study_instance_uid,
                accession_number,
                upload_date,
                uploaded_by_username,
                pacs_status,
                file_size
            FROM nextris.tbmanual_uploads
            WHERE islinked = 0
            ORDER BY upload_date DESC
        """)
        
        rows = cursor.fetchall()
        
        studies = []
        for row in rows:
            studies.append({
                'guid': str(row[0]),
                'filename': row[1],
                'patient_name': row[2],
                'patient_id': row[3],
                'study_date': row[4],
                'study_time': row[5],
                'study_description': row[6],
                'modality': row[7],
                'study_instance_uid': row[8],
                'accession_number': row[9],
                'upload_date': row[10].isoformat() if row[10] else None,
                'uploaded_by': row[11],
                'pacs_status': row[12],
                'file_size_mb': round(row[13] / (1024 * 1024), 2) if row[13] else 0
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'studies': studies,
                'total': len(studies)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error obteniendo estudios no vinculados: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@blueprint.route('/api/dicom/link-study', methods=['POST'])
@login_required
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
        
        # Verificar que el examen existe
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
        
        # Actualizar el registro de manual_uploads
        cursor.execute("""
            UPDATE nextris.tbmanual_uploads
            SET 
                islinked = 1,
                linked_examination_guid = %s,
                linked_date = CURRENT_TIMESTAMP
            WHERE guid = %s
            RETURNING guid, filename, patient_name, study_instance_uid
        """, (examination_guid, upload_guid))
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No se encontró el estudio cargado'
            }), 404
        
        # Actualizar isimage = 1 en tbexamination
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET isimage = 1
            WHERE guid = %s
        """, (examination_guid,))
        
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


@blueprint.route('/api/dicom/search-examinations', methods=['GET'])
@login_required  
def dicom_search_examinations():
    """
    Busca exámenes existentes para vincular con estudios DICOM
    Filtra por isimage = 0 (sin imagen asociada)
    """
    try:
        # Parámetros de búsqueda
        patient_name = request.args.get('patient_name', '')
        patient_id = request.args.get('patient_id', '')
        accession = request.args.get('accession', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # Construir query dinámicamente - solo exámenes sin imagen (isimage = null o 0)
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
            WHERE e.isimage IS NULL OR e.isimage = 0
        """
        
        params = []
        
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
                'examinations': examinations,
                'total': len(examinations)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Error buscando exámenes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
