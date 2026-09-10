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
    """
    Genera un PDF completo del reporte con firma digital.
    
    Args:
        report_id: ID del reporte/examen
        pdf_filename: Nombre personalizado del archivo PDF (opcional)
    """
    print(f"[PDF_GEN] Iniciando generación de PDF para report_id: {report_id}")
    print(f"[PDF_GEN] pdf_filename: {pdf_filename}")
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        import psycopg2

        # Raíz del proyecto nextris-dev-react (independiente del cwd del servicio)
        app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        
        # Configuración de base de datos
        config = ConfigService.get_db_config()
        
        # Conectar a la base de datos
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Consulta para obtener datos del reporte incluyendo iduser
        query = """
            WITH selected_report AS (
                SELECT rep.*
                FROM nextris.tbreport rep
                WHERE rep.IdExamination = %s
                ORDER BY
                    CASE
                        WHEN COALESCE(NULLIF(BTRIM(rep.study_reason), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.content), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.conclusion), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.Findings), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.Techniques), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.Impressions), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.Conclusions), ''), '') <> ''
                        THEN 0 ELSE 1
                    END,
                    COALESCE(rep.WasSaved, FALSE) DESC,
                    rep.Date DESC NULLS LAST,
                    rep.Guid DESC
                LIMIT 1
            )
                 SELECT p.Surname, p.Name, st.Description, rep.Date,
                     COALESCE(NULLIF(u_ref.username, ''), tbex.idreferringphysician::text) AS referring_physician_name,
                   tbex.clinicalquestion, tbex.history,
                   rep.study_reason, rep.content, rep.conclusion,
                   rep.Findings, rep.Techniques, rep.Impressions, rep.Conclusions, rep.iduser,
                   COALESCE(tbex.IsReported, 0) AS is_reported
            FROM selected_report rep
            LEFT JOIN nextris.tbexamination tbex ON tbex.Guid = rep.IdExamination
            LEFT JOIN nextris.isstudytype st ON tbex.studytype_id = st.Guid
            LEFT JOIN nextris.datapatient p ON p.guid = COALESCE(rep.IdPatient, tbex.IdPatient)
                 LEFT JOIN nextris.tbuser u_ref ON u_ref.guid = tbex.idreferringphysician
        """
        
        print(f"[PDF_GEN] Ejecutando query para obtener datos del reporte...")
        cursor.execute(query, (report_id,))
        data = cursor.fetchone()
        print(f"[PDF_GEN] Resultado de query: {data is not None}")

        if not data:
            print(f"[ERROR] No se encontraron datos para el reporte: {report_id}")
            cursor.close()
            connection.close()
            return None

        (
            surname, name, examen, fecha, refmed, clinical_question, history,
            study_reason, content, conclusion,
            legacy_findings, legacy_techniques, legacy_impressions, legacy_conclusions,
            userid, is_reported,
        ) = data
        if not bool(is_reported):
            cursor.close()
            connection.close()
            return None

        # El QR se crea en la misma transacción/conexión que genera el PDF. El
        # token plano vive únicamente en memoria durante esta operación; la BD
        # conserva exclusivamente su hash.
        share_data = None
        try:
            from apps.api.viewer_share_service import get_or_create_active_for_exam
            share_data = get_or_create_active_for_exam(report_id, created_by=userid, connection=connection)
            # El enlace del QR debe quedar persistido aunque una consulta
            # opcional posterior del encabezado falle para este estudio.
            connection.commit()
        except Exception as share_error:
            print(f"[PDF_GEN] No se pudo crear enlace QR de imágenes: {share_error}")

        fields = canonical_fields_from_row(
            study_reason, content, conclusion,
            legacy_findings=legacy_findings,
            legacy_impressions=legacy_impressions,
            legacy_technique=legacy_techniques,
            legacy_conclusion=legacy_conclusions,
            reason_fallback=clinical_question or history,
        )
        study_reason = _normalize_report_text_for_pdf(fields['study_reason'])
        content = _normalize_report_text_for_pdf(fields['content'])
        conclusion = _normalize_report_text_for_pdf(fields['conclusion'])

        pdf_stream = BytesIO()
        c = canvas.Canvas(pdf_stream, pagesize=letter)
        width, height = letter

        # Obtener datos institucionales (prioridad: ubicación del examen).
        # Se dejan vacíos inicialmente para que los datos de ubicación,
        # facility o institución general puedan completar cada campo.
        nombre_inst = ''
        direccion_inst = ''
        telefono_inst = ''
        mail_inst = ''
        logo_path_db = None

        inst_by_location_query = """
            SELECT loc.name, loc.address, loc.phone, loc.mail, loc.logo_path, loc.facility_id
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isequipment eq ON eq.guid = ex.idequipment
            LEFT JOIN nextris.tblocation loc ON loc.guid = COALESCE(ex.location_id, eq.location_id)
            WHERE ex.guid = %s
            LIMIT 1
        """

        inst_fallback = None
        facility_fallback = None

        institution_savepoint = f"pdf_institution_{uuid.uuid4().hex[:8]}"
        cursor.execute(f"SAVEPOINT {institution_savepoint}")
        try:
            cursor.execute(inst_by_location_query, (report_id,))
            inst_location = cursor.fetchone()

            # Algunos estudios antiguos no tienen location_id ni equipo
            # asociado. Si existe una única ubicación activa configurada, se
            # usa como identidad institucional (actualmente Clínica Parque).
            if not inst_location or not any(inst_location[:5]):
                cursor.execute(
                    """
                    SELECT name, address, phone, mail, logo_path, facility_id
                    FROM nextris.tblocation
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      AND (
                          SELECT COUNT(*)
                          FROM nextris.tblocation
                          WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      ) = 1
                    LIMIT 1
                    """
                )
                inst_location = cursor.fetchone()

            if inst_location:
                nombre_inst = inst_location[0] or nombre_inst
                direccion_inst = inst_location[1] or direccion_inst
                telefono_inst = inst_location[2] or telefono_inst
                mail_inst = inst_location[3] or mail_inst
                logo_path_db = inst_location[4] or logo_path_db

                facility_id = inst_location[5]
                if facility_id:
                    try:
                        cursor.execute(
                            "SELECT name, email FROM nextris.tbfacility WHERE guid = %s LIMIT 1",
                            (facility_id,),
                        )
                        facility_fallback = cursor.fetchone()
                    except Exception as facility_error:
                        # La tabla es opcional y no existe en algunas
                        # instalaciones. Limpiar solo este fallo evita dejar
                        # abortada la transacción que contiene el enlace QR.
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {institution_savepoint}")
                        print(f"[WARNING] No se pudieron cargar datos de facility fallback: {facility_error}")
        except Exception as inst_error:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {institution_savepoint}")
            print(f"[WARNING] No se pudieron cargar datos de location para encabezado PDF: {inst_error}")
        finally:
            cursor.execute(f"RELEASE SAVEPOINT {institution_savepoint}")

        # Fallback legacy opcional: en algunos entornos esta tabla no existe.
        facility_savepoint = f"pdf_facility_{uuid.uuid4().hex[:8]}"
        cursor.execute(f"SAVEPOINT {facility_savepoint}")
        try:
            cursor.execute("SELECT name, address, phone, mail, logo_path FROM nextris.isbasicinformation ORDER BY guid ASC LIMIT 1")
            inst_fallback = cursor.fetchone()
        except Exception:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {facility_savepoint}")
            inst_fallback = None
        finally:
            cursor.execute(f"RELEASE SAVEPOINT {facility_savepoint}")

        if facility_fallback:
            nombre_inst = nombre_inst or facility_fallback[0] or ''
            mail_inst = mail_inst or facility_fallback[1] or ''

        if inst_fallback:
            # La configuración institucional global es la identidad oficial
            # del informe (por ejemplo, Clínica Parque). La ubicación solo
            # completa campos que no estén configurados globalmente.
            nombre_inst = inst_fallback[0] or nombre_inst
            direccion_inst = inst_fallback[1] or direccion_inst
            telefono_inst = inst_fallback[2] or telefono_inst
            mail_inst = inst_fallback[3] or mail_inst
            logo_path_db = inst_fallback[4] or logo_path_db

        if not nombre_inst:
            print("[WARNING] No hay datos en nextris.isbasicinformation para el encabezado institucional")

        # Añadir logo si existe
        logo_to_use = _resolve_pdf_asset_path(logo_path_db, app_root)
        if not logo_to_use:
            logo_to_use = _resolve_pdf_asset_path('apps/static/assets/img/icono.jpg', app_root)
        try:
            if logo_to_use:
                from reportlab.lib.utils import ImageReader

                image_reader = ImageReader(logo_to_use)
                img_width, img_height = image_reader.getSize()

                max_logo_width = 140
                max_logo_height = 90
                scale = min(max_logo_width / float(img_width), max_logo_height / float(img_height))
                draw_width = float(img_width) * scale
                draw_height = float(img_height) * scale

                logo_x = 50
                logo_box_top = height - 40
                logo_y = logo_box_top - draw_height

                c.drawImage(
                    logo_to_use,
                    logo_x,
                    logo_y,
                    width=draw_width,
                    height=draw_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            else:
                print("[PDF_GEN] No se encontró logo institucional ni logo por defecto")
        except Exception as e:
            print(f"No se pudo cargar el logo: {e}")

        # Encabezado institucional
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, height - 50, nombre_inst)
        c.setFont("Helvetica", 12)
        c.drawString(200, height - 70, direccion_inst)
        c.drawString(200, height - 90, f"Tel: {telefono_inst}")
        c.drawString(200, height - 110, f"Mail: {mail_inst}")

        # Información del examen
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 150, f"Exámen: {examen or 'N/A'}")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 180, f"Paciente: {name or ''}, {surname or ''}")
        c.drawString(50, height - 200, f"Fecha: {fecha or 'N/A'}")
        c.drawString(50, height - 220, f"Médico Referente: {refmed or 'No proporcionado'}")

        # Contenido del reporte
        y_position = height - 260
        
        sections = [
            ("Razón del estudio:", study_reason or ""),
            ("Contenido:", content or ""),
            ("Conclusión:", conclusion or "")
        ]

        for title, content in sections:
            y_position = draw_text_section(c, title, content, y_position, width - 50)

        # ===== AGREGAR FIRMA DIGITAL =====
        if userid:
            signature_data = get_user_signature_data(userid)
            if not signature_data:
                signer = DatabaseService.execute_query(
                    "SELECT name, surname FROM nextris.tbuser WHERE guid=%s",
                    (userid,),
                    fetch_one=True,
                )
                if signer:
                    signature_data = {
                        'aclaracion_firma': ' '.join(
                            part for part in (signer[0], signer[1]) if part
                        ).strip(),
                        'matricula_nacional': None,
                        'firma_digital': None,
                        'firma_habilitada': False,
                        'firma_path': None,
                    }
            if signature_data and signature_data['firma_digital']:
                print(f"[INFO] Agregando firma del médico: {signature_data['aclaracion_firma']}")
                
                # Asegurar que hay espacio suficiente para la firma
                if y_position < 150:
                    c.showPage()
                    y_position = height - 50
                
                firma_path = signature_data['firma_path']
                
                try:
                    if os.path.exists(firma_path):
                        # Línea separadora
                        c.line(50, y_position - 20, width - 50, y_position - 20)
                        y_position -= 50
                        
                        # Imagen de la firma
                        signature_width = 120
                        signature_height = 60
                        c.drawImage(firma_path, 50, y_position - signature_height, 
                                  width=signature_width, height=signature_height, 
                                  preserveAspectRatio=True, mask='auto')
                        
                        # Datos del médico
                        c.setFont("Helvetica", 10)
                        c.drawString(signature_width + 70, y_position - 20, 
                                   f"Dr. {signature_data['aclaracion_firma']}")
                        c.drawString(signature_width + 70, y_position - 35, 
                                   f"M.N.: {signature_data['matricula_nacional']}")
                        c.drawString(signature_width + 70, y_position - 50, "Firma Digital")
                        
                        print("[SUCCESS] Firma agregada correctamente al PDF")
                    else:
                        print(f"[WARNING] Archivo de firma no encontrado: {firma_path}")
                        # Solo texto sin imagen
                        c.setFont("Helvetica", 10)
                        c.drawString(50, y_position - 30, f"Dr. {signature_data['aclaracion_firma']}")
                        c.drawString(50, y_position - 45, f"M.N.: {signature_data['matricula_nacional']}")
                        
                except Exception as e:
                    print(f"[ERROR] Error al agregar firma: {e}")
                    # Fallback: solo texto
                    c.setFont("Helvetica", 10)
                    c.drawString(50, y_position - 30, f"Dr. {signature_data['aclaracion_firma']}")
                    c.drawString(50, y_position - 45, f"M.N.: {signature_data['matricula_nacional']}")
            else:
                print(f"[INFO] No se encontró firma habilitada para el usuario: {userid}")
                if signature_data and signature_data.get('aclaracion_firma'):
                    if y_position < 110:
                        c.showPage()
                        y_position = height - 50
                    c.line(50, y_position - 20, width - 50, y_position - 20)
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(50, y_position - 40, "Médico firmante:")
                    c.setFont("Helvetica", 10)
                    c.drawString(50, y_position - 58, f"Dr. {signature_data['aclaracion_firma']}")
                    if signature_data.get('matricula_nacional'):
                        c.drawString(50, y_position - 73, f"M.N.: {signature_data['matricula_nacional']}")
                    c.setFont("Helvetica-Oblique", 9)
                    c.drawString(50, y_position - 88, "Firma digital no configurada")

        # El QR debe quedar siempre al final del informe, después del contenido
        # y de la firma. Se usa una página final dedicada para que nunca quede
        # mezclado con el encabezado ni se solape con texto variable.
        if share_data and share_data.get('share_url'):
            try:
                c.showPage()
                _draw_share_qr_page(c, share_data['share_url'], width, height)
            except Exception as qr_error:
                print(f"[PDF_GEN] No se pudo dibujar el QR: {qr_error}")

        c.save()
        pdf_bytes = pdf_stream.getvalue()
        pdf_stream.close()

        # Persistir el enlace que corresponde al QR generado en este PDF.
        connection.commit()
        
        # Cerrar conexión
        cursor.close()
        connection.close()
        
        print(f"[SUCCESS] PDF generado en memoria: {len(pdf_bytes)} bytes")
        return pdf_bytes
        
    except Exception as e:
        print(f"[ERROR] Error generando PDF con firma: {e}")
        import traceback
        traceback.print_exc()
        return None

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
            if not fields_are_complete(fields):
                cursor.close(); connection.close()
                return jsonify({'error': 'Razón del estudio, Contenido y Conclusión son requeridos', 'code': 'REPORT_FIELDS_REQUIRED'}), 400
        else:
            cursor.close(); connection.close()
            return jsonify({'error': 'Reporte no encontrado'}), 404
        cursor.execute(
            """
            UPDATE nextris.tbreport
            SET iduser = %s, wassaved = TRUE, date = NOW()
            WHERE idexamination = %s
            """,
            (reporter_physician_id, exam_id),
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

        # Keep the legacy signing endpoint consistent with the React API:
        # signed reports are sent to Clínica Parque by the persistent queue.
        from apps.services.clinicaparque_report_queue import enqueue_report_send
        report_send_schedule = enqueue_report_send(exam_id, connection=connection)

        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({
            'success': True,
            'message': 'Reporte firmado exitosamente',
            'report_send': report_send_schedule,
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

        from apps.services.report_pdf_service import ReportPdfNotAvailable, render_report_pdf
        try:
            rendered = render_report_pdf(report_id)
        except ReportPdfNotAvailable:
            return jsonify({"error": "Informe PDF no disponible"}), 404
            
        print("[DEBUG] PDF encontrado, preparando email...")
        
        # Crear el mensaje de email
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = 'Centro Médico - Informe de estudio e Imágenes'
        
        # Cuerpo del mensaje
        body_text = f'Adjunto encontrarás el reporte en PDF.\nLink de las imágenes: http://192.168.1.44/viewer.html?studyUID={study_instance_uid}'
        body = MIMEText(body_text)
        msg.attach(body)
        
        # Adjuntar el archivo PDF
        pdf_attachment = MIMEApplication(rendered.content, _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=rendered.filename)
        msg.attach(pdf_attachment)
        
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
