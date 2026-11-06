"""Authenticated PR ownership and exact-instance IOCM deletion for NextViewer."""
from io import BytesIO
import re
import uuid
from urllib.parse import quote

import pydicom
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from flask import jsonify, request, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from apps.api import api_blueprint
from apps.api.permissions import get_user_permission_codes
from apps.home.services import ConfigService
from apps.services.image_deletions import PacsClient

GSPS = '1.2.840.10008.5.1.4.1.1.11.1'
DELETE_PERMISSION = 'images.presentation_states.delete_any'
UID = re.compile(r'^[0-9]+(?:\.[0-9]+)+$')


class PRError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def _connection():
    return psycopg2.connect(**ConfigService.get_db_config())


def _uid(value):
    if not isinstance(value, str) or len(value) > 64 or not UID.fullmatch(value):
        raise PRError('Identificador DICOM no válido')
    return value


def may_delete(owner_id, user_id, permissions):
    return bool(owner_id and owner_id == user_id) or '*' in permissions or DELETE_PERMISSION in permissions


def _actor(connection, study):
    claims = get_jwt()
    if (claims.get('token_use') != 'nextviewer' or 'viewer-session' not in claims.get('scopes', [])
            or str(claims.get('user_type', '')).lower() == 'patient' or claims.get('study_iuid') != study):
        raise PRError('Abra el estudio desde una sesión de personal de NextRIS', 403)
    user_id = get_jwt_identity()
    with connection.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT guid, username, name, surname FROM nextris.tbuser WHERE guid=%s AND isactive=1', (user_id,))
        user = cur.fetchone()
    if not user:
        raise PRError('El usuario no está activo', 403)
    permissions = get_user_permission_codes(user_id, connection=connection)
    if '*' not in permissions and 'images.view' not in permissions:
        raise PRError('El usuario no tiene permiso para ver imágenes', 403)
    author = ' '.join(filter(None, [user['name'], user['surname']])).strip() or user['username']
    return user_id, author, permissions


def _error(error):
    if isinstance(error, PRError):
        return jsonify(success=False, message=error.message), error.status
    current_app.logger.exception('Presentation State operation failed')
    return jsonify(success=False, message='No se pudo completar la operación del PR en el PACS'), 502


def _metadata(row, user_id, permissions):
    return dict(sopInstanceUID=row['sop_iuid'], authorName=row.get('author_name') or 'Autor no registrado',
                canDelete=may_delete(row.get('owner_id'), user_id, permissions),
                deleted=bool(row.get('deleted_at')))


