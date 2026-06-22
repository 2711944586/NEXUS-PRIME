"""安全工具函数"""

from app.platform.auth import check_password_strength


def validate_file_upload(filename, allowed_extensions=None):
    if not allowed_extensions:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    if '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed_extensions
