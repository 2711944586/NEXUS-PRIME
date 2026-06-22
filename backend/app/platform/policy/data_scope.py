from app.domains.reporting.models import ReportingMetricDaily
from app.models.content import Article, ArticleComment, Attachment
from app.models.finance import AccountStatement, CustomerCredit, PaymentRecord, Receivable
from app.models.notification import GeneratedReport, Notification, ReportSubscription
from app.models.stock import InventoryLog, StockMovement
from app.models.stocktake import StockTake, StockTakeItem
from app.models.sys import AiChatMessage, AiChatSession
from app.models.trade import Order, OrderItem


class DataScopePolicy:
    """Apply row-level visibility rules for queryable ERP objects."""

    def __init__(self, *, is_admin, has_any_permission):
        self._is_admin = is_admin
        self._has_any_permission = has_any_permission

    def filter_query(self, query, model, user):
        if not user:
            return query.filter(False)
        if self._is_admin(user):
            return query
        if model is Notification:
            return query.filter(Notification.user_id == user.id)
        if model is Attachment:
            return query.filter(Attachment.uploader_id == user.id)
        if model is Article:
            if self._has_any_permission(user, {"content.write"}):
                return query
            return query.filter(Article.status == "published")
        if model is ArticleComment:
            if self._has_any_permission(user, {"content.write"}):
                return query
            return query.join(Article, ArticleComment.article_id == Article.id).filter(Article.status == "published")
        if model is AiChatSession:
            return query.filter(AiChatSession.user_id == user.id)
        if model is AiChatMessage:
            return query.join(AiChatSession, AiChatMessage.session_id == AiChatSession.id).filter(AiChatSession.user_id == user.id)
        if model is ReportSubscription:
            return query.filter(ReportSubscription.user_id == user.id)
        if model is GeneratedReport:
            return (
                query.outerjoin(ReportSubscription, GeneratedReport.subscription_id == ReportSubscription.id)
                .filter((GeneratedReport.generated_by == user.id) | (ReportSubscription.user_id == user.id))
            )
        if model is Order:
            return query.filter(Order.seller_id == user.id)
        if model is OrderItem:
            return query.join(Order, OrderItem.order_id == Order.id).filter(Order.seller_id == user.id)
        if model is Receivable:
            if self._has_any_permission(user, {"finance.payment"}):
                return query
            return query.outerjoin(Order, Receivable.order_id == Order.id).filter(Order.seller_id == user.id)
        if model is PaymentRecord:
            if self._has_any_permission(user, {"finance.payment"}):
                return query
            return query.outerjoin(Receivable, PaymentRecord.receivable_id == Receivable.id).outerjoin(Order, Receivable.order_id == Order.id).filter(
                (PaymentRecord.operator_id == user.id) | (Order.seller_id == user.id)
            )
        if model is CustomerCredit:
            if self._has_any_permission(user, {"finance.credit.write"}):
                return query
            return query.filter(False)
        if model is AccountStatement:
            if self._has_any_permission(user, {"reports.generate"}):
                return query
            return query.filter(AccountStatement.generated_by == user.id)
        if model is ReportingMetricDaily:
            if self._has_any_permission(user, {"reports.generate"}):
                return query
            return query.filter(False)
        if model is InventoryLog:
            return query.filter(InventoryLog.operator_id == user.id)
        if model is StockMovement:
            return query.filter(StockMovement.created_by == user.id)
        if model is StockTake:
            return query.filter(StockTake.created_by == user.id)
        if model is StockTakeItem:
            return query.join(StockTake, StockTakeItem.take_id == StockTake.id).filter(StockTake.created_by == user.id)
        return query
