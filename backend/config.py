import os
from dotenv import load_dotenv

from upload_policy import allowed_upload_extensions

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))
load_dotenv(os.path.abspath(os.path.join(basedir, '..', '.env')))


def runtime_path(*parts):
    """Return a writable path for local servers and serverless functions."""
    root = os.environ.get('NEXUS_RUNTIME_DIR')
    if not root and os.environ.get('VERCEL') == '1':
        root = '/tmp/nexus-prime'
    if not root:
        root = basedir
    return os.path.join(root, *parts)


def normalize_database_url(url):
    """Normalize local SQLite URLs after moving the backend into backend/."""
    default_sqlite = 'sqlite:///' + os.path.join(basedir, 'instance', 'nexus_prime.db')
    if not url:
        return default_sqlite
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    if not url.startswith('sqlite:///'):
        return url

    raw_path = url.replace('sqlite:///', '', 1)
    if raw_path == ':memory:':
        return url

    candidate = raw_path
    if not os.path.isabs(candidate):
        candidate = os.path.abspath(os.path.join(basedir, candidate))

    normalized = candidate.replace('\\', '/').lower()
    legacy_suffix = '/instance/nexus_prime.db'
    if not os.path.exists(candidate) and normalized.endswith(legacy_suffix):
        candidate = os.path.join(basedir, 'instance', 'nexus_prime.db')

    return 'sqlite:///' + candidate


def engine_options_for(url):
    if str(url or '').startswith('sqlite'):
        return {
            'connect_args': {
                'timeout': 30,
                'check_same_thread': False,
            }
        }
    return {}


def parse_cors_origins(value):
    return [
        origin.strip()
        for origin in str(value or '').split(',')
        if origin.strip()
    ]


def is_local_cors_origin(origin):
    lowered = (origin or '').lower()
    return 'localhost' in lowered or '127.0.0.1' in lowered or '0.0.0.0' in lowered


def parse_ai_timeout(value, default=20.0, min_value=3.0):
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(timeout, min_value), 60.0)


def looks_like_real_ai_key(value):
    cleaned = (value or '').strip()
    if len(cleaned) < 10:
        return False
    lowered = cleaned.lower()
    return not any(marker in lowered for marker in ('your-', 'change-this', 'example', 'placeholder'))


def cache_config_from_env(env=None):
    source = env or os.environ
    redis_url = source.get('CACHE_REDIS_URL') or source.get('REDIS_URL') or source.get('UPSTASH_REDIS_URL') or ''
    cache_type = source.get('CACHE_TYPE') or ('RedisCache' if redis_url else 'SimpleCache')
    config = {
        'CACHE_TYPE': cache_type,
        'CACHE_DEFAULT_TIMEOUT': int(source.get('CACHE_DEFAULT_TIMEOUT', 300)),
    }
    if cache_type.lower() in ('rediscache', 'redis'):
        config['CACHE_TYPE'] = 'RedisCache'
        config['CACHE_REDIS_URL'] = redis_url
    return config


def is_shared_cache_configured(env=None):
    source = env or os.environ
    cache_type = (source.get('CACHE_TYPE') or '').lower()
    redis_url = source.get('CACHE_REDIS_URL') or source.get('REDIS_URL') or source.get('UPSTASH_REDIS_URL') or ''
    if cache_type in ('rediscache', 'redis') and redis_url:
        return True
    if redis_url:
        return True
    return False


