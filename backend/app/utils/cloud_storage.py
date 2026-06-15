import os
import tempfile
import uuid
from flask import current_app

_cloudinary_configured = False


def init_cloud_storage(app):
    global _cloudinary_configured
    
    cloudinary_url = app.config.get('CLOUDINARY_URL')
    cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = app.config.get('CLOUDINARY_API_KEY')
    api_secret = app.config.get('CLOUDINARY_API_SECRET')
    
    if cloudinary_url or (cloud_name and api_key and api_secret):
        try:
            import cloudinary
            
            if cloudinary_url:
                cloudinary.config(cloudinary_url=cloudinary_url)
            else:
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True
                )
            
            _cloudinary_configured = True
            app.logger.info('Cloudinary storage is configured')
        except ImportError:
            app.logger.warning('cloudinary package is not installed; cloud storage is unavailable')
        except Exception as e:
            app.logger.error(f'Cloudinary configuration failed: {e}')
    else:
        app.logger.info('Cloud storage is not configured; using local file storage')


def is_cloud_storage_enabled():
    use_cloud = str(current_app.config.get('USE_CLOUD_STORAGE', 'auto')).lower()
    
    if use_cloud == 'false' or use_cloud == '0':
        return False
    
    if use_cloud == 'true' or use_cloud == '1':
        return _cloudinary_configured
    
    # auto 模式：生产环境且已配置时启用
    is_production = current_app.config.get('ENV') == 'production' or \
                    os.environ.get('FLASK_ENV') == 'production'
    
    return is_production and _cloudinary_configured


def uploads_require_cloud_storage():
    mode = str(current_app.config.get('REQUIRE_CLOUD_STORAGE_FOR_UPLOADS', 'auto')).lower()
    if mode in ('false', '0'):
        return False
    if mode in ('true', '1'):
        return True

    upload_folder = os.path.abspath(current_app.config.get('UPLOAD_FOLDER', ''))
    temp_root = os.path.abspath(tempfile.gettempdir())
    return (
        os.environ.get('VERCEL') == '1'
        or upload_folder == temp_root
        or upload_folder.startswith(temp_root + os.sep)
    )


def upload_to_cloud(file, folder='uploads', resource_type='auto'):
    if not _cloudinary_configured:
        current_app.logger.warning('Cloud storage is not configured')
        return None
    
    try:
        import cloudinary.uploader
        
        unique_id = uuid.uuid4().hex[:12]
        upload_options = {
            'folder': f'nexus_prime/{folder}',
            'public_id': unique_id,
            'resource_type': resource_type,
            'overwrite': True,
        }

        if hasattr(file, 'read'):
            result = cloudinary.uploader.upload(file, **upload_options)
        else:
            result = cloudinary.uploader.upload(file, **upload_options)
        
        current_app.logger.info(f'File uploaded to cloud storage: {result.get("secure_url")}')
        
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
        current_app.logger.error(f'Cloud storage upload failed: {e}')
        return None


def upload_avatar_to_cloud(file):
    if not _cloudinary_configured:
        return None
    
    try:
        import cloudinary.uploader
        
        unique_id = uuid.uuid4().hex[:12]
        
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

        secure_url = result.get('secure_url')
        current_app.logger.info(f'Avatar uploaded to cloud storage: {secure_url}')
        
        return secure_url
        
    except Exception as e:
        current_app.logger.error(f'Avatar upload failed: {e}')
        return None


def delete_from_cloud(public_id, resource_type='image'):
    if not _cloudinary_configured:
        return False
    
    try:
        import cloudinary.uploader
        
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        success = result.get('result') == 'ok'
        
        if success:
            current_app.logger.info(f'Cloud storage file deleted: {public_id}')
        else:
            current_app.logger.warning(f'Cloud storage file delete failed: {public_id}')
        
        return success
        
    except Exception as e:
        current_app.logger.error(f'Cloud storage file delete failed: {e}')
        return False


def get_cloud_url(public_id, resource_type='image', **transformations):
    if not _cloudinary_configured:
        return None
    
    try:
        import cloudinary
        
        return cloudinary.CloudinaryImage(public_id).build_url(
            resource_type=resource_type,
            **transformations
        )
        
    except Exception as e:
        current_app.logger.error(f'Cloud storage URL build failed: {e}')
        return None
