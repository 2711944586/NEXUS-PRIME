import logging
from time import perf_counter

import colorlog
from flask import Flask, g, request
from flask_cors import CORS
from sqlalchemy import event, text

from config import config
from app import commands
from app.extensions import cache, db, migrate


def create_app(config_name='default'):
    app = Flask(__name__, static_folder=None, template_folder=None)

    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    configure_database(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', [])}},
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization', 'X-CSRF-Token'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    )

    configure_logging(app)
    configure_request_metrics(app)
    register_api_blueprints(app)
    register_error_handlers(app)
    register_commands(app)
    register_root(app)

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
    @app.errorhandler(403)
    def forbidden(e):
        from app.api.responses import api_error
        return api_error('权限不足', status=403, error='forbidden')

    @app.errorhandler(404)
    def page_not_found(e):
        from app.api.responses import api_error
        message = '接口不存在' if request.path.startswith('/api/') else 'NEXUS 后端仅提供 REST API'
        return api_error(message, status=404, error='not_found')

    @app.errorhandler(500)
    def internal_server_error(e):
        from app.api.responses import api_error
        return api_error('服务器内部错误', status=500, error='internal_error')


def register_commands(app):
    app.cli.add_command(commands.forge)
    app.cli.add_command(commands.seed_enterprise)
    app.cli.add_command(commands.audit_enterprise_data)
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
            'frontend': 'Angular SPA',
            'status': health['status'],
            'ai': health['ai'],
            'storage': health['storage'],
        }, 'NEXUS 后端 API 正常运行')


def configure_request_metrics(app):
    @app.before_request
    def mark_request_start():
        g.request_started_at = perf_counter()

    @app.after_request
    def add_response_metrics(response):
        started = getattr(g, 'request_started_at', None)
        if started is not None:
            elapsed_ms = int(max((perf_counter() - started) * 1000, 0))
            response.headers['X-Response-Time-Ms'] = str(elapsed_ms)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        return response


def configure_logging(app):
    if not app.debug:
        return

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        style='%'
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
