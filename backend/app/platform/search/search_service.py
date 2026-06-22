from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from sqlalchemy import or_

from app.models.biz import Partner, Product
from app.models.content import Article, Attachment
from app.models.finance import Receivable
from app.models.purchase import PurchaseOrder
from app.models.stock import InventoryLog
from app.models.sys import AuditLog
from app.models.trade import Order
from app.platform.crud.permissions import is_admin_user


@dataclass(frozen=True)
class SearchHit:
    type: str
    label: str
    description: str | None
    path: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "label": self.label,
            "description": self.description,
            "path": self.path,
        }


@dataclass(frozen=True)
class SearchTarget:
    key: str
    model: type
    fields: Sequence[str]
    label: Callable[[object], str]
    description: Callable[[object], str | None]
    path: Callable[[object], str]
    scope: Callable[[object, object], object] | None = None


class SearchService:
    min_term_length = 2
    per_resource_limit = 5
    max_results = 20

    def search(self, term: str, *, user) -> list[dict]:
        normalized = (term or "").strip()
        if len(normalized) < self.min_term_length:
            return []

        like = f"%{normalized}%"
        hits: list[SearchHit] = []
        for target in self.targets:
            hits.extend(self._search_target(target, like, user))
            if len(hits) >= self.max_results:
                break
        return [hit.to_dict() for hit in hits[: self.max_results]]

    @property
    def targets(self) -> tuple[SearchTarget, ...]:
        return SEARCH_TARGETS

    def _search_target(self, target: SearchTarget, like: str, user) -> list[SearchHit]:
        filters = []
        for field in target.fields:
            column = getattr(target.model, field)
            filters.append(column.ilike(like))
        query = target.model.query.filter(or_(*filters))
        if hasattr(target.model, "is_deleted"):
            query = query.filter(target.model.is_deleted == False)
        if target.scope:
            query = target.scope(query, user)
        rows = query.limit(self.per_resource_limit).all()
        return [
            SearchHit(
                target.key,
                target.label(row),
                target.description(row),
                target.path(row),
            )
            for row in rows
        ]


def _file_scope(query, user):
    if not is_admin_user(user):
        return query.filter(Attachment.uploader_id == user.id)
    return query


def _audit_scope(query, user):
    if not is_admin_user(user):
        return query.filter(AuditLog.user_id == user.id)
    return query


SEARCH_TARGETS: tuple[SearchTarget, ...] = (
    SearchTarget(
        key="product",
        model=Product,
        fields=("name", "sku"),
        label=lambda item: item.name,
        description=lambda item: item.sku,
        path=lambda item: f"/app/inventory/products/{item.id}",
    ),
    SearchTarget(
        key="partner",
        model=Partner,
        fields=("name", "contact_person", "phone", "email"),
        label=lambda item: item.name,
        description=lambda item: item.type,
        path=lambda item: f"/app/{'suppliers/performance' if item.type == Partner.TYPE_SUPPLIER else 'customers'}",
    ),
    SearchTarget(
        key="order",
        model=Order,
        fields=("order_no",),
        label=lambda item: item.order_no,
        description=lambda item: item.status,
        path=lambda item: f"/app/sales/orders/{item.id}",
    ),
    SearchTarget(
        key="purchase",
        model=PurchaseOrder,
        fields=("po_no", "remark"),
        label=lambda item: item.po_no,
        description=lambda item: item.status,
        path=lambda item: f"/app/procurement/orders/{item.id}",
    ),
    SearchTarget(
        key="receivable",
        model=Receivable,
        fields=("receivable_no", "remark"),
        label=lambda item: item.receivable_no,
        description=lambda item: item.status,
        path=lambda item: f"/app/finance/receivables/{item.id}",
    ),
    SearchTarget(
        key="inventory-log",
        model=InventoryLog,
        fields=("transaction_code", "move_type", "remark"),
        label=lambda item: item.transaction_code or f"Inventory Log #{item.id}",
        description=lambda item: item.move_type,
        path=lambda item: "/app/inventory/stock",
    ),
    SearchTarget(
        key="file",
        model=Attachment,
        fields=("filename", "mimetype"),
        label=lambda item: item.filename,
        description=lambda item: item.mimetype,
        path=lambda item: f"/app/files/{item.id}",
        scope=_file_scope,
    ),
    SearchTarget(
        key="audit-log",
        model=AuditLog,
        fields=("module", "action", "details"),
        label=lambda item: f"{item.module}.{item.action}",
        description=lambda item: item.ip_address,
        path=lambda item: "/app/system/audit",
        scope=_audit_scope,
    ),
    SearchTarget(
        key="article",
        model=Article,
        fields=("title", "content_raw", "category"),
        label=lambda item: item.title,
        description=lambda item: item.category,
        path=lambda item: f"/app/content/articles/{item.id}",
    ),
)


search_service = SearchService()
