"""Read finalized local reports; no network service supplies clinical content."""

from html import escape
from html.parser import HTMLParser
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from apps.services.report_fields import canonical_fields_from_row, has_value


class ReportViewUnavailable(Exception):
    def __init__(self, message, code='REPORT_NOT_AVAILABLE', status=404, *, alternatives=None):
        super().__init__(message)
        self.code, self.status, self.alternatives = code, status, alternatives


class ReportTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'br', 'li', 'tr') and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'li', 'tr') and not self.hidden:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_report_text(value):
    parser = ReportTextParser()
    parser.feed(str(value or ''))
    parser.close()
    return ''.join(parser.parts).strip()


def resolve_report_view(exam_id, *, connection=None):
    """An exact examination ID is required; drafts and cancellations never render."""
    from apps.home.services.config_service import ConfigService
    from apps.services.patient_report_document import inline_image

    owned = connection is None
    connection = connection or psycopg2.connect(**ConfigService.get_db_config())
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute('''
                SELECT e.guid, e.isreported, e.status, e.workflow_state, e.localacc,
                       e.createdon, e.reportdate, e.clinicalquestion, e.history, e.requestingphysician_name,
                       dp.name, dp.surname, dp.patientid, dp.nationalcode,
                       st.description AS study_type, m.externalcode AS modality,
                       r.study_reason, r.content, r.conclusion,
                       r.findings, r.techniques, r.impressions, r.conclusions,
                       r.date AS report_date, r.iduser AS author_id,
                       u.name AS author_name, u.surname AS author_surname,
                       md.firma_habilitada, md.firma_digital, md.sello_digital,
                       md.aclaracion_firma, md.matricula_nacional,
                       COALESCE(l.name, ac.name, 'NextRIS') AS institution_name,
                       COALESCE(l.address, ac.address) AS address,
                       COALESCE(l.phone, ac.phone) AS phone,
                       COALESCE(l.mail, ac.email) AS mail, l.logo_path
                FROM nextris.tbexamination e
                JOIN nextris.datapatient dp ON dp.guid = e.idpatient
                LEFT JOIN nextris.isstudytype st ON st.guid = e.studytype_id
                LEFT JOIN nextris.ismodality m ON m.guid = st.modality_id
                LEFT JOIN nextris.isequipment eq ON eq.guid = e.idequipment
                LEFT JOIN nextris.tblocation l ON l.guid = COALESCE(e.location_id, eq.location_id)
                LEFT JOIN nextris.app_config ac ON ac.id = 1
                LEFT JOIN LATERAL (
                    SELECT rep.* FROM nextris.tbreport rep WHERE rep.idexamination = e.guid
                    ORDER BY rep.date DESC NULLS LAST, rep.guid DESC LIMIT 1
                ) r ON TRUE
                LEFT JOIN nextris.tbuser u ON u.guid = r.iduser
                LEFT JOIN nextris.tbuser_medical_data md ON md.user_id = u.guid
                WHERE e.guid = %s
            ''', (str(exam_id),))
            row = cursor.fetchone()
        if not row:
            raise ReportViewUnavailable('Estudio no encontrado', 'EXAM_NOT_FOUND')
        if (not row['isreported'] or row['workflow_state'] == 'cancelled'
                or str(row['status'] or '').lower() in ('cancelled', 'canceled')):
            raise ReportViewUnavailable('Este estudio no tiene un informe finalizado disponible')
        fields = canonical_fields_from_row(row['study_reason'], row['content'], row['conclusion'],
            legacy_findings=row['findings'], legacy_technique=row['techniques'],
            legacy_impressions=row['impressions'], legacy_conclusion=row['conclusions'],
            reason_fallback=row['clinicalquestion'] or row['history'])
        if not any(has_value(fields[key]) for key in ('content', 'conclusion')):
            raise ReportViewUnavailable('El informe no contiene texto disponible')
        author = ' '.join(filter(None, [row['author_name'], row['author_surname']])) or row['aclaracion_firma']
        signatures = []
        if author:
            image = inline_image(row['firma_digital'], signature=True) if row['firma_habilitada'] else None
            stamp = inline_image(row['sello_digital'], signature=True) if row['firma_habilitada'] else None
            signatures.append(dict(professional=author, available=bool(image), image=image,
                stamp_image=stamp, clarification=row['aclaracion_firma'], registration=row['matricula_nacional']))
        date = row['report_date'] or row['reportdate']
        report = dict(id_informe=str(row['guid']), fecha=date.isoformat() if date else None,
            profesional=author, procedimientos=row['study_type'], accession_number=row['localacc'],
            modalidad=row['modality'], textos={
                key: {'as': title, 'contenido': fields[key]} for key, title in (
                    ('study_reason', 'Motivo'), ('content', 'Informe'), ('conclusion', 'Conclusión'))},
            apendices=[], signatures=signatures)
        document = dict(
            patient=dict(name=' '.join(filter(None, [row['surname'], row['name']])),
                identifier=row['patientid'], national_code=row['nationalcode']),
            study=dict(description=row['study_type'], accession_number=row['localacc'],
                date=row['createdon'].isoformat() if row['createdon'] else None,
                referring=row['requestingphysician_name']),
            institution=dict(name=row['institution_name'], address=row['address'], phone=row['phone'],
                email=row['mail'], logo=inline_image(row['logo_path'] or os.getenv('NEXTRIS_INSTITUTION_LOGO'))), signatures=signatures)
        from apps.services.veterinary import mode as patient_mode, report_context
        if patient_mode() == 'veterinary':
            context = report_context(connection, exam_id)
            if context:
                document['veterinary'] = context
                document['patient']['name'] = context['name']
                document['patient']['identifier'] = context['patientid']
        return dict(source='nextris', report=report, document=document)
    finally:
        if owned:
            connection.close()


def report_view_text(report):
    parts = [report.get('procedimientos'), report.get('fecha'), report.get('profesional'), report.get('accession_number')]
    for key, section in report.get('textos', {}).items():
        parts.append(f"{section.get('as') or key}\n{plain_report_text(section.get('contenido'))}")
    return '\n\n'.join(str(part) for part in parts if part)


def report_view_response(exam_id):
    from flask import Response, jsonify
    try:
        report = resolve_report_view(exam_id)['report']
    except ReportViewUnavailable as error:
        return jsonify(success=False, message=str(error), code=error.code), error.status
    response = Response('<!doctype html><html lang="es"><meta charset="utf-8"><title>Informe · NextRIS</title><pre>'
                        + escape(report_view_text(report)) + '</pre></html>', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'self'"
    return response


def resolve_authorized_report_view(exam_id):
    """Patient JWTs use ownership; staff JWTs require a clinical read permission."""
    from flask_jwt_extended import get_jwt, get_jwt_identity
    from apps.api.permissions import get_user_permission_codes
    if str(get_jwt().get('user_type', '')).lower() == 'patient':
        from apps.services.patient_report_document import resolve_patient_report_view
        return resolve_patient_report_view(exam_id, get_jwt_identity())
    permissions = set(get_user_permission_codes(get_jwt_identity(), include_role_permissions=True))
    if not permissions.intersection({'*', 'reports.write', 'patients.view', 'distribution.view', 'tabs.worklist.view'}):
        raise ReportViewUnavailable('No tiene permiso para consultar informes', 'FORBIDDEN', 403)
    return resolve_report_view(exam_id)
