"""Permission-guarded AI tool execution.

The AI layer may read operational data and prepare drafts, but it must not
mutate core ERP records without an explicit business workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import func, or_

from app.extensions import db
from app.models.ai import DocumentChunk
from app.models.biz import Partner, Product
from app.models.content import Attachment
from app.models.finance import Receivable
from app.models.jobs import BackgroundJob
from app.models.purchase import PurchaseOrder
from app.models.stock import Stock, StockBalance
from app.models.trade import Order
from app.platform.crud.serializers import serialize_value
from app.platform.jobs import create_background_job, serialize_background_job
from app.platform.policy import policy
from app.services.audit_service import AuditService
from app.services.report_service import ReportService

from .action_drafts import AiActionDraftService, serialize_action_draft


ToolHandler = Callable[[dict[str, Any], Any], dict[str, Any]]


@dataclass(frozen=True)
class ToolRunResult:
    status: int
    payload: dict[str, Any]


class AiToolRunner:
    """Run a small whitelist of read-only or draft-only AI tools."""

    def __init__(self):
        self._handlers: dict[str, ToolHandler] = {
            "query_inventory_balance": self._query_inventory_balance,
            "query_sales_orders": self._query_sales_orders,
            "query_receivables": self._query_receivables,
            "query_purchase_orders": self._query_purchase_orders,
            "search_documents": self._search_documents,
            "generate_replenishment_draft": self._generate_replenishment_draft,
            "create_report_job": self._create_report_job,
        }

    @property
    def available_tools(self) -> list[str]:
        return sorted(self._handlers)

    def run(self, tool_name: str, params: dict[str, Any] | None, user) -> ToolRunResult:
        tool_name = (tool_name or "").strip()
        params = params or {}
        action = f"ai.tool.{tool_name}"
        resource = self._authorization_resource(tool_name, params)
        decision = policy.can(user, action, resource=resource, context={"tool": tool_name, "params": params})

        if not decision.allowed:
            payload = {
                "ok": False,
                "tool": tool_name,
                "allowed": False,
                "error": decision.error or "permission_denied",
                "message": decision.reason or "权限不足",
                "available_tools": self.available_tools,
            }
            self._audit(user, tool_name, params, decision=decision, payload=payload)
            return ToolRunResult(400 if decision.error == "unknown_ai_tool" else 403, payload)

        handler = self._handlers.get(tool_name)
        if handler is None:
            # Keep a defensive branch in case the policy whitelist and runner
            # whitelist drift apart during future iterations.
            payload = {
                "ok": False,
                "tool": tool_name,
                "allowed": False,
                "error": "unknown_ai_tool",
                "message": "未知 AI 工具",
                "available_tools": self.available_tools,
            }
            self._audit(user, tool_name, params, decision=decision, payload=payload)
            return ToolRunResult(400, payload)

        try:
            data = handler(params, user)
            payload = {
                "ok": True,
                "tool": tool_name,
                "allowed": True,
                "data": data,
            }
        except (TypeError, ValueError) as exc:
            payload = {
                "ok": False,
                "tool": tool_name,
                "allowed": True,
                "error": "invalid_tool_params",
                "message": str(exc),
            }
            self._audit(user, tool_name, params, decision=decision, payload=payload)
            return ToolRunResult(400, payload)
        self._audit(user, tool_name, params, decision=decision, payload=payload)
        return ToolRunResult(200, payload)

    def _authorization_resource(self, tool_name: str, params: dict[str, Any]):
        if tool_name != "search_documents":
            return None
        if str(params.get("source_type") or "") != "attachment":
            return None
        source_id = params.get("source_id")
        if not source_id:
            return None
        return db.session.get(Attachment, int(source_id)) if str(source_id).isdigit() else None

    def _audit(self, user, tool_name: str, params: dict[str, Any], *, decision, payload: dict[str, Any]) -> None:
        details = {
            "tool": tool_name,
            "allowed": bool(payload.get("allowed")),
            "ok": bool(payload.get("ok")),
            "error": payload.get("error"),
            "reason": decision.reason,
            "params": self._audit_params(params),
        }
        if payload.get("ok"):
            data = payload.get("data") or {}
            details["result_count"] = data.get("count") or len(data.get("items") or data.get("lines") or [])
            details["mutates_core_records"] = bool(data.get("mutates_core_records", False))
        AuditService.record("ai", "tool_call", user, details)

    def _audit_params(self, params: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in params.items():
            if key.lower() in {"password", "token", "secret", "api_key"}:
                safe[key] = "<redacted>"
            elif isinstance(value, str):
                safe[key] = value[:160]
            else:
                safe[key] = value
        return safe

    def _limit(self, params: dict[str, Any], default: int = 10, maximum: int = 50) -> int:
        try:
            value = int(params.get("limit") or default)
        except (TypeError, ValueError):
            value = default
        return max(1, min(value, maximum))

    def _query_inventory_balance(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params)
        query = (
            Stock.query
            .join(Product, Stock.product_id == Product.id)
            .join(Stock.warehouse)
            .filter(Stock.is_deleted == False, Product.is_deleted == False)
        )
        if params.get("product_id"):
            query = query.filter(Stock.product_id == int(params["product_id"]))
        if params.get("warehouse_id"):
            query = query.filter(Stock.warehouse_id == int(params["warehouse_id"]))
        if params.get("low_stock_only"):
            query = query.filter(Stock.quantity <= func.coalesce(Product.min_stock, 0))
        rows = query.order_by(Stock.quantity.asc(), Stock.id.asc()).limit(limit).all()
        balance_by_key = {
            (balance.product_id, balance.warehouse_id): balance
            for balance in StockBalance.query.filter(
                StockBalance.product_id.in_([row.product_id for row in rows] or [0]),
                StockBalance.warehouse_id.in_([row.warehouse_id for row in rows] or [0]),
                StockBalance.is_deleted == False,
            ).all()
        }
        items = []
        for row in rows:
            balance = balance_by_key.get((row.product_id, row.warehouse_id))
            items.append({
                "stock_id": row.id,
                "product_id": row.product_id,
                "product_sku": row.product.sku if row.product else None,
                "product_name": row.product.name if row.product else None,
                "warehouse_id": row.warehouse_id,
                "warehouse_name": row.warehouse.name if row.warehouse else None,
                "quantity": row.quantity or 0,
                "min_stock": row.product.min_stock if row.product else None,
                "max_stock": row.product.max_stock if row.product else None,
                "available_qty": balance.available_qty if balance else row.quantity or 0,
                "locked_qty": balance.locked_qty if balance else 0,
            })
        return {"count": len(items), "items": items, "mutates_core_records": False}

    def _query_sales_orders(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params)
        query = Order.query.filter(Order.is_deleted == False)
        query = policy.filter_query(query, Order, user)
        if params.get("status"):
            query = query.filter(Order.status == str(params["status"]))
        if params.get("customer_id"):
            query = query.filter(Order.customer_id == int(params["customer_id"]))
        rows = query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).all()
        items = [policy.filter_fields(user, Order, self._order_payload(row)) for row in rows]
        return {"count": len(items), "items": items, "mutates_core_records": False}

    def _query_receivables(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params)
        query = Receivable.query.filter(Receivable.is_deleted == False)
        query = policy.filter_query(query, Receivable, user)
        if params.get("status"):
            query = query.filter(Receivable.status == str(params["status"]))
        if params.get("customer_id"):
            query = query.filter(Receivable.customer_id == int(params["customer_id"]))
        rows = query.order_by(Receivable.due_date.asc(), Receivable.id.desc()).limit(limit).all()
        items = [policy.filter_fields(user, Receivable, self._receivable_payload(row)) for row in rows]
        return {"count": len(items), "items": items, "mutates_core_records": False}

    def _query_purchase_orders(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params)
        query = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False)
        if params.get("status"):
            query = query.filter(PurchaseOrder.status == str(params["status"]))
        if params.get("supplier_id"):
            query = query.filter(PurchaseOrder.supplier_id == int(params["supplier_id"]))
        rows = query.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc()).limit(limit).all()
        return {
            "count": len(rows),
            "items": [self._purchase_order_payload(row) for row in rows],
            "mutates_core_records": False,
        }

    def _search_documents(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params)
        query_text = (params.get("q") or params.get("query") or "").strip()
        query = DocumentChunk.query.filter(DocumentChunk.is_deleted == False)
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(or_(DocumentChunk.content.ilike(pattern), DocumentChunk.title.ilike(pattern)))
        if params.get("source_type"):
            query = query.filter(DocumentChunk.source_type == str(params["source_type"]))
        if params.get("source_id"):
            query = query.filter(DocumentChunk.source_id == str(params["source_id"]))

        items = []
        for chunk in query.order_by(DocumentChunk.id.asc()).limit(limit * 3).all():
            if chunk.source_type == "attachment":
                attachment = db.session.get(Attachment, int(chunk.source_id)) if str(chunk.source_id).isdigit() else None
                if attachment and not policy.can(user, "ai.tool.search_documents", resource=attachment).allowed:
                    continue
            items.append({
                "chunk_id": chunk.id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "chunk_index": chunk.chunk_index,
                "title": chunk.title,
                "excerpt": (chunk.content or "")[:500],
                "metadata": chunk.metadata_json or {},
            })
            if len(items) >= limit:
                break
        return {"count": len(items), "items": items, "mutates_core_records": False}

    def _generate_replenishment_draft(self, params: dict[str, Any], user) -> dict[str, Any]:
        limit = self._limit(params, default=8, maximum=25)
        query = (
            Stock.query
            .join(Product, Stock.product_id == Product.id)
            .filter(Stock.is_deleted == False, Product.is_deleted == False)
            .filter(Stock.quantity <= func.coalesce(Product.min_stock, 0))
        )
        if params.get("product_id"):
            query = query.filter(Stock.product_id == int(params["product_id"]))
        if params.get("warehouse_id"):
            query = query.filter(Stock.warehouse_id == int(params["warehouse_id"]))

        lines = []
        for row in query.order_by(Stock.quantity.asc(), Stock.id.asc()).limit(limit).all():
            product = row.product
            target_qty = product.max_stock or product.min_stock or row.quantity or 0
            suggested_qty = max(0, int(target_qty) - int(row.quantity or 0))
            supplier = db.session.get(Partner, product.supplier_id) if product and product.supplier_id else None
            lines.append({
                "product_id": row.product_id,
                "product_sku": product.sku if product else None,
                "product_name": product.name if product else None,
                "warehouse_id": row.warehouse_id,
                "warehouse_name": row.warehouse.name if row.warehouse else None,
                "supplier_id": supplier.id if supplier else None,
                "supplier_name": supplier.name if supplier else None,
                "current_qty": row.quantity or 0,
                "min_stock": product.min_stock if product else None,
                "target_qty": target_qty,
                "suggested_qty": suggested_qty,
                "estimated_unit_cost": serialize_value(product.cost) if product else None,
            })

        draft = AiActionDraftService.create_replenishment_draft(
            lines,
            user,
            source_tool="generate_replenishment_draft",
            params=params,
        )
        return {
            "draft": {
                "id": draft.id,
                "type": "replenishment",
                "status": "draft",
                "requires_human_confirmation": True,
                "lines": lines,
            },
            "draft_id": draft.id,
            "action_draft": serialize_action_draft(draft),
            "count": len(lines),
            "lines": lines,
            "persists_ai_draft": True,
            "mutates_core_records": False,
        }

    def _create_report_job(self, params: dict[str, Any], user) -> dict[str, Any]:
        report_type = str(params.get("report_type") or "").strip()
        if report_type not in ReportService.REPORT_TYPES:
            raise ValueError(f"报表生成器不存在: {report_type}")
        report_params = params.get("params") if isinstance(params.get("params"), dict) else {}
        job = create_background_job(
            "report.generate",
            {"report_type": report_type, "params": report_params, "requested_by_ai_tool": True},
            created_by=user,
            queue="reports",
            task_name="nexus.reports.generate",
        )
        from app.platform.events import outbox

        outbox.add(
            "ReportRequested",
            "BackgroundJob",
            job.job_id,
            {
                "job_id": job.job_id,
                "report_type": report_type,
                "params": report_params,
                "requested_by": user.id if user else None,
                "source": "ai_tool",
            },
            created_by=user.id if user else None,
        )
        return {
            "job_id": job.job_id,
            "job": serialize_background_job(job),
            "status": BackgroundJob.STATUS_PENDING,
            "mutates_core_records": False,
        }

    def _order_payload(self, order: Order) -> dict[str, Any]:
        return {
            "id": order.id,
            "order_no": order.order_no,
            "customer_id": order.customer_id,
            "customer_name": order.customer.name if order.customer else None,
            "seller_id": order.seller_id,
            "status": order.status,
            "total_amount": serialize_value(order.total_amount),
            "created_at": serialize_value(order.created_at),
        }

    def _receivable_payload(self, receivable: Receivable) -> dict[str, Any]:
        return {
            "id": receivable.id,
            "receivable_no": receivable.receivable_no,
            "order_id": receivable.order_id,
            "customer_id": receivable.customer_id,
            "customer_name": receivable.customer.name if receivable.customer else None,
            "status": receivable.status,
            "total_amount": serialize_value(receivable.total_amount),
            "paid_amount": serialize_value(receivable.paid_amount),
            "unpaid_amount": receivable.unpaid_amount,
            "due_date": serialize_value(receivable.due_date),
            "overdue_days": receivable.overdue_days,
        }

    def _purchase_order_payload(self, order: PurchaseOrder) -> dict[str, Any]:
        return {
            "id": order.id,
            "po_no": order.po_no,
            "supplier_id": order.supplier_id,
            "supplier_name": order.supplier.name if order.supplier else None,
            "warehouse_id": order.warehouse_id,
            "warehouse_name": order.warehouse.name if order.warehouse else None,
            "status": order.status,
            "total_amount": serialize_value(order.total_amount),
            "receive_progress": order.receive_progress,
            "created_at": serialize_value(order.created_at),
        }
