"""Read-only PACS storage monitoring for administrators (Gestión → Almacenamiento)."""
from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from apps.api import api_blueprint
from apps.api.permissions import require_permission
from apps.services import storage_monitor

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
        return jsonify(success=True, data=builder(), message='')
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
