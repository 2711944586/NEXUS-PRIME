import logging
import colorlog
from flask import Flask, render_template
from config import config
from app.extensions import db, migrate, login_manager, cache, assets, csrf

# 新增：导入 commands 模块，用于注册 CLI 命令
from app import commands


def create_app(config_name='default'):
    """NEXUS PRIME 应用工厂函数"""
    app = Flask(__name__)
    
    # 1. 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 2. 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    assets.init_app(app)
    csrf.init_app(app)

    # 3. 配置日志
    configure_logging(app)

    # 4. 注册蓝图 (Blueprints)
    register_blueprints(app)

    # 5. 注册全局错误处理
    register_error_handlers(app)

    # 6. 注册 CLI 命令
    register_commands(app)

    return app


def register_blueprints(app):
    """注册所有业务模块蓝图"""
    # 主页蓝图
    from app.blueprints.main import main_bp
    app.register_blueprint(main_bp)
    
    # 认证蓝图
    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # 库存管理蓝图
    from app.blueprints.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    
    # 销售管理蓝图
    from app.blueprints.sales import sales_bp
    app.register_blueprint(sales_bp, url_prefix='/sales')
    
    # 内容管理蓝图
    from app.blueprints.cms import cms_bp
    app.register_blueprint(cms_bp, url_prefix='/cms')
    
    # AI 助手蓝图
    from app.blueprints.ai import ai_bp
    app.register_blueprint(ai_bp, url_prefix='/ai')
    
    # 个人信息蓝图
    from app.blueprints.profile import profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')
    
    # 报表分析蓝图
    from app.blueprints.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    # 系统管理蓝图
    from app.blueprints.system import bp as system_bp
    app.register_blueprint(system_bp)
    
    # 采购管理蓝图
    from app.blueprints.purchase import purchase_bp
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    
    # 财务管理蓝图
    from app.blueprints.finance import finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')
    
    # 盘点管理蓝图
    from app.blueprints.stocktake import stocktake_bp
    app.register_blueprint(stocktake_bp, url_prefix='/stocktake')
    
    # 通知与预警蓝图
    from app.blueprints.notification import notification_bp
    app.register_blueprint(notification_bp, url_prefix='/notification')


def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500


def register_commands(app):
    """注册 Flask CLI 命令"""
    app.cli.add_command(commands.forge)
    app.cli.add_command(commands.status)
    app.cli.add_command(commands.forge_finance)


def configure_logging(app):
    """配置彩色控制台日志，提升开发体验"""
    if app.debug:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(blue)s%(message)s",
            datefmt="%H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)