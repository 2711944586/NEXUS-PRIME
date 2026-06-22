from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.utils.time import utcnow
from app.domains.reporting.models import ReportingMetricDaily, ReportingProjectionState


def _decimal(value):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _int(value):
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _event_date(event):
    created_at = getattr(event, "created_at", None) or utcnow()
    return created_at.date()


def _metric(metric_name, value=1, *, count=1, dimension_type="global", dimension_id="all", attributes=None):
    return {
        "metric_name": metric_name,
        "value": _decimal(value),
        "count": int(count or 0),
        "dimension_type": dimension_type,
        "dimension_id": str(dimension_id or "all"),
        "attributes": attributes or {},
    }


class ReportingMetricProjector:
    def project_event(self, event):
        event_key = getattr(event, "event_id", None) or f"domain-event:{event.id}"
        existing_state = ReportingProjectionState.query.filter_by(event_id=event_key, is_deleted=False).first()
        if existing_state:
            return existing_state

        changes = self._changes_for(event)
        if not changes:
            return None

        tenant_id = event.tenant_id or "default"
        metric_date = _event_date(event)
        projected_at = utcnow()
        for change in changes:
            metric = self._get_or_create_metric(
                tenant_id,
                metric_date,
                change["metric_name"],
                change["dimension_type"],
                change["dimension_id"],
            )
            metric.value = _decimal(metric.value) + change["value"]
            metric.count = int(metric.count or 0) + change["count"]
            metric.last_event_id = event_key
            metric.last_event_type = event.event_type
            metric.last_projected_at = projected_at
            metric.attributes = {**(metric.attributes or {}), **change["attributes"]}
            db.session.add(metric)

        state = ReportingProjectionState(
            event_id=event_key,
            event_type=event.event_type,
            tenant_id=tenant_id,
            metrics_count=len(changes),
            projected_at=projected_at,
        )
        db.session.add(state)
        return state

    def _get_or_create_metric(self, tenant_id, metric_date, metric_name, dimension_type, dimension_id):
        metric = ReportingMetricDaily.query.filter_by(
            tenant_id=tenant_id,
            metric_date=metric_date,
            metric_name=metric_name,
            dimension_type=dimension_type,
            dimension_id=dimension_id,
            is_deleted=False,
        ).first()
        if metric:
            return metric
        metric = ReportingMetricDaily(
            tenant_id=tenant_id,
            metric_date=metric_date,
            metric_name=metric_name,
            dimension_type=dimension_type,
            dimension_id=dimension_id,
            value=Decimal("0"),
            count=0,
            attributes={},
        )
        db.session.add(metric)
        return metric

    def _changes_for(self, event):
        payload = event.payload or {}
        builders = {
            "SalesOrderCreated": self._sales_order_created,
            "SalesOrderConfirmed": self._sales_order_confirmed,
            "SalesOrderCancelled": self._sales_order_cancelled,
            "PurchaseOrderCreated": self._purchase_order_created,
            "PurchaseOrderApproved": self._purchase_order_approved,
            "PurchaseGoodsReceived": self._purchase_goods_received,
            "ReceivableCreated": self._receivable_created,
            "PaymentRecorded": self._payment_recorded,
            "InventoryReserved": self._inventory_reserved,
            "InventoryReleased": self._inventory_released,
            "InventoryDeducted": self._inventory_deducted,
            "StockBelowSafetyLine": self._stock_below_safety_line,
            "ReportRequested": self._report_requested,
            "WorkflowStarted": self._workflow_started,
            "WorkflowTaskApproved": self._workflow_task_approved,
            "WorkflowTaskRejected": self._workflow_task_rejected,
            "QualityInspectionPassed": self._quality_inspection_passed,
            "QualityInspectionFailed": self._quality_inspection_failed,
        }
        builder = builders.get(event.event_type)
        return builder(payload) if builder else []

    def _sales_order_created(self, payload):
        return self._amount_metrics("sales_order_created", payload.get("total_amount"), payload, "seller")

    def _sales_order_confirmed(self, payload):
        return self._amount_metrics("sales_order_confirmed", payload.get("total_amount"), payload, "seller")

    def _sales_order_cancelled(self, payload):
        return self._amount_metrics("sales_order_cancelled", payload.get("total_amount"), payload, "seller")

    def _purchase_order_created(self, payload):
        return self._amount_metrics("purchase_order_created", payload.get("total_amount"), payload, "supplier")

    def _purchase_order_approved(self, payload):
        return self._amount_metrics("purchase_order_approved", payload.get("total_amount"), payload, "supplier")

    def _purchase_goods_received(self, payload):
        total_qty = sum(_int(line.get("receive_qty") or line.get("quantity")) for line in payload.get("received_lines") or [])
        return self._quantity_metrics("purchase_goods_received", total_qty, payload)

    def _receivable_created(self, payload):
        return self._amount_metrics("receivable_created", payload.get("total_amount"), payload, "customer")

    def _payment_recorded(self, payload):
        return self._amount_metrics("payment_recorded", payload.get("amount"), payload, "customer")

    def _inventory_reserved(self, payload):
        return self._quantity_metrics("inventory_reserved", payload.get("quantity"), payload)

    def _inventory_released(self, payload):
        return self._quantity_metrics("inventory_released", payload.get("quantity"), payload)

    def _inventory_deducted(self, payload):
        return self._quantity_metrics("inventory_deducted", payload.get("quantity"), payload)

    def _stock_below_safety_line(self, payload):
        return [
            _metric("stock_below_safety_line", 1, attributes={"product_id": payload.get("product_id")}),
            *self._dimension_metric("stock_below_safety_line", "product", payload.get("product_id"), 1),
        ]

    def _report_requested(self, payload):
        return [
            _metric("report_requested", 1, attributes={"report_type": payload.get("report_type")}),
            *self._dimension_metric("report_requested", "report_type", payload.get("report_type"), 1),
        ]

    def _workflow_started(self, payload):
        return [
            _metric("workflow_started", 1, attributes={"process_key": payload.get("process_key")}),
            *self._dimension_metric("workflow_started", "process", payload.get("process_key"), 1),
        ]

    def _workflow_task_approved(self, payload):
        return self._workflow_task_metric("workflow_task_approved", payload)

    def _workflow_task_rejected(self, payload):
        return self._workflow_task_metric("workflow_task_rejected", payload)

    def _quality_inspection_passed(self, payload):
        return [_metric("quality_inspection_passed", 1, attributes={"queue_item_id": payload.get("queue_item_id")})]

    def _quality_inspection_failed(self, payload):
        return [_metric("quality_inspection_failed", 1, attributes={"queue_item_id": payload.get("queue_item_id")})]

    def _amount_metrics(self, prefix, amount, payload, owner_dimension):
        value = _decimal(amount)
        metrics = [
            _metric(f"{prefix}_count", 1, attributes={"source": payload.get("order_no") or payload.get("po_no")}),
            _metric(f"{prefix}_amount", value),
        ]
        dimension_id = payload.get(f"{owner_dimension}_id")
        if dimension_id:
            metrics.append(_metric(f"{prefix}_amount", value, dimension_type=owner_dimension, dimension_id=dimension_id))
        return metrics

    def _quantity_metrics(self, prefix, quantity, payload):
        value = _decimal(quantity)
        metrics = [
            _metric(f"{prefix}_count", 1),
            _metric(f"{prefix}_quantity", value),
        ]
        metrics.extend(self._dimension_metric(f"{prefix}_quantity", "product", payload.get("product_id"), value))
        metrics.extend(self._dimension_metric(f"{prefix}_quantity", "warehouse", payload.get("warehouse_id"), value))
        return metrics

    def _workflow_task_metric(self, name, payload):
        return [
            _metric(name, 1, attributes={"process_key": payload.get("process_key")}),
            *self._dimension_metric(name, "process", payload.get("process_key"), 1),
        ]

    def _dimension_metric(self, metric_name, dimension_type, dimension_id, value):
        if not dimension_id:
            return []
        return [_metric(metric_name, value, dimension_type=dimension_type, dimension_id=dimension_id)]


projector = ReportingMetricProjector()


def project_reporting_event(event):
    return projector.project_event(event)


__all__ = ["ReportingMetricProjector", "project_reporting_event", "projector"]
