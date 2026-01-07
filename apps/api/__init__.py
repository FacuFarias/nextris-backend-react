# -*- encoding: utf-8 -*-
"""
API Blueprint para NextRIS - Endpoints REST para React
"""

from flask import Blueprint, jsonify

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


# Importar las rutas después de crear el blueprint para evitar imports circulares
from apps.api import auth, patients, studies, admin, appointments, institutional, medical, reports, config, general, execution, admissions, images, transcription
