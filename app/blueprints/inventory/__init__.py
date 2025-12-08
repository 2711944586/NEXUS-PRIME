from flask import Blueprint

# 定义蓝图
inventory_bp = Blueprint('inventory', __name__)

# 导入路由以注册视图函数
from . import routes