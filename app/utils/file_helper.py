import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'txt', 'csv', 'ppt', 'pptx', 'mp4', 'mp3', 'wav', 'avi', 'mov'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def get_file_extension(filename):
    """从文件名获取扩展名"""
    if not filename or '.' not in filename:
        return None
    return filename.rsplit('.', 1)[1].lower()

def save_file(file):
    """
    安全保存文件
    返回: (original_name, saved_filename, file_size, mimetype)
    """
    try:
        if not file or not file.filename:
            current_app.logger.warning('save_file: 没有文件或文件名为空')
            return None
        
        original_filename = file.filename
        current_app.logger.info(f'save_file: 原始文件名 = {original_filename}')
        
        # 从原始文件名获取扩展名（在 secure_filename 之前）
        ext = get_file_extension(original_filename)
        if not ext:
            current_app.logger.warning(f'save_file: 无法获取扩展名')
            return None
            
        if ext not in ALLOWED_EXTENSIONS:
            current_app.logger.warning(f'save_file: 扩展名 {ext} 不允许')
            return None
        
        # 处理文件名 - secure_filename 可能会清空中文字符
        safe_name = secure_filename(original_filename)
        current_app.logger.info(f'save_file: secure_filename 结果 = {safe_name}')
        
        # 如果 secure_filename 返回空或没有扩展名，使用 uuid 作为文件名
        if not safe_name or '.' not in safe_name:
            safe_name = f"file_{uuid.uuid4().hex[:8]}.{ext}"
            current_app.logger.info(f'save_file: 使用生成的文件名 = {safe_name}')
        
        # 生成唯一文件名防止覆盖
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        
        # 确保上传目录存在
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            current_app.logger.info(f'save_file: 创建目录 {upload_folder}')
        
        save_path = os.path.join(upload_folder, unique_name)
        current_app.logger.info(f'save_file: 保存路径 = {save_path}')
        
        file.save(save_path)
        
        # 验证文件是否保存成功
        if not os.path.exists(save_path):
            current_app.logger.error(f'save_file: 文件保存后不存在')
            return None
        
        file_size = os.path.getsize(save_path)
        current_app.logger.info(f'save_file: 文件保存成功, 大小 = {file_size}')
        
        # 返回安全处理后的文件名（保留原始名称用于显示）
        display_name = safe_name if safe_name and '.' in safe_name else f"file.{ext}"
        
        return display_name, unique_name, file_size, file.mimetype or 'application/octet-stream'
        
    except Exception as e:
        current_app.logger.error(f'save_file: 异常 - {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        return None

def format_size(size):
    """将字节转换为易读格式 (KB, MB)"""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}B"

def get_file_icon(mimetype):
    """根据类型返回 FontAwesome 图标类名和颜色 (icon_class, color)"""
    if 'image' in mimetype:
        return ('fas fa-file-image', '#10b981')
    if 'pdf' in mimetype:
        return ('fas fa-file-pdf', '#ef4444')
    if 'word' in mimetype or 'document' in mimetype:
        return ('fas fa-file-word', '#6366f1')
    if 'excel' in mimetype or 'sheet' in mimetype:
        return ('fas fa-file-excel', '#10b981')
    if 'zip' in mimetype or 'compressed' in mimetype:
        return ('fas fa-file-archive', '#fbbf24')
    if 'text' in mimetype:
        return ('fas fa-file-alt', '#9ca3af')
    if 'video' in mimetype:
        return ('fas fa-file-video', '#a855f7')
    if 'audio' in mimetype:
        return ('fas fa-file-audio', '#ec4899')
    return ('fas fa-file', '#6b7280')