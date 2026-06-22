import importlib
import os
from io import BytesIO
from zipfile import ZipFile

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

import config as config_module


def reload_config():
    return importlib.reload(config_module)


def production_app_from(config_cls):
    app = Flask(__name__)
    app.config.from_object(config_cls)
    return app


def office_zip_bytes(kind='xlsx', include_office_folder=True):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        if include_office_folder:
            if kind == 'docx':
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
            else:
                archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
        else:
            archive.writestr('payload.txt', 'ordinary zip payload')
    stream.seek(0)
    return stream.getvalue()


def test_production_config_requires_database_url(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'x' * 40)
    monkeypatch.setenv('CORS_ORIGINS', 'https://nexus.example.com')
    monkeypatch.delenv('DATABASE_URL', raising=False)

    module = reload_config()
    app = production_app_from(module.ProductionConfig)

    with pytest.raises(RuntimeError, match='DATABASE_URL'):
        module.ProductionConfig.init_app(app)


def test_production_config_rejects_sqlite_without_explicit_override(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'x' * 40)
    monkeypatch.setenv('CORS_ORIGINS', 'https://nexus.example.com')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///instance/nexus_prime.db')
    monkeypatch.delenv('ALLOW_PRODUCTION_SQLITE', raising=False)

    module = reload_config()
    app = production_app_from(module.ProductionConfig)

    with pytest.raises(RuntimeError, match='SQLite'):
        module.ProductionConfig.init_app(app)


def test_production_config_requires_explicit_cors_origins(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'x' * 40)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@db.example.com:5432/nexus?sslmode=require')
    monkeypatch.delenv('CORS_ORIGINS', raising=False)

    module = reload_config()
    app = production_app_from(module.ProductionConfig)

    with pytest.raises(RuntimeError, match='CORS_ORIGINS'):
        module.ProductionConfig.init_app(app)


def test_production_config_rejects_local_cors_origins(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'x' * 40)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@db.example.com:5432/nexus?sslmode=require')
    monkeypatch.setenv('CORS_ORIGINS', 'https://nexus.example.com,http://127.0.0.1:4200')
    monkeypatch.delenv('ALLOW_PRODUCTION_LOCAL_CORS', raising=False)

    module = reload_config()
    app = production_app_from(module.ProductionConfig)

    with pytest.raises(RuntimeError, match='localhost'):
        module.ProductionConfig.init_app(app)


def test_production_config_requires_shared_cache_for_rate_limits(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'x' * 40)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@db.example.com:5432/nexus?sslmode=require')
    monkeypatch.setenv('CORS_ORIGINS', 'https://nexus.example.com')
    monkeypatch.setenv('AUTH_COOKIE_SECURE', 'true')
    monkeypatch.setenv('AUTH_COOKIE_SAMESITE', 'None')
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('CACHE_REDIS_URL', raising=False)
    monkeypatch.delenv('UPSTASH_REDIS_URL', raising=False)
    monkeypatch.delenv('ALLOW_PRODUCTION_SIMPLE_CACHE', raising=False)

    module = reload_config()
    app = production_app_from(module.ProductionConfig)

    with pytest.raises(RuntimeError, match='REDIS_URL|UPSTASH_REDIS_URL'):
        module.ProductionConfig.init_app(app)


def test_cache_config_promotes_redis_url_to_shared_cache(monkeypatch):
    monkeypatch.setenv('REDIS_URL', 'redis://cache.example.com:6379/0')

    module = reload_config()

    assert module.cache_config_from_env()['CACHE_TYPE'] == 'RedisCache'
    assert module.cache_config_from_env()['CACHE_REDIS_URL'] == 'redis://cache.example.com:6379/0'
    assert module.is_shared_cache_configured() is True


