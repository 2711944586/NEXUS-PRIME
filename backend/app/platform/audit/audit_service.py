import json

from flask import g, has_request_context, request

from app.extensions import db
from app.models.sys import AuditLog

from .audit_middleware import audit_request_context


class AuditService:
    @staticmethod
    def record(module, action, user=None, details=None, commit=False):
        payload = _normalize_details(details)
        context = _current_audit_context()
        if context:
            payload.setdefault("_context", context)

        log = AuditLog(
            user_id=getattr(user, "id", None),
            module=module,
            action=action,
            ip_address=_client_ip(),
            details=json.dumps(payload, ensure_ascii=False),
        )
        db.session.add(log)
        if commit:
            db.session.commit()
        return log


def _normalize_details(details):
    if isinstance(details, dict):
        return dict(details)
    if isinstance(details, list):
        return {"items": details}
    if details:
        return {"message": details}
    return {}


def _current_audit_context() -> dict[str, object]:
    if not has_request_context():
        return {}
    return dict(getattr(g, "audit_context", None) or audit_request_context())


def _client_ip() -> str | None:
    if not has_request_context():
        return None
    forwarded = request.headers.get("X-Forwarded-For") or request.remote_addr or ""
    return forwarded.split(",")[0] or None
