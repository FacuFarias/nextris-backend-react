# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from importlib import import_module


db = SQLAlchemy()
login_manager = LoginManager()
jwt = JWTManager()


def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)


def register_context_processors(app):
    """Registra funciones globales para usar en templates"""
    from apps.home.utils.helpers import user_has_permission, get_current_user_permissions
    
    @app.context_processor
    def inject_permissions():
        return {
            'user_has_permission': user_has_permission,
            'get_current_user_permissions': get_current_user_permissions
        }


def register_blueprints(app, enable_legacy_ui=False):
    # La API debe estar siempre disponible para frontend React y clientes externos.
    from apps.api import api_blueprint
    from apps.home.controllers.structured_reports_controller import structured_reports_bp

    app.register_blueprint(api_blueprint)
    app.register_blueprint(structured_reports_bp)

    if enable_legacy_ui:
        for module_name in ('authentication', 'home'):
            module = import_module('apps.{}.routes'.format(module_name))
            app.register_blueprint(module.blueprint)


def configure_database(app):

    # Flask 2.2+ ya no soporta before_first_request, usar with app.app_context()
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error creating database tables: {e}")
            
            # fallback to SQLite
            basedir = os.path.abspath(os.path.dirname(__file__))
            app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
            
            print('> Fallback to SQLite ')
            try:
                db.create_all()
            except Exception as fallback_e:
                print(f'> SQLite fallback failed: {fallback_e}')
            db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)

    enable_legacy_ui = app.config.get('ENABLE_LEGACY_UI', False)

    register_extensions(app)
    if enable_legacy_ui:
        register_context_processors(app)
    register_blueprints(app, enable_legacy_ui=enable_legacy_ui)
    configure_database(app)
    return app
