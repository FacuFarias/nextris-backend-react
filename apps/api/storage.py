"""PACS storage monitoring and safe local cache management."""
from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
import requests

from apps.api import api_blueprint
from apps.api.permissions import require_permission
from apps.services import storage_monitor, storage_cache

ALLOWED_DAYS = (7, 30, 90, 365)


def _days():
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        days = 30
    return days if days in ALLOWED_DAYS else 30


def _respond(builder):
    # A viewer token is scoped to one study; it must not reach system-wide figures.
    if get_jwt().get('token_use'):
        return jsonify(success=False, message='Esta operación requiere una sesión de NextRIS'), 403
    try:
        response = jsonify(success=True, data=builder(), message='')
        response.headers['Cache-Control'] = 'no-store'
        return response
    except storage_cache.CacheError as exc:
        return jsonify(success=False, message=str(exc)), exc.status
    except requests.RequestException:
        current_app.logger.exception('Storage PACS request failed')
        return jsonify(success=False, message='No se pudo contactar al PACS. Actualizá el listado para comprobar el estado.'), 502
    except Exception:
        current_app.logger.exception('Storage monitoring failed')
        return jsonify(success=False, message='No se pudo obtener el estado del almacenamiento'), 500


@api_blueprint.route('/storage/overview', methods=['GET'])
@jwt_required()
@require_permission('storage.view')
def storage_overview():
    return _respond(lambda: storage_monitor.overview(_days()))


@api_blueprint.route('/storage/history', methods=['GET'])
@jwt_required()
@require_permission('storage.view')
def storage_history():
    return _respond(lambda: storage_monitor.history(_days()))


@api_blueprint.route('/storage/cache/studies', methods=['GET'])
@jwt_required()
@require_permission('storage.view')
def storage_cache_studies():
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = max(1, min(100, int(request.args.get('per_page', 25))))
    except ValueError:
        return jsonify(success=False, message='Paginación inválida'), 400
    search = request.args.get('search', '').strip()[:200]
    return _respond(lambda: storage_cache.studies(page, per_page, search))


@api_blueprint.route('/storage/cache/studies/<int:study_pk>', methods=['DELETE'])
@jwt_required()
@require_permission('storage.view')
@require_permission('storage.manage')
def storage_cache_remove(study_pk):
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('confirm') is not True:
        return jsonify(success=False, message='Confirmá la eliminación de la copia local'), 400
    if study_pk > 2147483647:
        return jsonify(success=False, message='Identificador inválido'), 400
    return _respond(lambda: storage_cache.remove(study_pk, body.get('storage'), str(get_jwt_identity())))
