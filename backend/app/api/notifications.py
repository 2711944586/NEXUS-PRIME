import json
import time

from flask import Response, current_app, request, stream_with_context

from app.extensions import db
from app.models.notification import Notification
from app.platform.policy import filter_fields, filter_query
from app.services.audit_service import AuditService
from app.utils.time import utcnow

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import is_admin_user, notification_extra, serialize_model


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f"event: {event}\ndata: {payload}\n\n"


def _notification_stream_payload(user, limit: int) -> dict:
    query = Notification.query.filter(Notification.is_deleted == False)
    query = filter_query(query, Notification, user)
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )
    return {
        'items': [
            filter_fields(user, Notification, serialize_model(item, notification_extra))
            for item in rows
        ],
        'unread': query.filter(Notification.is_read == False).count(),
        'generated_at': utcnow().isoformat(),
    }


@api_bp.get('/notifications/unread-count')
@jwt_required
def notifications_unread_count():
    user = current_api_user()
    q = Notification.query.filter_by(is_deleted=False, is_read=False)
    if not is_admin_user(user):
        q = q.filter_by(user_id=user.id)
    return api_success({'unread': q.count()}, '未读通知数')


@api_bp.get('/notifications/stream')
@jwt_required
def notifications_stream():
    user = current_api_user()
    max_events = max(1, int(current_app.config.get('NOTIFICATION_STREAM_MAX_EVENTS', 25)))
    interval_seconds = max(0.0, float(current_app.config.get('NOTIFICATION_STREAM_INTERVAL_SECONDS', 2.0)))
    limit = min(200, max(1, int(current_app.config.get('NOTIFICATION_STREAM_LIMIT', 100))))

    def generate():
        for index in range(max_events):
            yield _sse_event('snapshot', _notification_stream_payload(user, limit))
            if index < max_events - 1 and interval_seconds:
                time.sleep(interval_seconds)

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


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
