import os
import uuid

from flask import Response, current_app, request, send_from_directory
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.auth import User
from app.services.audit_service import AuditService
from app.utils.cloud_storage import (
    is_cloud_storage_enabled,
    upload_avatar_to_cloud,
    uploads_require_cloud_storage,
)
from app.utils.upload_policy import upload_size, validate_upload_type

from . import api_bp
from .auth import create_access_token, current_api_user, jwt_required, set_auth_cookies
from .responses import api_error, api_success
from .resource_support import (
    avatar_storage_dir,
    current_payload,
    permission_summary,
    remove_local_avatar,
    safe_upload_name,
    serialize_model,
    user_extra,
)


@api_bp.get('/auth/me')
@jwt_required
def api_me():
    user = current_api_user()
    payload = serialize_model(user, user_extra)
    body, status = api_success({**payload, 'user': payload, 'permissions': permission_summary(user)}, '当前用户')
    response = current_app.make_response((body, status))
    token = create_access_token(user, current_app.config.get('JWT_EXPIRES_HOURS', 12))
    set_auth_cookies(response, token, request.cookies.get('nexus_csrf_token'))
    return response


@api_bp.put('/me/profile')
@jwt_required
def api_update_profile():
    user = current_api_user()
    payload = current_payload()
    allowed = ['username', 'full_name', 'phone', 'position', 'bio', 'department_name']
    for field in allowed:
        if field in payload:
            value = payload.get(field)
            setattr(user, field, str(value).strip() if value is not None else None)
    prefs = payload.get('preferences')
    if isinstance(prefs, dict):
        current = user.preferences or {}
        for key in ('theme', 'density', 'default_workspace'):
            if key in prefs:
                current[key] = prefs[key]
        user.preferences = current
    AuditService.record('profile', 'update', user, {'fields': [field for field in allowed if field in payload]})
    db.session.commit()
    return api_success(serialize_model(user, user_extra), '个人资料已更新')


@api_bp.post('/me/avatar')
@jwt_required
def api_upload_avatar():
    file = request.files.get('file')
    if not file or not file.filename:
        return api_error('请选择头像文件', status=400, error='missing_file')
    safe_name = safe_upload_name(file.filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext.lstrip('.') not in {'png', 'jpg', 'jpeg', 'gif'}:
        return api_error('头像仅支持 png、jpg、jpeg、gif', status=400, error='unsupported_avatar_type')
    max_bytes = int(current_app.config.get('AVATAR_MAX_BYTES', 3 * 1024 * 1024))
    if upload_size(file) > max_bytes:
        return api_error('头像文件不能超过 3MB', status=400, error='avatar_too_large')
    if not validate_upload_type(file, ext):
        return api_error('头像内容类型不允许', status=400, error='unsupported_mime_type')
    user = current_api_user()
    old_avatar = user.avatar
    if is_cloud_storage_enabled():
        cloud_url = upload_avatar_to_cloud(file)
        if not cloud_url:
            return api_error('头像保存失败，请稍后重试', status=500, error='avatar_store_failed')
        user.avatar = cloud_url
    elif uploads_require_cloud_storage():
        return api_error('当前运行环境需要配置 Cloudinary 才能长期保存头像', status=503, error='persistent_storage_required')
    else:
        avatar_dir = avatar_storage_dir()
        os.makedirs(avatar_dir, exist_ok=True)
        stored_name = f'avatar-{user.id}-{uuid.uuid4().hex}{ext}'
        filepath = os.path.join(avatar_dir, stored_name)
        file.save(filepath)
        user.avatar = f'/api/v1/avatars/{stored_name}'
    AuditService.record('profile', 'avatar_upload', current_api_user(), {'filename': safe_name})
    db.session.commit()
    remove_local_avatar(old_avatar)
    return api_success(serialize_model(current_api_user(), user_extra), '头像已更新')


@api_bp.delete('/me/avatar')
@jwt_required
def api_delete_avatar():
    user = current_api_user()
    old_avatar = user.avatar
    user.avatar = None
    AuditService.record('profile', 'avatar_delete', user, {})
    db.session.commit()
    remove_local_avatar(old_avatar)
    return api_success(serialize_model(user, user_extra), '头像已恢复默认')


@api_bp.get('/avatars/<path:filename>')
def api_avatar_file(filename):
    if filename.startswith('initials/'):
        return initials_avatar_response(filename.split('/', 1)[1])
    safe_name = secure_filename(filename)
    avatar_dir = avatar_storage_dir()
    avatar_root = os.path.abspath(avatar_dir)
    filepath = os.path.abspath(os.path.join(avatar_dir, safe_name))
    if safe_name and os.path.commonpath([avatar_root, filepath]) == avatar_root and os.path.exists(filepath):
        return send_from_directory(avatar_dir, safe_name)
    return initials_avatar_response(avatar_fallback_key(safe_name))


@api_bp.get('/avatars/initials/<path:key>')
def api_initials_avatar(key):
    return initials_avatar_response(key)


def avatar_fallback_key(filename):
    parts = (filename or '').split('-')
    if len(parts) >= 3 and parts[0] == 'avatar' and parts[1].isdigit():
        user = db.session.get(User, int(parts[1]))
        if user:
            label = user.full_name or user.username or user.email or f'user-{user.id}'
            return f'{user.id}-{label[:8]}'
    return os.path.splitext(filename or '')[0] or 'nexus-user'


def initials_avatar_response(key):
    label = key.split('-', 1)[1] if '-' in key else key
    initials = ''.join(ch for ch in label if ch.isalnum())[:2].upper() or 'NX'
    palette = ['#62d8cb', '#9aa8ff', '#f0b76a', '#ff8fa3', '#c5a8ff', '#67d19b']
    accent = palette[sum(ord(ch) for ch in key) % len(palette)]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="{accent}" offset="0"/>
      <stop stop-color="#111827" offset="1"/>
    </linearGradient>
  </defs>
  <rect width="128" height="128" rx="36" fill="url(#g)"/>
  <circle cx="96" cy="28" r="30" fill="rgba(255,255,255,.22)"/>
  <text x="64" y="76" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="34" font-weight="800" fill="#fff">{initials}</text>
</svg>'''
    return Response(svg, mimetype='image/svg+xml')
