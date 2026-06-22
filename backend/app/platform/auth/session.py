"""Session, cookie, and JWT helpers for the Flask API boundary."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from flask import current_app, g, jsonify, make_response, request

from app.models.auth import User

from .csrf import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, generate_csrf_token


def _api_success(data=None, message='success', status=200, **extra):
    payload = {
        'data': data,
        'message': message,
        'error': None,
    }
    payload.update(extra)
    return jsonify(payload), status


def _jwt_private_key() -> str | None:
    """Return RSA private key PEM if configured, else None (fall back to HS256)."""
    return current_app.config.get('JWT_PRIVATE_KEY') or None


def _jwt_public_key() -> str | None:
    return current_app.config.get('JWT_PUBLIC_KEY') or None


def create_access_token(user: User, expires_hours: int = 12) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        'sub': str(user.id),
        'email': user.email,
        'username': user.username,
        'is_admin': bool(user.is_admin or (user.role and user.role.is_admin)),
        'iat': now,
        'exp': now + timedelta(hours=expires_hours),
    }
    private_key = _jwt_private_key()
    if private_key:
        return jwt.encode(payload, private_key, algorithm='RS256')
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_access_token(token: str) -> dict[str, Any]:
    public_key = _jwt_public_key()
    if public_key:
        return jwt.decode(token, public_key, algorithms=['RS256'])
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


def auth_cookie_options(http_only=True):
    samesite = current_app.config.get('AUTH_COOKIE_SAMESITE', 'Lax')
    return {
        'httponly': http_only,
        'secure': bool(current_app.config.get('AUTH_COOKIE_SECURE', current_app.config.get('SESSION_COOKIE_SECURE', False))),
        'samesite': samesite,
        'path': '/',
        # CHIPS: required for SameSite=None cross-site cookies (Werkzeug 3.0.1+)
        **({'partitioned': True} if samesite == 'None' else {}),
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
    body, _status = _api_success({**payload, 'csrf_token': csrf_token}, message, status=status)
    response.set_data(body.get_data())
    response.content_type = body.content_type or 'application/json'
    response.status_code = _status
    return response


def response_with_cleared_auth(data=None, message='退出成功'):
    body, status = _api_success(data or {'revoked': True}, message)
    response = make_response(body.get_data(), status)
    response.content_type = body.content_type or 'application/json'
    clear_auth_cookies(response)
    return response
