"""CSRF token helpers for cookie-authenticated API requests."""

import secrets

from flask import request

ACCESS_COOKIE_NAME = 'nexus_access_token'
CSRF_COOKIE_NAME = 'nexus_csrf_token'
CSRF_HEADER_NAME = 'X-CSRF-Token'
MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def generate_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_token_from_request():
    return request.headers.get(CSRF_HEADER_NAME) or request.headers.get(CSRF_HEADER_NAME.lower())


def csrf_is_valid():
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = csrf_token_from_request()
    return bool(cookie_token and header_token and secrets.compare_digest(cookie_token, header_token))
