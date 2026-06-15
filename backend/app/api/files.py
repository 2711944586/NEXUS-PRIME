import os
import uuid
from io import BytesIO

from flask import current_app, redirect, request, send_file, send_from_directory

from app.extensions import db
from app.models.content import Attachment
from app.services.audit_service import AuditService
from app.utils.cloud_storage import is_cloud_storage_enabled, upload_to_cloud, uploads_require_cloud_storage
from app.utils.upload_policy import normalized_upload_mime, validate_upload_type

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import (
    attachment_extra,
    file_storage_dir,
    is_admin_user,
    require_permission,
    resolve_attachment_path,
    safe_upload_name,
    serialize_model,
)


@api_bp.post('/files/upload')
@jwt_required
def api_upload_file():
    file = request.files.get('file')
    if not file or not file.filename:
        return api_error('请选择要上传的文件', status=400)
    safe_name = safe_upload_name(file.filename)
    if not safe_name:
        return api_error('文件名无效', status=400, error='invalid_filename')
    ext = os.path.splitext(safe_name)[1].lower()
    allowed_exts = current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS', set())
    if ext.lstrip('.') not in allowed_exts:
        return api_error('不支持的文件类型', status=400, error='unsupported_file_type')
    if not validate_upload_type(file, ext):
        return api_error('文件内容类型不允许', status=400, error='unsupported_mime_type')
    mimetype = normalized_upload_mime(file, ext)
    if is_cloud_storage_enabled():
        result = upload_to_cloud(file, folder='attachments', resource_type='auto')
        if not result:
            return api_error('文件保存失败，请稍后重试', status=500, error='file_store_failed')
        stored_name = result.get('secure_url') or result.get('url')
        file_size = int(result.get('bytes') or 0)
    elif uploads_require_cloud_storage():
        return api_error('当前运行环境需要配置 Cloudinary 才能长期保存文件', status=503, error='persistent_storage_required')
    else:
        stored_name = f'{uuid.uuid4().hex}{ext}'
        upload_dir = file_storage_dir()
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, stored_name)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
    attachment = Attachment(
        filename=safe_name,
        filepath=stored_name if stored_name.startswith(('http://', 'https://')) else f'files/{stored_name}',
        mimetype=mimetype,
        size=file_size,
        uploader_id=current_api_user().id,
    )
    db.session.add(attachment)
    db.session.flush()
    AuditService.record('files', 'upload', current_api_user(), {'id': attachment.id, 'filename': safe_name})
    db.session.commit()
    return api_success(serialize_model(attachment, attachment_extra), '上传成功', status=201)


@api_bp.get('/files/<int:file_id>/download')
@jwt_required
def api_download_file(file_id):
    attachment = db.session.get(Attachment, file_id)
    if not attachment or attachment.is_deleted:
        return api_error('文件不存在', status=404)
    if attachment.uploader_id != current_api_user().id and not is_admin_user(current_api_user()):
        return api_error('权限不足', status=403, error='forbidden')
    if attachment.filepath and str(attachment.filepath).startswith(('http://', 'https://')):
        return redirect(attachment.filepath, code=302)
    resolved_path = resolve_attachment_path(attachment.filepath)
    if not resolved_path:
        stream = BytesIO(
            (
                f'{attachment.filename}\n'
                f'文件记录 ID: {attachment.id}\n'
                f'创建时间: {attachment.created_at.isoformat() if attachment.created_at else ""}\n'
                '该文件记录来自系统资料库，可重新上传正式附件替换。'
            ).encode('utf-8')
        )
        return send_file(
            stream,
            mimetype='text/plain; charset=utf-8',
            as_attachment=True,
            download_name=(attachment.filename or f'file-{attachment.id}.txt'),
        )
    root_dir, relative_path = resolved_path
    return send_from_directory(
        root_dir,
        relative_path,
        as_attachment=True,
        download_name=attachment.filename,
    )


@api_bp.post('/files/bulk-delete')
@jwt_required
def files_bulk_delete():
    denied = require_permission('files.manage', '需要文件管理权限')
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    ids = [int(item) for item in payload.get('ids', []) if str(item).isdigit()]
    if not ids:
        return api_error('请选择要删除的文件', status=400, error='empty_ids')
    changed = 0
    query = Attachment.query.filter(Attachment.id.in_(ids), Attachment.is_deleted == False)
    if not is_admin_user(current_api_user()):
        query = query.filter(Attachment.uploader_id == current_api_user().id)
    for item in query:
        item.is_deleted = True
        changed += 1
    AuditService.record('files', 'bulk_delete', current_api_user(), {'ids': ids, 'changed': changed})
    db.session.commit()
    return api_success({'changed': changed, 'ids': ids}, '文件已移入归档')
