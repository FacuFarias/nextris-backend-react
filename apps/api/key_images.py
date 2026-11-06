"""Key images: created from a staff viewer session, used by the report editor and the report PDF."""
from io import BytesIO
import uuid

from flask import jsonify, request, send_file, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from PIL import Image
import psycopg2
from psycopg2.extras import RealDictCursor

from apps.api import api_blueprint
from apps.api.permissions import get_user_permission_codes, require_permission
from apps.api.presentation_states import PRError, _actor, _connection, _uid
from apps.services.key_images import key_image_path
from apps.services.medical_images import validate_medical_image


def _error(error):
    if isinstance(error, PRError):
        return jsonify(success=False, message=error.message), error.status
    current_app.logger.exception('Key image operation failed')
    return jsonify(success=False, message='No se pudo completar la operación con la imagen clave'), 500


def _staff_session():
    # A viewer token is scoped to one study; it must not reach other studies through these routes.
    if get_jwt().get('token_use'):
        raise PRError('Esta operación requiere una sesión de NextRIS', 403)


def _image_id(value):
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise PRError('Imagen clave no encontrada', 404) from error


def _read_source(study, connection):
    series, sop = request.args.get('series'), request.args.get('sop')
    if not series and not sop:
        return None, None, None
    if not series or not sop:
        raise PRError('La referencia a la imagen está incompleta')
    _uid(series), _uid(sop)
    with connection.cursor() as cur:
        cur.execute("""SELECT 1 FROM nextris.available_pacs_instance i
            JOIN public.series sr ON sr.pk=i.series_fk JOIN public.study s ON s.pk=sr.study_fk
            WHERE s.study_iuid=%s AND sr.series_iuid=%s AND i.sop_iuid=%s""", (study, series, sop))
        if not cur.fetchone():
            raise PRError('La imagen referenciada no pertenece al estudio o no está disponible', 403)
    frame = request.args.get('frame')
    if frame is not None and not (frame.isdecimal() and 0 < int(frame) < 100000):
        raise PRError('Fotograma no válido')
    return series, sop, int(frame) if frame else None


def _read_png():
    if request.mimetype != 'image/png':
        raise PRError('Se requiere una imagen PNG', 415)
    try:
        content, _ = validate_medical_image(request.stream, 'key-image.png')
    except ValueError as error:
        raise PRError(str(error)) from error
    with Image.open(BytesIO(content)) as image:
        if not image.width or not image.height:
            raise PRError('El archivo no es una imagen válida')
    return content


@api_blueprint.route('/viewer/key-images/<study>', methods=['POST'])
@jwt_required()
def create_key_image(study):
    connection = _connection()
    path = None
    try:
        _uid(study)
        user_id, author, _ = _actor(connection, study)
        series, sop, frame = _read_source(study, connection)
        content = _read_png()
        image_id = str(uuid.uuid4())
        path = key_image_path(image_id)
        with open(path, 'xb') as output:
            output.write(content)
        with connection.cursor() as cur:
            cur.execute("""INSERT INTO nextris.tb_key_image (id,study_iuid,series_iuid,sop_iuid,frame,owner_id,author_name)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""", (image_id, study, series, sop, frame, user_id, author))
        connection.commit()
        path = None
        return jsonify(success=True, data=dict(id=image_id, author_name=author)), 201
    except (PRError, psycopg2.Error, OSError) as error:
        connection.rollback()
        return _error(error)
    finally:
        if path:
            path.unlink(missing_ok=True)
        connection.close()


@api_blueprint.route('/key-images/study/<study>', methods=['GET'])
@jwt_required()
@require_permission('images.view')
def list_key_images(study):
    connection = _connection()
    try:
        _staff_session()
        _uid(study)
        user_id = get_jwt_identity()
        can_delete_any = '*' in get_user_permission_codes(user_id, connection=connection)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""SELECT id::text, owner_id, author_name, created_at FROM nextris.tb_key_image
                WHERE study_iuid=%s AND deleted_at IS NULL ORDER BY created_at""", (study,))
            rows = cur.fetchall()
        return jsonify(success=True, data=[dict(id=row['id'], author_name=row['author_name'], created_at=row['created_at'].isoformat(),
                                                can_delete=can_delete_any or row['owner_id'] == user_id) for row in rows])
    except (PRError, psycopg2.Error) as error:
        return _error(error)
    finally:
        connection.close()


@api_blueprint.route('/key-images/<image_id>/file', methods=['GET'])
@jwt_required()
@require_permission('images.view')
def key_image_file(image_id):
    connection = _connection()
    try:
        _staff_session()
        image_id = _image_id(image_id)
        # Deleted images are still served: reports that already use them keep showing them.
        with connection.cursor() as cur:
            cur.execute('SELECT 1 FROM nextris.tb_key_image WHERE id=%s', (image_id,))
            if not cur.fetchone():
                raise PRError('Imagen clave no encontrada', 404)
        path = key_image_path(image_id)
        if not path.is_file():
            raise PRError('Imagen clave no encontrada', 404)
        response = send_file(path, mimetype='image/png', max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        return response
    except (PRError, psycopg2.Error, OSError) as error:
        return _error(error)
    finally:
        connection.close()


@api_blueprint.route('/key-images/<image_id>', methods=['DELETE'])
@jwt_required()
@require_permission('images.view')
def delete_key_image(image_id):
    connection = _connection()
    try:
        _staff_session()
        image_id = _image_id(image_id)
        user_id = get_jwt_identity()
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT owner_id, deleted_at FROM nextris.tb_key_image WHERE id=%s FOR UPDATE', (image_id,))
            row = cur.fetchone()
            if not row or row['deleted_at']:
                raise PRError('Imagen clave no encontrada', 404)
            if row['owner_id'] != user_id and '*' not in get_user_permission_codes(user_id, connection=connection):
                raise PRError('Solo el autor puede eliminar esta imagen clave', 403)
            cur.execute('UPDATE nextris.tb_key_image SET deleted_at=now(), deleted_by=%s WHERE id=%s', (user_id, image_id))
        connection.commit()
        return jsonify(success=True, message='Imagen clave eliminada')
    except (PRError, psycopg2.Error) as error:
        connection.rollback()
        return _error(error)
    finally:
        connection.close()
