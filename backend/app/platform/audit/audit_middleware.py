from flask import g, has_request_context, request

from app.platform.observability import current_request_id, current_trace_id


def audit_request_context() -> dict[str, object]:
    if not has_request_context():
        return {}
    return {
        "request_id": current_request_id(),
        "trace_id": current_trace_id(),
        "method": request.method,
        "path": request.path,
        "endpoint": request.endpoint,
        "user_agent": request.headers.get("User-Agent", "")[:160],
    }


def install_audit_middleware(app) -> None:
    @app.before_request
    def attach_audit_context():
        g.audit_context = audit_request_context()
