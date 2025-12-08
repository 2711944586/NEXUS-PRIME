"""通知与预警路由"""
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.notification import notification_bp
from app.models.notification import (
    Notification, StockAlert, ReplenishmentSuggestion, 
    ReportSubscription, GeneratedReport
)
from app.services.stock_alert_service import StockAlertService
from app.services.report_service import ReportService


@notification_bp.route('/')
@login_required
def index():
    """通知列表"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    is_read = request.args.get('is_read', '')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if category:
        query = query.filter_by(category=category)
    if is_read == '0':
        query = query.filter_by(is_read=False)
    elif is_read == '1':
        query = query.filter_by(is_read=True)
    
    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 未读数量
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).count()
    
    return render_template('notification/index.html',
                         notifications=pagination.items,
                         pagination=pagination,
                         unread_count=unread_count,
                         current_category=category,
                         current_is_read=is_read)


@notification_bp.route('/<int:notification_id>')
@login_required
def detail(notification_id):
    """通知详情"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()
    
    # 标记为已读
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = db.func.now()
        db.session.commit()
    
    return render_template('notification/detail.html', notification=notification)


@notification_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id):
    """标记为已读"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()
    
    notification.is_read = True
    notification.read_at = db.func.now()
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    return redirect(url_for('notification.index'))


@notification_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """全部标记为已读"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True, 'read_at': db.func.now()})
    db.session.commit()
    
    flash('已全部标记为已读', 'success')
    return redirect(url_for('notification.index'))


# ============== 库存预警 ==============

@notification_bp.route('/alerts')
@login_required
def alerts():
    """库存预警列表"""
    page = request.args.get('page', 1, type=int)
    alert_level = request.args.get('level', '')
    status = request.args.get('status', '')
    
    query = StockAlert.query
    
    if alert_level:
        query = query.filter_by(alert_level=alert_level)
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(StockAlert.status != StockAlert.STATUS_RESOLVED)
    
    pagination = query.order_by(StockAlert.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 统计
    stats = StockAlertService.get_alert_statistics()
    
    return render_template('notification/alerts.html',
                         alerts=pagination.items,
                         pagination=pagination,
                         stats=stats,
                         current_level=alert_level,
                         current_status=status)


@notification_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    """解决预警"""
    alert = StockAlert.query.get_or_404(alert_id)
    alert.status = StockAlert.STATUS_RESOLVED
    alert.resolved_at = db.func.now()
    alert.resolved_by = current_user.id
    db.session.commit()
    
    flash('预警已解决', 'success')
    return redirect(url_for('notification.alerts'))


@notification_bp.route('/alerts/<int:alert_id>/ignore', methods=['POST'])
@login_required
def ignore_alert(alert_id):
    """忽略预警"""
    alert = StockAlert.query.get_or_404(alert_id)
    alert.status = StockAlert.STATUS_IGNORED
    db.session.commit()
    
    flash('预警已忽略', 'success')
    return redirect(url_for('notification.alerts'))


@notification_bp.route('/alerts/check', methods=['POST'])
@login_required
def check_alerts():
    """手动检查库存预警"""
    count = StockAlertService.check_all_stock_alerts()
    flash(f'检查完成，发现 {count} 个预警', 'info')
    return redirect(url_for('notification.alerts'))


# ============== 补货建议 ==============

@notification_bp.route('/replenishment')
@login_required
def replenishment():
    """补货建议列表"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')
    
    query = ReplenishmentSuggestion.query.filter_by(status=status)
    
    pagination = query.order_by(ReplenishmentSuggestion.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('notification/replenishment.html',
                         suggestions=pagination.items,
                         pagination=pagination,
                         current_status=status)


@notification_bp.route('/replenishment/generate', methods=['POST'])
@login_required
def generate_replenishment():
    """生成补货建议"""
    count = StockAlertService.generate_replenishment_suggestions()
    flash(f'已生成 {count} 条补货建议', 'success')
    return redirect(url_for('notification.replenishment'))


@notification_bp.route('/replenishment/<int:suggestion_id>/accept', methods=['POST'])
@login_required
def accept_suggestion(suggestion_id):
    """接受建议（创建采购订单）"""
    suggestion = ReplenishmentSuggestion.query.get_or_404(suggestion_id)
    
    # TODO: 自动创建采购订单
    suggestion.status = 'accepted'
    db.session.commit()
    
    flash('已接受建议，请前往采购模块创建订单', 'success')
    return redirect(url_for('notification.replenishment'))


@notification_bp.route('/replenishment/<int:suggestion_id>/reject', methods=['POST'])
@login_required
def reject_suggestion(suggestion_id):
    """拒绝建议"""
    suggestion = ReplenishmentSuggestion.query.get_or_404(suggestion_id)
    suggestion.status = 'rejected'
    db.session.commit()
    
    flash('已拒绝建议', 'info')
    return redirect(url_for('notification.replenishment'))


# ============== 报表订阅 ==============

@notification_bp.route('/subscriptions')
@login_required
def subscriptions():
    """报表订阅列表"""
    user_subscriptions = ReportService.get_user_subscriptions(current_user.id)
    available_reports = ReportService.get_available_reports()
    
    return render_template('notification/subscriptions.html',
                         subscriptions=user_subscriptions,
                         available_reports=available_reports)


@notification_bp.route('/subscriptions/create', methods=['POST'])
@login_required
def create_subscription():
    """创建订阅"""
    report_type = request.form.get('report_type')
    frequency = request.form.get('frequency', 'daily')
    send_hour = int(request.form.get('send_hour', 8))
    send_weekday = int(request.form.get('send_weekday', 1))
    send_day = int(request.form.get('send_day', 1))
    
    success, result = ReportService.create_subscription(
        user_id=current_user.id,
        report_type=report_type,
        frequency=frequency,
        send_hour=send_hour,
        send_weekday=send_weekday,
        send_day=send_day
    )
    
    if success:
        flash(f'已订阅 {result.report_name}', 'success')
    else:
        flash(result, 'danger')
    
    return redirect(url_for('notification.subscriptions'))


@notification_bp.route('/subscriptions/<int:subscription_id>/cancel', methods=['POST'])
@login_required
def cancel_subscription(subscription_id):
    """取消订阅"""
    success, msg = ReportService.cancel_subscription(subscription_id, current_user.id)
    if success:
        flash('已取消订阅', 'success')
    else:
        flash(msg, 'danger')
    
    return redirect(url_for('notification.subscriptions'))


@notification_bp.route('/reports')
@login_required
def reports():
    """历史报表列表"""
    reports_list = ReportService.get_user_reports(current_user.id, limit=50)
    return render_template('notification/reports.html', reports=reports_list)


@notification_bp.route('/reports/<int:report_id>')
@login_required
def report_detail(report_id):
    """报表详情"""
    report = GeneratedReport.query.get_or_404(report_id)
    
    # 验证权限
    if report.subscription.user_id != current_user.id:
        flash('无权查看', 'danger')
        return redirect(url_for('notification.reports'))
    
    return render_template('notification/report_detail.html', report=report)


# ============== API 接口 ==============

@notification_bp.route('/api/unread-count')
@login_required
def api_unread_count():
    """获取未读通知数"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})


@notification_bp.route('/api/latest')
@login_required
def api_latest():
    """获取最新通知"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'type': n.type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    })


@notification_bp.route('/api/alert-stats')
@login_required
def api_alert_stats():
    """获取预警统计"""
    stats = StockAlertService.get_alert_statistics()
    return jsonify(stats)
