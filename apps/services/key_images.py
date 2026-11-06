"""Key image files: immutable PNGs outside the releases, located only through their database row."""
import logging
import os
from pathlib import Path
import re

import psycopg2

logger = logging.getLogger(__name__)
REFERENCE = re.compile(r'data-key-image-id=')


def key_image_root():
    return Path(os.getenv('NEXTRIS_KEY_IMAGE_ROOT', str(Path(__file__).resolve().parents[2] / 'uploads_dicom' / 'key-images')))


def key_image_path(image_id):
    return key_image_root() / f'{image_id}.png'


def key_images_for_report(view):
    """Files a report may embed: only its own study's, including images hidden from the panel."""
    sections = view['report'].get('textos', {}).values()
    if not any(REFERENCE.search(str(section.get('contenido') or '')) for section in sections):
        return {}
    from apps.home.services.config_service import ConfigService
    try:
        connection = psycopg2.connect(**ConfigService.get_db_config())
        try:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT k.id::text FROM nextris.tb_key_image k
                    JOIN nextris.tbexamination e ON e.studyinstanceuid = k.study_iuid WHERE e.guid = %s""",
                               (str(view['report']['id_informe']),))
                return {row[0]: key_image_path(row[0]) for row in cursor.fetchall()}
        finally:
            connection.close()
    except psycopg2.Error:
        # A clinical report must still open; the PDF marks each image as unavailable.
        logger.exception('No se pudieron resolver las imágenes clave del informe')
        return {}
