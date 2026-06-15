from flask import Blueprint

# 定义采购蓝图
purchase_bp = Blueprint('purchase', __name__)

# 导入路由
from . import routes
