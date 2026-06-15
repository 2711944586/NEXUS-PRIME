from datetime import datetime

from flask import request

from app.extensions import db
from app.models.notification import Notification
from app.services.audit_service import AuditService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import is_admin_user, notification_extra, serialize_model


@api_bp.post('/notifications/mark-read')
@jwt_required
def notifications_mark_read():
    payload = request.get_json(silent=True) or {}
    ids = [int(item) for item in payload.get('ids', []) if str(item).isdigit()]
    if not ids:
        return api_error('请选择通知', status=400, error='empty_ids')
    changed = 0
    query = Notification.query.filter(Notification.id.in_(ids), Notification.is_deleted == False)
    if not is_admin_user(current_api_user()):
        query = query.filter(Notification.user_id == current_api_user().id)
    for item in query:
        item.is_read = True
        item.read_at = utcnow()
        changed += 1
    AuditService.record('notifications', 'mark_read', current_api_user(), {'ids': ids, 'changed': changed})
    db.session.commit()
    return api_success({'changed': changed, 'ids': ids}, '通知已标记为已读')


@api_bp.post('/notifications/complete')
@jwt_required
def notifications_complete():
    payload = request.get_json(silent=True) or {}
    notification_id = payload.get('id')
    if not str(notification_id or '').isdigit():
        return api_error('请选择通知', status=400, error='empty_id')
    query = Notification.query.filter(Notification.id == int(notification_id), Notification.is_deleted == False)
    if not is_admin_user(current_api_user()):
        query = query.filter(Notification.user_id == current_api_user().id)
    notification = query.first()
    if not notification:
        return api_error('通知不存在或无权处理', status=404, error='notification_not_found')
    notification.is_read = True
    notification.read_at = notification.read_at or utcnow()
    resolution = (payload.get('resolution') or '任务已处理完成。').strip()[:240]
    source_path = (payload.get('source_path') or '').strip()[:160]
    AuditService.record('notifications', 'complete_task', current_api_user(), {
        'notification_id': notification.id,
        'related_type': notification.related_type,
        'related_id': notification.related_id,
        'resolution': resolution,
        'source_path': source_path,
    })
    db.session.commit()
    return api_success(serialize_model(notification, notification_extra), '通知任务已处理')
