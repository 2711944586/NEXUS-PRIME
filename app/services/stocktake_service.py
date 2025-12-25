"""盘点服务 - 库存盘点管理"""
import uuid
from datetime import datetime
from sqlalchemy import func
from app.extensions import db
from app.models.stocktake import StockTake, StockTakeItem, StockTakeHistory
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product


class StockTakeService:
    """盘点服务"""
    
    @staticmethod
    def generate_take_no():
        """生成盘点单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"ST-{date_str}-{random_str}"
    
    @staticmethod
    def create_stocktake(warehouse_id, take_type, product_ids, user, remark=None, planned_date=None):
        """
        创建盘点单
        
        Args:
            warehouse_id: 仓库ID
            take_type: 盘点类型 (full/partial/cycle)
            product_ids: 商品ID列表 (partial时必填)
            user: 操作用户
            remark: 备注
            planned_date: 计划盘点日期
        """
        from datetime import datetime
        
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return False, "仓库不存在"
        
        # 检查是否有未完成的盘点
        existing = StockTake.query.filter(
            StockTake.warehouse_id == warehouse_id,
            StockTake.status.in_([StockTake.STATUS_DRAFT, StockTake.STATUS_IN_PROGRESS])
        ).first()
        
        if existing:
            return False, f"该仓库存在未完成的盘点单 {existing.take_no}"
        
        try:
            stocktake = StockTake(
                take_no=StockTakeService.generate_take_no(),
                warehouse_id=warehouse_id,
                take_type=take_type,
                created_by=user.id,
                remark=remark
            )
            
            # 设置计划日期
            if planned_date:
                try:
                    stocktake.planned_date = datetime.strptime(planned_date, '%Y-%m-%d').date()
                except:
                    pass
            
            db.session.add(stocktake)
            db.session.flush()
            
            # 根据盘点类型获取商品
            if take_type == StockTake.TYPE_FULL:
                # 全盘：仓库所有有库存的商品
                stocks = Stock.query.filter_by(warehouse_id=warehouse_id).filter(Stock.quantity > 0).all()
                product_ids = [s.product_id for s in stocks]
            elif take_type == StockTake.TYPE_PARTIAL and not product_ids:
                return False, "抽盘必须指定商品"
            
            # 创建盘点明细
            for product_id in product_ids:
                product = Product.query.get(product_id)
                if not product:
                    continue
                
                stock = Stock.query.filter_by(
                    product_id=product_id, 
                    warehouse_id=warehouse_id
                ).first()
                
                system_qty = stock.quantity if stock else 0
                
                item = StockTakeItem(
                    take_id=stocktake.id,
                    product_id=product_id,
                    system_qty=system_qty
                )
                db.session.add(item)
                stocktake.total_items += 1
            
            # 记录历史
            StockTakeService.add_history(stocktake.id, 'create', user, '创建盘点单')
            
            db.session.commit()
            return True, stocktake
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def start_stocktake(stocktake_id, user):
        """开始盘点"""
        stocktake = StockTake.query.get(stocktake_id)
        if not stocktake:
            return False, "盘点单不存在"
        
        if stocktake.status != StockTake.STATUS_DRAFT:
            return False, "只有草稿状态的盘点单可以开始"
        
        stocktake.status = StockTake.STATUS_IN_PROGRESS
        stocktake.started_at = datetime.utcnow()
        
        StockTakeService.add_history(stocktake_id, 'start', user, '开始盘点')
        
        db.session.commit()
        return True, "盘点已开始"
    
    @staticmethod
    def input_count(stocktake_id, item_id, actual_qty, user, remark=None):
        """录入盘点数量"""
        stocktake = StockTake.query.get(stocktake_id)
        if not stocktake:
            return False, "盘点单不存在"
        
        if stocktake.status != StockTake.STATUS_IN_PROGRESS:
            return False, "盘点单不在进行中状态"
        
        item = StockTakeItem.query.get(item_id)
        if not item or item.take_id != stocktake_id:
            return False, "盘点明细不存在"
        
        item.actual_qty = actual_qty
        item.counted_by = user.id
        item.counted_at = datetime.utcnow()
        item.remark = remark
        
        # 更新已盘点数量
        stocktake.counted_items = StockTakeItem.query.filter(
            StockTakeItem.take_id == stocktake_id,
            StockTakeItem.actual_qty.isnot(None)
        ).count()
        
        db.session.commit()
        return True, item
    
    @staticmethod
    def batch_input_count(stocktake_id, counts, user):
        """
        批量录入盘点数量
        
        Args:
            counts: [{'item_id': 1, 'actual_qty': 10, 'remark': '...'}]
        """
        success_count = 0
        for c in counts:
            ok, _ = StockTakeService.input_count(
                stocktake_id, 
                c['item_id'], 
                c['actual_qty'], 
                user,
                c.get('remark')
            )
            if ok:
                success_count += 1
        
        return success_count
    
    @staticmethod
    def confirm_item(stocktake_id, item_id, user, adjustment_reason=None):
        """确认盘点项（有差异时需要）"""
        item = StockTakeItem.query.get(item_id)
        if not item or item.take_id != stocktake_id:
            return False, "盘点明细不存在"
        
        if item.actual_qty is None:
            return False, "请先录入实盘数量"
        
        if item.variance_qty != 0 and not adjustment_reason:
            return False, "存在差异，请填写调整原因"
        
        item.remark = adjustment_reason
        
        db.session.commit()
        return True, "已确认"
    
    @staticmethod
    def complete_stocktake(stocktake_id, user, auto_adjust=True):
        """
        完成盘点
        
        Args:
            auto_adjust: 是否自动调整库存
        """
        stocktake = StockTake.query.get(stocktake_id)
        if not stocktake:
            return False, "盘点单不存在"
        
        if stocktake.status != StockTake.STATUS_IN_PROGRESS:
            return False, "盘点单不在进行中状态"
        
        # 检查是否所有项目都已盘点
        uncounted = StockTakeItem.query.filter(
            StockTakeItem.take_id == stocktake_id,
            StockTakeItem.actual_qty.is_(None)
        ).count()
        
        if uncounted > 0:
            return False, f"还有 {uncounted} 个商品未盘点"
        
        try:
            stocktake.status = StockTake.STATUS_COMPLETED
            stocktake.completed_at = datetime.utcnow()
            stocktake.approved_by = user.id
            
            # 自动调整库存
            if auto_adjust:
                items = StockTakeItem.query.filter_by(take_id=stocktake_id).all()
                
                for item in items:
                    if item.variance_qty != 0:
                        StockTakeService.adjust_stock(
                            stocktake, 
                            item, 
                            user
                        )
            
            StockTakeService.add_history(stocktake_id, 'complete', user, '完成盘点')
            
            db.session.commit()
            return True, "盘点已完成"
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def adjust_stock(stocktake, item, user):
        """根据盘点结果调整库存"""
        stock = Stock.query.filter_by(
            product_id=item.product_id,
            warehouse_id=stocktake.warehouse_id
        ).first()
        
        if not stock:
            stock = Stock(
                product_id=item.product_id,
                warehouse_id=stocktake.warehouse_id,
                quantity=0
            )
            db.session.add(stock)
        
        old_qty = stock.quantity
        stock.quantity = item.actual_qty
        
        # 创建库存日志
        log_type = 'check'  # 盘点调整
        log = InventoryLog(
            transaction_code=stocktake.take_no,
            move_type=log_type,
            product_id=item.product_id,
            warehouse_id=stocktake.warehouse_id,
            qty_change=item.variance_qty,
            balance_after=item.actual_qty,
            remark=f"盘点调整: {stocktake.take_no}, 原因: {item.remark or '正常盘点'}",
            operator_id=user.id
        )
        db.session.add(log)
    
    @staticmethod
    def cancel_stocktake(stocktake_id, user, reason):
        """取消盘点"""
        stocktake = StockTake.query.get(stocktake_id)
        if not stocktake:
            return False, "盘点单不存在"
        
        if stocktake.status == StockTake.STATUS_COMPLETED:
            return False, "已完成的盘点单不能取消"
        
        stocktake.status = StockTake.STATUS_CANCELLED
        StockTakeService.add_history(stocktake_id, 'cancel', user, f'取消盘点: {reason}')
        
        db.session.commit()
        return True, "盘点已取消"
    
    @staticmethod
    def add_history(stocktake_id, action, user, detail=None):
        """添加历史记录"""
        history = StockTakeHistory(
            take_id=stocktake_id,
            action=action,
            operator_id=user.id,
            details={'message': detail} if detail else None
        )
        db.session.add(history)
    
    @staticmethod
    def get_variance_summary(stocktake_id):
        """获取差异汇总"""
        items = StockTakeItem.query.filter_by(take_id=stocktake_id).all()
        
        summary = {
            'total_items': len(items),
            'counted_items': sum(1 for i in items if i.actual_qty is not None),
            'variance_items': sum(1 for i in items if i.variance_qty != 0),
            'surplus_items': sum(1 for i in items if i.variance_type == 'surplus'),
            'loss_items': sum(1 for i in items if i.variance_type == 'loss'),
            'total_surplus_qty': sum(i.variance_qty for i in items if i.variance_type == 'surplus'),
            'total_loss_qty': sum(abs(i.variance_qty) for i in items if i.variance_type == 'loss'),
            'total_surplus_value': sum(i.variance_value for i in items if i.variance_type == 'surplus'),
            'total_loss_value': sum(abs(i.variance_value) for i in items if i.variance_type == 'loss')
        }
        
        return summary
