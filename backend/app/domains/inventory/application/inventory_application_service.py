from app.extensions import db
from app.models.biz import Product
from app.models.stock import InventoryLog, Stock, StockBalance, StockMovement, Warehouse


EVENT_TYPES_BY_DIRECTION = {
    StockMovement.DIRECTION_RESERVE: "InventoryReserved",
    StockMovement.DIRECTION_RELEASE: "InventoryReleased",
    StockMovement.DIRECTION_DEDUCT: "InventoryDeducted",
}


def _positive_quantity(value):
    quantity = int(value or 0)
    if quantity <= 0:
        raise ValueError("库存数量必须大于 0")
    return quantity


def _item_rows(items):
    for item in items or []:
        yield {
            "product_id": int(item.get("product_id")),
            "warehouse_id": int(item.get("warehouse_id")),
            "quantity": _positive_quantity(item.get("quantity")),
        }


def _idempotency_key(base_key, operation, product_id, warehouse_id):
    return f"{base_key}:{operation}:{product_id}:{warehouse_id}"


def _locked(query):
    dialect_name = db.session.get_bind().dialect.name
    if not dialect_name.startswith("sqlite"):
        return query.with_for_update()
    return query


def stock_movement_event_payload(movement):
    return {
        "stock_movement_id": movement.id,
        "product_id": movement.product_id,
        "warehouse_id": movement.warehouse_id,
        "direction": movement.direction,
        "quantity": movement.quantity,
        "before_available_qty": movement.before_available_qty,
        "after_available_qty": movement.after_available_qty,
        "before_locked_qty": movement.before_locked_qty,
        "after_locked_qty": movement.after_locked_qty,
        "source_type": movement.source_type,
        "source_id": movement.source_id,
        "idempotency_key": movement.idempotency_key,
        "reason": movement.reason,
        "created_by": movement.created_by,
    }


