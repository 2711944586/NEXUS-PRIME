from __future__ import annotations

import re
import uuid
from time import perf_counter

from flask import g, has_app_context, request

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.:/@-]+")
_MAX_ID_LENGTH = 128


def _new_id() -> str:
    return uuid.uuid4().hex


def sanitize_context_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _SAFE_ID_RE.sub("-", value.strip())[:_MAX_ID_LENGTH].strip("-")
    return cleaned or None


def current_request_id(default: str | None = None) -> str | None:
    if not has_app_context():
        return default
    return getattr(g, "request_id", default)


def current_trace_id(default: str | None = None) -> str | None:
    if not has_app_context():
        return default
    return getattr(g, "trace_id", default)


def install_request_context(app) -> None:
    @app.before_request
    def attach_request_context():
        request_id = sanitize_context_id(request.headers.get(REQUEST_ID_HEADER)) or _new_id()
        trace_id = (
            sanitize_context_id(request.headers.get(TRACE_ID_HEADER))
            or sanitize_context_id(request.headers.get(REQUEST_ID_HEADER))
            or request_id
        )
        g.request_id = request_id
        g.trace_id = trace_id
        g.request_started_at = perf_counter()
