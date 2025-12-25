"""
权限控制工具
提供装饰器和辅助函数用于检查用户权限
"""
from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


def admin_required(f):
    """
    管理员权限装饰器
    只有管理员（is_admin=True 或 role.is_admin=True）才能访问
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not is_admin():
            flash('您没有权限访问此页面', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    """
    权限检查装饰器
    检查用户是否具有指定权限
    
    用法:
        @permission_required('inventory.edit')
        def edit_product():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if not current_user.can(permission):
                flash('您没有权限执行此操作', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def is_admin():
    """检查当前用户是否是管理员"""
    if not current_user.is_authenticated:
        return False
    
    # 检查用户直接的 is_admin 标志
    if current_user.is_admin:
        return True
    
    # 检查用户角色的 is_admin 标志
    if current_user.role and current_user.role.is_admin:
        return True
    
    return False


def can_access_module(module_name):
    """
    检查当前用户是否可以访问指定模块
    
    模块权限映射:
    - system: 系统管理（团队管理、审计日志、系统设置、数据导入）
    - finance: 财务管理
    - reports: 数据分析/报表
    - inventory: 库存管理
    - sales: 销售订单
    - purchase: 采购管理
    - stocktake: 库存盘点
    - cms: 内容管理
    - ai: AI 助手
    """
    if not current_user.is_authenticated:
        return False
    
    # 管理员可以访问所有模块
    if is_admin():
        return True
    
    # 系统管理模块只有管理员可以访问
    admin_only_modules = ['system']
    if module_name in admin_only_modules:
        return False
    
    # 其他模块普通用户可以访问（可以根据需要细化权限）
    return True


def get_user_menu_items():
    """
    根据用户权限获取可见的菜单项
    返回用户可以看到的菜单配置
    """
    if not current_user.is_authenticated:
        return []
    
    # 基础菜单（所有登录用户可见）
    menu_items = [
        {'name': '指挥舱', 'icon': 'fa-chart-pie', 'endpoint': 'main.index', 'badge': 'Dashboard'},
        {'name': '量子仓储', 'icon': 'fa-box', 'endpoint': 'inventory.index', 'badge': 'WMS'},
        {'name': '商业订单', 'icon': 'fa-file-invoice', 'endpoint': 'sales.kanban', 'badge': 'CRM'},
        {'name': '采购管理', 'icon': 'fa-truck-loading', 'endpoint': 'purchase.index', 'badge': 'PO'},
        {'name': '财务管理', 'icon': 'fa-chart-line', 'endpoint': 'finance.index', 'badge': 'FIN'},
        {'name': '库存盘点', 'icon': 'fa-clipboard-check', 'endpoint': 'stocktake.index', 'badge': 'ST'},
        {'name': '资讯中心', 'icon': 'fa-rss', 'endpoint': 'cms.index', 'badge': 'CMS'},
        {'name': '数字资产', 'icon': 'fa-folder-open', 'endpoint': 'cms.files', 'badge': 'Files'},
        {'name': 'AI 智脑', 'icon': 'fa-robot', 'endpoint': 'ai.chat_page', 'badge': 'DeepSeek'},
        {'name': '数据分析', 'icon': 'fa-chart-bar', 'endpoint': 'reports.index', 'badge': 'Reports'},
    ]
    
    # 系统管理菜单（仅管理员可见）
    system_menu = []
    if is_admin():
        system_menu = [
            {'name': '消息通知', 'icon': 'fa-bell', 'endpoint': 'notification.index', 'badge': 'Msg'},
            {'name': '库存预警', 'icon': 'fa-exclamation-triangle', 'endpoint': 'notification.alerts', 'badge': 'Alert'},
            {'name': '数据导入', 'icon': 'fa-upload', 'endpoint': 'system.data_import', 'badge': 'Import'},
            {'name': '团队管理', 'icon': 'fa-users-cog', 'endpoint': 'system.team', 'badge': 'Team'},
            {'name': '审计日志', 'icon': 'fa-history', 'endpoint': 'system.audit_log', 'badge': 'Audit'},
            {'name': '系统设置', 'icon': 'fa-cog', 'endpoint': 'system.settings', 'badge': 'Settings'},
        ]
    else:
        # 非管理员只能看到消息通知和库存预警
        system_menu = [
            {'name': '消息通知', 'icon': 'fa-bell', 'endpoint': 'notification.index', 'badge': 'Msg'},
            {'name': '库存预警', 'icon': 'fa-exclamation-triangle', 'endpoint': 'notification.alerts', 'badge': 'Alert'},
        ]
    
    # 个人中心（所有用户可见）
    profile_menu = [
        {'name': '个人中心', 'icon': 'fa-user-circle', 'endpoint': 'profile.view', 'badge': 'Profile'},
    ]
    
    return {
        'main': menu_items,
        'system': system_menu,
        'profile': profile_menu
    }
