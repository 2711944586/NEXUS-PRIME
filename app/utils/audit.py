"""
审计日志工具模块
用于记录系统中的所有重要操作
"""
from functools import wraps
from flask import request
from flask_login import current_user
from app.models.sys import AuditLog
from app.extensions import db
import json


def log_action(module, action, details=None):
    """
    记录审计日志
    :param module: 模块名称 (如 'auth', 'inventory', 'sales')
    :param action: 操作名称 (如 'login', 'create_order', 'update_stock')
    :param details: 详细信息 (dict)
    """
    if current_user.is_authenticated:
        log = AuditLog(
            user_id=current_user.id,
            module=module,
            action=action,
            ip_address=request.remote_addr,
            details=json.dumps(details, ensure_ascii=False) if details else None
        )
        db.session.add(log)
        db.session.commit()


def audit_log(module, action):
    """
    审计日志装饰器
    使用方法:
    @audit_log('inventory', 'adjust_stock')
    def adjust_stock_view():
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            log_action(module, action, {'args': str(args), 'kwargs': str(kwargs)})
            return result
        return decorated_function
    return decorator
