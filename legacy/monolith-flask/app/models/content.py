from app.extensions import db
from .base import BaseModel

class Article(BaseModel):
    """CMS 文章/公告"""
    __tablename__ = 'cms_articles'
    
    title = db.Column(db.String(256))
    content = db.Column(db.Text) # HTML 内容
    content_raw = db.Column(db.Text) # Markdown 原始内容
    category = db.Column(db.String(32), default='notice')  # notice公告, news新闻, docs文档, guide指南
    
    author_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    status = db.Column(db.String(20), default='published') # draft, published
    
    view_count = db.Column(db.Integer, default=0)
    
    author = db.relationship('User')

class Attachment(BaseModel):
    """文件附件"""
    __tablename__ = 'cms_attachments'
    
    filename = db.Column(db.String(256))
    filepath = db.Column(db.String(512)) # 存储路径
    mimetype = db.Column(db.String(64))
    size = db.Column(db.Integer) # 字节数
    
    uploader_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))