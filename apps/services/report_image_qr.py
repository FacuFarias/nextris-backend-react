"""QR block that gives report PDF readers access to the study images."""
from html import escape
import logging

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle

logger = logging.getLogger(__name__)
QR_SIZE = 86
BLOCK_WIDTH = 170


def image_link_for(view):
    """A clinical report must still open if its image link cannot be issued."""
    from apps.api.viewer_share_service import report_image_link
    try:
        return report_image_link(view['report']['id_informe'])
    except Exception:
        logger.exception('No se pudo generar el QR de imágenes del informe')
        return None


class _QrCode(Flowable):
    """Printed for scanning and clickable when the PDF is read on screen."""

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.width = self.height = QR_SIZE

    def wrap(self, _available_width, _available_height):
        return QR_SIZE, QR_SIZE

    def draw(self):
        drawing = Drawing(QR_SIZE, QR_SIZE)
        drawing.add(qr.QrCodeWidget(self.url, barLevel='M', barWidth=QR_SIZE, barHeight=QR_SIZE))
        renderPDF.draw(drawing, self.canv, 0, 0)
        self.canv.linkURL(self.url, (0, 0, QR_SIZE, QR_SIZE), relative=1, thickness=0)


def qr_block(link, title_style, caption_style):
    until = link['expires_at'].strftime('%d/%m/%Y')
    block = Table([[_QrCode(link['share_url'])],
                   [Paragraph('Imágenes del estudio', title_style)],
                   [Paragraph(escape(f"Escanee el código para verlas. Enlace válido por {link['valid_days']} días, hasta el {until}."), caption_style)]],
                  colWidths=[BLOCK_WIDTH])
    block.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    return block
