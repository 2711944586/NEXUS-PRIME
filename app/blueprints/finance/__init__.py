from flask import Blueprint

# 定义财务蓝图
finance_bp = Blueprint('finance', __name__)

# 导入路由
from . import routes
