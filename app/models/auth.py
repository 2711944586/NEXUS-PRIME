from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager
from .base import BaseModel

# 多对多关系表：角色 <-> 权限
roles_permissions = db.Table('roles_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('auth_roles.id')),
    db.Column('permission_id', db.Integer, db.ForeignKey('auth_permissions.id'))
)

class Permission(BaseModel):
    """权限点"""
    __tablename__ = 'auth_permissions'
    name = db.Column(db.String(64), unique=True)  # 例如: 'inventory.create'
    description = db.Column(db.String(128))

    def __repr__(self):
        return f'<Permission {self.name}>'

class Role(BaseModel):
    """角色"""
    __tablename__ = 'auth_roles'
    name = db.Column(db.String(64), unique=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # 关系
    permissions = db.relationship('Permission', secondary=roles_permissions, backref='roles')
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

class Department(BaseModel):
    """部门 (树形结构)"""
    __tablename__ = 'auth_departments'
    name = db.Column(db.String(64))
    code = db.Column(db.String(32), unique=True) # 部门代号
    
    # 自关联：上级部门
    parent_id = db.Column(db.Integer, db.ForeignKey('auth_departments.id'), nullable=True)
    children = db.relationship('Department', backref=db.backref('parent', remote_side='Department.id'))
    users = db.relationship('User', backref='department', lazy='dynamic')

class User(UserMixin, BaseModel):
    """用户"""
    __tablename__ = 'auth_users'
    email = db.Column(db.String(128), unique=True, index=True)
    username = db.Column(db.String(64), index=True)
    password_hash = db.Column(db.String(128))
    
    # 个人信息（从user.py合并）
    full_name = db.Column(db.String(128))
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(256)) # 头像URL
    department_name = db.Column(db.String(100))  # 部门名称（独立字段）
    position = db.Column(db.String(100))
    bio = db.Column(db.Text)
    preferences = db.Column(db.JSON)  # 存储用户偏好设置
    
    is_active_user = db.Column(db.Boolean, default=True) # 封号开关
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    
    # 安全字段
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_password_change = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # 外键
    role_id = db.Column(db.Integer, db.ForeignKey('auth_roles.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('auth_departments.id'))

    @property
    def password(self):
        raise AttributeError('密码不可读')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def check_password(self, password):
        """兼容旧接口"""
        return self.verify_password(password)
    
    def set_password(self, password):
        """兼容旧接口"""
        self.password = password
    
    def is_locked(self):
        """检查账号是否被锁定"""
        from datetime import datetime
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return True
        return False
    
    def record_failed_login(self):
        """记录登录失败"""
        from datetime import datetime, timedelta
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()
    
    def reset_failed_attempts(self):
        """重置失败次数"""
        from datetime import datetime
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def can(self, permission):
        """
        检查用户是否具有指定权限
        管理员拥有所有权限
        """
        if self.is_admin:
            return True
        if self.role and self.role.is_admin:
            return True
        if self.role:
            for perm in self.role.permissions:
                if perm.name == permission:
                    return True
        return False
    
    # Flask-Login 必须属性覆盖
    @property
    def is_active(self):
        return self.is_active_user and not self.is_deleted and not self.is_locked()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))