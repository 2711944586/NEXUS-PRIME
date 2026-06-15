import uuid
from datetime import datetime
from app.extensions import db
from app.models.trade import Order, OrderItem
from app.models.biz import Product, Partner
from app.models.stock import Stock, InventoryLog
from app.models.auth import User

class SalesService:
    @staticmethod
    def create_order(customer_id: int, user: User, items_data: list, status='pending') -> Order:
        """
        创建销售订单
        :param items_data: [{'product_id': 1, 'quantity': 2}, ...]
        """
        try:
            if not db.session.get(Partner, customer_id):
                raise ValueError("客户不存在")
            if not items_data:
                raise ValueError("订单至少需要一条商品明细")

            # 1. 生成唯一单号 (ORD-YYYYMMDD-XXXX)
            date_str = datetime.now().strftime('%Y%m%d')
            random_str = uuid.uuid4().hex[:4].upper()
            order_no = f"ORD-{date_str}-{random_str}"

            # 2. 创建订单头
            order = Order(
                order_no=order_no,
                customer_id=customer_id,
                seller_id=user.id,
                status=status,
                total_amount=0.0 # 稍后计算
            )
            db.session.add(order)
            db.session.flush() # 获取 order.id

            # 3. 处理订单行并计算总价
            total = 0.0
            valid_items = 0
            for item in items_data:
                pid = int(item.get('product_id'))
                qty = int(item.get('quantity'))
                if qty <= 0:
                    raise ValueError("商品数量必须大于0")

                product = db.session.get(Product, pid)
                if not product or product.is_deleted:
                    raise ValueError(f"商品不存在: {pid}")

                # 锁定快照价格
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    price_snapshot=product.price
                )
                db.session.add(order_item)
                total += (product.price * qty)
                valid_items += 1

            if valid_items == 0:
                raise ValueError("订单至少需要一条有效商品明细")

            # 4. 更新总价
            order.total_amount = total
            
            return order

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def transition_order(order: Order, target_status: str, user: User) -> None:
        old_status = order.status
        if target_status in (Order.STATUS_SHIPPED, Order.STATUS_DONE) and old_status not in (Order.STATUS_SHIPPED, Order.STATUS_DONE):
            SalesService._deduct_stock_for_order(order, user)
        order.status = target_status

    @staticmethod
    def _deduct_stock_for_order(order: Order, user: User) -> None:
        for item in order.items:
            remaining = int(item.quantity or 0)
            stocks = (
                Stock.query
                .filter(Stock.product_id == item.product_id, Stock.is_deleted == False, Stock.quantity > 0)
                .order_by(Stock.quantity.desc())
            )
            dialect_name = db.session.get_bind().dialect.name
            if not dialect_name.startswith('sqlite'):
                stocks = stocks.with_for_update()
            stocks = stocks.all()
            available = sum(stock.quantity for stock in stocks)
            if available < remaining:
                raise ValueError(f"商品 {item.product.name if item.product else item.product_id} 库存不足")
            for stock in stocks:
                if remaining <= 0:
                    break
                deduct = min(stock.quantity, remaining)
                stock.quantity -= deduct
                remaining -= deduct
                db.session.add(InventoryLog(
                    transaction_code=order.order_no,
                    move_type=InventoryLog.TYPE_OUT,
                    product_id=item.product_id,
                    warehouse_id=stock.warehouse_id,
                    qty_change=-deduct,
                    balance_after=stock.quantity,
                    operator_id=user.id,
                    remark=f"销售出库 - {order.order_no}"
                ))
