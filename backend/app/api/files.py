import os
import uuid
from io import BytesIO

from flask import current_app, redirect, request, send_file, send_from_directory

from app.domains.files.application.events import publish_file_deleted
from app.extensions import db
from app.models.content import Attachment
from app.platform.policy import policy
from app.platform.storage import get_storage_service
from app.services.audit_service import AuditService
from app.utils.cloud_storage import uploads_require_cloud_storage
from app.utils.upload_policy import normalized_upload_mime, validate_upload_type

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import (
    attachment_extra,
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
    storage_service = get_storage_service()
    if storage_service.provider == 'local' and uploads_require_cloud_storage():
        return api_error('当前运行环境需要配置 Cloudinary 才能长期保存文件', status=503, error='persistent_storage_required')
    stored_name = f'{uuid.uuid4().hex}{ext}'
    try:
        stored_object = storage_service.upload(
            file,
            path=f'files/{stored_name}',
            content_type=mimetype,
            metadata={'filename': safe_name, 'uploader_id': current_api_user().id},
        )
    except Exception as exc:
        current_app.logger.warning('File storage upload failed: %s', exc)
        return api_error('文件保存失败，请稍后重试', status=500, error='file_store_failed')
    attachment = Attachment(
        filename=safe_name,
        filepath=stored_object.object_key,
        mimetype=mimetype,
        size=int(stored_object.size or 0),
        uploader_id=current_api_user().id,
    )
    db.session.add(attachment)
    db.session.flush()
    from app.platform.events import outbox

    outbox.add(
        "FileUploaded",
        "Attachment",
        attachment.id,
        {
            "attachment_id": attachment.id,
            "filename": attachment.filename,
            "filepath": attachment.filepath,
            "mimetype": attachment.mimetype,
            "size": int(attachment.size or 0),
            "storage_provider": stored_object.provider,
            "uploader_id": attachment.uploader_id,
        },
        created_by=current_api_user().id,
    )
    AuditService.record('files', 'upload', current_api_user(), {'id': attachment.id, 'filename': safe_name})
    db.session.commit()
    return api_success(serialize_model(attachment, attachment_extra), '上传成功', status=201)


def require_attachment_access(attachment, action, *, permission=None):
    context = {'permission': permission} if permission else None
    decision = policy.can(current_api_user(), action, resource=attachment, context=context)
    if not decision.allowed:
        return api_error(decision.reason or '权限不足', status=403, error=decision.error or 'forbidden')
    return None


@api_bp.get('/files/<int:file_id>/download')
@jwt_required
def api_download_file(file_id):
    attachment = db.session.get(Attachment, file_id)
    if not attachment or attachment.is_deleted:
        return api_error('文件不存在', status=404)
    denied = require_attachment_access(attachment, 'get')
    if denied:
        return denied
    if attachment.filepath and str(attachment.filepath).startswith(('http://', 'https://')):
        return redirect(attachment.filepath, code=302)
    if attachment.filepath and str(attachment.filepath).startswith('cloudinary:'):
        signed_url = get_storage_service().get_signed_url(attachment.filepath)
        if signed_url:
            return redirect(signed_url, code=302)
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
    attachments = Attachment.query.filter(Attachment.id.in_(ids), Attachment.is_deleted == False).all()
    for item in attachments:
        denied = require_attachment_access(item, 'delete', permission='files.manage')
        if denied:
            return denied
    changed = 0
    for item in attachments:
        item.is_deleted = True
        publish_file_deleted(item, deleted_by=current_api_user())
        changed += 1
    AuditService.record('files', 'bulk_delete', current_api_user(), {'ids': ids, 'changed': changed})
    db.session.commit()
    return api_success({'changed': changed, 'ids': ids}, '文件已移入归档')
