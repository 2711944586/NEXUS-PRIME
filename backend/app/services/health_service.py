import os
from time import perf_counter
from typing import Any, Dict

from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.services.ai_service import AIService
from app.utils.cloud_storage import is_cloud_storage_enabled, uploads_require_cloud_storage
from app.utils.time import utcnow


def _configured_ai_key() -> str:
    return current_app.config.get('AI_API_KEY') or ''


def _configured_ai_base() -> str:
    return (current_app.config.get('AI_BASE_URL') or '').rstrip('/')


def _configured_ai_model() -> str:
    return current_app.config.get('AI_MODEL') or 'deepseek-chat'


def database_health() -> Dict[str, Any]:
    started = perf_counter()
    try:
        db.session.execute(text('select 1'))
        latency_ms = int(max((perf_counter() - started) * 1000, 0))
        engine_name = db.engine.url.get_backend_name()
        return {
            'status': 'ready',
            'latency_ms': latency_ms,
            'engine': engine_name,
        }
    except Exception as exc:
        current_app.logger.warning('Database health check failed: %s', exc)
        return {
            'status': 'down',
            'latency_ms': int(max((perf_counter() - started) * 1000, 0)),
            'engine': 'unknown',
            'message': str(exc),
        }


def ai_health() -> Dict[str, Any]:
    api_key = _configured_ai_key()
    base_url = _configured_ai_base()
    local_enabled = bool(current_app.config.get('AI_LOCAL_ANALYSIS', False))
    external_configured = AIService.is_real_key(api_key)
    provider = current_app.config.get('AI_PROVIDER') or 'openai-compatible'

    if external_configured:
        status = 'configured'
    elif local_enabled:
        status = 'local'
    else:
        status = 'not_configured'

    return {
        'status': status,
        'local_enabled': local_enabled,
        'external_configured': external_configured,
        'provider': provider,
        'source': current_app.config.get('AI_PROVIDER_SOURCE') or 'generic',
        'base_url': base_url,
        'model': _configured_ai_model(),
        'request_timeout_seconds': current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS'),
        'connect_timeout_seconds': current_app.config.get('AI_CONNECT_TIMEOUT_SECONDS'),
    }


def storage_health() -> Dict[str, Any]:
    cloud_enabled = bool(is_cloud_storage_enabled())
    cloud_required = bool(uploads_require_cloud_storage())
    requirement = current_app.config.get('REQUIRE_CLOUD_STORAGE_FOR_UPLOADS', 'auto')
    folders = {
        'root': current_app.config.get('UPLOAD_FOLDER'),
        'files': current_app.config.get('UPLOAD_FILES_FOLDER'),
        'avatars': current_app.config.get('UPLOAD_AVATARS_FOLDER'),
        'library': current_app.config.get('UPLOAD_LIBRARY_FOLDER'),
    }
    writable = {}
    for name, folder in folders.items():
        if not folder:
            writable[name] = False
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            writable[name] = os.access(folder, os.W_OK)
        except OSError:
            writable[name] = False
    if cloud_enabled:
        status = 'cloud'
    elif cloud_required:
        status = 'missing_cloud'
    elif not all(writable.values()):
        status = 'storage_unwritable'
    else:
        status = 'local'
    return {
        'status': status,
        'cloud_configured': cloud_enabled,
        'cloud_required': cloud_required,
        'requirement': requirement,
        'upload_folder': folders['root'],
        'folders': folders,
        'writable': writable,
    }


def service_health(include_database: bool = True) -> Dict[str, Any]:
    started = perf_counter()
    db_status = database_health() if include_database else {'status': 'not_checked'}
    ai_status = ai_health()
    storage_status = storage_health()

    checks = {
        'database': db_status['status'] == 'ready' if include_database else True,
        'ai': ai_status['local_enabled'] or ai_status['external_configured'],
        'storage': storage_status['status'] not in ('missing_cloud', 'storage_unwritable'),
    }
    status = 'ok' if all(checks.values()) else 'degraded'
    if include_database and not checks['database']:
        status = 'down'

    return {
        'status': status,
        'service': 'NEXUS API',
        'api_base': '/api/v1',
        'timestamp': utcnow().isoformat(),
        'latency_ms': int(max((perf_counter() - started) * 1000, 0)),
        'database': db_status,
        'ai': ai_status,
        'storage': storage_status,
        'checks': checks,
    }
