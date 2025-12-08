import uuid
from datetime import datetime
from app.extensions import db
from app.models.trade import Order, OrderItem
from app.models.biz import Product, Partner
from app.models.auth import User

class SalesService:
    @staticmethod
    def create_order(customer_id: int, user: User, items_data: list, status='pending') -> Order:
        """
        创建销售订单
        :param items_data: [{'product_id': 1, 'quantity': 2}, ...]
        """
        try:
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
            for item in items_data:
                pid = int(item.get('product_id'))
                qty = int(item.get('quantity'))
                if qty <= 0: continue

                product = Product.query.get(pid)
                if not product: continue

                # 锁定快照价格
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    price_snapshot=product.price
                )
                db.session.add(order_item)
                total += (product.price * qty)

            # 4. 更新总价
            order.total_amount = total
            
            # 5. 提交
            db.session.commit()
            return order

        except Exception as e:
            db.session.rollback()
            raise e