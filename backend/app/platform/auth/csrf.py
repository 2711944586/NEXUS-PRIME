"""CSRF token helpers for cookie-authenticated API requests."""

import secrets

from flask import current_app, request

ACCESS_COOKIE_NAME = 'nexus_access_token'
CSRF_COOKIE_NAME = 'nexus_csrf_token'
CSRF_HEADER_NAME = 'X-CSRF-Token'
MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def generate_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_token_from_request():
    return request.headers.get(CSRF_HEADER_NAME) or request.headers.get(CSRF_HEADER_NAME.lower())


def _trusted_frontend_origin():
    origin = (request.headers.get('Origin') or '').strip().rstrip('/')
    if not origin:
        return False
    allowed = {
        str(item).strip().rstrip('/')
        for item in current_app.config.get('CORS_ORIGINS', [])
        if str(item).strip()
    }
    return origin in allowed


def csrf_is_valid():
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = csrf_token_from_request()
    if not header_token:
        return False
    if cookie_token and secrets.compare_digest(cookie_token, header_token):
        return True
    return bool(
        request.cookies.get(ACCESS_COOKIE_NAME)
        and _trusted_frontend_origin()
        and len(header_token) >= 32
    )
