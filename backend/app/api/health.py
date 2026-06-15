from app.services.health_service import database_health, service_health
from app.utils.time import utcnow

from . import api_bp
from .responses import api_success


@api_bp.get('/health')
def health():
    payload = service_health(include_database=True)
    return api_success(payload, 'API 服务正常' if payload['status'] != 'down' else 'API 服务异常')


@api_bp.get('/health/live')
def health_live():
    return api_success({
        'status': 'ok',
        'service': 'NEXUS API',
        'api_base': '/api/v1',
        'probe': 'live',
        'timestamp': utcnow().isoformat(),
    }, 'API 进程存活')


@api_bp.get('/health/ready')
def health_ready():
    database = database_health()
    payload = {
        'status': 'ready' if database['status'] == 'ready' else 'down',
        'service': 'NEXUS API',
        'api_base': '/api/v1',
        'probe': 'ready',
        'database': database,
        'timestamp': utcnow().isoformat(),
    }
    status = 200 if payload['status'] == 'ready' else 503
    return api_success(payload, 'API 数据库就绪' if status == 200 else 'API 数据库不可用', status=status)
