"""
云存储工具模块
支持 Cloudinary 云存储，用于头像和附件上传
在生产环境（如 Railway）中使用，因为本地文件系统不持久化
"""
import os
import uuid
from flask import current_app

# Cloudinary 实例（延迟初始化）
_cloudinary_configured = False


def init_cloud_storage(app):
    """初始化云存储配置"""
    global _cloudinary_configured
    
    cloudinary_url = app.config.get('CLOUDINARY_URL')
    cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = app.config.get('CLOUDINARY_API_KEY')
    api_secret = app.config.get('CLOUDINARY_API_SECRET')
    
    # 检查是否配置了 Cloudinary
    if cloudinary_url or (cloud_name and api_key and api_secret):
        try:
            import cloudinary
            
            if cloudinary_url:
                # 使用 URL 配置
                cloudinary.config(cloudinary_url=cloudinary_url)
            else:
                # 使用分离的配置
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True
                )
            
            _cloudinary_configured = True
            app.logger.info('✅ Cloudinary 云存储已配置')
        except ImportError:
            app.logger.warning('⚠️ cloudinary 包未安装，云存储不可用')
        except Exception as e:
            app.logger.error(f'❌ Cloudinary 配置失败: {e}')
    else:
        app.logger.info('ℹ️ 未配置云存储，使用本地文件系统')


def is_cloud_storage_enabled():
    """检查云存储是否可用"""
    use_cloud = current_app.config.get('USE_CLOUD_STORAGE', 'auto')
    
    if use_cloud == 'false' or use_cloud == '0':
        return False
    
    if use_cloud == 'true' or use_cloud == '1':
        return _cloudinary_configured
    
    # auto 模式：生产环境且已配置时启用
    is_production = current_app.config.get('ENV') == 'production' or \
                    os.environ.get('FLASK_ENV') == 'production' or \
                    os.environ.get('RAILWAY_ENVIRONMENT')
    
    return is_production and _cloudinary_configured


def upload_to_cloud(file, folder='uploads', resource_type='auto'):
    """
    上传文件到云存储
    
    Args:
        file: 文件对象 (werkzeug FileStorage) 或文件路径
        folder: 云存储文件夹
        resource_type: 资源类型 ('image', 'raw', 'video', 'auto')
    
    Returns:
        dict: {'url': 公开URL, 'public_id': 云存储ID, 'secure_url': HTTPS URL}
        None: 上传失败
    """
    if not _cloudinary_configured:
        current_app.logger.warning('云存储未配置，无法上传')
        return None
    
    try:
        import cloudinary.uploader
        
        # 生成唯一的 public_id
        unique_id = uuid.uuid4().hex[:12]
        
        # 准备上传参数
        upload_options = {
            'folder': f'nexus_prime/{folder}',
            'public_id': unique_id,
            'resource_type': resource_type,
            'overwrite': True,
        }
        
        # 上传文件
        if hasattr(file, 'read'):
            # FileStorage 对象
            result = cloudinary.uploader.upload(file, **upload_options)
        else:
            # 文件路径
            result = cloudinary.uploader.upload(file, **upload_options)
        
        current_app.logger.info(f'✅ 文件上传到云存储: {result.get("secure_url")}')
        
        return {
            'url': result.get('url'),
            'secure_url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'format': result.get('format'),
            'width': result.get('width'),
            'height': result.get('height'),
            'bytes': result.get('bytes'),
        }
        
    except Exception as e:
        current_app.logger.error(f'❌ 云存储上传失败: {e}')
        return None


def upload_avatar_to_cloud(file):
    """
    上传头像到云存储（带图片处理）
    
    Args:
        file: 图片文件对象
    
    Returns:
        str: 头像 URL（带变换参数）
        None: 上传失败
    """
    if not _cloudinary_configured:
        return None
    
    try:
        import cloudinary.uploader
        
        unique_id = uuid.uuid4().hex[:12]
        
        # 上传并应用头像变换（200x200 正方形裁剪）
        result = cloudinary.uploader.upload(
            file,
            folder='nexus_prime/avatars',
            public_id=unique_id,
            resource_type='image',
            overwrite=True,
            transformation=[
                {'width': 200, 'height': 200, 'crop': 'fill', 'gravity': 'face'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        
        # 返回带变换的 URL
        secure_url = result.get('secure_url')
        current_app.logger.info(f'✅ 头像上传到云存储: {secure_url}')
        
        return secure_url
        
    except Exception as e:
        current_app.logger.error(f'❌ 头像上传失败: {e}')
        return None


def delete_from_cloud(public_id, resource_type='image'):
    """
    从云存储删除文件
    
    Args:
        public_id: 云存储文件 ID
        resource_type: 资源类型
    
    Returns:
        bool: 是否删除成功
    """
    if not _cloudinary_configured:
        return False
    
    try:
        import cloudinary.uploader
        
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        success = result.get('result') == 'ok'
        
        if success:
            current_app.logger.info(f'✅ 云存储文件已删除: {public_id}')
        else:
            current_app.logger.warning(f'⚠️ 云存储文件删除失败: {public_id}')
        
        return success
        
    except Exception as e:
        current_app.logger.error(f'❌ 删除云存储文件失败: {e}')
        return False


def get_cloud_url(public_id, resource_type='image', **transformations):
    """
    获取云存储文件的 URL（可带变换）
    
    Args:
        public_id: 云存储文件 ID
        resource_type: 资源类型
        **transformations: Cloudinary 变换参数
    
    Returns:
        str: 文件 URL
    """
    if not _cloudinary_configured:
        return None
    
    try:
        import cloudinary
        
        return cloudinary.CloudinaryImage(public_id).build_url(
            resource_type=resource_type,
            **transformations
        )
        
    except Exception as e:
        current_app.logger.error(f'❌ 获取云存储 URL 失败: {e}')
        return None