class InventoryApplicationService:
    def reserve_stock(self, source_type, source_id, items, idempotency_key, *, created_by=None, reason=None, write_legacy_log=True):
        return self._apply_many(
            StockMovement.DIRECTION_RESERVE,
            source_type,
            source_id,
            items,
            idempotency_key,
            created_by=created_by,
            reason=reason,
            write_legacy_log=write_legacy_log,
        )

    def release_stock(self, source_type, source_id, items, idempotency_key, *, created_by=None, reason=None, write_legacy_log=True):
        return self._apply_many(
            StockMovement.DIRECTION_RELEASE,
            source_type,
            source_id,
            items,
            idempotency_key,
            created_by=created_by,
            reason=reason,
            write_legacy_log=write_legacy_log,
        )

    def deduct_stock(self, source_type, source_id, items, idempotency_key, *, created_by=None, reason=None, write_legacy_log=True):
        return self._apply_many(
            StockMovement.DIRECTION_DEDUCT,
            source_type,
            source_id,
            items,
            idempotency_key,
            created_by=created_by,
            reason=reason,
            write_legacy_log=write_legacy_log,
        )

    def receive_stock(self, source_type, source_id, items, idempotency_key, *, created_by=None, reason=None, write_legacy_log=True, legacy_transaction_code=None):
        return self._apply_many(
            StockMovement.DIRECTION_RECEIVE,
            source_type,
            source_id,
            items,
            idempotency_key,
            created_by=created_by,
            reason=reason,
            write_legacy_log=write_legacy_log,
            legacy_transaction_code=legacy_transaction_code,
        )

    def adjust_stock(self, product_id, warehouse_id, delta, reason, idempotency_key, *, source_type="stock_adjustment", source_id=None, created_by=None, write_legacy_log=True):
        quantity = abs(int(delta or 0))
        if quantity <= 0:
            raise ValueError("库存调整数量不能为 0")
        direction = StockMovement.DIRECTION_RECEIVE if delta > 0 else StockMovement.DIRECTION_DEDUCT
        source_id = source_id or f"{product_id}:{warehouse_id}:{idempotency_key}"
        return self._apply_many(
            direction,
            source_type,
            source_id,
            [{"product_id": product_id, "warehouse_id": warehouse_id, "quantity": quantity}],
            idempotency_key,
            created_by=created_by,
            reason=reason,
            write_legacy_log=write_legacy_log,
        )

    def _apply_many(self, operation, source_type, source_id, items, idempotency_key, *, created_by=None, reason=None, write_legacy_log=True, legacy_transaction_code=None):
        movements = []
        created_movements = []
        for item in _item_rows(items):
            movement, created = self._apply_one(
                operation,
                source_type,
                str(source_id),
                item["product_id"],
                item["warehouse_id"],
                item["quantity"],
                _idempotency_key(idempotency_key, operation, item["product_id"], item["warehouse_id"]),
                created_by=created_by,
                reason=reason,
                write_legacy_log=write_legacy_log,
                legacy_transaction_code=legacy_transaction_code,
            )
            movements.append(movement)
            if created:
                created_movements.append(movement)
        db.session.flush()
        self._record_movement_events(operation, created_movements)
        return movements

    def _apply_one(self, operation, source_type, source_id, product_id, warehouse_id, quantity, idem_key, *, created_by=None, reason=None, write_legacy_log=True, legacy_transaction_code=None):
        existing = StockMovement.query.filter_by(idempotency_key=idem_key).first()
        if existing:
            return existing, False

        product = db.session.get(Product, product_id)
        warehouse = db.session.get(Warehouse, warehouse_id)
        if not product or not warehouse:
            raise ValueError("库存目标对象不存在")

        balance = self._balance_for_update(product_id, warehouse_id)
        before_available = int(balance.available_qty or 0)
        before_locked = int(balance.locked_qty or 0)

        if operation == StockMovement.DIRECTION_RESERVE:
            after_available = before_available - quantity
            after_locked = before_locked + quantity
        elif operation == StockMovement.DIRECTION_RELEASE:
            after_available = before_available + quantity
            after_locked = before_locked - quantity
        elif operation == StockMovement.DIRECTION_DEDUCT:
            if before_locked >= quantity:
                after_available = before_available
                after_locked = before_locked - quantity
            else:
                unlocked = quantity - before_locked
                after_available = before_available - unlocked
                after_locked = 0
        elif operation == StockMovement.DIRECTION_RECEIVE:
            after_available = before_available + quantity
            after_locked = before_locked
        else:
            raise ValueError(f"未知库存操作: {operation}")

        if after_available < 0 or after_locked < 0:
            raise ValueError("库存不足，不能产生负数库存")

        balance.available_qty = after_available
        balance.locked_qty = after_locked
        balance.version = int(balance.version or 0) + 1

        stock = self._stock_for_update(product_id, warehouse_id)
        stock.quantity = after_available + after_locked

        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            direction=operation,
            quantity=quantity,
            before_available_qty=before_available,
            after_available_qty=after_available,
            before_locked_qty=before_locked,
            after_locked_qty=after_locked,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idem_key,
            reason=reason,
            created_by=getattr(created_by, "id", created_by),
        )
        db.session.add(movement)
        if write_legacy_log:
            self._append_legacy_log(movement, stock.quantity, created_by=created_by, transaction_code=legacy_transaction_code)
        return movement, True

    def _record_movement_events(self, operation, movements):
        event_type = EVENT_TYPES_BY_DIRECTION.get(operation)
        if not event_type or not movements:
            return
        from app.platform.events import outbox

        for movement in movements:
            outbox.add(
                event_type,
                "StockMovement",
                movement.id,
                stock_movement_event_payload(movement),
                created_by=movement.created_by,
            )

    def _balance_for_update(self, product_id, warehouse_id):
        query = StockBalance.query.filter_by(tenant_id="default", product_id=product_id, warehouse_id=warehouse_id)
        balance = _locked(query).first()
        if balance:
            return balance

        stock = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
        balance = StockBalance(
            tenant_id="default",
            product_id=product_id,
            warehouse_id=warehouse_id,
            available_qty=int(getattr(stock, "quantity", 0) or 0),
            locked_qty=0,
            version=1,
        )
        db.session.add(balance)
        db.session.flush()
        return balance

    def _stock_for_update(self, product_id, warehouse_id):
        query = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id)
        stock = _locked(query).first()
        if stock:
            return stock
        stock = Stock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(stock)
        db.session.flush()
        return stock

    def _append_legacy_log(self, movement, balance_after, *, created_by=None, transaction_code=None):
        move_type = InventoryLog.TYPE_IN if movement.direction == StockMovement.DIRECTION_RECEIVE else InventoryLog.TYPE_OUT
        if movement.direction == StockMovement.DIRECTION_ADJUST:
            move_type = InventoryLog.TYPE_CHECK
        log = InventoryLog(
            transaction_code=(transaction_code or movement.idempotency_key)[:32],
            move_type=move_type,
            product_id=movement.product_id,
            warehouse_id=movement.warehouse_id,
            qty_change=movement.after_available_qty - movement.before_available_qty,
            balance_after=balance_after,
            operator_id=getattr(created_by, "id", created_by),
            remark=movement.reason or f"{movement.source_type}:{movement.source_id}:{movement.direction}",
        )
        db.session.add(log)
