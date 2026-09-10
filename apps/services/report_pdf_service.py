"""On-demand report PDF rendering.

The renderer returns bytes only.  It deliberately has no filesystem output
path so every consumer receives a PDF generated from the current report data.
"""

from dataclasses import dataclass

import psycopg2


class ReportPdfNotAvailable(Exception):
    """Raised when an exam does not have a signed report."""


@dataclass(frozen=True)
class RenderedReportPdf:
    content: bytes
    filename: str


def _db_config():
    from apps.home.services.config_service import ConfigService
    return ConfigService.get_db_config()


def _safe_filename_part(value, fallback):
    text = str(value or '').strip().replace(' ', '_')
    text = ''.join(char for char in text if char.isalnum() or char in ('_', '-'))
    return text or fallback


def _report_metadata(exam_id):
    connection = psycopg2.connect(**_db_config())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT e.guid, COALESCE(e.isreported, 0), r.guid,
                   e.localacc, dp.patientid, dp.name, dp.surname
            FROM nextris.tbexamination e
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            LEFT JOIN nextris.datapatient dp ON dp.guid = e.idpatient
            WHERE e.guid = %s
            LIMIT 1
            """,
            (str(exam_id),),
        )
        row = cursor.fetchone()
        if not row or not row[1] or not row[2]:
            raise ReportPdfNotAvailable('REPORT_NOT_AVAILABLE')

        accession = _safe_filename_part(row[3], 'estudio')
        patient_id = _safe_filename_part(row[4], 'paciente')
        surname = _safe_filename_part(row[6], 'sin_apellido')
        name = _safe_filename_part(row[5], 'sin_nombre')
        return f'informe_{accession}_{patient_id}_{surname}_{name}.pdf'
    finally:
        cursor.close()
        connection.close()


def render_report_pdf(exam_id, *, filename=None):
    """Render a signed report into memory and return its bytes and filename."""
    output_filename = filename or _report_metadata(exam_id)

    # Imported lazily to avoid the historical home/api circular import during
    # application startup.  The controller function now returns bytes only.
    from apps.home.controllers.report_controller import generate_report_pdf_with_signature

    content = generate_report_pdf_with_signature(exam_id, pdf_filename=output_filename)
    if not content:
        raise ReportPdfNotAvailable('REPORT_NOT_AVAILABLE')
    if not isinstance(content, (bytes, bytearray)):
        raise RuntimeError('El renderizador de reportes no devolvió bytes')

    return RenderedReportPdf(bytes(content), output_filename)
