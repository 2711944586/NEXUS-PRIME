from dataclasses import dataclass

from app.domains.reporting.models import ReportingMetricDaily
from app.models.content import Article, ArticleComment, Attachment
from app.models.finance import AccountStatement, CustomerCredit, PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReportSubscription
from app.models.stock import InventoryLog, StockMovement
from app.models.stocktake import StockTake, StockTakeItem
from app.models.sys import AiChatMessage, AiChatSession
from app.models.trade import Order, OrderItem


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    error: str | None = None


class ObjectAuthorizationPolicy:
    """Authorize operations against individual persisted objects."""

    def __init__(self, *, has_any_permission):
        self._has_any_permission = has_any_permission

    def decide(self, user, action, resource):
        if resource is None:
            return None
        if isinstance(resource, Order) and resource.seller_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, OrderItem):
            order = resource.order
            if order and order.seller_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, Receivable):
            if self._has_any_permission(user, {"finance.payment"}):
                return None
            order = resource.order
            if order and order.seller_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, PaymentRecord):
            if self._has_any_permission(user, {"finance.payment"}):
                return None
            receivable = resource.receivable
            order = receivable.order if receivable else None
            if resource.operator_id != user.id and order and order.seller_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, AccountStatement):
            if self._has_any_permission(user, {"reports.generate"}):
                return None
            if resource.generated_by != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, CustomerCredit):
            if self._has_any_permission(user, {"finance.credit.write"}):
                return None
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, InventoryLog) and resource.operator_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, StockMovement) and resource.created_by != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, StockTake) and resource.created_by != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, StockTakeItem):
            stocktake = resource.stock_take
            if stocktake and stocktake.created_by != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, Notification):
            if resource.user_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
            if action == "delete":
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, Attachment) and resource.uploader_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, Article):
            if resource.status != "published" and not self._has_any_permission(user, {"content.write"}):
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, ArticleComment):
            article = resource.article
            if article and article.status != "published" and not self._has_any_permission(user, {"content.write"}):
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, ArticleComment) and action in {"update", "delete"} and resource.author_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, AiChatSession) and resource.user_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, AiChatMessage):
            session = resource.session
            if session and session.user_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, ReportSubscription) and resource.user_id != user.id:
            return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, GeneratedReport):
            owner_id = resource.generated_by
            subscription_user_id = resource.subscription.user_id if resource.subscription else None
            if owner_id != user.id and subscription_user_id != user.id:
                return PolicyDecision(False, "权限不足", "forbidden")
        if isinstance(resource, ReportingMetricDaily) and not self._has_any_permission(user, {"reports.generate"}):
            return PolicyDecision(False, "权限不足", "forbidden")
        return None
