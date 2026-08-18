# -*- encoding: utf-8 -*-
"""Hanging protocols personales y handoff limitado para NextViewer."""

from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets
import uuid

import psycopg2
import psycopg2.extras
import requests
from flask import jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required

from apps.api import api_blueprint
from apps.home.services import ConfigService


MODALITIES = {'CT','MR','CR','DX','MG','US','XA','RF','NM','PT','SC','OT'}
LAYOUT_SLOTS = {'1x1': 1, '1x2': 2, '2x1': 2, '2x2': 4, 'mpr': 1}
ALLOWED_MATCH_KEYS = {
    'modality', 'descriptionIncludes', 'descriptionExcludes', 'laterality',
    'viewPosition', 'bodyPart', 'seriesNumberMin', 'seriesNumberMax',
}
DICOM_UID = re.compile(r'^[0-9]+(?:\.[0-9]+)+$')


def _connection():
    return psycopg2.connect(**ConfigService.get_db_config())


def _viewer_claims_required():
    claims = get_jwt()
    if claims.get('token_use') != 'nextviewer' or 'hanging-protocols' not in claims.get('scopes', []):
        return jsonify({'success': False, 'message': 'La sesión no habilita protocolos personales'}), 403
    if str(claims.get('user_type', '')).lower() == 'patient':
        return jsonify({'success': False, 'message': 'Los pacientes no pueden modificar protocolos'}), 403
    return None