def test_celery_config_defaults_to_redis_url(monkeypatch):
    monkeypatch.setenv('REDIS_URL', 'redis://cache.example.com:6379/0')
    monkeypatch.delenv('CELERY_BROKER_URL', raising=False)
    monkeypatch.delenv('CELERY_RESULT_BACKEND', raising=False)

    module = reload_config()

    assert module.celery_config_from_env()['CELERY_BROKER_URL'] == 'redis://cache.example.com:6379/0'
    assert module.celery_config_from_env()['CELERY_RESULT_BACKEND'] == 'redis://cache.example.com:6379/0'


def test_testing_config_uses_eager_in_memory_celery():
    module = reload_config()

    assert module.TestingConfig.CELERY_BROKER_URL == 'memory://'
    assert module.TestingConfig.CELERY_RESULT_BACKEND == 'cache+memory://'
    assert module.TestingConfig.CELERY_TASK_ALWAYS_EAGER is True
    assert module.TestingConfig.CELERY_TASK_EAGER_PROPAGATES is True


def test_otel_tracing_config_from_env(monkeypatch):
    monkeypatch.setenv('OTEL_TRACES_ENABLED', 'true')
    monkeypatch.setenv('OTEL_SERVICE_NAME', 'nexus-prime-test')
    monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://collector:4318/v1/traces')

    module = reload_config()

    assert module.Config.OTEL_TRACES_ENABLED is True
    assert module.Config.OTEL_SERVICE_NAME == 'nexus-prime-test'
    assert module.Config.OTEL_EXPORTER_OTLP_ENDPOINT == 'http://collector:4318/v1/traces'


def test_ai_timeout_parser_bounds_values():
    module = reload_config()

    assert module.parse_ai_timeout('1', 20.0) == 3.0
    assert module.parse_ai_timeout('120', 20.0) == 60.0
    assert module.parse_ai_timeout('bad', 20.0) == 20.0
    assert module.parse_ai_timeout('0.25', 2.0, min_value=0.5) == 0.5


def test_ai_provider_config_prefers_coherent_openai_tuple():
    module = reload_config()

    result = module.resolve_ai_provider_config({
        'OPENAI_API_KEY': 'sk-live-openai-credential',
        'DEEPSEEK_API_KEY': 'sk-live-deepseek-credential',
    })

    assert result['api_key'] == 'sk-live-openai-credential'
    assert result['base_url'] == 'https://api.openai.com'
    assert result['model'] == 'gpt-4.1-mini'
    assert result['provider'] == 'openai'
    assert result['source'] == 'openai'


def test_ai_provider_config_does_not_mix_placeholder_generic_key_with_deepseek_base():
    module = reload_config()

    result = module.resolve_ai_provider_config({
        'AI_API_KEY': 'your-openai-compatible-api-key',
        'AI_BASE_URL': 'https://api.deepseek.com',
        'OPENAI_API_KEY': 'sk-live-openai-credential',
    })

    assert result['api_key'] == 'sk-live-openai-credential'
    assert result['base_url'] == 'https://api.openai.com'
    assert result['provider'] == 'openai'


def test_ai_provider_config_keeps_generic_tuple_when_real_key_is_set():
    module = reload_config()

    result = module.resolve_ai_provider_config({
        'AI_API_KEY': 'sk-live-gateway-credential',
        'AI_BASE_URL': 'https://ai-gateway.example.com',
        'AI_MODEL': 'company/ops-model',
        'OPENAI_API_KEY': 'sk-live-openai-credential',
    })

    assert result['api_key'] == 'sk-live-gateway-credential'
    assert result['base_url'] == 'https://ai-gateway.example.com'
    assert result['model'] == 'company/ops-model'
    assert result['provider'] == 'openai-compatible'
    assert result['source'] == 'generic'


def test_init_app_creates_dedicated_upload_directories(tmp_path):
    module = reload_config()
    app = Flask(__name__)
    upload_root = tmp_path / 'uploads'
    app.config.update({
        'UPLOAD_FOLDER': os.fspath(upload_root),
        'UPLOAD_FILES_FOLDER': os.fspath(upload_root / 'files'),
        'UPLOAD_AVATARS_FOLDER': os.fspath(upload_root / 'avatars'),
        'UPLOAD_LIBRARY_FOLDER': os.fspath(upload_root / 'library'),
    })

    module.Config.init_app(app)

    assert upload_root.is_dir()
    assert (upload_root / 'files').is_dir()
    assert (upload_root / 'avatars').is_dir()
    assert (upload_root / 'library').is_dir()


