"""库存预警服务"""
import uuid
from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product
from app.models.trade import Order, OrderItem
from app.models.notification import StockAlert, ReplenishmentSuggestion, Notification
from app.utils.time import utcnow


class StockAlertService:
    """库存预警服务"""
    
    @staticmethod
    def check_all_stock_alerts():
        """检查所有库存预警"""
        alerts_created = 0
        
        # 获取所有产品的库存情况
        products = Product.query.filter_by(is_deleted=False).all()
        
        for product in products:
            total_stock = product.total_stock
            min_stock = product.min_stock or 10
            
            # 判断预警级别
            if total_stock <= 0:
                alert_level = StockAlert.LEVEL_RED
            elif total_stock < min_stock * 0.5:
                alert_level = StockAlert.LEVEL_RED
            elif total_stock < min_stock:
                alert_level = StockAlert.LEVEL_YELLOW
            else:
                # 库存充足，检查是否有活跃预警需要关闭
                StockAlertService.resolve_alerts_for_product(product.id)
                continue
            
            # 检查是否已有活跃预警
            existing = StockAlert.query.filter_by(
                product_id=product.id,
                status=StockAlert.STATUS_ACTIVE
            ).first()
            
            if existing:
                # 更新现有预警
                existing.alert_level = alert_level
                existing.current_qty = total_stock
            else:
                # 创建新预警
                suggested_qty = StockAlertService.calculate_suggested_qty(product)
                
                alert = StockAlert(
                    product_id=product.id,
                    alert_level=alert_level,
                    current_qty=total_stock,
                    min_qty=min_stock,
                    suggested_qty=suggested_qty
                )
                db.session.add(alert)
                alerts_created += 1
                
                # 发送通知
                StockAlertService.send_alert_notification(product, alert_level, total_stock, min_stock)
        
        return alerts_created
    
    @staticmethod
    def resolve_alerts_for_product(product_id):
        """解决产品的所有活跃预警"""
        alerts = StockAlert.query.filter_by(
            product_id=product_id,
            status=StockAlert.STATUS_ACTIVE
        ).all()
        
        for alert in alerts:
            alert.status = StockAlert.STATUS_RESOLVED
            alert.resolved_at = utcnow()
            alert.resolution_note = "库存已恢复正常"
    
    @staticmethod
    def calculate_suggested_qty(product):
        """计算建议补货数量"""
        # 获取最近30天的日均销量
        thirty_days_ago = utcnow() - timedelta(days=30)
        
        daily_sales = db.session.query(
            func.sum(OrderItem.quantity)
        ).join(Order).filter(
            OrderItem.product_id == product.id,
            Order.created_at >= thirty_days_ago,
            Order.status.in_(['paid', 'shipped', 'done'])
        ).scalar() or 0
        
        avg_daily = daily_sales / 30
        
        # 建议补货量 = (日均销量 * 采购周期 + 安全库存) - 当前库存
        lead_time = 7  # 默认采购周期7天
        safety_stock = product.min_stock or 10
        current_stock = product.total_stock
        
        suggested = int(avg_daily * lead_time + safety_stock - current_stock)
        return max(suggested, product.min_stock or 10)  # 至少补到最小库存
    
    @staticmethod
    def send_alert_notification(product, alert_level, current_qty, min_qty):
        """发送预警通知"""
        from app.models.auth import User
        
        # 获取有库存管理权限的用户（简化：发给所有管理员）
        admins = User.query.filter_by(is_admin=True, is_deleted=False).all()
        
        level_text = "🔴 紧急" if alert_level == StockAlert.LEVEL_RED else "🟡 预警"
        
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title=f"{level_text} 库存预警 - {product.name}",
                content=f"商品 {product.name} (SKU: {product.sku}) 当前库存 {current_qty}，低于安全库存 {min_qty}，请及时补货。",
                type=Notification.TYPE_WARNING if alert_level == StockAlert.LEVEL_YELLOW else Notification.TYPE_ALERT,
                category=Notification.CATEGORY_STOCK,
                related_type='product',
                related_id=product.id
            )
            db.session.add(notification)
    
    @staticmethod
    def generate_replenishment_suggestions():
        """生成补货建议"""
        suggestions_created = 0
        
        # 获取所有活跃的库存预警
        alerts = StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE).all()
        
        for alert in alerts:
            product = alert.product
            
            # 检查是否已有待处理的建议
            existing = ReplenishmentSuggestion.query.filter_by(
                product_id=product.id,
                status=ReplenishmentSuggestion.STATUS_PENDING
            ).first()
            
            if existing:
                continue
            
            # 获取默认供应商
            supplier_id = product.supplier_id
            if not supplier_id:
                continue
            
            # 计算日均销量
            thirty_days_ago = utcnow() - timedelta(days=30)
            daily_sales = db.session.query(
                func.sum(OrderItem.quantity)
            ).join(Order).filter(
                OrderItem.product_id == product.id,
                Order.created_at >= thirty_days_ago
            ).scalar() or 0
            
            avg_daily = daily_sales / 30
            
            suggestion = ReplenishmentSuggestion(
                product_id=product.id,
                supplier_id=supplier_id,
                current_qty=alert.current_qty,
                suggested_qty=alert.suggested_qty,
                avg_daily_sales=round(avg_daily, 2),
                safety_stock=product.min_stock or 10
            )
            db.session.add(suggestion)
            suggestions_created += 1
        
        return suggestions_created
    
    @staticmethod
    def get_active_alerts(page=1, per_page=20):
        """获取活跃预警列表"""
        return StockAlert.query.filter_by(
            status=StockAlert.STATUS_ACTIVE
        ).order_by(
            StockAlert.alert_level.desc(),
            StockAlert.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def get_alert_statistics():
        """获取预警统计"""
        total = StockAlert.query.filter_by(status=StockAlert.STATUS_ACTIVE).count()
        red_count = StockAlert.query.filter_by(
            status=StockAlert.STATUS_ACTIVE,
            alert_level=StockAlert.LEVEL_RED
        ).count()
        yellow_count = total - red_count
        
        return {
            'total': total,
            'red': red_count,
            'yellow': yellow_count
        }
