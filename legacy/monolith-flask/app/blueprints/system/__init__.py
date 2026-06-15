# 系统管理蓝图
from flask import Blueprint

bp = Blueprint('system', __name__, url_prefix='/system')

from . import routes
