from app.domains.inventory.domain.dto import InventoryHealth, InventoryRiskItem
from app.domains.inventory.infrastructure.repository import InventoryRepository


class InventoryHealthQuery:
    def __init__(self, repository=None):
        self.repository = repository or InventoryRepository()

    def execute(self):
        rows = self.repository.product_stock_totals()
        risk_items = []
        out_of_stock = 0
        low_stock = 0
        stock_quantity = 0

        for product, total_stock in rows:
            total = int(total_stock or 0)
            minimum = product.min_stock or 0
            stock_quantity += total
            if total <= 0:
                out_of_stock += 1
            if total <= minimum:
                low_stock += 1
                risk_items.append(
                    InventoryRiskItem(
                        id=product.id,
                        sku=product.sku,
                        name=product.name,
                        total_stock=total,
                        min_stock=minimum,
                    )
                )

        return InventoryHealth(
            total_products=len(rows),
            low_stock_products=low_stock,
            out_of_stock_products=out_of_stock,
            stock_quantity=stock_quantity,
            risk_items=tuple(risk_items[:10]),
        )
