import os
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    
    # 数据库配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # DeepSeek / AI 配置
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-placeholder')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    # 如果未配置外部 AI Key，可启用本地回退模式（返回简单回应或使用内置分析）
    AI_FALLBACK = os.environ.get('AI_FALLBACK', 'true').lower() in ('1', 'true', 'yes')
    
    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 限制最大上传 16MB
    
    # 缓存配置 (默认使用 SimpleCache，生产环境可改 Redis)
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    @staticmethod
    def init_app(app):
        # 确保上传目录存在
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'nexus_prime.db')

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    
    # Railway 数据库 URL 兼容
    DATABASE_URL = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'nexus_prod.db')
    # PostgreSQL URL 修正（Railway 使用 postgres://）
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    
    # 安全设置
    SESSION_COOKIE_SECURE = False  # Railway 会处理 HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # 生产环境日志配置 (可在此添加邮件通知等)

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}