"""
Controller para gestión de reportes y plantillas predefinidas
Migrado masivamente desde routes.py para reducir el archivo principal
"""

from flask import Blueprint, request, jsonify, send_file, session, redirect
from flask_login import current_user
import os
import uuid
import shutil
import html
import re
from io import BytesIO
import psycopg2
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from apps.home.services.database_service import DatabaseService
from apps.home.services.config_service import ConfigService
from apps.services.report_fields import (
    canonical_fields_from_row,
    fields_are_complete,
    legacy_aliases,
    normalize_report_payload,
    remove_indicative_brackets,
)

# Importar funciones para firmas digitales
from apps.home.controllers.config_controller import get_user_signature_data

# Crear blueprint para reportes
report_bp = Blueprint('report', __name__, url_prefix='/api')

# Obtener configuración de BD
config = ConfigService.get_db_config()

def wrap_text_advanced(text, max_width, font_name, font_size, c):
    """
    Envuelve texto de manera inteligente respetando los márgenes
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    if not text:
        return ['']
    
    lines = []
    paragraphs = text.split('\n')  # Respetar saltos de línea existentes
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append('')
            continue
            
        words = paragraph.split()
        current_line = ''
        
        for word in words:
            # Verificar si la palabra sola es muy larga
            if stringWidth(word, font_name, font_size) > max_width:
                # Partir palabras muy largas
                if current_line:
                    lines.append(current_line)
                    current_line = ''
                
                # Dividir palabra larga en chunks
                chunk_size = 1
                while chunk_size < len(word):
                    chunk = word[:chunk_size]
                    if stringWidth(chunk + '-', font_name, font_size) > max_width:
                        if chunk_size > 1:
                            lines.append(word[:chunk_size-1] + '-')
                            word = word[chunk_size-1:]
                            chunk_size = 1
                        else:
                            chunk_size += 1
                    else:
                        chunk_size += 1
                
                if word:
                    current_line = word
            else:
                # Palabra normal
                test_line = current_line + (' ' if current_line else '') + word
                
                if stringWidth(test_line, font_name, font_size) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
        
        if current_line:
            lines.append(current_line)
    
    return lines

def draw_text_section(c, title, content, y_pos, max_width):
    """
    Dibuja una sección de texto con título y contenido, manejando páginas automáticamente
    """
    from reportlab.lib.pagesizes import letter
    width, height = letter
    margin_bottom = 80  # Margen inferior mínimo
    
    # Verificar espacio para el título
    if y_pos < margin_bottom + 40:
        c.showPage()
        y_pos = height - 50
    
    # Dibujar título
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, title)
    y_pos -= 25
    
    # Procesar contenido
    if content and content.strip():
        c.setFont("Helvetica", 11)
        content_lines = wrap_text_advanced(content, max_width - 50, "Helvetica", 11, c)
        
        for line in content_lines:
            # Verificar espacio para la línea
            if y_pos < margin_bottom:
                c.showPage()
                y_pos = height - 50
            
            c.drawString(50, y_pos, line)
            y_pos -= 16
    else:
        # Contenido vacío o solo espacios
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(50, y_pos, "[No especificado]")
        y_pos -= 16
    
    return y_pos - 10  # Espacio adicional entre secciones


def _resolve_pdf_asset_path(path_candidate, app_root):
    """Resuelve rutas de assets usadas en PDF para no depender del cwd del proceso."""
    if not path_candidate:
        return None

    raw_path = str(path_candidate).strip()
    if not raw_path:
        return None

    normalized = raw_path.replace('\\', '/')

    # Si ya es absoluta y existe, usarla tal cual.
    if os.path.isabs(normalized) and os.path.exists(normalized):
        return normalized

    candidates = [
        os.path.join(app_root, normalized.lstrip('/')),
    ]

    if normalized.startswith('/static/'):
        candidates.append(os.path.join(app_root, 'apps', normalized.lstrip('/')))

    if normalized.startswith('apps/'):
        candidates.append(os.path.join(app_root, normalized))

    for candidate in candidates:
        candidate_abs = os.path.abspath(candidate)
        if os.path.exists(candidate_abs):
            return candidate_abs

    return None


def _normalize_report_text_for_pdf(content):
    """Convierte HTML/RichText a texto plano legible para el PDF."""
    if content is None:
        return ''

    text = str(content)

    # Mantener estructura básica de bloques antes de limpiar etiquetas.
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p\s*>', '\n', text)
    text = re.sub(r'(?i)</div\s*>', '\n', text)
    text = re.sub(r'(?i)</li\s*>', '\n', text)

    # Eliminar etiquetas HTML y decodificar entidades.
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)

    # Los corchetes se usan en el editor para marcar variables/campos
    # pendientes, pero nunca deben llegar al informe PDF final.
    text = text.replace('[', '').replace(']', '')

    # Normalizar espacios sin romper saltos de línea.
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    return '\n'.join(lines).strip()


def _draw_share_qr_page(c, share_url, width, height):
    """Dibuja un QR y enlaces PDF clickeables para el acceso a imágenes."""
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from reportlab.pdfbase.pdfmetrics import stringWidth

    qr_size = 180
    qr_x = (width - qr_size) / 2
    qr_y = height - 300

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 80, "Acceso a las imágenes del estudio")

    qr_widget = qr.QrCodeWidget(share_url)
    qr_widget.barWidth = qr_size
    qr_widget.barHeight = qr_size
    qr_drawing = Drawing(qr_size, qr_size)
    qr_drawing.add(qr_widget)
    renderPDF.draw(qr_drawing, c, qr_x, qr_y)
    # El QR también se puede abrir con un clic desde un lector PDF.
    c.linkURL(share_url, (qr_x, qr_y, qr_x + qr_size, qr_y + qr_size), thickness=0)

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, height - 325, "Escanee este código para ver las imágenes")
    c.setFont("Helvetica", 8)
    url_width = stringWidth(share_url, "Helvetica", 8)
    url_x = max(50, (width - url_width) / 2)
    c.drawString(url_x, height - 350, share_url)
    c.linkURL(share_url, (url_x, height - 352, url_x + url_width, height - 340), thickness=0)

def generate_report_pdf_with_signature(report_id, pdf_filename=None):
    from apps.services.report_pdf_service import render_report_pdf
    return render_report_pdf(report_id, filename=pdf_filename).content

@report_bp.route('/plantilla/<guid>', methods=['GET'])
def api_plantilla(guid):
    """Obtiene los textos de una plantilla predefinida"""
    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        cur.execute("SELECT report FROM nextris.isreporttemplate WHERE guid=%s", (guid,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result:
            return jsonify({'report': result[0]})
        else:
            return jsonify({'report': ''})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@report_bp.route('/isstudytype/<tipo_id>/default_predef_id', methods=['GET'])
def get_default_predef_id(tipo_id):
    """Obtiene el ID de plantilla predefinida por defecto para un tipo de estudio"""
    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        cur.execute("SELECT default_predef_id FROM nextris.isstudytype WHERE guid=%s", (tipo_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result:
            return jsonify({'default_predef_id': result[0]})
        else:
            return jsonify({'default_predef_id': None})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@report_bp.route('/get_predefinido/<guid>', methods=['GET'])
def get_predefinido(guid):
    """Obtiene datos de un predefinido específico desde tbinfpredef"""
    try:
        print(f"[INFO] Solicitando predefinido con guid: {guid}")
        
        query = """
            SELECT guid, tittle, findings, impression, technique, conclusion, studytype_id,
                   study_reason, content
            FROM nextris.tbinfpredef 
            WHERE guid=%s
        """
        
        result = DatabaseService.execute_query(query, (guid,))
        
        if result and len(result) > 0:
            row = result[0]
            response = {
                'guid': row[0],
                'tittle': row[1] or '',  # Frontend espera 'tittle'
                **legacy_aliases(canonical_fields_from_row(
                    row[7], row[8], row[5],
                    legacy_findings=row[2], legacy_impressions=row[3],
                    legacy_technique=row[4], legacy_conclusion=row[5],
                )),
                'study_reason': canonical_fields_from_row(
                    row[7], row[8], row[5], legacy_findings=row[2],
                    legacy_impressions=row[3], legacy_technique=row[4],
                    legacy_conclusion=row[5]
                )['study_reason'],
                'content': canonical_fields_from_row(
                    row[7], row[8], row[5], legacy_findings=row[2],
                    legacy_impressions=row[3], legacy_technique=row[4],
                    legacy_conclusion=row[5]
                )['content'],
                'conclusion': canonical_fields_from_row(
                    row[7], row[8], row[5], legacy_findings=row[2],
                    legacy_impressions=row[3], legacy_technique=row[4],
                    legacy_conclusion=row[5]
                )['conclusion'],
                'studytype_id': row[6],
                # También mantener los nombres en español por compatibilidad
                'titulo': row[1] or '',
                'hallazgos': row[2] or '',
                'conclusiones': row[3] or '',
                'recomendaciones': row[4] or '',
                'conclusions': row[5] or ''
            }
            print(f"[SUCCESS] Predefinido encontrado: {row[1]}")
            return jsonify(response)
        else:
            print(f"[WARNING] No se encontró predefinido con guid: {guid}")
            return jsonify({})
            
    except Exception as e:
        print(f"[ERROR] Error en get_predefinido: {str(e)}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/guardar_predefinido', methods=['POST'])
def guardar_predefinido():
    """Guarda una nueva plantilla predefinida"""
    try:
        data = request.get_json()
        print(f"[INFO] Guardando nuevo predefinido - datos recibidos: {data}")
        
        # Extraer datos del request (coincidiendo con el frontend)
        title = data.get('title', '')
        studytype_id = data.get('studytype_id')
        normalized = normalize_report_payload({
            **data,
            'findings': data.get('findings', data.get('hallazgostext', '')),
            'technique': data.get('technique', data.get('tecnicastext', '')),
            'impression': data.get('impression', data.get('impresionestext', '')),
            'conclusion': data.get('conclusion', data.get('conclusionestext', '')),
        })
        study_reason = normalized.get('study_reason', '')
        content = normalized.get('content', '')
        conclusion = normalized.get('conclusion', '')
        isdefault = data.get('isdefault', 0)
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Insertar en la base de datos
        query = """
            INSERT INTO nextris.tbinfpredef
            (guid, tittle, study_reason, content, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        result = DatabaseService.execute_query(
            query, 
            (new_guid, title, study_reason, content, conclusion, studytype_id),
            commit=True
        )
        
        # Si es default, actualizar el studytype
        if isdefault == 1:
            update_query = """
                UPDATE nextris.isstudytype 
                SET default_predef_id = %s 
                WHERE guid = %s
            """
            DatabaseService.execute_query(update_query, (new_guid, studytype_id), commit=True)
            print(f"[INFO] Predefinido marcado como default para studytype: {studytype_id}")
        
        print(f"[SUCCESS] Predefinido guardado exitosamente - GUID: {new_guid}")
        return jsonify({'success': True, 'guid': new_guid})
        
    except Exception as e:
        print(f"[ERROR] Error en guardar_predefinido: {str(e)}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/get_inf_predefinidos', methods=['GET'])
def get_inf_predefinidos():
    """Obtiene lista de todos los predefinidos"""
    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        query = """
            SELECT ip.guid, ip.tittle, ist.description
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            ORDER BY ip.guid ASC
        """
        cur.execute(query)
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        predefinidos = []
        for row in results:
            predefinidos.append([row[0], row[1], row[2]])
        
        return jsonify(predefinidos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@report_bp.route('/get_inf_predef', methods=['POST'])
def get_inf_predef():
    """Obtiene información específica de predefinidos con filtros"""
    try:
        data = request.get_json()
        study_type_id = data.get('study_type_id')
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        if study_type_id:
            query = """
                SELECT guid, titulo, hallazgos, conclusiones, recomendaciones
                FROM nextris.isreporttemplate 
                WHERE studytype_id = %s
                ORDER BY titulo
            """
            cur.execute(query, (study_type_id,))
        else:
            query = """
                SELECT guid, titulo, hallazgos, conclusiones, recomendaciones
                FROM nextris.isreporttemplate 
                ORDER BY titulo
            """
            cur.execute(query)
            
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        predefinidos = []
        for row in results:
            predefinidos.append({
                'guid': row[0],
                'titulo': row[1] or '',
                'hallazgos': row[2] or '',
                'conclusiones': row[3] or '',
                'recomendaciones': row[4] or ''
            })
        
        return jsonify(predefinidos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@report_bp.route('/verpdf/<report_id>', methods=['GET'])
def verpdf(report_id):
    """Endpoint para ver/descargar el PDF de un reporte"""
    try:
        print(f"[INFO] Redirigiendo apertura de PDF a endpoint unificado para report_id: {report_id}")
        return redirect(f"/api/pdfs/by-exam/{report_id}", code=302)

    except Exception as e:
        print(f"[ERROR] Error al obtener PDF: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ====================================================================
# FUNCIONES DE GESTIÓN DE REPORTES MÉDICOS
# ====================================================================

@report_bp.route('/quitar_definitivo', methods=['POST'])
def quitar_definitivo():
    """Quita un reporte definitivo (cambia IsReported a 0)"""
    try:
        print("[INFO] Iniciando quitar_definitivo")
        
        # Obtener datos del request
        reporteid = request.get_json()
        if not reporteid:
            print("[ERROR] No se recibieron datos JSON")
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        exam_id = reporteid.get('id')
        if not exam_id:
            print("[ERROR] Falta el ID del examen en el request")
            return jsonify({'error': 'Falta el ID del examen'}), 400
        
        print(f"[INFO] Procesando exam_id: {exam_id}")
        
        # Ejecutar query usando DatabaseService
        query = """
            UPDATE nextris.tbexamination
            SET IsReported = 0, reportdate = NULL
            WHERE Guid = %s
        """
        print(f"[INFO] Ejecutando query: {query} con ID: {exam_id}")
        
        result = DatabaseService.execute_query(query, (exam_id,), fetch_all=False, commit=True)
        
        # Actualizar estado si existe la función
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
            print("[INFO] Estado actualizado exitosamente")
        except Exception as update_error:
            print(f"[WARNING] No se pudo actualizar el estado: {str(update_error)}")
        
        print("[INFO] Reporte removido exitosamente")
        return jsonify({'success': True, 'message': 'Reporte removido exitosamente'})
        
    except Exception as e:
        print(f"[ERROR] Error en quitar_definitivo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/guardar_reporte', methods=['POST'])
def guardar_reporte():
    """Guarda los datos de un reporte médico"""
    try:
        print("[INFO] Iniciando guardar_reporte")
        
        # Obtener datos del request
        data = request.get_json()
        if not data:
            print("[ERROR] No se recibieron datos JSON")
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        print(f"[INFO] Datos recibidos: {data}")
        
        exam_id = data['id']
        compat_payload = dict(data)
        compat_payload.setdefault('study_reason', data.get('val_study_reason', ''))
        compat_payload.setdefault('findings', data.get('val_findings', ''))
        compat_payload.setdefault('technique', data.get('val_tecnicas', ''))
        compat_payload.setdefault('impression', data.get('val_impresiones', ''))
        compat_payload.setdefault('conclusion', data.get('val_conclusions', data.get('val_conclusiones', '')))
        normalized = normalize_report_payload(compat_payload)
        if not normalized.get('study_reason'):
            fallback = DatabaseService.execute_query(
                "SELECT clinicalquestion, history FROM nextris.tbexamination WHERE guid=%s",
                (exam_id,), fetch_one=True,
            )
            if fallback:
                normalized['study_reason'] = fallback[0] or fallback[1] or ''
        if not fields_are_complete(normalized):
            return jsonify({'error': 'Razón del estudio, Contenido y Conclusión son requeridos'}), 400
        
        print(f"[INFO] Guardando reporte para examen ID: {exam_id}")
        
        # Query seguro usando parámetros para evitar SQL injection
        query = """
            UPDATE nextris.tbReport 
            SET study_reason=%s, content=%s, conclusion=%s, wassaved=true
            WHERE IdExamination=%s
        """
        
        print(f"[INFO] Ejecutando query de actualización para exam_id: {exam_id}")
        
        result = DatabaseService.execute_query(
            query, 
            (normalized['study_reason'], normalized['content'], normalized['conclusion'], exam_id),
            fetch_all=False, 
            commit=True
        )
        
        print("[INFO] Reporte guardado exitosamente")
        return jsonify({'success': True, 'message': 'Reporte guardado exitosamente'})
        
    except Exception as e:
        print(f"[ERROR] Error en guardar_reporte: {str(e)}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/firmar_reporte', methods=['POST'])
def firmar_reporte():
    """Firma un reporte legacy sin generar ni almacenar un PDF."""
    try:
        payload = request.get_json(silent=True) or {}
        exam_id = payload.get('id')
        if not exam_id:
            return jsonify({'error': 'Falta el ID del examen'}), 400

        reporter_physician_id = (
            payload.get('reporter_physician_id')
            or session.get('user_guid')
            or session.get('user_id')
        )
        if not reporter_physician_id:
            return jsonify({'error': 'No se pudo determinar el médico firmante'}), 400

        connection = psycopg2.connect(**ConfigService.get_db_config())
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT r.study_reason, r.content, r.conclusion,
                   r.findings, r.techniques, r.impressions, r.conclusions,
                   e.clinicalquestion, e.history
            FROM nextris.tbreport r
            JOIN nextris.tbexamination e ON e.guid = r.idexamination
            WHERE r.idexamination=%s
            ORDER BY r.date DESC NULLS LAST LIMIT 1
            """, (exam_id,)
        )
        existing = cursor.fetchone()
        if existing:
            fields = canonical_fields_from_row(
                existing[0], existing[1], existing[2],
                legacy_findings=existing[3], legacy_technique=existing[4],
                legacy_impressions=existing[5], legacy_conclusion=existing[6],
                reason_fallback=existing[7] or existing[8],
            )
            fields = remove_indicative_brackets(fields)
            if not fields_are_complete(fields):
                cursor.close(); connection.close()
                return jsonify({'error': 'Razón del estudio, Contenido y Conclusión son requeridos', 'code': 'REPORT_FIELDS_REQUIRED'}), 400
        else:
            cursor.close(); connection.close()
            return jsonify({'error': 'Reporte no encontrado'}), 404
        cursor.execute(
            """
            UPDATE nextris.tbreport
            SET iduser = %s, wassaved = TRUE, date = NOW(),
                study_reason = %s, content = %s, conclusion = %s
            WHERE idexamination = %s
            """,
            (reporter_physician_id, fields['study_reason'], fields['content'], fields['conclusion'], exam_id),
        )
        cursor.execute(
            """
            UPDATE nextris.tbexamination
            SET isreported = 1, assignto = %s, reportdate = CURRENT_TIMESTAMP
            WHERE guid = %s
            """,
            (reporter_physician_id, exam_id),
        )
        if cursor.rowcount == 0:
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({'error': 'Examen no encontrado'}), 404

        connection.commit()
        cursor.close()
        connection.close()
        from apps.api.integration.hl7_oru import send_report_hl7
        send_report_hl7(exam_id)
        return jsonify({
            'success': True,
            'message': 'Reporte firmado exitosamente',
        }), 200
    except Exception as error:
        return jsonify({'error': str(error)}), 500


@report_bp.route('/editar_predefinido', methods=['POST'])
def editar_predefinido():
    """Edita una plantilla predefinida existente"""
    try:
        data = request.get_json()
        print(f"[INFO] Editando predefinido - datos recibidos: {data}")
        
        # Extraer datos del request
        guid = data.get('guid')
        if not guid:
            return jsonify({'error': 'GUID es requerido para editar'}), 400
        
        title = data.get('title', '')
        studytype_id = data.get('studytype_id')
        normalized = normalize_report_payload({
            **data,
            'findings': data.get('findings', data.get('hallazgostext', '')),
            'technique': data.get('technique', data.get('tecnicastext', '')),
            'impression': data.get('impression', data.get('impresionestext', '')),
            'conclusion': data.get('conclusion', data.get('conclusionestext', '')),
        })
        
        # Actualizar en la base de datos
        query = """
            UPDATE nextris.tbinfpredef 
            SET tittle=%s, study_reason=%s, content=%s, conclusion=%s, studytype_id=%s
            WHERE guid=%s
        """
        
        result = DatabaseService.execute_query(
            query, 
            (title, normalized.get('study_reason', ''), normalized.get('content', ''),
             normalized.get('conclusion', ''), studytype_id, guid),
            commit=True
        )
        
        print(f"[SUCCESS] Predefinido editado exitosamente - GUID: {guid}")
        return jsonify({'success': True, 'guid': guid})
        
    except Exception as e:
        print(f"[ERROR] Error en editar_predefinido: {str(e)}")
        return jsonify({'error': str(e)}), 500


def send_mail(report_id):
    """Envía un reporte por email al paciente"""
    try:
        from apps.home.controllers.admin_controller import updatestatus
        
        # Obtener email del parámetro de consulta
        TO_EMAIL = request.args.get('mail')
        
        print(f"[DEBUG] Enviando email para reporte: {report_id}, email: {TO_EMAIL}")
        
        # Configuración del servidor SMTP (esto debería estar en configuración)
        SMTP_SERVER = 'smtp.gmail.com'
        SMTP_PORT = 587
        SMTP_USER = 'facufarias93@gmail.com'
        SMTP_PASSWORD = 'pjiwxoqulgvdctgc'
        FROM_EMAIL = 'facufarias93@gmail.com'
        
        # Obtener información del examen
        exam_query = "SELECT StudyInstanceUID, IsImage, IdPatient, LocalAcc, guid FROM nextris.tbexamination WHERE Guid = %s"
        exam_result = DatabaseService.execute_query(exam_query, (report_id,))
        
        if not exam_result:
            print("[ERROR] Reporte o examen no encontrado en la base de datos")
            return jsonify({"error": "Reporte no encontrado"}), 404
            
        study_data = exam_result[0]
        study_instance_uid = study_data[0]
        guid_examination = study_data[4]
        
        print(f"[DEBUG] GUID examination: {guid_examination}")

        from apps.services.report_view_service import ReportViewUnavailable, resolve_report_view, report_view_text
        try:
            external_text = report_view_text(resolve_report_view(report_id)['report'])
        except ReportViewUnavailable as error:
            return jsonify({'error': str(error), 'code': error.code}), error.status

        # Crear el mensaje de email
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = 'Centro Médico - Informe de estudio e Imágenes'
        
        # Cuerpo del mensaje
        body_text = f"{external_text}\n\nLink de las imágenes: {os.getenv('DICOM_VIEWER_URL', 'http://localhost:3000/viewer')}?StudyInstanceUIDs={study_instance_uid}"
        body = MIMEText(body_text)
        msg.attach(body)
        
        # Enviar el email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print("[DEBUG] Email enviado exitosamente")
        
        # Actualizar estado del examen (ispublicated=1)
        try:
            update_query = "UPDATE nextris.tbexamination SET ispublicated=1 WHERE Guid = %s"
            DatabaseService.execute_query(update_query, (guid_examination,), commit=True)
            print("[DEBUG] Flag ispublicated actualizado a 1")
            
            # Actualizar status usando la función completa
            status_result = updatestatus(guid_examination)
            if status_result == 'success':
                print("[SUCCESS] Estado del examen actualizado exitosamente")
            else:
                print(f"[WARNING] Problema actualizando estado: {status_result}")
            
        except Exception as e:
            print(f"[ERROR] Error al actualizar estado del examen: {e}")
            # No devolver error aquí, el email ya se envió exitosamente
        
        return jsonify({"message": "Correo enviado con éxito."})
        
    except Exception as e:
        print(f"[ERROR] Error enviando email: {str(e)}")
        return jsonify({"error": f"Error enviando email: {str(e)}"}), 500
