"""采购管理服务"""
import uuid
from datetime import datetime
from app.extensions import db
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchasePriceHistory, SupplierPerformance
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product, Partner


class PurchaseService:
    """采购服务"""
    
    @staticmethod
    def generate_po_no():
        """生成采购单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        random_str = uuid.uuid4().hex[:4].upper()
        return f"PO-{date_str}-{random_str}"
    
    @staticmethod
    def create_purchase_order(supplier_id, warehouse_id, items_data, user, expected_date=None, remark=None):
        """
        创建采购订单
        :param items_data: [{'product_id': 1, 'quantity': 10, 'unit_price': 50.0}, ...]
        """
        try:
            po = PurchaseOrder(
                po_no=PurchaseService.generate_po_no(),
                supplier_id=supplier_id,
                warehouse_id=warehouse_id,
                expected_date=expected_date,
                remark=remark,
                status=PurchaseOrder.STATUS_DRAFT
            )
            db.session.add(po)
            db.session.flush()
            
            total = 0.0
            for item_data in items_data:
                item = PurchaseOrderItem(
                    order_id=po.id,
                    product_id=item_data['product_id'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price']
                )
                db.session.add(item)
                total += item.quantity * item.unit_price
                
                # 记录采购价格历史
                PurchaseService.record_price_history(
                    item_data['product_id'],
                    supplier_id,
                    item_data['unit_price']
                )
            
            po.total_amount = total
            db.session.commit()
            return True, po
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def submit_for_approval(po_id, user):
        """提交审批"""
        po = PurchaseOrder.query.get(po_id)
        if not po:
            return False, "采购单不存在"
        if po.status != PurchaseOrder.STATUS_DRAFT:
            return False, "只有草稿状态可以提交审批"
        
        po.status = PurchaseOrder.STATUS_PENDING
        po.submitted_at = datetime.utcnow()
        po.submitted_by = user.id
        db.session.commit()
        return True, "提交成功"
    
    @staticmethod
    def approve(po_id, user, approved=True, remark=None):
        """审批"""
        po = PurchaseOrder.query.get(po_id)
        if not po:
            return False, "采购单不存在"
        if po.status != PurchaseOrder.STATUS_PENDING:
            return False, "只有待审批状态可以审批"
        
        if approved:
            po.status = PurchaseOrder.STATUS_APPROVED
        else:
            po.status = PurchaseOrder.STATUS_DRAFT
            po.remark = (po.remark or '') + f"\n[审批驳回] {remark}"
        
        po.approved_at = datetime.utcnow()
        po.approved_by = user.id
        db.session.commit()
        return True, "审批完成"
    
    @staticmethod
    def receive_items(po_id, receive_data, user):
        """
        收货
        :param receive_data: [{'item_id': 1, 'receive_qty': 5}, ...]
        """
        po = PurchaseOrder.query.get(po_id)
        if not po:
            return False, "采购单不存在"
        if po.status not in [PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL]:
            return False, "当前状态不允许收货"
        
        try:
            all_received = True
            for data in receive_data:
                item = PurchaseOrderItem.query.get(data['item_id'])
                if not item or item.order_id != po_id:
                    continue
                
                receive_qty = min(data['receive_qty'], item.pending_qty)
                if receive_qty <= 0:
                    continue
                
                item.received_qty += receive_qty
                
                # 更新库存
                stock = Stock.query.filter_by(
                    product_id=item.product_id,
                    warehouse_id=po.warehouse_id
                ).first()
                
                if not stock:
                    stock = Stock(
                        product_id=item.product_id,
                        warehouse_id=po.warehouse_id,
                        quantity=0
                    )
                    db.session.add(stock)
                
                stock.quantity += receive_qty
                
                # 记录库存流水
                log = InventoryLog(
                    transaction_code=po.po_no,
                    move_type=InventoryLog.TYPE_IN,
                    product_id=item.product_id,
                    warehouse_id=po.warehouse_id,
                    qty_change=receive_qty,
                    balance_after=stock.quantity,
                    operator_id=user.id,
                    remark=f"采购入库 - {po.po_no}"
                )
                db.session.add(log)
                
                if item.pending_qty > 0:
                    all_received = False
            
            # 更新订单状态
            if all_received:
                po.status = PurchaseOrder.STATUS_RECEIVED
                po.actual_receive_date = datetime.utcnow()
                # 更新供应商绩效
                PurchaseService.update_supplier_performance(po)
            else:
                po.status = PurchaseOrder.STATUS_PARTIAL
            
            db.session.commit()
            return True, "收货成功"
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    @staticmethod
    def record_price_history(product_id, supplier_id, price):
        """记录采购价格历史"""
        history = PurchasePriceHistory(
            product_id=product_id,
            supplier_id=supplier_id,
            price=price
        )
        db.session.add(history)
    
    @staticmethod
    def update_supplier_performance(po):
        """更新供应商绩效"""
        perf = SupplierPerformance.query.filter_by(supplier_id=po.supplier_id).first()
        if not perf:
            perf = SupplierPerformance(supplier_id=po.supplier_id)
            db.session.add(perf)
        
        perf.total_orders += 1
        perf.total_amount += po.total_amount
        perf.last_order_date = datetime.utcnow()
        
        # 判断是否准时
        if po.expected_date and po.actual_receive_date:
            if po.actual_receive_date.date() <= po.expected_date:
                perf.on_time_orders += 1
        else:
            perf.on_time_orders += 1  # 无预期日期默认准时
        
        # 默认质量合格
        perf.quality_pass_orders += 1
    
    @staticmethod
    def get_supplier_price(product_id, supplier_id):
        """获取最近采购价格"""
        history = PurchasePriceHistory.query.filter_by(
            product_id=product_id,
            supplier_id=supplier_id
        ).order_by(PurchasePriceHistory.effective_date.desc()).first()
        
        if history:
            return history.price
        
        # 如果没有历史，返回产品成本价
        product = Product.query.get(product_id)
        return product.cost if product else 0
