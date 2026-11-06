"""Patient ownership and public-link guards for local reports."""

import base64
from io import BytesIO
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import psycopg2
from apps.services.report_view_service import ReportViewUnavailable, resolve_report_view

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def inline_image(value, *, signature=False):
    """Read only configured local image directories, never URLs or arbitrary files."""
    if not value:
        return None
    allowed = PROJECT_ROOT / ('media/firmas' if signature else 'apps/static/assets/img')
    path = Path(str(value))
    if not path.is_absolute():
        path = allowed / path if signature and len(path.parts) == 1 else PROJECT_ROOT / path
    try:
        path = path.resolve()
        if not path.is_relative_to(allowed.resolve()) or path.stat().st_size > 5 * 1024 * 1024:
            return None
        with Image.open(path) as image:
            if image.width * image.height > 16_000_000:
                return None
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.convert('RGBA').save(output, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None



def resolve_patient_report_view(exam_id, patient_user_id):
    from apps.home.services.config_service import ConfigService
    connection = psycopg2.connect(**ConfigService.get_db_config())
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM nextris.tbuser_patient up
                JOIN nextris.tbexamination e ON e.idpatient = up.datapatient_id
                WHERE up.guid = %s AND e.guid = %s
                  AND COALESCE(e.hidden_in_portal, 0) = 0
            """, (str(patient_user_id), str(exam_id)))
            if not cursor.fetchone():
                raise ReportViewUnavailable('Informe no encontrado')
        return resolve_report_view(exam_id, connection=connection)
    finally:
        connection.close()


def resolve_case_report_view(study_uid):
    """Called only after validation of a token authorizing this exact study."""
    from apps.home.services.config_service import ConfigService
    connection = psycopg2.connect(**ConfigService.get_db_config())
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT guid FROM nextris.tbexamination
                WHERE studyinstanceuid = %s AND COALESCE(hidden_in_portal, 0) = 0
                ORDER BY createdon DESC LIMIT 1
            """, (str(study_uid),))
            row = cursor.fetchone()
            if not row:
                raise ReportViewUnavailable('Informe no encontrado')
        return resolve_report_view(row[0], connection=connection)
    finally:
        connection.close()