def resolve_ai_provider_config(env=None):
    """Resolve AI credentials as a coherent provider tuple."""
    source = env or os.environ
    generic_key = source.get('AI_API_KEY') or ''
    generic_base = source.get('AI_BASE_URL') or ''
    generic_model = source.get('AI_MODEL') or ''
    openai_key = source.get('OPENAI_API_KEY') or ''
    openai_base = source.get('OPENAI_BASE_URL') or ''
    openai_model = source.get('OPENAI_MODEL') or ''
    deepseek_key = source.get('DEEPSEEK_API_KEY') or ''
    deepseek_base = source.get('DEEPSEEK_BASE_URL') or ''
    deepseek_model = source.get('DEEPSEEK_MODEL') or ''

    if looks_like_real_ai_key(generic_key):
        base_url = generic_base or 'https://api.deepseek.com'
        provider = 'openai' if 'api.openai.com' in base_url.lower() else 'deepseek-compatible' if 'deepseek' in base_url.lower() else 'openai-compatible'
        return {
            'api_key': generic_key,
            'base_url': base_url,
            'model': generic_model or ('gpt-4.1-mini' if provider == 'openai' else 'deepseek-chat'),
            'provider': provider,
            'source': 'generic',
        }

    if looks_like_real_ai_key(openai_key):
        return {
            'api_key': openai_key,
            'base_url': openai_base or 'https://api.openai.com',
            'model': openai_model or 'gpt-4.1-mini',
            'provider': 'openai',
            'source': 'openai',
        }

    if looks_like_real_ai_key(deepseek_key):
        return {
            'api_key': deepseek_key,
            'base_url': deepseek_base or 'https://api.deepseek.com',
            'model': deepseek_model or 'deepseek-chat',
            'provider': 'deepseek-compatible',
            'source': 'deepseek',
        }

    if generic_key or generic_base or generic_model:
        base_url = generic_base or 'https://api.deepseek.com'
        provider = 'openai' if 'api.openai.com' in base_url.lower() else 'deepseek-compatible' if 'deepseek' in base_url.lower() else 'openai-compatible'
        return {
            'api_key': '',
            'base_url': base_url,
            'model': generic_model or ('gpt-4.1-mini' if provider == 'openai' else 'deepseek-chat'),
            'provider': provider,
            'source': 'generic',
        }

    return {
        'api_key': '',
        'base_url': deepseek_base or 'https://api.deepseek.com',
        'model': deepseek_model or 'deepseek-chat',
        'provider': 'deepseek-compatible',
        'source': 'deepseek',
    }

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    
    # 数据库配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # OpenAI-compatible AI provider. Resolve key/base/model as one provider tuple
    # so OpenAI and DeepSeek credentials are never accidentally mixed.
    AI_PROVIDER_CONFIG = resolve_ai_provider_config()
    AI_API_KEY = AI_PROVIDER_CONFIG['api_key']
    AI_BASE_URL = AI_PROVIDER_CONFIG['base_url']
    AI_MODEL = AI_PROVIDER_CONFIG['model']
    AI_PROVIDER = AI_PROVIDER_CONFIG['provider']
    AI_PROVIDER_SOURCE = AI_PROVIDER_CONFIG['source']
    AI_REQUEST_TIMEOUT_SECONDS = parse_ai_timeout(os.environ.get('AI_REQUEST_TIMEOUT_SECONDS'), 20.0)
    AI_CONNECT_TIMEOUT_SECONDS = parse_ai_timeout(os.environ.get('AI_CONNECT_TIMEOUT_SECONDS'), 5.0)
    AI_DIAGNOSTICS_TIMEOUT_SECONDS = parse_ai_timeout(os.environ.get('AI_DIAGNOSTICS_TIMEOUT_SECONDS'), 2.0, min_value=0.5)
    AI_DIAGNOSTICS_CACHE_SECONDS = int(os.environ.get('AI_DIAGNOSTICS_CACHE_SECONDS', 60))
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', '')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', '')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', '')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', '')
    AI_LOCAL_ANALYSIS = os.environ.get('AI_LOCAL_ANALYSIS', 'true').lower() in ('1', 'true', 'yes')
    
    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or runtime_path('storage', 'uploads')
    UPLOAD_FILES_FOLDER = os.environ.get('UPLOAD_FILES_FOLDER') or os.path.join(UPLOAD_FOLDER, 'files')
    UPLOAD_AVATARS_FOLDER = os.environ.get('UPLOAD_AVATARS_FOLDER') or os.path.join(UPLOAD_FOLDER, 'avatars')
    UPLOAD_LIBRARY_FOLDER = os.environ.get('UPLOAD_LIBRARY_FOLDER') or os.path.join(UPLOAD_FOLDER, 'library')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 限制最大上传 16MB
    AVATAR_MAX_BYTES = int(os.environ.get('AVATAR_MAX_BYTES', 3 * 1024 * 1024))
    ALLOWED_UPLOAD_EXTENSIONS = allowed_upload_extensions()
    
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    
    USE_CLOUD_STORAGE = os.environ.get('USE_CLOUD_STORAGE', 'auto').lower()
    REQUIRE_CLOUD_STORAGE_FOR_UPLOADS = os.environ.get('REQUIRE_CLOUD_STORAGE_FOR_UPLOADS', 'auto').lower()
    
    # 缓存配置。生产环境建议使用 Redis/Upstash，让登录限流跨实例生效。
    CACHE_SETTINGS = cache_config_from_env()
    CACHE_TYPE = CACHE_SETTINGS['CACHE_TYPE']
    CACHE_DEFAULT_TIMEOUT = CACHE_SETTINGS['CACHE_DEFAULT_TIMEOUT']
    CACHE_REDIS_URL = CACHE_SETTINGS.get('CACHE_REDIS_URL')
    
    # API/CORS/JWT 配置
    DEV_CORS_PORTS = list(range(4200, 4231)) + list(range(4300, 4311))
    DEFAULT_CORS_ORIGINS = ','.join(
        [f'http://localhost:{port}' for port in DEV_CORS_PORTS] +
        [f'http://127.0.0.1:{port}' for port in DEV_CORS_PORTS]
    )
    CORS_ORIGINS = parse_cors_origins(os.environ.get('CORS_ORIGINS', DEFAULT_CORS_ORIGINS))
    JWT_EXPIRES_HOURS = int(os.environ.get('JWT_EXPIRES_HOURS', 12))
    AUTH_COOKIE_SECURE = os.environ.get('AUTH_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
    AUTH_COOKIE_SAMESITE = os.environ.get('AUTH_COOKIE_SAMESITE', 'Lax')
    LOGIN_RATE_LIMIT_ATTEMPTS = int(os.environ.get('LOGIN_RATE_LIMIT_ATTEMPTS', 8))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('LOGIN_RATE_LIMIT_WINDOW_SECONDS', 10 * 60))
    DISABLE_API_CSRF = False

    @staticmethod
    def init_app(app):
        for key in ('UPLOAD_FOLDER', 'UPLOAD_FILES_FOLDER', 'UPLOAD_AVATARS_FOLDER', 'UPLOAD_LIBRARY_FOLDER'):
            folder = app.config.get(key)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
        instance_path = os.path.join(basedir, 'instance')
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)
        
        # 初始化云存储
        from app.utils.cloud_storage import init_cloud_storage
        init_cloud_storage(app)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    
    # Normalize managed PostgreSQL URLs and local SQLite paths.
    DATABASE_URL = normalize_database_url(os.environ.get('DATABASE_URL'))
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)
    
    # 安全设置
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'true').lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'None')
    AUTH_COOKIE_SECURE = os.environ.get('AUTH_COOKIE_SECURE', 'true').lower() in ('1', 'true', 'yes')
    AUTH_COOKIE_SAMESITE = os.environ.get('AUTH_COOKIE_SAMESITE', 'None')
    CORS_ORIGINS = parse_cors_origins(os.environ.get('CORS_ORIGINS'))
    
    @classmethod
    def init_app(cls, app):
        if not os.environ.get('SECRET_KEY') or cls.SECRET_KEY == 'hard-to-guess-string':
            raise RuntimeError('生产环境必须设置强随机 SECRET_KEY')
        if not os.environ.get('DATABASE_URL'):
            raise RuntimeError('生产环境必须设置 DATABASE_URL，建议使用 Supabase/PostgreSQL 连接串')
        if str(cls.SQLALCHEMY_DATABASE_URI).startswith('sqlite') and os.environ.get('ALLOW_PRODUCTION_SQLITE', '').lower() not in ('1', 'true', 'yes'):
            raise RuntimeError('生产环境默认禁止 SQLite，请设置 PostgreSQL DATABASE_URL；本地演练可显式设置 ALLOW_PRODUCTION_SQLITE=true')
        if not os.environ.get('CORS_ORIGINS') or not cls.CORS_ORIGINS:
            raise RuntimeError('生产环境必须设置 CORS_ORIGINS，且应精确包含前端域名')
        if (
            any(is_local_cors_origin(origin) for origin in cls.CORS_ORIGINS)
            and os.environ.get('ALLOW_PRODUCTION_LOCAL_CORS', '').lower() not in ('1', 'true', 'yes')
        ):
            raise RuntimeError('生产环境 CORS_ORIGINS 不允许使用 localhost 或 127.0.0.1')
        if cls.AUTH_COOKIE_SAMESITE == 'None' and not cls.AUTH_COOKIE_SECURE:
            raise RuntimeError('AUTH_COOKIE_SAMESITE=None 时必须启用 AUTH_COOKIE_SECURE=true')
        if not is_shared_cache_configured() and os.environ.get('ALLOW_PRODUCTION_SIMPLE_CACHE', '').lower() not in ('1', 'true', 'yes'):
            raise RuntimeError('生产环境必须配置 REDIS_URL/UPSTASH_REDIS_URL 或 CACHE_TYPE=RedisCache，让登录限流跨实例生效')
        Config.init_app(app)
        # 生产环境日志配置
        import logging
        from logging.handlers import RotatingFileHandler
        import sys

        # 将日志输出到 stdout
        log_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_formatter)
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)

        if os.environ.get('VERCEL') != '1':
            logs_dir = runtime_path('logs')
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            file_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'nexus_prime.log'), maxBytes=10240, backupCount=10
            )
            file_handler.setFormatter(log_formatter)
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Nexus Prime startup')

class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'testing-secret-key-with-at-least-32-bytes'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)
    CACHE_TYPE = 'SimpleCache'
    CACHE_REDIS_URL = None
    WTF_CSRF_ENABLED = False
    DISABLE_API_CSRF = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
