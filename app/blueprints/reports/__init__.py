from flask import Blueprint

# 注意：url_prefix 在 app/__init__.py 注册时设置，这里不重复设置
reports_bp = Blueprint('reports', __name__)

from . import routes
