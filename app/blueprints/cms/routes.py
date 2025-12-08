import os
from flask import render_template, request, flash, redirect, url_for, send_from_directory, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.cms import cms_bp
from app.models.content import Article, Attachment
from app.blueprints.cms.forms import ArticleForm, UploadForm
from app.utils.file_helper import save_file, format_size, get_file_icon

@cms_bp.route('/news')
@login_required
def index():
    """公告列表 / 新闻流"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '', type=str)
    
    # 构建查询
    query = Article.query.filter_by(status='published')
    
    # 如果指定了分类，则筛选
    if category:
        query = query.filter_by(category=category)
    
    pagination = query.order_by(Article.created_at.desc()).paginate(page=page, per_page=6)
    
    return render_template('cms/index.html', 
                           pagination=pagination, 
                           articles=pagination.items,
                           current_category=category)

@cms_bp.route('/article/<int:id>')
@login_required
def article_detail(id):
    """文章详情页"""
    article = Article.query.get_or_404(id)
    # 增加阅读数
    article.view_count += 1
    db.session.commit()
    return render_template('cms/article_detail.html', article=article)

@cms_bp.route('/editor', methods=['GET', 'POST'])
@login_required
def editor():
    """文章发布编辑器"""
    form = ArticleForm()
    if form.validate_on_submit():
        article = Article(
            title=form.title.data,
            category=form.category.data,
            content=form.content.data, # HTML
            status=form.status.data,
            author=current_user
        )
        db.session.add(article)
        db.session.commit()
        flash('内容发布成功！', 'success')
        return redirect(url_for('cms.index'))
    return render_template('cms/editor.html', form=form)

@cms_bp.route('/files', methods=['GET', 'POST'])
@login_required
def files():
    """文件管理器"""
    form = UploadForm()
    
    if request.method == 'POST':
        current_app.logger.info(f'POST 请求收到, request.files keys: {list(request.files.keys())}')
        
        # 直接从request.files获取文件
        if 'file' in request.files:
            file_data = request.files['file']
            current_app.logger.info(f'文件对象: {file_data}, 文件名: {file_data.filename if file_data else "None"}')
            
            if file_data and file_data.filename and file_data.filename.strip():
                try:
                    result = save_file(file_data)
                    if result:
                        orig_name, saved_name, size, mimetype = result
                        attachment = Attachment(
                            filename=orig_name,
                            filepath=saved_name,
                            size=size,
                            mimetype=mimetype,
                            uploader_id=current_user.id
                        )
                        db.session.add(attachment)
                        db.session.commit()
                        flash(f'文件 {orig_name} 上传成功', 'success')
                    else:
                        flash('上传失败：文件类型不支持或文件无效', 'danger')
                except Exception as e:
                    current_app.logger.error(f'上传异常: {str(e)}')
                    import traceback
                    current_app.logger.error(traceback.format_exc())
                    flash(f'上传出错: {str(e)}', 'danger')
            else:
                flash('请选择要上传的文件', 'warning')
        else:
            current_app.logger.warning('request.files 中没有 file 键')
            flash('未检测到上传文件', 'warning')
        return redirect(url_for('cms.files'))

    # 获取所有文件
    files = Attachment.query.order_by(Attachment.created_at.desc()).all()
    # 计算总占用空间
    total_size = sum([f.size for f in files])
    
    return render_template('cms/files.html', 
                           form=form, 
                           files=files, 
                           total_size=format_size(total_size),
                           format_size=format_size,
                           get_icon=get_file_icon)

@cms_bp.route('/files/download/<int:id>')
@login_required
def download_file(id):
    """下载文件"""
    att = Attachment.query.get_or_404(id)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], att.filepath, as_attachment=True, download_name=att.filename)

@cms_bp.route('/files/delete/<int:id>')
@login_required
def delete_file(id):
    """删除文件"""
    att = Attachment.query.get_or_404(id)
    try:
        # 删除物理文件
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filepath)
        if os.path.exists(full_path):
            os.remove(full_path)
        
        db.session.delete(att)
        db.session.commit()
        flash('文件已从服务器物理删除', 'success')
    except Exception as e:
        flash(f'删除失败: {str(e)}', 'danger')
    
    return redirect(url_for('cms.files'))