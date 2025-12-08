"""
系统管理模块 - 系统设置、审计日志、通知中心
"""
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from . import bp
from app.extensions import db
from app.models.stock import InventoryLog
from app.models.trade import Order
from app.models.auth import User
from app.models.content import Article


@bp.route('/settings')
@login_required
def settings():
    """系统设置页面"""
    return render_template('system/settings.html')


@bp.route('/audit-log')
@login_required
def audit_log():
    """审计日志查看器"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # 获取筛选参数
    move_type = request.args.get('type', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    # 构建查询
    query = InventoryLog.query
    
    # 类型筛选
    if move_type in ['inbound', 'outbound']:
        query = query.filter(InventoryLog.move_type == move_type)
    
    # 日期筛选
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(InventoryLog.created_at >= start_date)
        except ValueError:
            pass
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # 设置为当天结束时间
            end_date = end_date.replace(hour=23, minute=59, second=59)
            query = query.filter(InventoryLog.created_at <= end_date)
        except ValueError:
            pass
    
    # 获取库存日志
    logs = query.order_by(desc(InventoryLog.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # 统计数据
    stats = {
        'total_logs': InventoryLog.query.count(),
        'today_logs': InventoryLog.query.filter(
            InventoryLog.created_at >= datetime.utcnow().date()
        ).count(),
        'inbound_count': InventoryLog.query.filter_by(move_type='inbound').count(),
        'outbound_count': InventoryLog.query.filter_by(move_type='outbound').count()
    }
    
    return render_template('system/audit_log.html', 
                          logs=logs, 
                          stats=stats,
                          current_type=move_type,
                          current_start_date=start_date_str,
                          current_end_date=end_date_str)


@bp.route('/notifications')
@login_required  
def notifications():
    """通知中心"""
    # 模拟通知数据
    notifications_list = [
        {
            'id': 1,
            'type': 'order',
            'title': '新订单提醒',
            'message': '您有3个新订单待处理',
            'time': datetime.utcnow() - timedelta(minutes=5),
            'read': False,
            'icon': 'fa-shopping-cart',
            'color': '#6366f1'
        },
        {
            'id': 2,
            'type': 'stock',
            'title': '库存预警',
            'message': '15个商品库存低于安全线',
            'time': datetime.utcnow() - timedelta(hours=1),
            'read': False,
            'icon': 'fa-exclamation-triangle',
            'color': '#fbbf24'
        },
        {
            'id': 3,
            'type': 'system',
            'title': '系统升级完成',
            'message': 'NEXUS V3.0 已成功部署',
            'time': datetime.utcnow() - timedelta(hours=2),
            'read': True,
            'icon': 'fa-rocket',
            'color': '#10b981'
        },
        {
            'id': 4,
            'type': 'ai',
            'title': 'AI分析报告就绪',
            'message': '本月销售趋势分析已生成',
            'time': datetime.utcnow() - timedelta(hours=5),
            'read': True,
            'icon': 'fa-robot',
            'color': '#ef4444'
        },
        {
            'id': 5,
            'type': 'security',
            'title': '安全提醒',
            'message': '检测到新设备登录您的账号',
            'time': datetime.utcnow() - timedelta(days=1),
            'read': True,
            'icon': 'fa-shield-alt',
            'color': '#8b5cf6'
        }
    ]
    
    return render_template('system/notifications.html', notifications=notifications_list)


@bp.route('/team')
@login_required
def team():
    """团队仪表板"""
    # 按部门统计用户
    from app.models.auth import Department
    
    departments = db.session.query(
        Department.name,
        func.count(User.id).label('count')
    ).join(User).group_by(Department.name).all()
    
    # 最近活跃用户
    recent_users = User.query.order_by(desc(User.created_at)).limit(10).all()
    
    # 统计
    stats = {
        'total_users': User.query.count(),
        'total_departments': Department.query.count(),
        'active_today': User.query.filter(
            User.created_at >= datetime.utcnow().date()
        ).count()
    }
    
    # 获取所有部门用于添加成员表单
    all_departments = Department.query.all()
    
    return render_template('system/team.html', 
                         departments=departments, 
                         recent_users=recent_users,
                         stats=stats,
                         all_departments=all_departments)


@bp.route('/team/add-member', methods=['POST'])
@login_required
def add_member():
    """添加团队成员"""
    from flask import flash, redirect, url_for
    from app.models.auth import Department
    from werkzeug.security import generate_password_hash
    
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        department_id = request.form.get('department')
        role = request.form.get('role', 'member')
        
        # 验证必填字段
        if not username or not email:
            flash('用户名和邮箱是必填项', 'error')
            return redirect(url_for('system.team'))
        
        # 检查用户名是否存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('system.team'))
        
        # 检查邮箱是否存在
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'error')
            return redirect(url_for('system.team'))
        
        # 生成默认密码
        default_password = 'nexus123'
        
        # 创建新用户
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(default_password),
            role=role
        )
        
        # 设置部门
        if department_id:
            dept = Department.query.get(int(department_id))
            if dept:
                new_user.department_id = dept.id
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'成员 {username} 添加成功！默认密码: {default_password}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'添加失败: {str(e)}', 'error')
    
    return redirect(url_for('system.team'))


@bp.route('/api/stats')
@login_required
def api_stats():
    """系统统计 API"""
    stats = {
        'users': User.query.count(),
        'orders': Order.query.count(),
        'articles': Article.query.count(),
        'logs': InventoryLog.query.count(),
        'revenue': db.session.query(func.sum(Order.total_amount)).scalar() or 0
    }
    return jsonify(stats)


@bp.route('/ai-settings', methods=['GET', 'POST'])
@login_required
def ai_settings():
    """AI 设置页面 - 配置 DeepSeek API Key"""
    from flask import flash, redirect, url_for
    from sqlalchemy.orm.attributes import flag_modified
    
    if request.method == 'POST':
        data = request.form
        api_key = data.get('api_key', '').strip()
        
        # 更新用户偏好 - 必须重新赋值整个dict并标记修改
        prefs = dict(current_user.preferences or {})
        
        if api_key:
            prefs['ai_api_key'] = api_key
            current_user.preferences = prefs
            flag_modified(current_user, 'preferences')
            db.session.commit()
            flash('API Key 已保存成功！', 'success')
        else:
            if 'ai_api_key' in prefs:
                del prefs['ai_api_key']
            current_user.preferences = prefs
            flag_modified(current_user, 'preferences')
            db.session.commit()
            flash('API Key 已清除', 'info')
        
        return redirect(url_for('system.ai_settings'))
    
    # 检查是否有 Key
    prefs = current_user.preferences or {}
    has_key = isinstance(prefs, dict) and bool(prefs.get('ai_api_key'))
    
    # 获取已保存的key用于显示(部分隐藏)
    saved_key = ''
    if has_key:
        key = prefs.get('ai_api_key', '')
        if len(key) > 8:
            saved_key = key[:4] + '*' * (len(key) - 8) + key[-4:]
        else:
            saved_key = '****'
    
    return render_template('system/ai_settings.html', has_key=has_key, saved_key=saved_key)


# ============== 数据导入 ==============

@bp.route('/import')
@login_required
def data_import():
    """数据导入页面"""
    from app.services.import_service import ImportService
    templates = ImportService.TEMPLATES
    return render_template('system/import.html', templates=templates)


@bp.route('/import/template/<template_type>')
@login_required
def download_template(template_type):
    """下载导入模板"""
    from flask import make_response
    from app.services.import_service import ImportService
    
    csv_content = ImportService.generate_template_csv(template_type)
    if not csv_content:
        return jsonify({'error': '模板不存在'}), 404
    
    template = ImportService.TEMPLATES.get(template_type, {})
    filename = f"{template.get('name', template_type)}_导入模板.csv"
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@bp.route('/import/upload/<template_type>', methods=['POST'])
@login_required
def upload_import(template_type):
    """上传导入文件"""
    from app.services.import_service import ImportService
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择文件'})
    
    if not ImportService.allowed_file(file.filename):
        return jsonify({'success': False, 'message': '不支持的文件类型，请上传CSV或Excel文件'})
    
    update_existing = request.form.get('update_existing', '0') == '1'
    
    result = ImportService.process_import(file, template_type, current_user, update_existing)
    
    return jsonify(result)

