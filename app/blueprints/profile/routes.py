import os
import uuid
from flask import render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from sqlalchemy.orm.attributes import flag_modified

from . import profile_bp
from .forms import ProfileForm
from app.extensions import db
from app.models.auth import User

@profile_bp.route('/')
@login_required
def view():
    """查看个人信息"""
    return render_template('profile/view.html', user=current_user)

@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """编辑个人信息"""
    form = ProfileForm(obj=current_user)
    
    if request.method == 'POST':
        try:
            current_app.logger.info('=== 开始处理个人信息更新 ===')
            current_app.logger.info(f'request.files: {list(request.files.keys())}')
            current_app.logger.info(f'request.form: {list(request.form.keys())}')
            
            # 更新基本信息
            current_user.username = request.form.get('username', current_user.username)
            current_user.email = request.form.get('email', current_user.email)
            current_user.phone = request.form.get('phone', '')
            current_user.department_name = request.form.get('department', '')
            current_user.position = request.form.get('position', '')
            current_user.bio = request.form.get('bio', '')
            
            # 更新偏好设置 - 使用深拷贝和flag_modified确保JSON字段变化被检测
            prefs = dict(current_user.preferences or {})
            prefs['theme'] = request.form.get('theme_preference', 'auto')
            prefs['language'] = request.form.get('language', 'zh-CN')
            current_user.preferences = prefs
            flag_modified(current_user, 'preferences')
            
            # 处理头像上传
            if 'avatar' in request.files:
                avatar_file = request.files['avatar']
                current_app.logger.info(f'头像文件对象: {avatar_file}')
                current_app.logger.info(f'头像文件名: {avatar_file.filename if avatar_file else "None"}')
                
                if avatar_file and avatar_file.filename and avatar_file.filename.strip() != '':
                    current_app.logger.info(f'开始处理头像上传...')
                    avatar_path = save_avatar(avatar_file)
                    if avatar_path:
                        current_user.avatar = avatar_path
                        flag_modified(current_user, 'avatar')
                        current_app.logger.info(f'头像路径已设置为: {avatar_path}')
                    else:
                        flash('头像上传失败，请检查文件格式。', 'warning')
                else:
                    current_app.logger.info('没有选择新头像')
            else:
                current_app.logger.info('request.files 中没有 avatar 键')
            
            db.session.commit()
            current_app.logger.info(f'数据库已提交, 当前头像路径: {current_user.avatar}')
            flash('个人信息更新成功！', 'success')
            return redirect(url_for('profile.view'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'更新个人信息失败: {str(e)}')
            import traceback
            current_app.logger.error(traceback.format_exc())
            flash(f'更新失败：{str(e)}', 'danger')
    
    return render_template('profile/edit.html', form=form)

def save_avatar(file):
    """保存头像图片（支持云存储和本地存储）"""
    try:
        # 检查文件是否有效
        if not file or not file.filename:
            current_app.logger.warning('没有提供头像文件')
            return None
        
        original_filename = file.filename
        current_app.logger.info(f'原始文件名: {original_filename}')
        
        # 从原始文件名获取扩展名（在 secure_filename 之前）
        if '.' not in original_filename:
            current_app.logger.warning('文件名没有扩展名')
            return None
            
        ext = '.' + original_filename.rsplit('.', 1)[1].lower()
        current_app.logger.info(f'文件扩展名: {ext}')
        
        if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
            current_app.logger.warning(f'不支持的文件格式: {ext}')
            return None
        
        # 检查是否使用云存储
        from app.utils.cloud_storage import is_cloud_storage_enabled, upload_avatar_to_cloud
        
        if is_cloud_storage_enabled():
            current_app.logger.info('使用云存储上传头像')
            cloud_url = upload_avatar_to_cloud(file)
            if cloud_url:
                current_app.logger.info(f'头像云存储 URL: {cloud_url}')
                return cloud_url  # 返回完整的云存储 URL
            else:
                current_app.logger.warning('云存储上传失败，回退到本地存储')
        
        # 本地存储模式
        filename = f"{uuid.uuid4().hex}{ext}"
        
        # 确保目录存在
        avatar_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars')
        os.makedirs(avatar_dir, exist_ok=True)
        
        filepath = os.path.join(avatar_dir, filename)
        current_app.logger.info(f'正在保存头像到: {filepath}')
        
        # 打开并调整图片大小
        image = Image.open(file)
        
        # 转换为RGB（处理RGBA/PNG）
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # 生成正方形缩略图（200x200）
        image.thumbnail((200, 200), Image.Resampling.LANCZOS)
        
        # 裁剪为正方形
        width, height = image.size
        if width != height:
            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            image = image.crop((left, top, left + size, top + size))
        
        # 保存 - 根据格式选择保存参数
        if ext in ['.jpg', '.jpeg']:
            image.save(filepath, 'JPEG', quality=90, optimize=True)
        elif ext == '.png':
            image.save(filepath, 'PNG', optimize=True)
        elif ext == '.gif':
            image.save(filepath, 'GIF')
        else:
            image.save(filepath, quality=90, optimize=True)
        
        # 验证文件是否保存成功
        if not os.path.exists(filepath):
            current_app.logger.error('文件保存后不存在')
            return None
        
        # 返回相对路径（用于URL）
        relative_path = f'uploads/avatars/{filename}'
        current_app.logger.info(f'头像保存成功: {relative_path}')
        return relative_path
        
    except Exception as e:
        current_app.logger.error(f'保存头像失败: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        return None


@profile_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    try:
        data = request.get_json() or request.form
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        # 验证当前密码
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({'success': False, 'message': '当前密码不正确'}), 400
        
        # 验证新密码
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '新密码长度至少6位'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400
        
        # 更新密码
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        current_app.logger.info(f'用户 {current_user.username} 修改了密码')
        return jsonify({'success': True, 'message': '密码修改成功'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'修改密码失败: {str(e)}')
        return jsonify({'success': False, 'message': f'修改失败: {str(e)}'}), 500
