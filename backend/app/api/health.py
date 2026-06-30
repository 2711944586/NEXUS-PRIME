import os
import traceback

from sqlalchemy import text

from app.extensions import db
from app.models.auth import User
from app.services.health_service import database_health, service_health
from app.platform.observability import metrics_snapshot
from app.utils.time import utcnow

from . import api_bp
from .responses import api_success
from .auth import create_access_token
from .resource_support import permission_summary, serialize_model, user_extra


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


@api_bp.get('/health/deployment-data')
def deployment_data_health():
    if os.environ.get('NEXUS_DEPLOYMENT_DIAGNOSTICS', '').lower() not in ('1', 'true', 'yes', 'on'):
        return api_success({'enabled': False}, '部署诊断未启用', status=404)

    payload = {
        'enabled': True,
        'timestamp': utcnow().isoformat(),
        'database': database_health(),
        'counts': {},
        'write_test': {'ok': False},
        'login_probe': {},
    }
    try:
        for table in (
            'auth_users',
            'biz_products',
            'biz_partners',
            'trade_orders',
            'purchase_orders',
            'finance_receivables',
            'stock_quantities',
            'sys_notifications',
            'generated_reports',
        ):
            payload['counts'][table] = db.session.execute(text(f'select count(*) from {table}')).scalar()

        db.session.execute(
            text(
                "insert into sys_audit_logs "
                "(user_id, module, action, ip_address, details, created_at, updated_at, is_deleted) "
                "values (null, 'diagnostics', 'write_probe', '127.0.0.1', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)"
            )
        )
        db.session.rollback()
        payload['write_test'] = {'ok': True, 'rolled_back': True}

        user = User.query.filter_by(email='admin@nexus.com').first()
        payload['login_probe']['user_found'] = bool(user)
        if user:
            payload['login_probe']['password_ok'] = bool(user.verify_password('admin123'))
            payload['login_probe']['active'] = bool(user.is_active)
            payload['login_probe']['permissions_count'] = len(permission_summary(user))
            payload['login_probe']['serialized'] = bool(serialize_model(user, user_extra).get('email'))
            payload['login_probe']['token_created'] = bool(create_access_token(user, 1))
        db.session.rollback()
    except Exception as exc:
        db.session.rollback()
        payload['error'] = {
            'type': type(exc).__name__,
            'message': str(exc),
            'traceback': traceback.format_exc(limit=8),
        }

    return api_success(payload, '部署数据诊断')


@api_bp.get('/observability/metrics')
def observability_metrics():
    return api_success({
        'service': 'NEXUS API',
        'api_base': '/api/v1',
        'metrics': metrics_snapshot(),
        'timestamp': utcnow().isoformat(),
    }, 'API 可观测性指标')
