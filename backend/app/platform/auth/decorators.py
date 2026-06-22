"""Authentication and authorization decorators for API endpoints."""

from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from app.extensions import db
from app.models.auth import User

from .csrf import ACCESS_COOKIE_NAME, MUTATING_METHODS, csrf_is_valid
from .session import current_api_user, decode_access_token, get_bearer_token


def _api_error(message='error', status=400, error=None, **extra):
    payload = {
        'data': None,
        'message': message,
        'error': error or message,
    }
    payload.update(extra)
    return jsonify(payload), status


def csrf_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if (
            request.method in MUTATING_METHODS
            and not current_app.config.get('DISABLE_API_CSRF', False)
            and not csrf_is_valid()
        ):
            return _api_error('CSRF 校验失败，请刷新后重试', status=403, error='csrf_failed')
        return fn(*args, **kwargs)
    return wrapper


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        bearer_token = get_bearer_token()
        token = bearer_token or request.cookies.get(ACCESS_COOKIE_NAME)
        if not token:
            return _api_error('请先登录', status=401, error='missing_token')
        if (
            not bearer_token
            and request.method in MUTATING_METHODS
            and not current_app.config.get('DISABLE_API_CSRF', False)
            and not csrf_is_valid()
        ):
            return _api_error('CSRF 校验失败，请刷新后重试', status=403, error='csrf_failed')
        try:
            payload = decode_access_token(token)
            user_id = int(payload.get('sub'))
        except jwt.ExpiredSignatureError:
            return _api_error('登录已过期，请重新登录', status=401, error='token_expired')
        except Exception:
            return _api_error('无效的登录凭证', status=401, error='invalid_token')

        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            return _api_error('用户不存在或已被禁用', status=401, error='inactive_user')
        g.api_user = user
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @jwt_required
    def wrapper(*args, **kwargs):
        user = current_api_user()
        if not user or not (user.is_admin or (user.role and user.role.is_admin)):
            return _api_error('需要管理员权限', status=403, error='admin_required')
        return fn(*args, **kwargs)
    return wrapper


def permission_required(permission):
    def decorator(fn):
        @wraps(fn)
        @jwt_required
        def wrapper(*args, **kwargs):
            user = current_api_user()
            if not user or not user.can(permission):
                return _api_error('权限不足', status=403, error='permission_denied')
            return fn(*args, **kwargs)
        return wrapper
    return decorator
