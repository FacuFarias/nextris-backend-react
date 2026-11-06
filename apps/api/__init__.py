# -*- encoding: utf-8 -*-
"""
API Blueprint para NextRIS - Endpoints REST para React
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

api_blueprint = Blueprint('api', __name__, url_prefix='/api')


@api_blueprint.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint para verificar que la API está funcionando
    """
    return jsonify({
        'success': True,
        'message': 'NextRIS API is running',
        'version': '1.0.0'
    }), 200


# Error handlers para JWT - devolver JSON en lugar de HTML
@api_blueprint.errorhandler(401)
def unauthorized_error(error):
    """Handler para errores 401 - Token inválido o ausente"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación requerido o inválido'
    }), 401


@api_blueprint.errorhandler(422)
def unprocessable_error(error):
    """Handler para errores 422 - Token mal formado"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación mal formado'
    }), 422


# Importar rutas DICOM
from apps.api import dicom_routes
from apps.api import image_deletions


# Importar las rutas después de crear el blueprint para evitar imports circulares
from apps.api import auth, patients, studies, admin, appointments, institutional, medical, reports, config, general, execution, admissions, images, transcription, distribution, patient_portal, templates, filter_presets, hanging_protocols, tags, analytics, external
from apps.permission_policy import DISABLED_MODULES

if 'nexi' not in DISABLED_MODULES:
    from apps.api import nexi
from apps.api.integration import orders, hl7_oru
from apps.api import presentation_states
from apps.api import key_images