def _normalize_strings(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError('Las reglas de texto deben ser listas de hasta 20 valores')
    result = []
    for entry in value:
        text = str(entry).strip().upper()
        if not text or len(text) > 80:
            raise ValueError('Una regla de texto no es válida')
        result.append(text)
    return result


def _validate_payload(data):
    if not isinstance(data, dict):
        raise ValueError('El cuerpo debe ser un objeto JSON')
    name = str(data.get('name', '')).strip()
    modality = str(data.get('modality', '')).strip().upper()
    layout = str(data.get('layout', '')).strip().lower()
    rules = data.get('viewportRules')
    if not name or len(name) > 80:
        raise ValueError('El nombre es requerido y admite hasta 80 caracteres')
    if modality not in MODALITIES or layout not in LAYOUT_SLOTS:
        raise ValueError('Modalidad o layout no válido')
    if layout == 'mpr' and modality not in {'CT', 'MR'}:
        raise ValueError('MPR sólo está disponible para CT y MR')
    if not isinstance(rules, list) or len(rules) != LAYOUT_SLOTS[layout]:
        raise ValueError('La cantidad de viewports no corresponde al layout')
    normalized = []
    seen_slots = set()
    for raw in rules:
        if not isinstance(raw, dict) or not isinstance(raw.get('match', {}), dict):
            raise ValueError('Una regla de viewport no es válida')
        slot = raw.get('slot')
        if not isinstance(slot, int) or slot < 0 or slot >= LAYOUT_SLOTS[layout] or slot in seen_slots:
            raise ValueError('Los slots deben ser únicos y correlativos')
        seen_slots.add(slot)
        match = raw.get('match', {})
        if set(match) - ALLOWED_MATCH_KEYS:
            raise ValueError('La regla contiene campos no admitidos')
        normalized_match = {}
        match_modality = str(match.get('modality', modality)).strip().upper()
        if match_modality not in MODALITIES:
            raise ValueError('La modalidad del viewport no es válida')
        normalized_match['modality'] = match_modality
        for key in ('descriptionIncludes','descriptionExcludes','laterality','viewPosition','bodyPart'):
            values = _normalize_strings(match.get(key))
            if values:
                normalized_match[key] = values
        for key in ('seriesNumberMin', 'seriesNumberMax'):
            if match.get(key) is not None:
                value = int(match[key])
                if value < -32768 or value > 32767:
                    raise ValueError('El número de serie está fuera de rango')
                normalized_match[key] = value
        if normalized_match.get('seriesNumberMin', -32768) > normalized_match.get('seriesNumberMax', 32767):
            raise ValueError('El rango de serie no es válido')
        normalized.append({'slot': slot, 'label': str(raw.get('label', '')).strip()[:40], 'match': normalized_match})
    return {
        'name': name, 'modality': modality, 'layout': layout,
        'is_active': bool(data.get('isActive', False)),
        'viewport_rules': sorted(normalized, key=lambda entry: entry['slot']),
    }


def _serialize(row):
    return {
        'id': str(row['guid']), 'name': row['name'], 'modality': row['modality'],
        'layout': row['layout'], 'isActive': row['is_active'], 'source': 'user',
        'viewportRules': row['viewport_rules'],
    }


def _request_dicom_token():
    response = requests.post(os.environ['VIEWER_KEYCLOAK_TOKEN_URL'], data={
        'client_id': os.environ['VIEWER_KEYCLOAK_CLIENT_ID'],
        'grant_type': 'password',
        'username': os.environ['VIEWER_KEYCLOAK_USERNAME'],
        'password': os.environ['VIEWER_KEYCLOAK_PASSWORD'],
        'scope': 'openid profile email',
    }, timeout=10, verify=os.environ.get('VIEWER_KEYCLOAK_VERIFY_TLS', 'false').lower() == 'true')
    response.raise_for_status()
    return response.json()


@api_blueprint.route('/viewer/session/exchange', methods=['POST'])
def exchange_viewer_session():
    data = request.get_json(silent=True) or {}
    code = str(data.get('code', '')).strip()
    study_iuid = str(data.get('studyInstanceUID', '')).strip()
    if len(code) < 32 or len(code) > 256 or not DICOM_UID.fullmatch(study_iuid):
        return jsonify({'success': False, 'message': 'El handoff no es válido'}), 400
    digest = hashlib.sha256(code.encode()).hexdigest()
    connection = _connection()
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("""
                SELECT code_hash, user_id, study_iuid, user_type, expires_at, consumed_at
                FROM nextris.tb_viewer_handoff WHERE code_hash = %s FOR UPDATE
            """, (digest,))
            handoff = cursor.fetchone()
            now = datetime.now(timezone.utc)
            if not handoff or handoff['study_iuid'] != study_iuid or handoff['consumed_at'] or handoff['expires_at'] <= now:
                connection.rollback()
                return jsonify({'success': False, 'message': 'El handoff venció o ya fue utilizado'}), 401
            cursor.execute("UPDATE nextris.tb_viewer_handoff SET consumed_at = NOW() WHERE code_hash = %s", (digest,))
            connection.commit()

        dicom_token = _request_dicom_token()
        is_patient = str(handoff['user_type']).lower() == 'patient'
        scopes = ['viewer-session'] if is_patient else ['viewer-session', 'hanging-protocols']
        viewer_token = create_access_token(
            identity=handoff['user_id'], expires_delta=timedelta(hours=8),
            additional_claims={
                'token_use': 'nextviewer', 'scopes': scopes,
                'user_type': handoff['user_type'], 'study_iuid': study_iuid,
            },
        )
        return jsonify({'success': True, 'data': {
            'dicomAccessToken': dicom_token['access_token'],
            'viewerAccessToken': viewer_token,
            'expiresIn': dicom_token.get('expires_in', 300),
            'viewerExpiresIn': 28800,
            'personalizationEnabled': not is_patient,
        }}), 200
    except (KeyError, requests.RequestException):
        return jsonify({'success': False, 'message': 'No se pudo iniciar la sesión DICOM'}), 502
    finally:
        connection.close()


@api_blueprint.route('/viewer/session/refresh', methods=['POST'])
@jwt_required()
def refresh_viewer_session():
    claims = get_jwt()
    study_iuid = str((request.get_json(silent=True) or {}).get('studyInstanceUID', '')).strip()
    if claims.get('token_use') != 'nextviewer' or 'viewer-session' not in claims.get('scopes', []):
        return jsonify({'success': False, 'message': 'La sesión no permite renovación'}), 403
    if not DICOM_UID.fullmatch(study_iuid) or study_iuid != claims.get('study_iuid'):
        return jsonify({'success': False, 'message': 'El estudio no corresponde a la sesión'}), 403
    try:
        dicom_token = _request_dicom_token()
        return jsonify({'success': True, 'data': {
            'dicomAccessToken': dicom_token['access_token'],
            'expiresIn': dicom_token.get('expires_in', 300),
        }}), 200
    except (KeyError, requests.RequestException):
        return jsonify({'success': False, 'message': 'No se pudo renovar la sesión DICOM'}), 502


@api_blueprint.route('/viewer/hanging-protocols', methods=['GET'])
@jwt_required()
def list_hanging_protocols():
    denied = _viewer_claims_required()
    if denied: return denied
    connection = _connection()
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("""
                SELECT guid, name, modality, layout, viewport_rules, is_active
                FROM nextris.tb_hanging_protocol WHERE user_id = %s
                ORDER BY modality, name
            """, (get_jwt_identity(),))
            return jsonify({'success': True, 'data': [_serialize(row) for row in cursor.fetchall()]}), 200
    finally:
        connection.close()


def _write_protocol(protocol_id=None):
    denied = _viewer_claims_required()
    if denied: return denied
    try:
        values = _validate_payload(request.get_json(silent=True))
    except (ValueError, TypeError) as error:
        return jsonify({'success': False, 'message': str(error)}), 400
    user_id = get_jwt_identity()
    connection = _connection()
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            if values['is_active']:
                cursor.execute("UPDATE nextris.tb_hanging_protocol SET is_active = FALSE, updated_on = NOW() WHERE user_id = %s AND modality = %s", (user_id, values['modality']))
            if protocol_id:
                cursor.execute("""
                    UPDATE nextris.tb_hanging_protocol SET name=%s, modality=%s, layout=%s,
                        viewport_rules=%s::jsonb, is_active=%s, updated_on=NOW()
                    WHERE guid=%s AND user_id=%s
                    RETURNING guid, name, modality, layout, viewport_rules, is_active
                """, (values['name'], values['modality'], values['layout'], psycopg2.extras.Json(values['viewport_rules']), values['is_active'], protocol_id, user_id))
            else:
                cursor.execute("""
                    INSERT INTO nextris.tb_hanging_protocol
                        (guid,user_id,name,modality,layout,viewport_rules,is_active)
                    VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                    RETURNING guid, name, modality, layout, viewport_rules, is_active
                """, (str(uuid.uuid4()), user_id, values['name'], values['modality'], values['layout'], psycopg2.extras.Json(values['viewport_rules']), values['is_active']))
            row = cursor.fetchone()
            if not row:
                connection.rollback()
                return jsonify({'success': False, 'message': 'Protocolo no encontrado'}), 404
            connection.commit()
            return jsonify({'success': True, 'data': _serialize(row)}), 200 if protocol_id else 201
    except psycopg2.errors.UniqueViolation:
        connection.rollback()
        return jsonify({'success': False, 'message': 'Ya existe un protocolo con ese nombre'}), 409
    finally:
        connection.close()


@api_blueprint.route('/viewer/hanging-protocols', methods=['POST'])
@jwt_required()
def create_hanging_protocol():
    return _write_protocol()


@api_blueprint.route('/viewer/hanging-protocols/<uuid:protocol_id>', methods=['PUT'])
@jwt_required()
def update_hanging_protocol(protocol_id):
    return _write_protocol(str(protocol_id))


@api_blueprint.route('/viewer/hanging-protocols/<uuid:protocol_id>', methods=['DELETE'])
@jwt_required()
def delete_hanging_protocol(protocol_id):
    denied = _viewer_claims_required()
    if denied: return denied
    connection = _connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM nextris.tb_hanging_protocol WHERE guid=%s AND user_id=%s", (str(protocol_id), get_jwt_identity()))
            if cursor.rowcount != 1:
                connection.rollback()
                return jsonify({'success': False, 'message': 'Protocolo no encontrado'}), 404
            connection.commit()
            return jsonify({'success': True, 'data': None}), 200
    finally:
        connection.close()


@api_blueprint.route('/viewer/hanging-protocols/deactivate', methods=['POST'])
@jwt_required()
def deactivate_hanging_protocols():
    denied = _viewer_claims_required()
    if denied: return denied
    modality = str((request.get_json(silent=True) or {}).get('modality', '')).upper()
    if modality not in MODALITIES:
        return jsonify({'success': False, 'message': 'Modalidad no válida'}), 400
    connection = _connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE nextris.tb_hanging_protocol SET is_active=FALSE, updated_on=NOW() WHERE user_id=%s AND modality=%s", (get_jwt_identity(), modality))
            connection.commit()
            return jsonify({'success': True, 'data': None}), 200
    finally:
        connection.close()
