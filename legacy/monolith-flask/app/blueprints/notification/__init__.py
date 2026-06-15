from flask import Blueprint

# 定义通知蓝图
notification_bp = Blueprint('notification', __name__)

# 导入路由
from . import routes
