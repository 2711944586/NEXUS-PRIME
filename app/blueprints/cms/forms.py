from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, FileField
from wtforms.validators import DataRequired, Length

class ArticleForm(FlaskForm):
    """文章发布表单"""
    title = StringField('公告标题', validators=[DataRequired(), Length(max=100)])
    category = SelectField('分类', choices=[
        ('notice', '📢 公告通知'),
        ('news', '📰 新闻动态'),
        ('docs', '📚 技术文档'),
        ('guide', '🎯 使用指南')
    ], default='notice')
    # content 将存储 Quill.js 生成的 HTML
    content = TextAreaField('内容', validators=[DataRequired()])
    status = SelectField('发布状态', choices=[
        ('published', '立即发布 (Published)'),
        ('draft', '存为草稿 (Draft)')
    ], default='published')
    submit = SubmitField('提交发布')

class UploadForm(FlaskForm):
    """文件上传表单"""
    file = FileField('选择文件')
    submit = SubmitField('开始上传')