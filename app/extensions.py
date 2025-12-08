from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from flask_assets import Environment
from flask_wtf.csrf import CSRFProtect

# 初始化扩展对象 (暂不绑定 app)
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
assets = Environment()
login_manager = LoginManager()
csrf = CSRFProtect()

# 配置 LoginManager
login_manager.login_view = 'auth.login'  # 未登录跳转视图
login_manager.login_message = 'NEXUS 安全警报：请先验证您的身份权限。'
login_manager.login_message_category = 'warning'  # 消息类别
login_manager.session_protection = 'strong'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login 用户加载回调"""
    from app.models import User
    return User.query.get(int(user_id))