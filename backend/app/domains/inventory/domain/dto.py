from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryRiskItem:
    id: int
    sku: str | None
    name: str | None
    total_stock: int
    min_stock: int


@dataclass(frozen=True)
class InventoryHealth:
    total_products: int
    low_stock_products: int
    out_of_stock_products: int
    stock_quantity: int
    risk_items: tuple[InventoryRiskItem, ...]

    def to_dict(self):
        return {
            "total_products": self.total_products,
            "low_stock_products": self.low_stock_products,
            "out_of_stock_products": self.out_of_stock_products,
            "stock_quantity": self.stock_quantity,
            "risk_items": [
                {
                    "id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "total_stock": item.total_stock,
                    "min_stock": item.min_stock,
                }
                for item in self.risk_items
            ],
        }
