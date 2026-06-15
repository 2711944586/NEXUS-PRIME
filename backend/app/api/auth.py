import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, make_response, request, g

from app.extensions import db
from app.models.auth import User
from .responses import api_error

ACCESS_COOKIE_NAME = 'nexus_access_token'
CSRF_COOKIE_NAME = 'nexus_csrf_token'
CSRF_HEADER_NAME = 'X-CSRF-Token'
MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def create_access_token(user, expires_hours=12):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'username': user.username,
        'is_admin': bool(user.is_admin or (user.role and user.role.is_admin)),
        'iat': now,
        'exp': now + timedelta(hours=expires_hours),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_access_token(token):
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


def get_bearer_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    return auth.split(' ', 1)[1].strip()


def get_access_token():
    return get_bearer_token() or request.cookies.get(ACCESS_COOKIE_NAME)


def current_api_user():
    return getattr(g, 'api_user', None)


def generate_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_token_from_request():
    return request.headers.get(CSRF_HEADER_NAME) or request.headers.get(CSRF_HEADER_NAME.lower())


def csrf_is_valid():
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = csrf_token_from_request()
    return bool(cookie_token and header_token and secrets.compare_digest(cookie_token, header_token))


def csrf_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if (
            request.method in MUTATING_METHODS
            and not current_app.config.get('DISABLE_API_CSRF', False)
            and not csrf_is_valid()
        ):
            return api_error('CSRF 校验失败，请刷新后重试', status=403, error='csrf_failed')
        return fn(*args, **kwargs)
    return wrapper


def auth_cookie_options(http_only=True):
    return {
        'httponly': http_only,
        'secure': bool(current_app.config.get('AUTH_COOKIE_SECURE', current_app.config.get('SESSION_COOKIE_SECURE', False))),
        'samesite': current_app.config.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        'path': '/',
    }


def set_auth_cookies(response, token, csrf_token=None):
    csrf_token = csrf_token or generate_csrf_token()
    max_age = int(current_app.config.get('JWT_EXPIRES_HOURS', 12) * 3600)
    response.set_cookie(ACCESS_COOKIE_NAME, token, max_age=max_age, **auth_cookie_options(http_only=True))
    response.set_cookie(CSRF_COOKIE_NAME, csrf_token, max_age=max_age, **auth_cookie_options(http_only=False))
    return csrf_token


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path='/', samesite=current_app.config.get('AUTH_COOKIE_SAMESITE', 'Lax'))
    response.delete_cookie(CSRF_COOKIE_NAME, path='/', samesite=current_app.config.get('AUTH_COOKIE_SAMESITE', 'Lax'))
    return response


def with_auth_cookies(payload, message, token, status=200):
    response = make_response()
    csrf_token = set_auth_cookies(response, token)
    from .responses import api_success
    body, _status = api_success({**payload, 'csrf_token': csrf_token}, message, status=status)
    response.set_data(body.get_data())
    response.content_type = body.content_type or 'application/json'
    response.status_code = _status
    return response


def response_with_cleared_auth(data=None, message='退出成功'):
    from .responses import api_success
    body, status = api_success(data or {'revoked': True}, message)
    response = make_response(body.get_data(), status)
    response.content_type = body.content_type or 'application/json'
    clear_auth_cookies(response)
    return response


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        bearer_token = get_bearer_token()
        token = bearer_token or request.cookies.get(ACCESS_COOKIE_NAME)
        if not token:
            return api_error('请先登录', status=401, error='missing_token')
        if (
            not bearer_token
            and request.method in MUTATING_METHODS
            and not current_app.config.get('DISABLE_API_CSRF', False)
            and not csrf_is_valid()
        ):
            return api_error('CSRF 校验失败，请刷新后重试', status=403, error='csrf_failed')
        try:
            payload = decode_access_token(token)
            user_id = int(payload.get('sub'))
        except jwt.ExpiredSignatureError:
            return api_error('登录已过期，请重新登录', status=401, error='token_expired')
        except Exception:
            return api_error('无效的登录凭证', status=401, error='invalid_token')

        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            return api_error('用户不存在或已被禁用', status=401, error='inactive_user')
        g.api_user = user
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @jwt_required
    def wrapper(*args, **kwargs):
        user = current_api_user()
        if not user or not user.can('admin') and not (user.is_admin or (user.role and user.role.is_admin)):
            return api_error('需要管理员权限', status=403, error='admin_required')
        return fn(*args, **kwargs)
    return wrapper


def permission_required(permission):
    def decorator(fn):
        @wraps(fn)
        @jwt_required
        def wrapper(*args, **kwargs):
            user = current_api_user()
            if not user or not user.can(permission):
                return api_error('权限不足', status=403, error='permission_denied')
            return fn(*args, **kwargs)
        return wrapper
    return decorator