@api_blueprint.route('/viewer/presentation-states/<study>', methods=['GET'])
@jwt_required()
def presentation_state_metadata(study):
    connection = _connection()
    try:
        _uid(study)
        user_id, _, permissions = _actor(connection, study)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT i.sop_iuid, p.owner_id, p.author_name, p.deleted_at
                FROM public.instance i JOIN public.series sr ON sr.pk=i.series_fk
                JOIN public.study s ON s.pk=sr.study_fk
                LEFT JOIN nextris.tb_viewer_presentation_state p ON p.sop_iuid=i.sop_iuid
                WHERE s.study_iuid=%s AND sr.modality='PR' AND i.sop_cuid=%s
                UNION
                SELECT sop_iuid, owner_id, author_name, deleted_at
                FROM nextris.tb_viewer_presentation_state WHERE study_iuid=%s
            """, (study, GSPS, study))
            rows = cur.fetchall()
        return jsonify(success=True, data=[_metadata(row, user_id, permissions) for row in rows])
    except (PRError, requests.RequestException, psycopg2.Error) as error:
        return _error(error)
    finally:
        connection.close()


def _read_pr(study):
    # A PR contains vector graphics, never image pixels. Bound untrusted uploads.
    if request.mimetype != 'application/dicom':
        raise PRError('Se requiere un archivo DICOM PR', 415)
    body = request.stream.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise PRError('El PR supera el tamaño permitido', 413)
    try:
        ds = pydicom.dcmread(BytesIO(body))
        if str(ds.SOPClassUID) != GSPS or str(ds.Modality) != 'PR' or 'PixelData' in ds:
            raise PRError('Solo se admiten Presentation States GSPS')
        if str(ds.StudyInstanceUID) != study:
            raise PRError('El PR no corresponde al estudio autorizado', 403)
        _uid(str(ds.SOPInstanceUID)); _uid(str(ds.SeriesInstanceUID))
        references = [(str(series.SeriesInstanceUID), str(image.ReferencedSOPInstanceUID))
                      for series in ds.ReferencedSeriesSequence for image in series.ReferencedImageSequence]
        if not references:
            raise PRError('El PR no referencia ninguna imagen')
        return ds, references
    except (AttributeError, KeyError, ValueError, pydicom.errors.InvalidDicomError) as error:
        raise PRError('El archivo PR no es válido') from error


def _verify_stow(response, sop):
    if not response.ok:
        raise PRError('El PACS rechazó el guardado del PR', 502)
    try:
        payload = response.json()
        if isinstance(payload, list):
            payload = payload[0]
        success = payload.get('00081199', {}).get('Value', [])
        failed = payload.get('00081198', {}).get('Value', [])
        if failed or not any(item.get('00081155', {}).get('Value', [None])[0] == sop for item in success):
            raise PRError('El PACS no confirmó el almacenamiento del PR', 502)
    except (ValueError, TypeError, IndexError, AttributeError) as error:
        raise PRError('El PACS no confirmó el almacenamiento del PR', 502) from error


@api_blueprint.route('/viewer/presentation-states/<study>', methods=['POST'])
@jwt_required()
def save_presentation_state(study):
    connection = _connection()
    try:
        _uid(study)
        user_id, author, permissions = _actor(connection, study)
        ds, references = _read_pr(study)
        sop, series = str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            for ref_series, ref_sop in references:
                cur.execute("""SELECT 1 FROM nextris.available_pacs_instance i
                    JOIN public.series sr ON sr.pk=i.series_fk JOIN public.study s ON s.pk=sr.study_fk
                    WHERE s.study_iuid=%s AND sr.series_iuid=%s AND i.sop_iuid=%s AND sr.modality <> 'PR'""",
                            (study, ref_series, ref_sop))
                if not cur.fetchone():
                    raise PRError('La imagen referenciada no pertenece al estudio o no está disponible', 403)
            # Never allow a client to claim a pre-existing, unowned PACS object.
            cur.execute('SELECT 1 FROM public.instance WHERE sop_iuid=%s', (sop,))
            exists = bool(cur.fetchone())
            cur.execute('SELECT * FROM nextris.tb_viewer_presentation_state WHERE sop_iuid=%s FOR UPDATE', (sop,))
            owned = cur.fetchone()
            if owned:
                if (owned['owner_id'] != user_id or owned['study_iuid'] != study
                        or owned['series_iuid'] != series or owned['deleted_at']):
                    raise PRError('Este identificador PR ya está utilizado', 409)
                if owned['saved_at']:
                    return jsonify(success=True, data=_metadata(owned, user_id, permissions))
            elif exists:
                raise PRError('Este identificador PR ya existe en el PACS', 409)
            else:
                cur.execute("""INSERT INTO nextris.tb_viewer_presentation_state
                    (sop_iuid,study_iuid,series_iuid,owner_id,author_name) VALUES (%s,%s,%s,%s,%s)""",
                            (sop, study, series, user_id, author))
        # Reserve ownership durably even if the remote acknowledgement is lost.
        connection.commit()
        ds.SpecificCharacterSet = 'ISO_IR 192'
        ds.ContentCreatorName = author.replace('^', ' ')[:64]
        output = BytesIO()
        pydicom.dcmwrite(output, ds, write_like_original=False)
        boundary = 'NextRIS-' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Type: application/dicom\r\n\r\n'.encode()
                + output.getvalue() + f'\r\n--{boundary}--\r\n'.encode())
        pacs = PacsClient()
        response = pacs.request('POST', pacs.base + '/studies/' + quote(study, safe=''), data=body,
                               headers={'Content-Type': f'multipart/related; type="application/dicom"; boundary={boundary}',
                                        'Accept': 'application/dicom+json'})
        _verify_stow(response, sop)
        with connection.cursor() as cur:
            cur.execute('UPDATE nextris.tb_viewer_presentation_state SET saved_at=now() WHERE sop_iuid=%s', (sop,))
        connection.commit()
        return jsonify(success=True, data=dict(sopInstanceUID=sop, authorName=author, canDelete=True, deleted=False)), 201
    except (PRError, requests.RequestException, psycopg2.Error) as error:
        connection.rollback()
        return _error(error)
    finally:
        connection.close()


@api_blueprint.route('/viewer/presentation-states/<study>/<sop>', methods=['DELETE'])
@jwt_required()
def delete_presentation_state(study, sop):
    connection = _connection()
    try:
        _uid(study); _uid(sop)
        user_id, _, permissions = _actor(connection, study)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            # Serialize operations without locking PACS rows needed by remote IOCM.
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (sop,))
            cur.execute("""SELECT i.sop_iuid, sr.series_iuid, i.sop_cuid, sr.modality
                FROM public.instance i JOIN public.series sr ON sr.pk=i.series_fk
                JOIN public.study s ON s.pk=sr.study_fk
                WHERE s.study_iuid=%s AND i.sop_iuid=%s""", (study, sop))
            target = cur.fetchone()
            if not target or target['modality'] != 'PR' or target['sop_cuid'] != GSPS:
                raise PRError('PR no encontrado', 404)
            cur.execute('SELECT * FROM nextris.tb_viewer_presentation_state WHERE sop_iuid=%s FOR UPDATE', (sop,))
            owned = cur.fetchone()
            if not may_delete(owned['owner_id'] if owned else None, user_id, permissions):
                raise PRError('Solo puede eliminar sus propios PR', 403)
            if owned and owned['deleted_at']:
                return jsonify(success=True)
            pacs = PacsClient()
            # Exact-instance IOCM rejection, matching existing PACS deletion policy.
            response = pacs.reject(study, target['series_iuid'], sop, '113001')
            if not response.ok:
                raise PRError('El PACS no confirmó la eliminación del PR', 502)
            cur.execute("""INSERT INTO nextris.tb_viewer_presentation_state
                (sop_iuid,study_iuid,series_iuid,owner_id,author_name,deleted_at,deleted_by)
                VALUES (%s,%s,%s,%s,%s,now(),%s)
                ON CONFLICT (sop_iuid) DO UPDATE SET deleted_at=now(),deleted_by=EXCLUDED.deleted_by""",
                        (sop, study, target['series_iuid'], '', 'Autor no registrado', user_id))
        connection.commit()
        return jsonify(success=True)
    except (PRError, requests.RequestException, psycopg2.Error) as error:
        connection.rollback()
        return _error(error)
    finally:
        connection.close()
