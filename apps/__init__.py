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

    # Delayed Clínica Parque transmissions are persisted in PostgreSQL and
    # claimed safely by whichever Gunicorn worker is available.
    try:
        from apps.services.clinicaparque_report_queue import start_report_queue_worker
        start_report_queue_worker()
    except Exception as error:
        print(f"[WARNING] Could not start Clínica Parque report queue: {error}")

    if enable_legacy_ui:
        for module_name in ('authentication', 'home'):
            module = import_module('apps.{}.routes'.format(module_name))
            app.register_blueprint(module.blueprint)


def setup_analytics_middleware(app):
    """
    Registra before/after_request hooks para capturar métricas de uso.
    Falla silenciosamente para no interrumpir ninguna petición.
    """
    import time
    from flask import g, request as flask_request

    @app.before_request
    def _analytics_before():
        g._analytics_start = time.monotonic()

    @app.after_request
    def _analytics_after(response):
        try:
            _record_request_event(app, flask_request, response, g)
        except Exception:
            pass
        return response


def _get_real_ip(req) -> str:
    """
    Returns the real client IP, respecting X-Forwarded-For from trusted proxies.
    Nginx forwards this header (see appseed-app.conf).
    """
    forwarded_for = req.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Take the leftmost (original client) IP
        return forwarded_for.split(",")[0].strip()
    return req.remote_addr or ""


def _get_jwt_user_id(req) -> tuple:
    """
    Tries to extract (user_id, facility_id) from the Bearer token without
    requiring auth (optional=True). Returns (None, None) on any failure.
    """
    try:
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if not identity:
            return None, None
        if isinstance(identity, dict):
            user_id = (
                identity.get("id")
                or identity.get("guid")
                or identity.get("user_id")
            )
            facility_id = identity.get("facility_id")
        else:
            user_id = str(identity)
            facility_id = None
        if not facility_id:
            claims = get_jwt()
            facility_id = claims.get("facility_id") or claims.get("activeFacilityId")
        return user_id, facility_id
    except Exception:
        return None, None


def _record_request_event(app, req, response, g_ctx) -> None:
    """Core recording logic — called from after_request."""
    import time

    if not app.config.get("ANALYTICS_ENABLED", True):
        return

    path = req.path or ""
    exclude_prefixes = app.config.get(
        "ANALYTICS_EXCLUDE_PREFIXES", ["/api/health", "/api/analytics", "/static"]
    )
    if any(path.startswith(p) for p in exclude_prefixes):
        return

    # Duration
    start = getattr(g_ctx, "_analytics_start", None)
    duration_ms = int((time.monotonic() - start) * 1000) if start is not None else None

    # IP
    store_ip = app.config.get("ANALYTICS_STORE_IP", True)
    ip = _get_real_ip(req) if store_ip else None

    # Session-id forwarded by the frontend as X-Session-ID header
    session_id = req.headers.get("X-Session-ID")

    # User / facility from JWT
    user_id, facility_id = _get_jwt_user_id(req)

    user_agent = req.headers.get("User-Agent", "")

    from apps.home.services.analytics_service import record_event
    record_event(
        event_type="api_request",
        user_id=user_id,
        session_id=session_id,
        facility_id=facility_id,
        route=path,
        http_method=req.method,
        http_status=response.status_code,
        duration_ms=duration_ms,
        ip_address=ip,
        user_agent=user_agent,
        run_geo_async=app.config.get("ANALYTICS_GEO_LOOKUP", True),
    )


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

    # ProxyFix: trust 1 proxy level so X-Forwarded-For gives the real client IP
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    setup_analytics_middleware(app)

    return app
