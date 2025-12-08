from app.extensions import db
from app.models.stock import Stock, InventoryLog, Warehouse
from app.models.biz import Product
from app.models.auth import User
import uuid

class InventoryService:
    @staticmethod
    def adjust_stock(product_id: int, warehouse_id: int, quantity: int, move_type: str, user: User, remark: str) -> bool:
        """
        原子化库存调整方法
        :param quantity: 始终为正整数，方向由 move_type 决定
        :return: (bool, message)
        """
        try:
            # 1. 获取对象
            product = Product.query.get(product_id)
            warehouse = Warehouse.query.get(warehouse_id)
            if not product or not warehouse:
                return False, "目标对象不存在"

            # 2. 查找或初始化库存记录
            stock_record = Stock.query.filter_by(product_id=product.id, warehouse_id=warehouse.id).first()
            if not stock_record:
                stock_record = Stock(product=product, warehouse=warehouse, quantity=0)
                db.session.add(stock_record)

            # 3. 计算实际变动值
            # inbound/return 为加，outbound/check(假设损耗) 为减
            # 这里简化逻辑：check 视为 inventory loss (减)
            delta = quantity
            if move_type in ['outbound', 'check']:
                delta = -quantity

            # 4. 检查库存是否充足 (防止超卖)
            if delta < 0 and (stock_record.quantity + delta) < 0:
                return False, f"库存不足！当前库存: {stock_record.quantity}, 尝试扣减: {abs(delta)}"

            # 5. 执行更新
            stock_record.quantity += delta
            
            # 6. 记录审计流水
            log = InventoryLog(
                transaction_code=f"TRX-{uuid.uuid4().hex[:8].upper()}",
                move_type=move_type,
                product=product,
                warehouse=warehouse,
                qty_change=delta,
                balance_after=stock_record.quantity, # 记录变动后的快照
                operator=user,
                remark=remark
            )
            db.session.add(log)

            # 7. 提交事务
            db.session.commit()
            return True, f"操作成功。流水号: {log.transaction_code}"

        except Exception as e:
            db.session.rollback()
            return False, f"系统错误: {str(e)}"