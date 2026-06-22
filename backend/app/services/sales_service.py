import uuid
from datetime import datetime
from decimal import Decimal
from app.extensions import db
from app.models.trade import Order, OrderItem
from app.models.biz import Product, Partner
from app.models.stock import Stock, InventoryLog, StockMovement
from app.models.auth import User
from app.domains.inventory.application import InventoryApplicationService
from app.platform.events import outbox


def sales_order_created_event_payload(order: Order) -> dict:
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "customer_id": order.customer_id,
        "seller_id": order.seller_id,
        "status": order.status,
        "total_amount": float(order.total_amount or 0),
        "items": [
            {
                "item_id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price_snapshot": float(item.price_snapshot or 0),
            }
            for item in order.items
        ],
    }


def sales_order_transition_event_payload(order: Order, old_status: str) -> dict:
    payload = sales_order_created_event_payload(order)
    payload["previous_status"] = old_status
    return payload


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
            total = Decimal("0")
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
                total += (product.price or Decimal("0")) * qty
                valid_items += 1

            if valid_items == 0:
                raise ValueError("订单至少需要一条有效商品明细")

            # 4. 更新总价
            order.total_amount = total
            db.session.flush()
            SalesService.record_order_created_event(order, user)
            
            return order

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def record_order_created_event(order: Order, user: User) -> None:
        outbox.add(
            "SalesOrderCreated",
            "Order",
            order.id,
            sales_order_created_event_payload(order),
            created_by=user.id if user else None,
        )

    @staticmethod
    def transition_order(order: Order, target_status: str, user: User) -> None:
        old_status = order.status
        if target_status in (Order.STATUS_SHIPPED, Order.STATUS_DONE) and old_status not in (Order.STATUS_SHIPPED, Order.STATUS_DONE):
            SalesService._deduct_stock_for_order(order, user)
        order.status = target_status
        if old_status != Order.STATUS_PAID and target_status == Order.STATUS_PAID:
            SalesService.record_order_confirmed_event(order, old_status, user)
        if old_status != Order.STATUS_CANCEL and target_status == Order.STATUS_CANCEL:
            SalesService.record_order_cancelled_event(order, old_status, user)

    @staticmethod
    def record_order_confirmed_event(order: Order, old_status: str, user: User) -> None:
        outbox.add(
            "SalesOrderConfirmed",
            "Order",
            order.id,
            sales_order_transition_event_payload(order, old_status),
            created_by=user.id if user else None,
        )

    @staticmethod
    def record_order_cancelled_event(order: Order, old_status: str, user: User) -> None:
        outbox.add(
            "SalesOrderCancelled",
            "Order",
            order.id,
            sales_order_transition_event_payload(order, old_status),
            created_by=user.id if user else None,
        )

    @staticmethod
    def _deduct_stock_for_order(order: Order, user: User) -> None:
        reserved_items = SalesService._reserved_items_for_order(order)
        if reserved_items:
            InventoryApplicationService().deduct_stock(
                "sales_order",
                order.id,
                reserved_items,
                f"sales-order:{order.id}:ship",
                created_by=user,
                reason=f"销售出库 - {order.order_no}",
            )
            return
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

    @staticmethod
    def _reserved_items_for_order(order: Order):
        movements = (
            StockMovement.query
            .filter(
                StockMovement.source_type == "sales_order",
                StockMovement.source_id == str(order.id),
                StockMovement.direction == StockMovement.DIRECTION_RESERVE,
                StockMovement.is_deleted == False,
            )
            .order_by(StockMovement.id.asc())
            .all()
        )
        if not movements:
            return []
        return [
            {
                "product_id": movement.product_id,
                "warehouse_id": movement.warehouse_id,
                "quantity": movement.quantity,
            }
            for movement in movements
        ]
