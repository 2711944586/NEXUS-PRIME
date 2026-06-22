"""Authentication platform helpers.

The API package keeps compatibility exports, while new code can import from
``app.platform.auth`` directly.
"""

from .csrf import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    MUTATING_METHODS,
    csrf_is_valid,
    csrf_token_from_request,
    generate_csrf_token,
)
from .decorators import admin_required, csrf_required, jwt_required, permission_required
from .password import check_password_strength
from .session import (
    auth_cookie_options,
    clear_auth_cookies,
    create_access_token,
    current_api_user,
    decode_access_token,
    get_access_token,
    get_bearer_token,
    response_with_cleared_auth,
    set_auth_cookies,
    with_auth_cookies,
)

__all__ = [
    'ACCESS_COOKIE_NAME',
    'CSRF_COOKIE_NAME',
    'CSRF_HEADER_NAME',
    'MUTATING_METHODS',
    'admin_required',
    'auth_cookie_options',
    'check_password_strength',
    'clear_auth_cookies',
    'create_access_token',
    'csrf_is_valid',
    'csrf_required',
    'csrf_token_from_request',
    'current_api_user',
    'decode_access_token',
    'generate_csrf_token',
    'get_access_token',
    'get_bearer_token',
    'jwt_required',
    'permission_required',
    'response_with_cleared_auth',
    'set_auth_cookies',
    'with_auth_cookies',
]
