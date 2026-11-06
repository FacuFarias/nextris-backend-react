"""Permission-protected management API for permanent PACS deletions."""
from functools import wraps
import logging

from flask import jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from psycopg2.extras import RealDictCursor
import psycopg2
import requests

from apps.api import api_blueprint
from apps.api.permissions import require_permission, user_has_permission_code
from apps.services import image_deletions as service

log = logging.getLogger(__name__)


def management(fn):
    @wraps(fn)
    @jwt_required()
    @require_permission('images.delete', include_role_permissions=True)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except service.DeletionError as exc:
            return jsonify(success=False, message=str(exc)), exc.status
        except requests.RequestException:
            return jsonify(success=False, message='No se pudo consultar el PACS'), 502
        except psycopg2.Error:
            log.exception('Image management database failure')
            return jsonify(success=False, message='No se pudo actualizar la operación; vuelva a consultar su estado'), 503
    return wrapper


def paging():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = max(1, min(100, int(request.args.get('per_page', 25))))
    except (TypeError, ValueError):
        raise service.DeletionError('Paginación inválida')
    return page, size


def identity():
    user_id = str(get_jwt_identity())
    return user_id, user_has_permission_code(user_id, '*', include_role_permissions=True)


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise service.DeletionError('Se requiere un objeto JSON')
    return value


@api_blueprint.route('/dicom/studies/<int:study_pk>/series', methods=['GET'])
@management
def deletion_series(study_pk):
    page, size = paging()
    with service.database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT 1 FROM nextris.available_pacs_study WHERE pk=%s', (study_pk,))
        if not cur.fetchone():
            raise service.DeletionError('Estudio sin imágenes disponibles', 404)
        cur.execute('SELECT count(*) AS total FROM nextris.available_pacs_series WHERE study_fk=%s', (study_pk,))
        total = cur.fetchone()['total']
        cur.execute("""SELECT sr.series_iuid AS series_uid, sr.series_no, sr.series_desc, sr.modality,
                       (SELECT count(*) FROM nextris.available_pacs_instance i WHERE i.series_fk=sr.pk) AS instance_count
                       FROM nextris.available_pacs_series sr WHERE sr.study_fk=%s
                       ORDER BY sr.series_no NULLS LAST, sr.series_iuid LIMIT %s OFFSET %s""",
                    (study_pk, size, (page-1)*size))
        return jsonify(success=True, data={'items': [dict(r) for r in cur.fetchall()],
                                          'total': total, 'page': page, 'per_page': size})


@api_blueprint.route('/dicom/studies/<int:study_pk>/series/<series_uid>/instances', methods=['GET'])
@management
def deletion_instances(study_pk, series_uid):
    page, size = paging()
    with service.database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT pk FROM nextris.available_pacs_series WHERE study_fk=%s AND series_iuid=%s',
                    (study_pk, series_uid))
        series = cur.fetchone()
        if not series:
            raise service.DeletionError('Serie no encontrada o sin imágenes disponibles', 404)
        cur.execute('SELECT count(*) AS total FROM nextris.available_pacs_instance WHERE series_fk=%s', (series['pk'],))
        total = cur.fetchone()['total']
        cur.execute("""SELECT sop_iuid AS sop_uid, inst_no AS instance_number, num_frames, sop_cuid AS sop_class_uid
                       FROM nextris.available_pacs_instance WHERE series_fk=%s
                       ORDER BY inst_no NULLS LAST, sop_iuid LIMIT %s OFFSET %s""",
                    (series['pk'], size, (page-1)*size))
        return jsonify(success=True, data={'items': [dict(r) for r in cur.fetchall()],
                                          'total': total, 'page': page, 'per_page': size})


@api_blueprint.route('/dicom/studies/<int:study_pk>/series/<series_uid>/instances/<sop_uid>/thumbnail', methods=['GET'])
@management
def deletion_thumbnail(study_pk, series_uid, sop_uid):
    with service.database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT s.study_iuid FROM nextris.available_pacs_instance i
                       JOIN public.series sr ON sr.pk=i.series_fk JOIN public.study s ON s.pk=sr.study_fk
                       WHERE s.pk=%s AND sr.series_iuid=%s AND i.sop_iuid=%s""", (study_pk, series_uid, sop_uid))
        row = cur.fetchone()
        if not row:
            raise service.DeletionError('Imagen no disponible', 404)
    pacs = service.PacsClient()
    upstream = pacs.request('GET', pacs.instance_url(row[0], series_uid, sop_uid) + '/rendered',
                            params={'viewport': '240,240'}, stream=True)
    try:
        if upstream.status_code != 200 or not upstream.headers.get('Content-Type', '').startswith('image/'):
            raise service.DeletionError('Miniatura no disponible para este objeto DICOM', 422)
        chunks, length = [], 0
        for chunk in upstream.iter_content(65536):
            length += len(chunk)
            if length > 2 * 1024 * 1024:
                raise service.DeletionError('La miniatura supera el tamaño permitido', 422)
            chunks.append(chunk)
        return Response(b''.join(chunks), content_type=upstream.headers['Content-Type'],
                        headers={'Cache-Control': 'no-store'})
    finally:
        upstream.close()


@api_blueprint.route('/dicom/rejection-reasons', methods=['GET'])
@management
def deletion_reasons():
    return jsonify(success=True, data=service.PacsClient().reasons())


@api_blueprint.route('/dicom/image-deletions/preview', methods=['POST'])
@management
def deletion_preview():
    user_id, wildcard = identity()
    operation_id = service.preview(body(), user_id)
    return jsonify(success=True, data=service.status(operation_id, user_id, wildcard)), 201


@api_blueprint.route('/dicom/image-deletions/<operation_id>/execute', methods=['POST'])
@management
def deletion_execute(operation_id):
    user_id, wildcard = identity()
    service.execute(operation_id, body(), user_id, wildcard)
    return jsonify(success=True, data=service.status(operation_id, user_id, wildcard)), 202


@api_blueprint.route('/dicom/image-deletions/<operation_id>', methods=['GET'])
@management
def deletion_status(operation_id):
    user_id, wildcard = identity()
    page, _ = paging()
    return jsonify(success=True, data=service.status(operation_id, user_id, wildcard, page))
