import json

from flask import has_request_context, request

from app.extensions import db
from app.models.sys import AuditLog


class AuditService:
    @staticmethod
    def record(module, action, user=None, details=None, commit=False):
        payload = details if isinstance(details, (dict, list)) else {'message': details} if details else {}
        ip_address = None
        if has_request_context():
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        log = AuditLog(
            user_id=getattr(user, 'id', None),
            module=module,
            action=action,
            ip_address=ip_address,
            details=json.dumps(payload, ensure_ascii=False)
        )
        db.session.add(log)
        if commit:
            db.session.commit()
        return log