def test_save_file_uses_dedicated_upload_directories(tmp_path):
    module = reload_config()
    app = Flask(__name__)
    upload_root = tmp_path / 'uploads'
    app.config.update({
        'UPLOAD_FOLDER': os.fspath(upload_root),
        'UPLOAD_FILES_FOLDER': os.fspath(upload_root / 'files'),
        'UPLOAD_AVATARS_FOLDER': os.fspath(upload_root / 'avatars'),
        'UPLOAD_LIBRARY_FOLDER': os.fspath(upload_root / 'library'),
    })

    module.Config.init_app(app)

    with app.app_context():
        from app.utils.file_helper import resolve_upload_destination, save_file

        assert resolve_upload_destination('attachments') == (os.fspath(upload_root / 'files'), 'files')
        assert resolve_upload_destination('avatars') == (os.fspath(upload_root / 'avatars'), 'avatars')
        assert resolve_upload_destination('library') == (os.fspath(upload_root / 'library'), 'library')

        stored = save_file(FileStorage(stream=BytesIO(b'NEXUS document'), filename='handover.txt', content_type='text/plain'), folder='attachments')
        assert stored is not None
        display_name, logical_path, file_size, mimetype = stored
        assert display_name == 'handover.txt'
        assert logical_path.startswith('files/')
        assert file_size == len(b'NEXUS document')
        assert mimetype == 'text/plain'
        assert os.path.exists(upload_root / logical_path)
        assert not (upload_root / logical_path.split('/', 1)[1]).exists()


def test_save_file_rejects_disallowed_extensions_and_mime_signatures(tmp_path):
    module = reload_config()
    app = Flask(__name__)
    upload_root = tmp_path / 'uploads'
    app.config.update({
        'UPLOAD_FOLDER': os.fspath(upload_root),
        'UPLOAD_FILES_FOLDER': os.fspath(upload_root / 'files'),
        'UPLOAD_AVATARS_FOLDER': os.fspath(upload_root / 'avatars'),
        'UPLOAD_LIBRARY_FOLDER': os.fspath(upload_root / 'library'),
    })

    module.Config.init_app(app)

    with app.app_context():
        from app.utils.file_helper import allowed_file, save_file

        assert allowed_file('handover.txt') is True
        assert allowed_file('report.xlsx') is True
        assert allowed_file('video.mp4') is False
        assert allowed_file('archive.zip') is False

        assert save_file(
            FileStorage(stream=BytesIO(b'<svg onload=alert(1)>'), filename='payload.svg', content_type='image/svg+xml'),
            folder='attachments',
        ) is None
        assert save_file(
            FileStorage(stream=BytesIO(b'<script>alert(1)</script>'), filename='payload.pdf', content_type='text/html'),
            folder='attachments',
        ) is None
        assert save_file(
            FileStorage(stream=BytesIO(b'not a real pdf'), filename='payload.pdf', content_type='application/pdf'),
            folder='attachments',
        ) is None
        assert save_file(
            FileStorage(stream=BytesIO(b'<html><body>x</body></html>'), filename='payload.txt', content_type='text/plain'),
            folder='attachments',
        ) is None
        assert save_file(
            FileStorage(stream=BytesIO(office_zip_bytes('xlsx', include_office_folder=False)), filename='payload.xlsx', content_type='application/octet-stream'),
            folder='attachments',
        ) is None
        assert save_file(
            FileStorage(stream=BytesIO(office_zip_bytes('xlsx')), filename='report.xlsx', content_type='application/octet-stream'),
            folder='attachments',
        ) is not None
        assert save_file(
            FileStorage(stream=BytesIO(office_zip_bytes('docx')), filename='brief.docx', content_type='application/octet-stream'),
            folder='attachments',
        ) is not None
