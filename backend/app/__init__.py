import logging
from time import perf_counter

import colorlog
from flask import Flask, g, request
from flask_compress import Compress
from flask_cors import CORS
from sqlalchemy import event, text

from config import config
from app import commands
from app.extensions import cache, db, migrate

_compress = Compress()


def create_app(config_name='default'):
    app = Flask(__name__, static_folder=None, template_folder=None)

    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    configure_database(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    _compress.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', [])}},
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization', 'X-CSRF-Token', 'X-Request-ID', 'X-Trace-ID'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        max_age=86400,
    )

    configure_logging(app)
    configure_request_metrics(app)
    configure_audit(app)
    configure_tracing(app)
    register_api_blueprints(app)
    register_error_handlers(app)
    register_commands(app)
    register_root(app)
    register_health(app)

    return app


def register_api_blueprints(app):
    from app.api import api_bp
    app.register_blueprint(api_bp)


def configure_database(app):
    if not str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite'):
        return

    with app.app_context():
        engine = db.engine

        @event.listens_for(engine, 'connect')
        def set_sqlite_pragmas(connection, _record):
            cursor = connection.cursor()
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

        with engine.connect() as connection:
            connection.execute(text('PRAGMA journal_mode=WAL'))
            connection.execute(text('PRAGMA synchronous=NORMAL'))
            connection.execute(text('PRAGMA busy_timeout=30000'))


def register_error_handlers(app):
    from app.api.responses import api_error

    @app.errorhandler(403)
    def forbidden(e):
        return api_error('权限不足', status=403, error='forbidden')

    @app.errorhandler(404)
    def page_not_found(e):
        message = '接口不存在' if request.path.startswith('/api/') else 'NEXUS 后端仅提供 REST API'
        return api_error(message, status=404, error='not_found')

    @app.errorhandler(413)
    def too_large(e):
        return api_error('请求体过大', status=413, error='payload_too_large')

    @app.errorhandler(429)
    def rate_limited(e):
        return api_error('请求过于频繁，请稍后再试', status=429, error='rate_limited')

    @app.errorhandler(500)
    def internal_server_error(e):
        return api_error('服务器内部错误', status=500, error='internal_error')


def register_commands(app):
    app.cli.add_command(commands.forge)
    app.cli.add_command(commands.seed_enterprise)
    app.cli.add_command(commands.audit_enterprise_data)
    app.cli.add_command(commands.events_dispatch)
    app.cli.add_command(commands.events_retry_failed)
    app.cli.add_command(commands.events_worker)
    app.cli.add_command(commands.openapi_export)
    app.cli.add_command(commands.status)
    if hasattr(commands, 'forge_finance'):
        app.cli.add_command(commands.forge_finance)


def register_root(app):
    @app.get('/')
    def root_health():
        from app.api.responses import api_success
        from app.services.health_service import service_health
        health = service_health(include_database=False)
        return api_success({
            'service': 'NEXUS API',
            'api_base': '/api/v1',
            'status': health['status'],
            'ai': health['ai'],
            'storage': health['storage'],
        }, 'NEXUS 后端 API 正常运行')


def register_health(app):
    @app.get('/health/live')
    def health_live():
        return {'status': 'ok'}, 200

    @app.get('/health/ready')
    def health_ready():
        try:
            db.session.execute(text('SELECT 1'))
            return {'status': 'ready'}, 200
        except Exception:
            return {'status': 'not_ready', 'error': 'database_unavailable'}, 503


def configure_request_metrics(app):
    from app.platform.observability import (
        REQUEST_ID_HEADER,
        TRACE_ID_HEADER,
        install_request_context,
        record_http_request,
    )
    from app.platform.observability.logging import request_log_extra

    install_request_context(app)

    @app.after_request
    def add_response_metrics(response):
        started = getattr(g, 'request_started_at', None)
        elapsed_ms = 0
        if started is not None:
            elapsed_ms = int(max((perf_counter() - started) * 1000, 0))
            response.headers['X-Response-Time-Ms'] = str(elapsed_ms)
        response.headers.setdefault(REQUEST_ID_HEADER, getattr(g, 'request_id', ''))
        response.headers.setdefault(TRACE_ID_HEADER, getattr(g, 'trace_id', ''))
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        record_http_request(request.method, request.path, response.status_code, elapsed_ms)
        user = getattr(g, 'api_user', None)
        app.logger.info(
            'http_request',
            extra=request_log_extra(
                request_id=getattr(g, 'request_id', None),
                trace_id=getattr(g, 'trace_id', None),
                tenant_id=getattr(g, 'tenant_id', None),
                user_id=getattr(user, 'id', None),
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=elapsed_ms,
                operation=request.endpoint,
            ),
        )
        return response


def configure_tracing(app):
    from app.platform.observability import configure_tracing as configure_observability_tracing

    configure_observability_tracing(app, db=db)


def configure_audit(app):
    from app.platform.audit import install_audit_middleware

    install_audit_middleware(app)


def configure_logging(app):
    level = getattr(logging, str(app.config.get('LOG_LEVEL', 'INFO')).upper(), logging.INFO)
    if not app.debug:
        from app.platform.observability.logging import JsonRequestFormatter

        formatter = JsonRequestFormatter()
        if not app.logger.handlers:
            app.logger.addHandler(logging.StreamHandler())
        for handler in app.logger.handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
        app.logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={'DEBUG': 'cyan', 'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red', 'CRITICAL': 'red,bg_white'},
        style='%'
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
