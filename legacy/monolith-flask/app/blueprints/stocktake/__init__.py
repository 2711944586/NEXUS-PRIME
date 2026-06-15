from flask import Blueprint

# 定义盘点蓝图
stocktake_bp = Blueprint('stocktake', __name__)

# 导入路由
from . import routes
