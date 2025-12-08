from app.extensions import db
from .base import BaseModel
from datetime import datetime

class AuditLog(BaseModel):
    """系统操作审计"""
    __tablename__ = 'sys_audit_logs'
    
    user_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    module = db.Column(db.String(32)) # e.g., 'auth', 'stock'
    action = db.Column(db.String(64)) # e.g., 'login', 'create_order'
    ip_address = db.Column(db.String(64))
    details = db.Column(db.Text) # JSON 详情
    
    user = db.relationship('User')

class AiChatLog(BaseModel):
    """AI 智脑对话记录"""
    __tablename__ = 'sys_ai_logs'
    
    user_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'))
    prompt = db.Column(db.Text)
    response = db.Column(db.Text) # DeepSeek 的回复
    model_version = db.Column(db.String(32), default='deepseek-v2')


class AiChatSession(BaseModel):
    """AI 对话会话"""
    __tablename__ = 'sys_ai_sessions'
    
    user_id = db.Column(db.Integer, db.ForeignKey('auth_users.id'), nullable=False, index=True)
    title = db.Column(db.String(128), default='新对话')
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    
    # 关系
    user = db.relationship('User', backref=db.backref('ai_sessions', lazy='dynamic'))
    messages = db.relationship('AiChatMessage', backref='session', lazy='dynamic', 
                               order_by='AiChatMessage.created_at', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'lastMessageAt': self.last_message_at.isoformat() if self.last_message_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'messageCount': self.messages.count()
        }


class AiChatMessage(BaseModel):
    """AI 对话消息"""
    __tablename__ = 'sys_ai_messages'
    
    session_id = db.Column(db.Integer, db.ForeignKey('sys_ai_sessions.id'), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    tokens = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'tokens': self.tokens,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }