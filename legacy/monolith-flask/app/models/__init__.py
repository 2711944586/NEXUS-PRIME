# 按照依赖顺序导入
from .base import BaseModel
from .auth import User, Role, Permission, Department
from .biz import Category, Product, Partner, Tag
from .stock import Warehouse, Stock, InventoryLog
from .trade import Order, OrderItem
from .content import Article, Attachment
from .sys import AuditLog, AiChatLog, AiChatSession, AiChatMessage

# 采购管理
from .purchase import PurchaseOrder, PurchaseOrderItem, PurchasePriceHistory, SupplierPerformance

# 财务管理
from .finance import CustomerCredit, Receivable, PaymentRecord, AccountStatement

# 盘点管理
from .stocktake import StockTake, StockTakeItem, StockTakeHistory

# 通知与报表
from .notification import (
    Notification, StockAlert, ReplenishmentSuggestion,
    ReportSubscription, GeneratedReport
)