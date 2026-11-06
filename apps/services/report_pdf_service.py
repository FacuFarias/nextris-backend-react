"""On-demand local report PDFs, rendered in memory without stored clinical files."""
from dataclasses import dataclass
from io import BytesIO
from html import escape
from apps.services.report_view_service import ReportViewUnavailable, resolve_report_view, plain_report_text


class ReportPdfNotAvailable(ReportViewUnavailable):
    pass


@dataclass(frozen=True)
class RenderedReportPdf:
    content: bytes
    filename: str


def render_report_pdf(exam_id, *, filename=None, view=None):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    import base64

    view = view or resolve_report_view(exam_id)
    safe_id = ''.join(c for c in str(exam_id) if c.isalnum() or c in '-_')
    from apps.services.report_letterhead_pdf import letterhead_path, render as render_letterhead
    background = letterhead_path()
    if background:
        accession = ''.join(c for c in str(view['report'].get('accession_number') or '') if c.isalnum() or c in '-_')
        return RenderedReportPdf(render_letterhead(view, background, plain_report_text), filename or f'informe_{accession or safe_id}.pdf')
    report, document = view['report'], view['document']
    styles = getSampleStyleSheet()
    output = BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm, title='Informe médico')
    story = []
    def paragraph(value, style='Normal'):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), styles[style])
    def image(value):
        if value and value.startswith('data:image/png;base64,'):
            return Image(BytesIO(base64.b64decode(value.split(',', 1)[1])), width=45*mm, height=22*mm, kind='proportional')
        return None
    logo = image(document['institution'].get('logo'))
    if logo:
        story.append(logo)
    story += [paragraph(document['institution'].get('name') or 'NextRIS', 'Title'),
              paragraph(report.get('procedimientos') or 'Informe médico', 'Heading2'),
              paragraph('Paciente: ' + document['patient']['name']),
              paragraph(('Identificador del animal: ' if document.get('veterinary') else 'Documento: ') + str(document['patient'].get('national_code') or document['patient'].get('identifier') or '')),
              paragraph('Número de acceso: ' + str(report.get('accession_number') or '')),
              paragraph('Fecha del informe: ' + str(report.get('fecha') or '')), Spacer(1, 5*mm)]
    context = document.get('veterinary')
    if context:
        reproductive = {'unknown':'Desconocido','intact':'No esterilizado','neutered':'Esterilizado'}.get(context.get('reproductive_status'),'')
        responsible = ', '.join(r['name'] for r in context.get('responsibles',[])) or 'Pendiente'
        for label, value in [('Especie',context.get('species_name')),('Raza',context.get('breed_name')),
            ('Nacimiento' + (' estimado' if context.get('birthdate_estimated') else ''),context.get('birthdate')),
            ('Sexo',context.get('gender')),('Estado reproductivo',reproductive),('Peso (kg)',context.get('weight_kg')),('Responsable registrado al firmar',responsible)]:
            story.append(paragraph(label + ': ' + str(value if value is not None else 'No informado')))
    for key, section in report.get('textos', {}).items():
        story += [paragraph(section.get('as') or key, 'Heading3'),
                  paragraph(plain_report_text(section.get('contenido'))), Spacer(1, 4*mm)]
    for signature in document['signatures']:
        block = []
        for key in ('image', 'stamp_image'):
            asset = image(signature.get(key))
            if asset:
                block.append(asset)
        block += [paragraph(signature['professional']), paragraph(signature.get('clarification')),
                  paragraph(signature.get('registration'))]
        story.append(KeepTogether(block))
    footer = ' · '.join(str(document['institution'].get(key)) for key in ('address','phone','email') if document['institution'].get(key))
    if footer:
        story += [Spacer(1, 8*mm), paragraph(footer)]
    pdf.build(story)
    return RenderedReportPdf(output.getvalue(), filename or f'informe_{safe_id}.pdf')
