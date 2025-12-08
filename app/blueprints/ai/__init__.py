"""AI 助手蓝图"""
from flask import Blueprint

ai_bp = Blueprint('ai', __name__)

from . import routes
