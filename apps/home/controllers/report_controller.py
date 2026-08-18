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
import psycopg2
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from apps.home.services.database_service import DatabaseService
from apps.home.services.config_service import ConfigService

# Importar funciones para firmas digitales
from apps.home.controllers.config_controller import get_user_signature_data
from apps.api.viewer_share_service import create_for_exam as create_share_for_exam

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

def generate_report_pdf_with_signature(report_id, output_dir='output_pdfs', pdf_filename=None):
    """
    Genera un PDF completo del reporte con firma digital.
    
    Args:
        report_id: ID del reporte/examen
        output_dir: Directorio donde se guardará el PDF
        pdf_filename: Nombre personalizado del archivo PDF (opcional)
    """
    print(f"[PDF_GEN] Iniciando generación de PDF para report_id: {report_id}")
    print(f"[PDF_GEN] output_dir: {output_dir}, pdf_filename: {pdf_filename}")
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        import psycopg2

        # Raíz del proyecto nextris-dev-react (independiente del cwd del servicio)
        app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

        # Forzar directorio de salida absoluto para que siempre quede en el repo.
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(app_root, output_dir)
        
        # Configuración de base de datos
        config = {
            'host': 'localhost',
            'database': 'pacsdb',
            'user': 'pacs',
            'password': 'pacs'
        }
        
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
                        WHEN COALESCE(NULLIF(BTRIM(rep.Findings), ''), '') <> ''
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
                   rep.Findings, rep.Techniques, rep.Impressions, rep.Conclusions, rep.iduser
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

        surname, name, examen, fecha, refmed, findings, techniques, impressions, conclusions, userid = data

        # El QR se crea en la misma transacción/conexión que genera el PDF. El
        # token plano vive únicamente en memoria durante esta operación; la BD
        # conserva exclusivamente su hash.
        share_data = None
        try:
            share_data = create_share_for_exam(report_id, created_by=userid, connection=connection)
            # El enlace del QR debe quedar persistido aunque una consulta
            # opcional posterior del encabezado falle para este estudio.
            connection.commit()
        except Exception as share_error:
            print(f"[PDF_GEN] No se pudo crear enlace QR de imágenes: {share_error}")

        findings = _normalize_report_text_for_pdf(findings)
        techniques = _normalize_report_text_for_pdf(techniques)
        impressions = _normalize_report_text_for_pdf(impressions)
        conclusions = _normalize_report_text_for_pdf(conclusions)

        # Crear directorio si no existe
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Usar nombre personalizado o el predeterminado
        if pdf_filename:
            pdf_file_path = os.path.join(output_dir, pdf_filename)
        else:
            pdf_file_path = os.path.join(output_dir, f"r_{report_id}.pdf")
            
        c = canvas.Canvas(pdf_file_path, pagesize=letter)
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
            ("Técnicas de Examen:", techniques or ""),
            ("Hallazgos:", findings or ""),
            ("Impresiones:", impressions or ""),
            ("Conclusión:", conclusions or "")
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

        # Persistir el enlace que corresponde al QR generado en este PDF.
        connection.commit()
        
        # Cerrar conexión
        cursor.close()
        connection.close()
        
        print(f"[SUCCESS] PDF generado con firma: {pdf_file_path}")
        return pdf_file_path
        
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
            SELECT guid, tittle, findings, impression, technique, conclusion, studytype_id
            FROM nextris.tbinfpredef 
            WHERE guid=%s
        """
        
        result = DatabaseService.execute_query(query, (guid,))
        
        if result and len(result) > 0:
            row = result[0]
            response = {
                'guid': row[0],
                'tittle': row[1] or '',  # Frontend espera 'tittle'
                'findings': row[2] or '',  # Frontend espera 'findings'
                'impression': row[3] or '',  # Frontend espera 'impression'
                'technique': row[4] or '',  # Frontend espera 'technique'
                'conclusion': row[5] or '',  # Frontend espera 'conclusion'
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
        findings = data.get('hallazgostext', '')  # hallazgos
        technique = data.get('tecnicastext', '')  # técnicas
        impression = data.get('impresionestext', '')  # impresiones
        conclusion = data.get('conclusionestext', '')  # conclusiones
        isdefault = data.get('isdefault', 0)
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Insertar en la base de datos
        query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, findings, impression, technique, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        result = DatabaseService.execute_query(
            query, 
            (new_guid, title, findings, impression, technique, conclusion, studytype_id),
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
        query = "UPDATE nextris.tbexamination SET IsReported=0 WHERE Guid=%s"
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
        
        # Validar campos requeridos
        required_fields = ['id', 'val_findings', 'val_tecnicas', 'val_impresiones', 'val_conclusiones']
        for field in required_fields:
            if field not in data:
                print(f"[ERROR] Campo requerido faltante: {field}")
                return jsonify({'error': f'Campo requerido faltante: {field}'}), 400
        
        exam_id = data['id']
        findings = data['val_findings']
        techniques = data['val_tecnicas']
        impressions = data['val_impresiones']
        conclusions = data['val_conclusiones']
        
        print(f"[INFO] Guardando reporte para examen ID: {exam_id}")
        
        # Query seguro usando parámetros para evitar SQL injection
        query = """
            UPDATE nextris.tbReport 
            SET findings=%s, techniques=%s, impressions=%s, conclusions=%s, wassaved=true 
            WHERE IdExamination=%s
        """
        
        print(f"[INFO] Ejecutando query de actualización para exam_id: {exam_id}")
        
        result = DatabaseService.execute_query(
            query, 
            (findings, techniques, impressions, conclusions, exam_id), 
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
    """Firma un reporte médico (marca como reportado)"""
    try:
        print("[INFO] Iniciando firmar_reporte")
        
        # Obtener datos del request
        reporteid = request.get_json()
        if not reporteid:
            print("[ERROR] No se recibieron datos JSON")
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        exam_id = reporteid.get('id')
        if not exam_id:
            print("[ERROR] Falta el ID del examen en el request")
            return jsonify({'error': 'Falta el ID del examen'}), 400
        
        # Obtener el ID del médico que firma (puede venir del request o de la sesión)
        reporter_physician_id = reporteid.get('reporter_physician_id')
        if not reporter_physician_id:
            # Fallback: intentar obtener de la sesión
            reporter_physician_id = session.get('user_guid') or session.get('user_id')
            print(f"[INFO] ID del médico obtenido de sesión: {reporter_physician_id}")
        else:
            print(f"[INFO] ID del médico recibido del frontend: {reporter_physician_id}")
        
        if not reporter_physician_id:
            print("[WARNING] No se pudo determinar el ID del médico que firma")
        
        print(f"[INFO] Firmando reporte para examen ID: {exam_id}, Médico: {reporter_physician_id}")
        
        # 1. Marcar el examen como reportado
        query = "UPDATE nextris.tbexamination SET isreported=1 WHERE Guid=%s"
        print(f"[INFO] Ejecutando query: {query} con ID: {exam_id}")
        
        result = DatabaseService.execute_query(query, (exam_id,), fetch_all=False, commit=True)
        
        # 2. Actualizar estado si existe la función
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
            print("[INFO] Estado actualizado exitosamente")
        except Exception as update_error:
            print(f"[WARNING] No se pudo actualizar el estado: {str(update_error)}")
        
        # 3. Crear PDF con formato profesional usando ReportLab
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            
            print("[INFO] Generando PDF con formato profesional...")
            
            pdf_path = f"output_pdfs/r_{exam_id}.pdf"
            absolute_pdf_path = os.path.abspath(pdf_path)
            
            pdf_directory = os.path.dirname(absolute_pdf_path)
            if not os.path.exists(pdf_directory):
                os.makedirs(pdf_directory, exist_ok=True)
            
            # Consulta para obtener datos completos del reporte
            query = """
                  SELECT p.surname, p.name, st.description, rep.date,
                      COALESCE(NULLIF(u_ref.username, ''), rep.idreferringphysician::text) AS referring_physician_name,
                       rep.findings, rep.techniques, rep.impressions, rep.conclusions
                FROM nextris.tbreport rep
                LEFT JOIN nextris.tbexamination tbex ON tbex.guid = rep.idexamination
                LEFT JOIN nextris.isstudytype st ON tbex.studytype_id = st.guid
                LEFT JOIN nextris.datapatient p ON p.patientid = rep.idpatient
                  LEFT JOIN nextris.tbuser u_ref ON u_ref.guid = rep.idreferringphysician
                WHERE rep.idexamination = %s
            """
            
            datos = DatabaseService.execute_query(query, (exam_id,), fetch_one=True)
            print(f"[DEBUG] Datos del reporte: {datos}")
            
            if datos:
                surname, name, examen, fecha, refmed, findings, techniques, impressions, conclusions = datos
            else:
                # Fallback si no hay datos completos
                surname = name = "Información pendiente"
                examen = "Examen médico"
                fecha = datetime.now().strftime('%d/%m/%Y')
                refmed = "No proporcionado"
                findings = techniques = impressions = conclusions = ""

            # El endpoint legado también debe generar el mismo enlace corto
            # que usa el generador principal, para que sus PDFs incluyan QR.
            share_data = None
            try:
                share_connection = psycopg2.connect(**ConfigService.get_db_config())
                share_data = create_share_for_exam(
                    exam_id,
                    created_by=reporter_physician_id,
                    connection=share_connection,
                )
                share_connection.commit()
                share_connection.close()
            except Exception as share_error:
                print(f"[WARNING] No se pudo crear enlace QR para PDF legado: {share_error}")
            
            # Crear el PDF
            c = canvas.Canvas(absolute_pdf_path, pagesize=letter)
            width, height = letter
            
            # Obtener datos institucionales y logo
            inst_query = "SELECT name, address, phone, mail, logo_path FROM nextris.isbasicinformation ORDER BY guid ASC LIMIT 1"
            institucion = DatabaseService.execute_query(inst_query, fetch_one=True)
            
            if institucion:
                nombre_inst = institucion[0] or ''
                direccion_inst = institucion[1] or ''
                telefono_inst = institucion[2] or ''
                mail_inst = institucion[3] or ''
                logo_path_db = institucion[4]
            else:
                nombre_inst = ''
                direccion_inst = ''
                telefono_inst = ''
                mail_inst = ''
                logo_path_db = None

            # Si el informe pertenece a una ubicación configurada, sus datos
            # tienen prioridad; los campos vacíos conservan el fallback general.
            location_query = """
                SELECT loc.name, loc.address, loc.phone, loc.mail, loc.logo_path
                FROM nextris.tbexamination ex
                LEFT JOIN nextris.isequipment eq ON eq.guid = ex.idequipment
                LEFT JOIN nextris.tblocation loc ON loc.guid = COALESCE(ex.location_id, eq.location_id)
                WHERE ex.guid = %s
                LIMIT 1
            """
            location_data = DatabaseService.execute_query(location_query, (exam_id,), fetch_one=True)
            if not location_data or not any(location_data):
                location_data = DatabaseService.execute_query(
                    """
                    SELECT name, address, phone, mail, logo_path
                    FROM nextris.tblocation
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      AND (
                          SELECT COUNT(*)
                          FROM nextris.tblocation
                          WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      ) = 1
                    LIMIT 1
                    """,
                    fetch_one=True
                )
            if location_data:
                nombre_inst = nombre_inst or location_data[0] or ''
                direccion_inst = direccion_inst or location_data[1] or ''
                telefono_inst = telefono_inst or location_data[2] or ''
                mail_inst = mail_inst or location_data[3] or ''
                logo_path_db = logo_path_db or location_data[4]
            
            # Añadir el logo institucional si existe
            legacy_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            logo_to_use = _resolve_pdf_asset_path(logo_path_db, legacy_app_root)
            if not logo_to_use:
                logo_to_use = _resolve_pdf_asset_path(
                    'apps/static/assets/img/icono.jpg',
                    legacy_app_root
                )
            print(f"[DEBUG] Using logo: {logo_to_use}")
            try:
                c.drawImage(logo_to_use, 50, height - 125, width=2*inch, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"[WARNING] No se pudo cargar el logo: {e}")
            
            # Encabezado institucional
            c.setFont("Helvetica-Bold", 16)
            c.drawString(200, height - 50, nombre_inst)
            c.setFont("Helvetica", 12)
            c.drawString(200, height - 70, direccion_inst)
            c.drawString(200, height - 90, f"Tel: {telefono_inst}")
            c.drawString(200, height - 110, f"Mail: {mail_inst}")
            
            # Examen debajo del logo
            c.setFont("Helvetica-Bold", 14)
            examen_lines = wrap_text_advanced(f"Exámen: {examen or 'Examen médico'}", width - 50, "Helvetica-Bold", 14, c)
            y_examen = height - 220
            for line in examen_lines:
                if y_examen < 80:  # Nueva página si no hay espacio
                    c.showPage()
                    y_examen = height - 50
                c.drawString(50, y_examen, line)
                y_examen -= 18
            
            # Añadir los datos del informe
            c.setFont("Helvetica", 12)
            
            # Verificar espacio para datos del paciente
            if y_examen < 150:
                c.showPage()
                y_position = height - 50
            else:
                y_position = y_examen - 30
            
            c.drawString(50, y_position, f"Paciente: {name or ''}, {surname or ''}")
            y_position -= 20
            c.drawString(50, y_position, f"Fecha: {fecha or 'N/A'}")
            y_position -= 20
            c.drawString(50, y_position, f"Médico Referente: {refmed or 'No proporcionado'}")
            y_position -= 40
            
            # Añadir contenido médico usando la nueva función
            max_width = width - 50  # Margen derecho optimizado
            
            # Secciones de contenido médico
            medical_sections = [
                ("Técnicas de Examen:", techniques or ""),
                ("Hallazgos:", findings or ""),
                ("Impresiones:", impressions or ""),
                ("Conclusión:", conclusions or "")
            ]
            
            for title, content in medical_sections:
                y_position = draw_text_section(c, title, content, y_position, max_width)
            
            # ===== AGREGAR FIRMA DIGITAL AL FINAL =====
            # Asegurar espacio suficiente para la firma
            if y_position < 200:
                c.showPage()
                y_position = height - 50
            
            # Obtener datos de firma del usuario actual usando Flask-Login
            # Usar como firmante el médico recibido al firmar el reporte. La
            # sesión puede corresponder a otro usuario en la UI legado.
            current_user_id = reporter_physician_id
            if not current_user_id and current_user and current_user.is_authenticated:
                current_user_id = current_user.id
                print(f"[INFO] Usuario autenticado: {current_user.username} (ID: {current_user_id})")
            elif not current_user_id:
                print(f"[WARNING] No hay usuario autenticado")
                # Fallback: intentar obtener de session si existe
                current_user_id = session.get('_user_id') or session.get('user_guid')
                print(f"[DEBUG] Usando ID de sesión como fallback: {current_user_id}")
            
            print(f"[DEBUG] Datos completos de sesión: {dict(session)}")
            
            if current_user_id:
                print(f"[INFO] Buscando firma para usuario: {current_user_id}")
                try:
                    signature_data = get_user_signature_data(current_user_id)
                    if not signature_data:
                        # Aunque no exista una firma gráfica habilitada, el
                        # PDF debe identificar al médico que realizó la firma.
                        signer = DatabaseService.execute_query(
                            "SELECT name, surname FROM nextris.tbuser WHERE guid=%s",
                            (current_user_id,),
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
                    print(f"[DEBUG] Datos de firma obtenidos: {signature_data}")
                    
                    if signature_data and signature_data.get('firma_digital'):
                        print(f"[INFO] Agregando firma del médico: {signature_data.get('aclaracion_firma', 'N/A')}")
                        
                        # Línea separadora
                        y_position -= 30
                        c.line(50, y_position, width - 50, y_position)
                        y_position -= 30
                        
                        # Título de firma
                        c.setFont("Helvetica-Bold", 12)
                        c.drawString(50, y_position, "FIRMA DIGITAL:")
                        y_position -= 30
                        
                        # Imagen de la firma
                        firma_path = signature_data.get('firma_path')
                        if firma_path and os.path.exists(firma_path):
                            try:
                                signature_width = 150
                                signature_height = 75
                                c.drawImage(firma_path, 50, y_position - signature_height, 
                                          width=signature_width, height=signature_height, 
                                          preserveAspectRatio=True, mask='auto')
                                
                                # Datos del médico al lado de la firma
                                c.setFont("Helvetica", 11)
                                text_x = signature_width + 80
                                c.drawString(text_x, y_position - 20, 
                                           f"Dr. {signature_data.get('aclaracion_firma', 'N/A')}")
                                c.drawString(text_x, y_position - 35, 
                                           f"M.N.: {signature_data.get('matricula_nacional', 'N/A')}")
                                c.drawString(text_x, y_position - 50, "Firma Digital Verificada")
                                
                                # Fecha y hora de firma
                                c.setFont("Helvetica", 9)
                                c.drawString(text_x, y_position - 65, 
                                           f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                                
                                print("[SUCCESS] Firma agregada correctamente al PDF")
                                
                            except Exception as img_error:
                                print(f"[WARNING] Error agregando imagen de firma: {str(img_error)}")
                                # Fallback: solo texto sin imagen
                                c.setFont("Helvetica", 11)
                                c.drawString(50, y_position - 20, f"Dr. {signature_data.get('aclaracion_firma', 'N/A')}")
                                c.drawString(50, y_position - 35, f"M.N.: {signature_data.get('matricula_nacional', 'N/A')}")
                                c.drawString(50, y_position - 50, "Firma Digital")
                                c.setFont("Helvetica", 9)
                                c.drawString(50, y_position - 65, f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                        else:
                            print(f"[WARNING] Archivo de firma no encontrado: {firma_path}")
                            # Solo texto sin imagen
                            c.setFont("Helvetica", 11)
                            c.drawString(50, y_position - 20, f"Dr. {signature_data.get('aclaracion_firma', 'N/A')}")
                            c.drawString(50, y_position - 35, f"M.N.: {signature_data.get('matricula_nacional', 'N/A')}")
                            c.drawString(50, y_position - 50, "Firma Digital")
                            c.setFont("Helvetica", 9)
                            c.drawString(50, y_position - 65, f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                    else:
                        print(f"[INFO] No se encontró firma habilitada para el usuario: {current_user_id}")
                        print(f"[DEBUG] Signature data completa: {signature_data}")
                        # Agregar texto indicativo de que no hay firma configurada pero con datos del usuario
                        y_position -= 30
                        c.line(50, y_position, width - 50, y_position)
                        y_position -= 30
                        c.setFont("Helvetica-Bold", 12)
                        c.drawString(50, y_position, "FIRMA DIGITAL:")
                        y_position -= 25
                        c.setFont("Helvetica", 11)
                        
                        # Intentar mostrar al menos los datos del usuario si están disponibles
                        if signature_data and signature_data.get('aclaracion_firma'):
                            c.drawString(50, y_position, f"Dr. {signature_data.get('aclaracion_firma', 'N/A')}")
                            c.drawString(50, y_position - 15, f"M.N.: {signature_data.get('matricula_nacional', 'N/A')}")
                            c.drawString(50, y_position - 30, "Firma digital no configurada")
                        else:
                            c.drawString(50, y_position, f"Usuario ID: {current_user_id}")
                            c.drawString(50, y_position - 15, "Firma digital no configurada")
                        
                        c.setFont("Helvetica", 9)
                        c.drawString(50, y_position - 45, f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                        
                except Exception as signature_error:
                    print(f"[ERROR] Error obteniendo datos de firma: {str(signature_error)}")
                    # Fallback básico pero con información del usuario
                    y_position -= 30
                    c.line(50, y_position, width - 50, y_position)
                    y_position -= 30
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(50, y_position, "FIRMA DIGITAL:")
                    y_position -= 25
                    c.setFont("Helvetica", 11)
                    c.drawString(50, y_position, f"Usuario ID: {current_user_id}")
                    c.drawString(50, y_position - 15, "Error al cargar firma digital")
                    c.setFont("Helvetica", 9)
                    c.drawString(50, y_position - 30, f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            else:
                print("[WARNING] No hay usuario en sesión para agregar firma")
                print(f"[DEBUG] session.keys(): {list(session.keys())}")
                # Firma genérica
                y_position -= 30
                c.line(50, y_position, width - 50, y_position)
                y_position -= 30
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, y_position, "FIRMA DIGITAL:")
                y_position -= 25
                c.setFont("Helvetica", 11)
                c.drawString(50, y_position, "Usuario no identificado")
                c.setFont("Helvetica", 9)
                c.drawString(50, y_position - 15, f"Firmado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

            # Mantener el QR al final también en este generador legado.
            if share_data and share_data.get('share_url'):
                try:
                    c.showPage()
                    _draw_share_qr_page(c, share_data['share_url'], width, height)
                except Exception as qr_error:
                    print(f"[WARNING] No se pudo dibujar el QR en PDF legado: {qr_error}")
            
            c.save()
            print(f"[SUCCESS] PDF generado con formato profesional y firma: {absolute_pdf_path}")
                
        except Exception as pdf_generation_error:
            print(f"[ERROR] Error generando PDF con ReportLab: {str(pdf_generation_error)}")
            return jsonify({'error': f'Error generando PDF: {str(pdf_generation_error)}'}), 500

        print(f"[INFO] PDF final en: {pdf_path}")
        
        # 4. Actualizar la ruta del PDF y el médico que firmó en tbReport
        try:
            query = "UPDATE nextris.tbReport SET pdfpath=%s, idreporterphysician=%s WHERE IdExamination=%s"
            DatabaseService.execute_query(query, (pdf_path, reporter_physician_id, exam_id), fetch_all=False, commit=True)
            print(f"[INFO] Ruta del PDF y médico firmante actualizados en tbReport")
        except Exception as pdf_error:
            print(f"[WARNING] No se pudo actualizar la ruta del PDF o médico firmante: {str(pdf_error)}")
        
        print("[INFO] Reporte firmado exitosamente")
        return jsonify({
            'success': True, 
            'message': 'Reporte firmado exitosamente',
            'pdf_path': pdf_path
        })
        
    except Exception as e:
        print(f"[ERROR] Error en firmar_reporte: {str(e)}")
        return jsonify({'error': str(e)}), 500


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
        findings = data.get('hallazgostext', '')  # hallazgos
        technique = data.get('tecnicastext', '')  # técnicas
        impression = data.get('impresionestext', '')  # impresiones
        conclusion = data.get('conclusionestext', '')  # conclusiones
        
        # Actualizar en la base de datos
        query = """
            UPDATE nextris.tbinfpredef 
            SET tittle=%s, findings=%s, impression=%s, technique=%s, conclusion=%s, studytype_id=%s
            WHERE guid=%s
        """
        
        result = DatabaseService.execute_query(
            query, 
            (title, findings, impression, technique, conclusion, studytype_id, guid),
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
        
        # Obtener información del reporte
        pdf_query = "SELECT pdfpath FROM nextris.tbReport WHERE IdExamination = %s"
        pdf_result = DatabaseService.execute_query(pdf_query, (report_id,))
        
        # Obtener información del examen
        exam_query = "SELECT StudyInstanceUID, IsImage, IdPatient, LocalAcc, guid FROM nextris.tbexamination WHERE Guid = %s"
        exam_result = DatabaseService.execute_query(exam_query, (report_id,))
        
        if not pdf_result or not exam_result:
            print("[ERROR] Reporte o examen no encontrado en la base de datos")
            return jsonify({"error": "Reporte no encontrado"}), 404
            
        pdf_path = pdf_result[0][0]
        study_data = exam_result[0]
        study_instance_uid = study_data[0]
        guid_examination = study_data[4]
        
        print(f"[DEBUG] PDF path: {pdf_path}")
        print(f"[DEBUG] GUID examination: {guid_examination}")
        
        # Normalizar y verificar la ruta del PDF
        pdf_path = os.path.normpath(pdf_path)
        absolute_path = os.path.abspath(pdf_path)
        
        if not os.path.exists(absolute_path):
            print(f"[ERROR] PDF no encontrado en la ruta: {absolute_path}")
            return jsonify({"error": "PDF no encontrado"}), 404
            
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
        with open(absolute_path, 'rb') as file:
            pdf_attachment = MIMEApplication(file.read(), _subtype='pdf')
            pdf_attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(absolute_path))
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
