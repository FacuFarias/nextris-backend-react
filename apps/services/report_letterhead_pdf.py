"""Report PDF over an institution letterhead image (NEXTRIS_REPORT_LETTERHEAD)."""
import base64
from datetime import date, datetime
from html import escape
from io import BytesIO
import os
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, Image, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import TopPadder

ROOT = Path(__file__).resolve().parents[2]
HEADING = HexColor('#435f73')
MUTED = '#969696'
LEFT, RIGHT, TOP, BOTTOM = 42.5, 552.8, 150, 82
WIDTH = RIGHT - LEFT
COLUMNS = [186, 152, WIDTH - 338]
SEX = {'M': 'Macho', 'F': 'Hembra', 'O': 'Desconocido'}
REPRODUCTIVE = {'intact': 'No esterilizado', 'neutered': 'Esterilizado'}


def letterhead_path():
    value = os.getenv('NEXTRIS_REPORT_LETTERHEAD')
    if not value:
        return None
    path = (ROOT / value).resolve()
    return path if path.is_relative_to(ROOT / 'apps/static/assets/img') and path.is_file() else None


def _fonts():
    folder = ROOT / 'apps/static/assets/fonts/carlito'
    for name, filename in (('Carlito', 'Carlito-Regular.ttf'), ('Carlito-Bold', 'Carlito-Bold.ttf')):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(folder / filename)))


class SectionHeading(Flowable):
    """Square bullet, title and rule up to the right margin, as in the letterhead design."""
    keepWithNext = True

    def __init__(self, text):
        super().__init__()
        self.text = text

    def wrap(self, available_width, _available_height):
        self.width = available_width
        return available_width, 15

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(HEADING)
        canvas.rect(0, 7, 2.8, 2.8, stroke=0, fill=1)
        canvas.setFont('Carlito-Bold', 12)
        canvas.drawString(8.5, 3, self.text)
        start = 8.5 + canvas.stringWidth(self.text, 'Carlito-Bold', 12) + 3
        canvas.setStrokeColor(HEADING)
        canvas.setLineWidth(0.57)
        canvas.line(start, 2.4, self.width, 2.4)


def _date(value):
    if not value:
        return '-'
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).strftime('%d/%m/%Y')
    except ValueError:
        return str(value)


def _age(birthdate, reference):
    """Age at the study date, e.g. 3 años, 2 meses. Marked when the birth date is estimated."""
    try:
        born = datetime.fromisoformat(str(birthdate)).date()
        at = datetime.fromisoformat(str(reference).replace('Z', '+00:00')).date() if reference else date.today()
    except ValueError:
        return '-'
    months = (at.year - born.year) * 12 + at.month - born.month - (at.day < born.day)
    if months < 0:
        return '-'
    years, months = divmod(months, 12)
    parts = ([f"{years} año{'s' if years != 1 else ''}"] if years else []) + ([f"{months} mes{'es' if months != 1 else ''}"] if months or not years else [])
    return ', '.join(parts)


def _fields(rows, style):
    def cell(label, value):
        shown = '-' if value in (None, '') else value
        return Paragraph(f'<font color="{MUTED}">{escape(label)}:&nbsp;&nbsp;</font>{escape(str(shown))}', style)
    table = Table([[cell(*item) for item in row] for row in rows], colWidths=COLUMNS)
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 2.8),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5)]))
    return table


def _signature(signature, name_style, small_style):
    def asset(value, width, height):
        if value and value.startswith('data:image/png;base64,'):
            return Image(BytesIO(base64.b64decode(value.split(',', 1)[1])), width=width, height=height, kind='proportional')
        return None
    rows = [[item] for item in (asset(signature.get('image'), 170, 76), asset(signature.get('stamp_image'), 120, 54)) if item]
    if not signature.get('image'):
        rows.append([Paragraph('Firma no disponible', small_style)])
    rows.append([Paragraph(escape(signature.get('professional') or ''), name_style)])
    clarification = signature.get('clarification')
    if clarification and clarification != signature.get('professional'):
        rows.append([Paragraph(escape(clarification), small_style)])
    if signature.get('registration'):
        rows.append([Paragraph('M.P. ' + escape(str(signature['registration'])), small_style)])
    block = Table(rows, colWidths=[230])
    block.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    block.hAlign = 'RIGHT'
    return block


def render(view, background, plain_report_text):
    _fonts()
    report, document = view['report'], view['document']
    context = document.get('veterinary') or {}
    patient = document['patient']
    study = document.get('study', {})
    text = ParagraphStyle('text', fontName='Carlito', fontSize=12, leading=15)
    field = ParagraphStyle('field', parent=text, leading=14.5)
    name = ParagraphStyle('name', fontName='Carlito-Bold', fontSize=11, leading=13, textColor=HEADING, alignment=TA_CENTER)
    small = ParagraphStyle('small', fontName='Carlito', fontSize=9, leading=11, alignment=TA_CENTER)
    responsible = ', '.join(item['name'] for item in context.get('responsibles', []))
    age = _age(context['birthdate'], study.get('date')) if context.get('birthdate') else '-'
    if age != '-' and context.get('birthdate_estimated'):
        age += ' (estimada)'
    story = [
        SectionHeading('ESTUDIO'), Spacer(1, 7),
        _fields([[('Fecha Estudio', _date(study.get('date'))), ('Fecha Informe', _date(report.get('fecha'))), ('N.º de acceso', report.get('accession_number'))],
                 [('Estudio', report.get('procedimientos')), ('Modalidad', report.get('modalidad')), ('Derivante', study.get('referring'))]], field),
        Spacer(1, 15),
        SectionHeading('ANIMAL' if context else 'PACIENTE'), Spacer(1, 7),
        _fields([[('Nombre', patient.get('name')), ('ID', patient.get('identifier')), ('Sexo', SEX.get(context.get('gender'), context.get('gender')))],
                 [('Especie', context.get('species_name')), ('Raza', context.get('breed_name')), ('Edad', age)],
                 [('Responsable', responsible), ('Peso', f"{context['weight_kg']} kg" if context.get('weight_kg') is not None else None),
                  ('Estado', REPRODUCTIVE.get(context.get('reproductive_status')))]], field),
        Spacer(1, 15),
    ]
    for key, section in report.get('textos', {}).items():
        content = plain_report_text(section.get('contenido'))
        if not (content or '').strip():
            continue
        story += [SectionHeading((section.get('as') or key).upper()), Spacer(1, 8),
                  Paragraph(escape(content).replace('\n', '<br/>'), text), Spacer(1, 17)]
    for signature in document.get('signatures', []):
        story.append(TopPadder(_signature(signature, name, small)))

    image = ImageReader(str(background))

    def page(canvas, _doc):
        canvas.drawImage(image, 0, 0, width=A4[0], height=A4[1])

    output = BytesIO()
    pdf = BaseDocTemplate(output, pagesize=A4, title='Informe veterinario' if context else 'Informe médico',
                          author=document['institution'].get('name') or 'NextRIS')
    frame = Frame(LEFT, BOTTOM, WIDTH, A4[1] - TOP - BOTTOM, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    pdf.addPageTemplates(PageTemplate(id='letterhead', frames=[frame], onPage=page))
    pdf.build(story)
    return output.getvalue()
