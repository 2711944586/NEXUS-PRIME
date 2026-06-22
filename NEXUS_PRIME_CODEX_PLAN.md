# NEXUS-PRIME ERP 架构与前后端技术栈全面升级 PLAN

> 目标读者：Codex / 代码智能体 / 项目维护者
> 适用项目：`NEXUS-PRIME` ERP
> 计划类型：架构升级 + 前端体验升级 + 后端平台化升级 + 数据/权限/AI/DevOps 升级
> 推荐执行方式：分阶段、小步提交、每阶段可回滚
> 重要原则：不要一次性推倒重写；先模块化、再事件化、再服务化；前端先视觉底座，后业务页面升级。

---

## 0. 总目标

将现有 NEXUS-PRIME 从：

```text
Angular + PrimeNG + Flask + SQLAlchemy 的功能型 ERP 原型
```

升级为：

```text
领域边界清晰的模块化 ERP
+ 事件驱动的业务协作机制
+ 企业级权限、审计、流程、数据平台
+ 高级动效和工业智能指挥中心风格前端
+ 可观测、可测试、可部署的生产级工程体系
+ 可扩展 AI 经营分析与 Agent 能力
```

最终系统应具备以下特征：

```text
1. 架构清晰：domains/platform 分层，业务领域独立。
2. 前端高级：视频背景、Aurora、粒子、玻璃态、Spotlight、流程流光、数字孪生风格。
3. 后端可靠：模块化单体优先，Outbox + Worker 解耦，后续可拆 FastAPI/微服务。
4. 数据严谨：PostgreSQL 主交易库、Redis、对象存储、搜索、报表 Read Model、可选分析库。
5. 权限企业级：RBAC + ABAC + 数据范围 + 字段权限 + 对象级授权。
6. 流程可配置：工作流中心独立，采购/销售/财务/库存审批不写死。
7. AI 安全可控：RAG、Agent、工具调用、权限校验、人工确认、审计日志。
8. 工程成熟：OpenAPI 合同、CI/CD、Playwright、pytest、OpenTelemetry、Docker Compose。
```

---

## 1. 当前系统判断

### 1.1 当前系统定位

当前项目不是完全不可用的“烂架构”，而是：

```text
前后端分离的模块化单体 ERP
```

它适合：

```text
1. 课程项目展示。
2. 早期产品原型。
3. 中小型 ERP 功能验证。
4. 制造业智能经营平台的基础版本。
```

但暂时还不满足高级企业级 ERP 的要求：

```text
1. 领域边界不够清楚。
2. 后端 routes/resource 配置存在中心化倾向。
3. 销售、库存、财务、采购之间耦合较强。
4. 缺少事件驱动。
5. 缺少完整后台任务系统。
6. 权限仍偏 RBAC，缺少对象级、数据级、字段级权限。
7. 工作流没有完全独立。
8. 报表与主交易库边界不够明确。
9. 前端视觉可以继续大幅升级。
10. 生产级 DevOps、可观测性、合同测试仍需完善。
```

### 1.2 不建议立刻做的事情

Codex 执行时禁止在第一阶段做以下动作：

```text
1. 不要直接全量重写前端为 React。
2. 不要直接把所有后端拆成几十个微服务。
3. 不要一次性替换 Flask 为 FastAPI。
4. 不要删除现有业务功能后重写。
5. 不要为了动画破坏 ERP 的可用性、性能和权限控制。
6. 不要引入过重技术但不落地测试、部署和监控。
```

正确策略：

```text
先结构化重构 → 再事件化解耦 → 再高级前端体验 → 再 AI 和数据平台升级 → 最后选择性服务化。
```

---

## 2. 总体目标架构

### 2.1 目标系统分层

```text
NEXUS-PRIME 目标架构

Frontend
├─ Angular 主应用
├─ PrimeNG 企业组件
├─ Motion Design System
├─ Canvas / WebGL / GSAP 动效层
├─ Optional ReactBits Islands
└─ OpenAPI Typed Client

API / BFF
├─ Flask API Gateway / Modular Monolith
├─ Auth / CSRF / Session
├─ Rate Limit
├─ Request Context
├─ Object-level Authorization
├─ Audit Middleware
└─ API Versioning

Backend Domain Layer
├─ Identity Context
├─ Master Data Context
├─ Inventory Context
├─ Sales Context
├─ Procurement Context
├─ Finance Context
├─ Workflow Context
├─ Reporting Context
├─ File Context
├─ AI Context
└─ Integration Context

Platform Layer
├─ Event Bus
├─ Outbox
├─ Worker / Task Queue
├─ Policy Engine
├─ Audit Service
├─ Storage Service
├─ Notification Service
├─ Search Service
├─ Observability
└─ Config / Secrets

Data Layer
├─ PostgreSQL OLTP
├─ Redis Cache / Lock / Queue
├─ Object Storage
├─ Search Index
├─ Reporting Read Models
├─ Optional Analytics Warehouse
├─ Optional pgvector
└─ Audit / Event Store
```

### 2.2 架构升级原则

```text
1. 业务优先于技术：按销售、采购、库存、财务、工作流等领域分层。
2. 模块化单体优先：在业务边界清楚前不要贸然微服务化。
3. 事件驱动解耦：领域之间通过事件协作，减少直接 import 和直接改表。
4. 数据所有权清晰：每个领域拥有自己的数据，不允许跨领域随意改表。
5. 权限统一：所有 API 都必须经过统一认证、授权、数据范围、字段策略。
6. 审计默认开启：核心业务操作必须记录 who/when/what/before/after。
7. 前端视觉高级但可控：动效可降级，尊重 prefers-reduced-motion。
8. AI 不绕过权限：AI 只能建议、生成草稿、辅助分析，关键操作必须人工确认。
```

---

## 3. 后端架构升级计划

## 3.1 后端目录重构

### 3.1.1 当前问题

典型结构类似：

```text
backend/app
├─ api
├─ models
├─ services
├─ utils
├─ extensions.py
└─ exceptions.py
```

问题：

```text
1. 按技术分层，不按业务领域分层。
2. api/models/services 分散同一业务。
3. routes.py 容易成为上帝文件。
4. SalesService/InventoryService/FinanceService 等直接互相依赖模型。
5. 难以进行领域级测试和后续服务拆分。
```

### 3.1.2 目标目录

Codex 应重构为：

```text
backend/app
├─ __init__.py
├─ app.py
├─ config.py
├─ extensions.py
├─ exceptions.py
│
├─ platform/
│  ├─ __init__.py
│  ├─ auth/
│  │  ├─ __init__.py
│  │  ├─ session.py
│  │  ├─ csrf.py
│  │  ├─ password.py
│  │  └─ decorators.py
│  │
│  ├─ audit/
│  │  ├─ __init__.py
│  │  ├─ audit_service.py
│  │  ├─ audit_models.py
│  │  └─ audit_middleware.py
│  │
│  ├─ policy/
│  │  ├─ __init__.py
│  │  ├─ policy_engine.py
│  │  ├─ data_scope.py
│  │  ├─ field_policy.py
│  │  └─ object_authorization.py
│  │
│  ├─ events/
│  │  ├─ __init__.py
│  │  ├─ event.py
│  │  ├─ event_bus.py
│  │  ├─ outbox.py
│  │  ├─ handlers.py
│  │  └─ registry.py
│  │
│  ├─ jobs/
│  │  ├─ __init__.py
│  │  ├─ celery_app.py
│  │  ├─ worker.py
│  │  ├─ schedules.py
│  │  └─ tasks/
│  │
│  ├─ crud/
│  │  ├─ __init__.py
│  │  ├─ resource_registry.py
│  │  ├─ generic_resource_api.py
│  │  ├─ query_builder.py
│  │  └─ serializers.py
│  │
│  ├─ storage/
│  │  ├─ __init__.py
│  │  ├─ storage_service.py
│  │  ├─ cloudinary_storage.py
│  │  ├─ supabase_storage.py
│  │  └─ local_storage.py
│  │
│  ├─ observability/
│  │  ├─ __init__.py
│  │  ├─ logging.py
│  │  ├─ tracing.py
│  │  ├─ metrics.py
│  │  └─ request_context.py
│  │
│  └─ openapi/
│     ├─ __init__.py
│     ├─ schema.py
│     └─ export.py
│
└─ domains/
   ├─ __init__.py
   ├─ identity/
   ├─ master_data/
   ├─ inventory/
   ├─ sales/
   ├─ procurement/
   ├─ finance/
   ├─ workflow/
   ├─ reporting/
   ├─ files/
   ├─ ai/
   └─ integration/
```

每个领域目录应尽量采用：

```text
domains/<domain>/
├─ __init__.py
├─ api.py
├─ resources.py
├─ models.py
├─ schemas.py
├─ application/
│  ├─ __init__.py
│  ├─ use_cases.py
│  ├─ commands.py
│  ├─ queries.py
│  └─ dto.py
├─ domain/
│  ├─ __init__.py
│  ├─ entities.py
│  ├─ value_objects.py
│  ├─ events.py
│  ├─ policies.py
│  └─ exceptions.py
└─ infrastructure/
   ├─ __init__.py
   ├─ repository.py
   └─ mappers.py
```

### 3.1.3 Codex 执行任务

```text
[BE-001] 新建 backend/app/platform 与 backend/app/domains 目录。
[BE-002] 建立每个业务领域空模块。
[BE-003] 保留旧 api/models/services，先通过兼容导入避免破坏系统。
[BE-004] 逐步把 identity/inventory/sales/procurement/finance/workflow 迁移到 domains。
[BE-005] 每迁移一个领域，必须补充基本测试。
[BE-006] 不得在一次提交里同时迁移所有领域。
```

验收标准：

```text
1. 应用能启动。
2. 现有接口不破坏。
3. 至少 identity 和 inventory 有 domains 版本。
4. 新增领域模块具备 api/application/domain/infrastructure 四层雏形。
5. pytest 通过。
```

---

## 3.2 拆分 routes.py 与 RESOURCE_CONFIG

### 3.2.1 当前问题

当前后端存在一个过大的路由/资源配置文件，容易形成：

```text
1. 所有资源集中管理。
2. 所有模型、权限、搜索字段混在一起。
3. 新增业务必须改中央文件。
4. 文件越来越大，难维护。
```

### 3.2.2 目标设计

将大路由拆成：

```text
backend/app/api/
├─ __init__.py
├─ auth_routes.py
├─ health_routes.py
├─ profile_routes.py
├─ generic_crud_routes.py
├─ search_routes.py
└─ blueprints.py
```

将资源配置拆入领域：

```text
backend/app/domains/inventory/resources.py
backend/app/domains/sales/resources.py
backend/app/domains/procurement/resources.py
backend/app/domains/finance/resources.py
backend/app/domains/identity/resources.py
```

示例：

```python
# backend/app/domains/inventory/resources.py

from .models import Stock, StockMovement, Warehouse

inventory_resources = {
    "warehouses": {
        "model": Warehouse,
        "permission_prefix": "inventory.warehouse",
        "search_fields": ["name", "code", "location"],
        "default_sort": "-created_at",
    },
    "stock": {
        "model": Stock,
        "permission_prefix": "inventory.stock",
        "search_fields": ["product_name", "warehouse_name"],
        "default_sort": "-updated_at",
    },
    "stock-movements": {
        "model": StockMovement,
        "permission_prefix": "inventory.movement",
        "search_fields": ["source_type", "source_id"],
        "default_sort": "-created_at",
    },
}
```

统一注册：

```python
# backend/app/platform/crud/resource_registry.py

class ResourceRegistry:
    def __init__(self):
        self._resources = {}

    def register_many(self, resources: dict):
        for key, config in resources.items():
            if key in self._resources:
                raise ValueError(f"Duplicate resource key: {key}")
            self._resources[key] = config

    def get(self, key: str):
        return self._resources[key]

    def all(self):
        return self._resources.copy()
```

启动时注册：

```python
def register_resources(app):
    from app.platform.crud.resource_registry import registry
    from app.domains.inventory.resources import inventory_resources
    from app.domains.sales.resources import sales_resources
    from app.domains.procurement.resources import procurement_resources
    from app.domains.finance.resources import finance_resources
    from app.domains.identity.resources import identity_resources

    registry.register_many(identity_resources)
    registry.register_many(inventory_resources)
    registry.register_many(sales_resources)
    registry.register_many(procurement_resources)
    registry.register_many(finance_resources)
```

### 3.2.3 Codex 执行任务

```text
[BE-010] 找到现有 RESOURCE_CONFIG。
[BE-011] 按领域拆分资源配置。
[BE-012] 新建 ResourceRegistry。
[BE-013] generic CRUD 路由通过 registry 查资源配置。
[BE-014] 原接口 URL 保持兼容。
[BE-015] 给每个领域 resources.py 添加最少 1 个测试，验证资源 key 不重复。
```

验收标准：

```text
1. routes.py 行数明显下降。
2. 资源配置不再集中堆在 routes.py。
3. 所有原 REST 资源接口仍可访问。
4. 权限前缀仍能正确识别。
5. OpenAPI/前端合同检查不失败。
```

---

## 3.3 引入领域事件与 Outbox

### 3.3.1 当前问题

当前业务更像：

```text
HTTP 请求 → Flask API → Service → 直接改数据库
```

典型耦合：

```text
SalesService 直接改库存。
PurchaseService 直接影响库存。
FinanceService 直接依赖销售/应收状态。
通知、审计、报表可能同步混在业务请求里。
```

目标改为：

```text
HTTP 请求 → Application Use Case → Domain Event → Outbox → Worker → Event Handlers
```

### 3.3.2 事件类型设计

先定义核心业务事件：

```text
SalesOrderCreated
SalesOrderConfirmed
SalesOrderCancelled
InventoryReserved
InventoryReleased
InventoryDeducted
PurchaseOrderCreated
PurchaseOrderApproved
PurchaseGoodsReceived
QualityInspectionPassed
QualityInspectionFailed
ReceivableCreated
PaymentRecorded
StockBelowSafetyLine
StocktakeSubmitted
StocktakeApproved
WorkflowStarted
WorkflowTaskApproved
WorkflowTaskRejected
FileUploaded
ReportRequested
AiInsightRequested
```

### 3.3.3 Outbox 表

新增迁移：

```sql
CREATE TABLE domain_events (
    id UUID PRIMARY KEY,
    event_type VARCHAR(128) NOT NULL,
    aggregate_type VARCHAR(128) NOT NULL,
    aggregate_id VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    published_at TIMESTAMP NULL,
    trace_id VARCHAR(128),
    tenant_id VARCHAR(128),
    created_by VARCHAR(128)
);

CREATE INDEX idx_domain_events_status_created_at
ON domain_events(status, created_at);

CREATE INDEX idx_domain_events_type
ON domain_events(event_type);
```

SQLAlchemy 模型：

```python
class DomainEvent(db.Model):
    __tablename__ = "domain_events"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = db.Column(db.String(128), nullable=False)
    aggregate_type = db.Column(db.String(128), nullable=False)
    aggregate_id = db.Column(db.String(128), nullable=False)
    payload = db.Column(JSONB, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    trace_id = db.Column(db.String(128))
    tenant_id = db.Column(db.String(128))
    created_by = db.Column(db.String(128))
```

### 3.3.4 Event Bus 初版

```python
# backend/app/platform/events/event_bus.py

class EventBus:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, event_type: str, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event):
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
```

Outbox 添加：

```python
# backend/app/platform/events/outbox.py

class Outbox:
    def add(self, event_type, aggregate_type, aggregate_id, payload, *, tenant_id=None, created_by=None, trace_id=None):
        event = DomainEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload,
            tenant_id=tenant_id,
            created_by=created_by,
            trace_id=trace_id,
        )
        db.session.add(event)
        return event
```

### 3.3.5 订单确认链路改造

当前链路应从：

```text
销售订单确认 → 直接扣库存 → 直接生成应收 → 直接通知
```

改成：

```text
销售订单确认
    ↓
写 SalesOrderConfirmed 到 Outbox
    ↓
Worker 消费事件
    ↓
库存 handler 锁定/扣减库存
    ↓
财务 handler 生成应收
    ↓
通知 handler 发送通知
    ↓
报表 handler 更新 read model
```

### 3.3.6 Codex 执行任务

```text
[BE-020] 新建 domain_events 表与模型。
[BE-021] 新建 Outbox 服务。
[BE-022] 新建 EventBus 与 handler registry。
[BE-023] 新建 worker 命令，能消费 pending event。
[BE-024] 先改 SalesOrderConfirmed 一个事件链路。
[BE-025] 加测试：确认销售订单后，必须写入 domain_events。
[BE-026] 加测试：重复处理同一个事件不应重复扣库存。
```

验收标准：

```text
1. 确认订单仍能完成。
2. 确认订单后 domain_events 有 SalesOrderConfirmed。
3. Worker 能处理 pending 事件。
4. 失败事件 retry_count 增加，error_message 记录原因。
5. 事件处理具备幂等保护。
```

---

## 3.4 后台任务系统升级

### 3.4.1 需要异步化的任务

以下任务不得长期放在同步 API 中：

```text
1. 报表生成。
2. Excel/PDF 导出。
3. AI 经营分析。
4. 文件解析。
5. 通知发送。
6. 数据质量扫描。
7. 补货建议生成。
8. Cloudinary/Supabase Storage 文件后处理。
9. 事件 Outbox 派发。
10. 定时库存风险扫描。
```

### 3.4.2 技术选型

初期：

```text
Celery + Redis
```

中期：

```text
Celery + RabbitMQ
```

长期复杂流程：

```text
Temporal
```

### 3.4.3 新增依赖

```text
backend/requirements.txt 增加：
celery
```

可选：

```text
flower
```

### 3.4.4 目录

```text
backend/app/platform/jobs/
├─ celery_app.py
├─ worker.py
├─ schedules.py
└─ tasks/
   ├─ events.py
   ├─ reports.py
   ├─ notifications.py
   ├─ ai.py
   ├─ files.py
   └─ data_quality.py
```

### 3.4.5 Celery 配置示例

```python
# backend/app/platform/jobs/celery_app.py

from celery import Celery

celery_app = Celery(
    "nexus_prime",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
)
```

### 3.4.6 Codex 执行任务

```text
[BE-030] 添加 Celery 基础配置。
[BE-031] 添加 make/cmd 启动 worker 的命令。
[BE-032] 将报表生成任务改为异步。
[BE-033] 将 Outbox 事件处理改为异步 task。
[BE-034] 添加任务状态表 report_jobs 或 background_jobs。
[BE-035] 前端轮询或 SSE 展示任务进度。
```

验收标准：

```text
1. Redis 存在时 worker 能启动。
2. 报表请求立即返回 job_id。
3. 后台生成成功后状态变 success。
4. 失败后状态变 failed，记录 error_message。
5. pytest 覆盖成功和失败路径。
```

---

## 3.5 库存模型升级

### 3.5.1 当前问题

当前库存更偏：

```text
Stock 当前数量 + InventoryLog
```

这能跑通，但企业级 ERP 应采用：

```text
库存流水是事实
库存余额是结果
```

### 3.5.2 目标表设计

```text
stock_movements
├─ id
├─ tenant_id
├─ product_id
├─ warehouse_id
├─ direction
├─ quantity
├─ before_available_qty
├─ after_available_qty
├─ before_locked_qty
├─ after_locked_qty
├─ source_type
├─ source_id
├─ idempotency_key
├─ reason
├─ created_by
├─ created_at

stock_balances
├─ id
├─ tenant_id
├─ product_id
├─ warehouse_id
├─ available_qty
├─ locked_qty
├─ damaged_qty
├─ in_transit_qty
├─ version
├─ updated_at
```

### 3.5.3 库存操作 API

统一库存服务：

```python
class InventoryApplicationService:
    def reserve_stock(self, source_type, source_id, items, idempotency_key):
        ...

    def release_stock(self, source_type, source_id, items, idempotency_key):
        ...

    def deduct_stock(self, source_type, source_id, items, idempotency_key):
        ...

    def receive_stock(self, source_type, source_id, items, idempotency_key):
        ...

    def adjust_stock(self, product_id, warehouse_id, delta, reason, idempotency_key):
        ...
```

### 3.5.4 幂等要求

每个库存变动必须带：

```text
idempotency_key = source_type + source_id + operation + product_id + warehouse_id
```

如果同一个 key 已处理：

```text
直接返回已有结果，不重复扣减。
```

### 3.5.5 Codex 执行任务

```text
[BE-040] 新建 stock_movements 和 stock_balances。
[BE-041] 将现有 Stock/InventoryLog 映射到新模型。
[BE-042] 实现 reserve/release/deduct/receive/adjust。
[BE-043] 销售订单确认事件调用 reserve 或 deduct。
[BE-044] 采购到货事件调用 receive。
[BE-045] 添加并发测试：两个请求同时扣库存不能扣成负数。
[BE-046] 添加幂等测试：同一事件重复处理不会重复扣库存。
```

验收标准：

```text
1. 库存余额准确。
2. 每次变化都有流水。
3. 不允许库存负数，除非明确配置允许。
4. 重复事件不会重复扣减。
5. 盘点/调整能追溯原因和操作人。
```

---

## 3.6 权限系统升级

### 3.6.1 当前权限不足

已有 RBAC 基础，但不够企业级。

必须增加：

```text
1. 对象级授权。
2. 数据范围权限。
3. 字段权限。
4. 审批额度权限。
5. 导出权限。
6. AI 工具调用权限。
```

### 3.6.2 目标权限模型

```text
User
Role
Permission
Department
Position
DataScope
FieldPolicy
ApprovalLimit
Tenant
UserRole
RolePermission
```

### 3.6.3 policy.can 接口

统一授权入口：

```python
policy.can(
    user=current_user,
    action="finance.receivable.view",
    resource=receivable,
    context={
        "tenant_id": receivable.tenant_id,
        "department_id": receivable.department_id,
        "owner_id": receivable.owner_id,
        "amount": receivable.amount,
    },
)
```

禁止：

```text
1. 在 Controller 里到处手写 if user.role == "admin"。
2. 只检查登录，不检查对象归属。
3. 只检查 permission，不检查具体资源。
```

### 3.6.4 字段权限

字段权限例子：

```text
warehouse_user:
  can_view: product_name, sku, available_qty, warehouse_name
  cannot_view: cost_price, profit_margin

finance_user:
  can_view: cost_price, receivable_amount, payment_status
  can_export: finance fields

sales_user:
  can_view: customer_name, order_amount
  cannot_view: supplier_settlement_price
```

### 3.6.5 Codex 执行任务

```text
[BE-050] 新建 platform/policy。
[BE-051] 实现 policy.can 基础版本。
[BE-052] 为订单、应收、库存、文件增加对象级授权。
[BE-053] 新增 DataScope 表或配置。
[BE-054] 新增 FieldPolicy 配置。
[BE-055] generic CRUD 输出数据前应用字段过滤。
[BE-056] 导出接口应用字段权限。
[BE-057] AI 工具调用前应用 policy.can。
```

验收标准：

```text
1. 普通用户不能访问不属于自己数据范围的订单。
2. 仓库用户看不到成本和利润字段。
3. 没有导出权限的用户不能导出敏感数据。
4. 所有详情接口有对象级授权测试。
5. AI 不能绕过后端权限访问数据。
```

---

## 3.7 工作流中心升级

### 3.7.1 当前问题

采购、销售、财务状态流转可能分散在各业务服务中。

目标：

```text
审批流程独立，业务模块只发起流程，不写死流程节点。
```

### 3.7.2 目录

```text
backend/app/domains/workflow/
├─ api.py
├─ resources.py
├─ models.py
├─ application/
│  ├─ start_workflow.py
│  ├─ approve_task.py
│  ├─ reject_task.py
│  ├─ transfer_task.py
│  └─ query_todo_tasks.py
├─ domain/
│  ├─ workflow_definition.py
│  ├─ workflow_instance.py
│  ├─ workflow_task.py
│  ├─ transition.py
│  └─ events.py
└─ infrastructure/
   └─ repository.py
```

### 3.7.3 表设计

```text
workflow_definitions
workflow_nodes
workflow_edges
workflow_instances
workflow_tasks
workflow_actions
workflow_logs
```

### 3.7.4 API

```text
POST   /api/workflows/definitions
GET    /api/workflows/definitions
POST   /api/workflows/start
GET    /api/workflows/tasks/todo
POST   /api/workflows/tasks/{id}/approve
POST   /api/workflows/tasks/{id}/reject
POST   /api/workflows/tasks/{id}/transfer
GET    /api/workflows/instances/{id}
```

### 3.7.5 业务集成

采购单提交：

```python
workflow.start(
    process_key="purchase_order_approval",
    business_type="purchase_order",
    business_id=purchase_order.id,
    applicant_id=current_user.id,
    variables={
        "amount": purchase_order.total_amount,
        "department_id": purchase_order.department_id,
    },
)
```

审批完成后发布事件：

```text
WorkflowCompleted
PurchaseOrderApproved
```

### 3.7.6 Codex 执行任务

```text
[BE-060] 建立 workflow 领域目录。
[BE-061] 新增 workflow 基础表。
[BE-062] 实现 start/approve/reject/todo。
[BE-063] 采购审批迁移到 workflow。
[BE-064] 销售超额折扣审批迁移到 workflow。
[BE-065] 财务付款审批迁移到 workflow。
[BE-066] 前端任务中心接入 todo tasks。
```

验收标准：

```text
1. 采购单能发起审批。
2. 审批人能看到待办。
3. 审批通过后采购单状态改变。
4. 驳回后采购单状态正确。
5. 审批日志完整记录。
```

---

## 3.8 报表与分析数据升级

### 3.8.1 目标

不要让复杂报表直接压主交易表。

阶段路线：

```text
阶段 1：PostgreSQL View / Materialized View
阶段 2：Reporting Read Model
阶段 3：ClickHouse / Doris / StarRocks
```

### 3.8.2 Read Model

```text
report_sales_daily
report_inventory_turnover
report_supplier_performance
report_receivable_aging
report_procurement_cycle
report_quality_failure_rate
```

### 3.8.3 Codex 执行任务

```text
[BE-070] 新建 reporting 领域。
[BE-071] 将首页 KPI 从实时复杂查询改为 read model。
[BE-072] Outbox 事件更新 reporting read models。
[BE-073] 报表生成改为 Celery 异步任务。
[BE-074] 添加报表任务状态 API。
```

验收标准：

```text
1. 首页 KPI 查询时间稳定。
2. 报表生成不阻塞 API。
3. 报表任务可查询状态。
4. read model 更新失败可重试。
```

---

## 4. 前端技术栈升级计划

## 4.1 前端目标形态

当前主栈保留：

```text
Angular + PrimeNG + ECharts
```

升级为：

```text
Angular 企业级业务前端
+ Motion Design System
+ GSAP / Three.js / Rive / dotLottie
+ TanStack Query Angular
+ NgRx SignalStore
+ OpenAPI Typed Client
+ Optional ReactBits Islands
```

### 4.1.1 不建议全量迁移 React

原因：

```text
1. 当前页面多，业务复杂。
2. Angular + PrimeNG 更适合 ERP 大量表格表单。
3. ReactBits 是 React 动效组件集合，不适合直接替换全部业务页面。
4. 全量迁移会打断功能。
```

推荐策略：

```text
业务系统继续 Angular。
ReactBits 作为视觉参考。
少量核心视觉页可用 ReactBits Islands。
```

---

## 4.2 前端依赖升级

### 4.2.1 推荐新增依赖

```bash
cd frontend

npm install @tanstack/angular-query
npm install @ngrx/signals
npm install gsap three @lottiefiles/dotlottie-web @rive-app/canvas
npm install -D @types/three openapi-typescript
```

可选 ReactBits Islands：

```bash
npm install react react-dom
npm install -D @vitejs/plugin-react typescript
```

### 4.2.2 Angular 升级

```bash
ng update @angular/core @angular/cli
ng update @angular/cdk
```

升级后优先使用：

```text
1. Signals。
2. 新控制流 @if/@for/@switch。
3. Deferrable Views。
4. Route View Transitions。
5. Standalone Components。
```

---

## 4.3 前端目录升级

### 4.3.1 目标目录

```text
frontend/src/app
├─ app.config.ts
├─ app.routes.ts
├─ shell/
│  ├─ app-shell.component.ts
│  ├─ sidebar/
│  ├─ topbar/
│  ├─ command-palette/
│  ├─ dock/
│  └─ layout-state.service.ts
│
├─ core/
│  ├─ api/
│  │  ├─ api-client.ts
│  │  ├─ generated/
│  │  └─ api-error.ts
│  ├─ auth/
│  ├─ http/
│  ├─ config/
│  ├─ realtime/
│  ├─ motion/
│  │  ├─ motion-preference.service.ts
│  │  ├─ reveal.directive.ts
│  │  ├─ spotlight.directive.ts
│  │  ├─ magnetic.directive.ts
│  │  ├─ count-up.directive.ts
│  │  ├─ parallax.directive.ts
│  │  └─ route-transition.ts
│  └─ theme/
│
├─ shared/
│  ├─ ui/
│  │  ├─ scene-background/
│  │  ├─ glass-card/
│  │  ├─ metric-card/
│  │  ├─ bento-grid/
│  │  ├─ workflow-stepper/
│  │  └─ empty-state/
│  ├─ pipes/
│  ├─ directives/
│  └─ utils/
│
└─ features/
   ├─ dashboard/
   ├─ inventory/
   ├─ procurement/
   ├─ sales/
   ├─ finance/
   ├─ workflow/
   ├─ reporting/
   ├─ ai/
   ├─ identity/
   ├─ files/
   └─ integration/
```

### 4.3.2 Codex 执行任务

```text
[FE-001] 新建 core/motion。
[FE-002] 新建 shared/ui。
[FE-003] 将 pages 按 features 逐步迁移。
[FE-004] 保留旧路由兼容。
[FE-005] 每迁移一个 feature，添加 feature routes。
```

验收标准：

```text
1. 原有页面仍能访问。
2. 新页面从 features 注册。
3. 公共 UI 不再散落在业务目录。
4. 动效指令统一从 core/motion 引入。
```

---

## 4.4 Motion Design System

### 4.4.1 样式目录

```text
frontend/src/styles/
├─ tokens/
│  ├─ _color.scss
│  ├─ _motion.scss
│  ├─ _shadow.scss
│  ├─ _radius.scss
│  ├─ _z-index.scss
│  └─ _typography.scss
│
├─ effects/
│  ├─ _aurora.scss
│  ├─ _glass.scss
│  ├─ _spotlight.scss
│  ├─ _video-bg.scss
│  ├─ _scanline.scss
│  ├─ _flow-line.scss
│  ├─ _noise.scss
│  └─ _particles.scss
│
├─ components/
│  ├─ _command-card.scss
│  ├─ _metric-card.scss
│  ├─ _dock.scss
│  ├─ _bento.scss
│  ├─ _workflow-stepper.scss
│  └─ _data-table-polish.scss
│
└─ index.scss
```

`src/styles.scss`：

```scss
@use './styles/tokens/color';
@use './styles/tokens/motion';
@use './styles/tokens/shadow';
@use './styles/effects/aurora';
@use './styles/effects/glass';
@use './styles/effects/spotlight';
@use './styles/effects/video-bg';
@use './styles/effects/flow-line';
@use './styles/components/metric-card';
@use './styles/components/dock';
@use './styles/components/workflow-stepper';
```

### 4.4.2 Design Tokens

示例：

```scss
:root {
  --nexus-bg: #020617;
  --nexus-panel: rgba(15, 23, 42, 0.72);
  --nexus-panel-soft: rgba(15, 23, 42, 0.48);
  --nexus-border: rgba(148, 163, 184, 0.20);
  --nexus-cyan: #22d3ee;
  --nexus-blue: #3b82f6;
  --nexus-violet: #6366f1;
  --nexus-green: #10b981;
  --nexus-red: #ef4444;

  --motion-fast: 160ms;
  --motion-normal: 260ms;
  --motion-slow: 420ms;
  --motion-spring: cubic-bezier(.2, .8, .2, 1);

  --radius-card: 24px;
  --radius-panel: 32px;
  --shadow-glow-cyan: 0 0 40px rgba(34, 211, 238, .25);
}
```

---

## 4.5 高级背景组件

### 4.5.1 SceneBackgroundComponent

```text
路径：
frontend/src/app/shared/ui/scene-background/
```

功能：

```text
1. 支持视频背景。
2. 支持 poster。
3. 支持 Aurora 层。
4. 支持网格层。
5. 支持 noise 层。
6. 支持暗角。
7. 支持 reduced-motion 降级。
```

组件 API：

```ts
@Input() videoSrc = '';
@Input() mp4Src = '';
@Input() poster = '';
@Input() intensity: 'soft' | 'normal' | 'strong' = 'normal';
@Input() showGrid = true;
@Input() showNoise = true;
```

HTML：

```html
<div class="nexus-scene-bg" [class.with-video]="videoSrc || mp4Src">
  @if (videoSrc || mp4Src) {
    <video autoplay muted loop playsinline preload="metadata" [poster]="poster">
      @if (videoSrc) {
        <source [src]="videoSrc" type="video/webm" />
      }
      @if (mp4Src) {
        <source [src]="mp4Src" type="video/mp4" />
      }
    </video>
  }

  <div class="nexus-bg-aurora"></div>
  @if (showGrid) {
    <div class="nexus-bg-grid"></div>
  }
  <div class="nexus-bg-vignette"></div>
  @if (showNoise) {
    <div class="nexus-bg-noise"></div>
  }
</div>
```

验收标准：

```text
1. 登录页可使用视频背景。
2. 移动端可隐藏视频，仅保留 poster + aurora。
3. prefers-reduced-motion 时禁用动态背景。
4. 背景层 pointer-events: none。
```

---

## 4.6 ReactBits 应用策略

### 4.6.1 三种模式

```text
模式 A：Angular 移植 ReactBits 效果
模式 B：ReactBits Islands
模式 C：全量 React 重构
```

采用：

```text
主方案：模式 A
辅助方案：模式 B
禁止当前阶段采用：模式 C
```

### 4.6.2 ReactBits 效果映射

```text
ReactBits Aurora
→ Angular SceneBackground / Aurora Effect

ReactBits Hyperspeed
→ 登录页或 AI 分析页 ReactBits Island，或 OGL/Three.js 复刻

ReactBits Spotlight Card
→ Angular nexusSpotlight Directive

ReactBits Dock
→ Angular Shell Dock

ReactBits Magic Bento
→ Dashboard Bento Grid

ReactBits Text Reveal / Blur Text
→ GSAP Text Reveal Directive

ReactBits Animated List
→ Notifications / Tasks Stagger List

ReactBits Particles
→ Canvas Particle Background

ReactBits Orb / 3D Effects
→ AI 页面 / 设备维护 / 产能规划 Three.js 视觉
```

### 4.6.3 Optional ReactBits Islands 结构

```text
frontend/reactbits-islands/
├─ package.json
├─ vite.config.ts
├─ tsconfig.json
└─ src/
   ├─ main.tsx
   ├─ islands/
   │  ├─ NexusHeroIsland.tsx
   │  ├─ NexusHyperspeedIsland.tsx
   │  ├─ NexusAuroraIsland.tsx
   │  └─ NexusDockIsland.tsx
   └─ mount.ts
```

构建后输出：

```text
frontend/src/assets/reactbits-islands/
├─ nexus-hero.js
├─ nexus-hyperspeed.js
└─ nexus-dock.js
```

Angular 宿主组件：

```html
<div id="nexus-reactbits-hero"></div>
```

生命周期：

```ts
ngAfterViewInit() {
  (window as any).NexusHeroIsland?.mount('#nexus-reactbits-hero', {
    title: 'NEXUS PRIME',
  });
}

ngOnDestroy() {
  (window as any).NexusHeroIsland?.unmount('#nexus-reactbits-hero');
}
```

验收标准：

```text
1. React island 不影响 Angular 路由。
2. React island 可独立构建。
3. React island 失败时页面仍可用。
4. 不在普通业务表单页使用 React island。
```

---

## 4.7 页面视觉升级计划

### 4.7.1 登录页

目标风格：

```text
工业智能系统入口
全屏视频背景
Aurora 流光
网格 + Noise
玻璃登录卡
标题逐字显现
能力浮动卡片
磁吸登录按钮
```

任务：

```text
[FE-020] 重做 login 页面结构。
[FE-021] 接入 SceneBackgroundComponent。
[FE-022] 登录卡改为 GlassCard。
[FE-023] 标题使用 reveal 动效。
[FE-024] 登录按钮加入 magnetic/spotlight 效果。
[FE-025] 移动端禁用视频背景。
```

验收：

```text
1. 登录功能不变。
2. CSRF / Cookie 流程不破坏。
3. 首屏加载不超过合理体积。
4. 视频不可用时 poster 正常显示。
```

### 4.7.2 运营首页 / Dashboard

目标：

```text
制造经营指挥中心
实时 KPI
Bento Grid
Spotlight Cards
AI 风险雷达
动态仓库网络
任务流
业务流程线
```

任务：

```text
[FE-030] 新建 dashboard feature。
[FE-031] MetricCard 加 count-up。
[FE-032] KPI 卡加 spotlight。
[FE-033] 建 BentoGrid 组件。
[FE-034] 加业务流程 SVG 流光线。
[FE-035] 接入 dashboard API 或 mock fallback。
[FE-036] 图表加进入动画。
```

验收：

```text
1. Dashboard 可加载真实数据。
2. 无数据时有高级 empty state。
3. 动效不会阻塞交互。
4. E2E 覆盖 Dashboard 渲染。
```

### 4.7.3 仓库 / 库存页面

目标：

```text
动态仓库网络
库存节点发光
低库存红色脉冲
调拨线流动
表格 + 网络视图切换
```

任务：

```text
[FE-040] 新增 warehouse-network 组件。
[FE-041] 支持 SVG flow-line。
[FE-042] 低库存节点 pulse。
[FE-043] 节点点击展开库存详情。
[FE-044] 表格与图谱共用 TanStack Query 数据。
```

验收：

```text
1. 网络图可展示仓库和库存状态。
2. 点击节点能跳详情。
3. 大量节点时不卡顿。
4. reduced-motion 下禁用流光动画。
```

### 4.7.4 采购/销售/财务流程页

目标：

```text
流程阶段可视化
当前节点发光
已完成节点扫描动效
异常节点脉冲
审批任务抽屉
```

任务：

```text
[FE-050] 新建 WorkflowStepper。
[FE-051] 采购单详情接入 WorkflowStepper。
[FE-052] 销售单详情接入 WorkflowStepper。
[FE-053] 应收/付款详情接入 WorkflowStepper。
[FE-054] 审批操作弹窗统一化。
```

验收：

```text
1. 状态与后端一致。
2. 审批通过/驳回后 UI 实时更新。
3. 失败提示明确。
4. 流程日志可查看。
```

### 4.7.5 AI 分析台

目标：

```text
AI 经营驾驶舱
流式输出
RAG 引用卡片
工具调用轨迹
风险解释
经营建议草稿
```

任务：

```text
[FE-060] 新建 ai feature。
[FE-061] AI 聊天支持 SSE 流式输出。
[FE-062] 工具调用过程可视化。
[FE-063] AI 结果必须展示“仅供建议，需要人工确认”。
[FE-064] 高风险操作需二次确认。
```

验收：

```text
1. AI 输出可流式显示。
2. 用户能看到 AI 使用了哪些数据/工具。
3. AI 不能直接提交核心业务操作。
4. 权限不足时 AI 返回拒绝说明。
```

---

## 4.8 前端状态与数据层升级

### 4.8.1 API Client

目标：

```text
不要让业务组件直接拼 URL。
```

结构：

```text
core/api/
├─ api-client.ts
├─ generated/
├─ domain-clients/
│  ├─ sales-api.ts
│  ├─ inventory-api.ts
│  ├─ procurement-api.ts
│  ├─ finance-api.ts
│  ├─ workflow-api.ts
│  └─ ai-api.ts
└─ api-error.ts
```

### 4.8.2 TanStack Query

使用场景：

```text
1. 列表。
2. 详情。
3. Dashboard KPI。
4. 通知。
5. 审批任务。
6. 报表任务状态。
```

禁止：

```text
1. 每个组件自己重复写 loading/error/retry。
2. 提交后手动乱刷新。
```

### 4.8.3 SignalStore

使用场景：

```text
1. 页面筛选条件。
2. 表格列配置。
3. 当前选中仓库。
4. 当前工作台布局。
5. 当前流程视图模式。
```

任务：

```text
[FE-070] 新建 TanStack Query provider。
[FE-071] 新建 domain API service。
[FE-072] inventory 列表迁移到 TanStack Query。
[FE-073] procurement 列表迁移到 TanStack Query。
[FE-074] dashboard 迁移到 TanStack Query。
[FE-075] 建立 workbench SignalStore。
```

验收：

```text
1. 列表返回页后保留缓存。
2. 新增/更新后相关 query 自动 invalidation。
3. loading/error 状态统一。
4. SignalStore 不存接口数据，只存交互状态。
```

---

## 4.9 实时能力

### 4.9.1 目标实时场景

```text
1. 新审批任务。
2. 库存风险预警。
3. 报表生成进度。
4. AI 流式输出。
5. 通知中心。
6. 仓库任务状态。
```

### 4.9.2 技术选型

初期：

```text
SSE
```

中期：

```text
WebSocket
```

如果使用 Supabase：

```text
Supabase Realtime
```

### 4.9.3 前端目录

```text
frontend/src/app/core/realtime/
├─ realtime.service.ts
├─ sse.service.ts
├─ websocket.service.ts
└─ realtime-events.ts
```

### 4.9.4 任务

```text
[FE-080] 新建 realtime service。
[FE-081] 报表任务进度接入 SSE。
[FE-082] 通知中心接入 SSE/WebSocket。
[FE-083] AI 输出接入 SSE。
```

验收：

```text
1. 断线可重连。
2. 重连后不会重复插入消息。
3. 权限不足不能订阅对应频道。
4. 页面销毁时关闭连接。
```

---

## 5. 数据库与数据平台升级

## 5.1 PostgreSQL 正式化

### 5.1.1 目标

从本地 SQLite 演示模式升级为：

```text
PostgreSQL 作为正式主交易库
```

### 5.1.2 必须补齐

```text
1. 外键约束。
2. 唯一约束。
3. 索引。
4. version 乐观锁。
5. created_at / updated_at。
6. tenant_id 预留。
7. soft delete 可选。
8. JSONB 用于事件 payload 和灵活配置。
```

### 5.1.3 任务

```text
[DB-001] 检查所有模型字段类型是否兼容 PostgreSQL。
[DB-002] 清理 SQLite 专用逻辑。
[DB-003] 增加 PostgreSQL 专用迁移。
[DB-004] 添加关键索引。
[DB-005] 添加 docker-compose postgres。
[DB-006] CI 中跑迁移测试。
```

验收：

```text
1. 本地 docker compose 可启动 PostgreSQL。
2. flask db upgrade 成功。
3. 所有测试基于 PostgreSQL 跑通。
4. 核心列表查询有索引。
```

---

## 5.2 Redis 使用规范

Redis 用途：

```text
1. Session/登录限流。
2. 缓存。
3. Celery broker。
4. 分布式锁。
5. 短期实时状态。
```

禁止：

```text
1. 把核心业务事实只存在 Redis。
2. 不设置 TTL 的无界缓存。
3. 缓存不考虑 tenant_id。
```

任务：

```text
[DB-010] 统一 Redis key 命名。
[DB-011] 登录限流接入 Redis。
[DB-012] 报表任务进度可选写 Redis。
[DB-013] 库存关键操作使用 PostgreSQL 锁为主，Redis 锁为辅。
```

---

## 5.3 对象存储

可选实现：

```text
Cloudinary
Supabase Storage
MinIO
Local Storage for dev
```

统一接口：

```python
class StorageService:
    def upload(self, file, *, path, content_type, metadata): ...
    def get_signed_url(self, object_key, expires_in): ...
    def delete(self, object_key): ...
```

任务：

```text
[DB-020] 抽象 StorageService。
[DB-021] 文件表只存 object_key，不依赖具体供应商 URL。
[DB-022] 上传后发布 FileUploaded 事件。
[DB-023] 文件访问做对象级授权。
```

---

## 5.4 搜索升级

初期：

```text
PostgreSQL full text search
```

中期：

```text
Meilisearch / OpenSearch
```

搜索对象：

```text
产品
客户
供应商
订单
采购单
库存流水
文件
审计日志
```

任务：

```text
[DB-030] 新建 search 领域或 platform/search。
[DB-031] 统一 SearchService。
[DB-032] 先支持 PostgreSQL 搜索。
[DB-033] 后续可替换 OpenSearch/Meilisearch。
```

---

## 5.5 AI 向量库

推荐：

```text
pgvector
```

向量对象：

```text
制度文档
合同
质检报告
采购说明
供应商资料
销售记录
报表归档
```

任务：

```text
[AI-DB-001] 新建 document_chunks。
[AI-DB-002] 新建 embedding 字段。
[AI-DB-003] 文件上传后异步切片和 embedding。
[AI-DB-004] AI 问答接入检索。
```

---

## 6. AI 能力升级

## 6.1 AI 架构

目标：

```text
AI Gateway
├─ Model Provider Adapter
├─ Prompt Templates
├─ RAG Retrieval
├─ Tool Calling
├─ Agent Workflow
├─ Permission Guard
├─ Human Confirmation
├─ Audit Log
└─ Cost Tracking
```

### 6.1.1 目录

```text
backend/app/domains/ai/
├─ api.py
├─ models.py
├─ application/
│  ├─ chat.py
│  ├─ analyze_business.py
│  ├─ generate_replenishment_suggestion.py
│  ├─ rag_answer.py
│  └─ tool_runner.py
├─ domain/
│  ├─ prompts.py
│  ├─ tools.py
│  ├─ guardrails.py
│  └─ events.py
└─ infrastructure/
   ├─ openai_provider.py
   ├─ embedding_provider.py
   └─ vector_repository.py
```

### 6.1.2 AI 使用边界

AI 可以：

```text
1. 查询经营数据。
2. 总结风险。
3. 解释异常。
4. 生成采购建议草稿。
5. 生成报表解读。
6. 生成审批意见草稿。
7. 从文件中回答问题。
```

AI 不可以：

```text
1. 绕过权限读取数据。
2. 自动创建采购单并提交审批。
3. 自动修改库存。
4. 自动记录付款。
5. 自动删除数据。
6. 自动导出敏感字段。
```

关键动作必须：

```text
权限校验 + 人工确认 + 审计日志。
```

### 6.1.3 AI 工具调用

工具示例：

```text
query_sales_orders
query_inventory_balance
query_receivables
query_purchase_orders
generate_replenishment_draft
create_report_job
search_documents
```

工具调用前：

```python
policy.can(user, action="ai.tool.query_inventory_balance", context=...)
```

### 6.1.4 任务

```text
[AI-001] 新建 AI Gateway。
[AI-002] 抽象 ModelProvider。
[AI-003] 增加 Prompt 模板目录。
[AI-004] AI chat 支持 SSE。
[AI-005] AI 工具调用接入 policy.can。
[AI-006] AI 调用记录审计日志。
[AI-007] RAG 接入 document_chunks。
[AI-008] AI 建议生成后只保存为 draft，不直接执行。
```

验收：

```text
1. AI 无权限不能访问数据。
2. AI 输出能流式展示。
3. AI 工具调用有审计。
4. AI 生成采购建议只是草稿。
5. 用户确认后才进入正式业务流程。
```

---

## 7. DevOps 与工程体系升级

## 7.1 Docker Compose

### 7.1.1 目标服务

```text
frontend
backend
postgres
redis
worker
optional minio
optional meilisearch
```

### 7.1.2 文件

```text
Dockerfile.backend
Dockerfile.frontend
docker-compose.yml
.env.example
Makefile
```

### 7.1.3 Makefile

```makefile
dev:
	docker compose up -d

logs:
	docker compose logs -f

test-backend:
	docker compose exec backend pytest

test-frontend:
	docker compose exec frontend npm test

migrate:
	docker compose exec backend flask db upgrade

worker:
	docker compose exec worker celery -A app.platform.jobs.celery_app worker -l info
```

任务：

```text
[OPS-001] 新建 Dockerfile.backend。
[OPS-002] 新建 Dockerfile.frontend。
[OPS-003] 新建 docker-compose.yml。
[OPS-004] 新建 .env.example。
[OPS-005] 新建 Makefile。
```

验收：

```text
1. docker compose up 可启动基础环境。
2. backend 能连接 postgres/redis。
3. worker 能启动。
4. frontend 能访问 backend API。
```

---

## 7.2 CI/CD

GitHub Actions 阶段：

```text
Frontend:
1. npm ci
2. npm run lint
3. npm run test
4. npm run build
5. npx playwright test

Backend:
1. pip install
2. ruff
3. pytest
4. flask db upgrade test
5. OpenAPI export

Security:
1. npm audit
2. pip-audit
3. secret scan
4. dependency review
```

任务：

```text
[OPS-010] 新建 .github/workflows/frontend.yml。
[OPS-011] 新建 .github/workflows/backend.yml。
[OPS-012] 新建 .github/workflows/e2e.yml。
[OPS-013] CI 上传测试报告。
[OPS-014] CI 失败禁止合并。
```

---

## 7.3 OpenAPI 合同

### 7.3.1 目标

后端导出：

```text
backend/openapi.json
```

前端生成：

```text
frontend/src/app/core/api/generated/
```

命令：

```bash
npm run api:generate
```

### 7.3.2 任务

```text
[OPS-020] 后端添加 OpenAPI export 命令。
[OPS-021] 前端接入 openapi-typescript。
[OPS-022] CI 检查 OpenAPI 文件是否同步。
[OPS-023] 逐步替换 any 类型 API。
```

验收：

```text
1. 后端 schema 能导出。
2. 前端类型能生成。
3. API 字段变化会导致类型检查失败。
```

---

## 7.4 可观测性

### 7.4.1 日志

结构化日志字段：

```text
timestamp
level
trace_id
request_id
tenant_id
user_id
method
path
status_code
duration_ms
operation
error_code
```

### 7.4.2 指标

```text
http_request_duration_seconds
http_request_total
celery_task_duration_seconds
celery_task_failed_total
domain_event_pending_total
domain_event_failed_total
db_query_slow_total
```

### 7.4.3 链路追踪

后端：

```text
OpenTelemetry Flask instrumentation
SQLAlchemy instrumentation
Redis instrumentation
Celery instrumentation
```

前端：

```text
Sentry or OpenTelemetry web
```

任务：

```text
[OPS-030] 新建 platform/observability。
[OPS-031] 请求中间件生成 request_id/trace_id。
[OPS-032] 后端结构化日志。
[OPS-033] 添加 Sentry 前端异常监控。
[OPS-034] 添加 OpenTelemetry 基础 tracing。
[OPS-035] 添加 domain event pending 指标。
```

验收：

```text
1. 每个请求有 trace_id。
2. 错误日志包含用户、租户、路径、操作。
3. 慢接口可定位。
4. worker 失败任务可追踪。
```

---

## 8. 测试升级

## 8.1 后端测试

必须新增测试类型：

```text
1. Domain use case tests。
2. API integration tests。
3. Permission tests。
4. Object authorization tests。
5. Inventory concurrency tests。
6. Idempotency tests。
7. Outbox event tests。
8. Workflow tests。
9. Report job tests。
10. AI guardrail tests。
```

目录：

```text
backend/tests/
├─ unit/
├─ integration/
├─ permissions/
├─ workflows/
├─ inventory/
├─ events/
├─ ai/
└─ conftest.py
```

关键测试：

```text
[TEST-BE-001] 普通用户不能看别人订单。
[TEST-BE-002] 仓库用户不能看成本字段。
[TEST-BE-003] 销售订单确认会写 SalesOrderConfirmed。
[TEST-BE-004] 重复事件不重复扣库存。
[TEST-BE-005] 并发扣库存不出现负数。
[TEST-BE-006] 采购审批通过后状态正确。
[TEST-BE-007] AI 无权限不能查询财务数据。
```

---

## 8.2 前端测试

### 8.2.1 Vitest / Unit

测试：

```text
1. motion directives。
2. API client。
3. stores。
4. formatters。
5. permission UI guards。
```

### 8.2.2 Playwright E2E

业务流：

```text
1. 登录。
2. 创建采购单。
3. 审批采购单。
4. 采购收货。
5. 库存增加。
6. 创建销售单。
7. 确认销售单。
8. 库存扣减。
9. 生成应收。
10. 记录收款。
11. 查看报表。
12. AI 分析。
```

前端体验测试：

```text
1. 登录页视频背景 fallback。
2. Dashboard 渲染。
3. reduced-motion 生效。
4. 权限不足按钮不显示。
5. API 错误显示统一。
```

---

## 9. 分阶段执行路线

## Phase 0：基线检查

目标：

```text
保证当前项目可运行、可测试、可回滚。
```

任务：

```text
[P0-001] 跑前端 build。
[P0-002] 跑后端 pytest。
[P0-003] 记录当前 API 列表。
[P0-004] 记录当前前端路由。
[P0-005] 创建 upgrade 分支。
[P0-006] 创建 docs/architecture-current.md。
```

交付物：

```text
docs/architecture-current.md
docs/api-current.md
docs/frontend-routes-current.md
```

---

## Phase 1：后端结构化重构

目标：

```text
建立 domains/platform 结构，但不破坏业务。
```

任务：

```text
[P1-001] 新建 platform/domains。
[P1-002] 拆 routes.py。
[P1-003] 拆 RESOURCE_CONFIG。
[P1-004] identity 领域迁移。
[P1-005] inventory 领域迁移。
[P1-006] 测试通过。
```

验收：

```text
1. 应用启动。
2. 核心接口不变。
3. routes.py 显著变小。
4. resource config 按领域分散。
```

---

## Phase 2：事件驱动与异步任务

目标：

```text
建立 Outbox + Worker，先改销售订单确认链路。
```

任务：

```text
[P2-001] domain_events 表。
[P2-002] Outbox。
[P2-003] EventBus。
[P2-004] Celery worker。
[P2-005] SalesOrderConfirmed 链路。
[P2-006] 报表任务异步化。
```

验收：

```text
1. 事件可写入。
2. worker 可消费。
3. 失败可重试。
4. 销售订单确认链路可用。
```

---

## Phase 3：库存、权限、工作流企业化

目标：

```text
让 ERP 核心业务具备企业级可靠性。
```

任务：

```text
[P3-001] stock_movements / stock_balances。
[P3-002] 库存幂等。
[P3-003] 并发扣减。
[P3-004] policy.can。
[P3-005] 对象级授权。
[P3-006] 字段权限。
[P3-007] Workflow Center。
[P3-008] 采购审批迁移。
```

验收：

```text
1. 库存可追溯。
2. 权限测试通过。
3. 工作流独立运行。
4. 采购审批不再写死。
```

---

## Phase 4：前端视觉与体验升级

目标：

```text
将前端从普通后台升级为高级工业智能指挥中心。
```

任务：

```text
[P4-001] Motion Design System。
[P4-002] SceneBackground。
[P4-003] Spotlight Directive。
[P4-004] Route View Transition。
[P4-005] 登录页重做。
[P4-006] Dashboard 重做。
[P4-007] 仓库网络图。
[P4-008] WorkflowStepper。
[P4-009] AI 分析台初版。
```

验收：

```text
1. 页面高级感明显提升。
2. 动效可降级。
3. 业务功能不受影响。
4. 移动端可用。
```

---

## Phase 5：前端数据层升级

目标：

```text
让 API 状态、缓存、刷新、错误处理统一。
```

任务：

```text
[P5-001] TanStack Query provider。
[P5-002] domain API services。
[P5-003] inventory/procurement/sales 列表迁移。
[P5-004] SignalStore 管页面状态。
[P5-005] OpenAPI typed client。
```

验收：

```text
1. 列表缓存正常。
2. 更新后自动刷新。
3. 类型安全增强。
4. any 减少。
```

---

## Phase 6：AI 与数据平台

目标：

```text
AI 能安全分析企业经营数据。
```

任务：

```text
[P6-001] AI Gateway。
[P6-002] SSE 流式输出。
[P6-003] AI 工具调用权限。
[P6-004] document_chunks。
[P6-005] pgvector。
[P6-006] RAG 问答。
[P6-007] AI 审计。
```

验收：

```text
1. AI 可回答文档问题。
2. AI 可分析库存/销售/应收风险。
3. AI 不绕过权限。
4. AI 建议必须人工确认。
```

---

## Phase 7：DevOps 与可观测性

目标：

```text
项目具备生产部署与问题定位能力。
```

任务：

```text
[P7-001] Docker Compose。
[P7-002] GitHub Actions。
[P7-003] OpenAPI 合同检查。
[P7-004] OpenTelemetry。
[P7-005] Sentry。
[P7-006] Prometheus/Grafana 可选。
```

验收：

```text
1. 一键启动。
2. CI 自动测试。
3. 错误可定位。
4. 慢接口可观察。
```

---

## 10. Codex 执行规范

### 10.1 每次任务必须遵守

```text
1. 先读 PLAN.md。
2. 先查看当前文件再修改。
3. 不要假设不存在的文件结构。
4. 小步提交。
5. 每次只完成一个任务组。
6. 保持原 API 兼容，除非任务明确要求改。
7. 修改后运行相关测试。
8. 新增功能必须新增测试。
9. 涉及权限必须加负向测试。
10. 涉及库存必须加幂等/并发测试。
```

### 10.2 禁止行为

```text
1. 不要删除大批现有代码后重写。
2. 不要绕过测试。
3. 不要在前端硬编码权限绕过后端。
4. 不要让 AI 接口直接修改核心业务数据。
5. 不要把敏感信息写入前端。
6. 不要把业务事实只存 Redis。
7. 不要把动效写得无法关闭。
8. 不要在普通 CRUD 页堆大量 WebGL。
```

### 10.3 每个任务完成后输出

Codex 完成任务后必须输出：

```text
1. 修改文件列表。
2. 新增文件列表。
3. 删除文件列表。
4. 数据库迁移说明。
5. 新增环境变量。
6. 测试命令和结果。
7. 兼容性影响。
8. 下一步建议。
```

---

## 11. 推荐环境变量

```env
# App
FLASK_ENV=development
SECRET_KEY=change-me
FRONTEND_ORIGIN=http://localhost:4200

# Database
DATABASE_URL=postgresql+psycopg2://nexus:nexus@localhost:5432/nexus_prime

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Storage
STORAGE_PROVIDER=local
CLOUDINARY_URL=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# AI
OPENAI_API_KEY=
AI_PROVIDER=openai
AI_ENABLE_TOOLS=true

# Security
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
PASSWORD_MIN_LENGTH=8

# Observability
SENTRY_DSN=
OTEL_EXPORTER_OTLP_ENDPOINT=
LOG_LEVEL=INFO
```

---

## 12. 关键验收清单

### 12.1 架构验收

```text
[ ] domains/platform 结构建立。
[ ] routes.py 不再是上帝文件。
[ ] RESOURCE_CONFIG 按领域拆分。
[ ] 至少 sales/inventory/procurement/finance/workflow 有领域模块。
[ ] 领域之间不再随意直接改对方表。
```

### 12.2 后端验收

```text
[ ] Outbox 可写入和消费。
[ ] Celery worker 可运行。
[ ] 销售订单确认通过事件影响库存/财务。
[ ] 库存流水完整。
[ ] 幂等测试通过。
[ ] 权限测试通过。
[ ] 工作流中心可处理采购审批。
```

### 12.3 前端验收

```text
[ ] Motion Design System 建立。
[ ] 登录页有视频/Aurora/玻璃态高级视觉。
[ ] Dashboard 有 Bento、Spotlight、数字滚动、业务流线。
[ ] 仓库页面有网络图或流向图。
[ ] 流程详情页有 WorkflowStepper。
[ ] 动效可通过 prefers-reduced-motion 降级。
[ ] TanStack Query 接入核心列表。
```

### 12.4 数据验收

```text
[ ] PostgreSQL 本地环境可启动。
[ ] 迁移可重复执行。
[ ] 关键表有索引。
[ ] 报表 read model 初版可用。
[ ] 文件存储抽象完成。
```

### 12.5 AI 验收

```text
[ ] AI chat 可流式输出。
[ ] AI 工具调用做权限校验。
[ ] AI 操作有审计日志。
[ ] RAG 文档问答初版可用。
[ ] AI 不直接执行核心业务变更。
```

### 12.6 工程验收

```text
[ ] Docker Compose 可启动。
[ ] GitHub Actions 可跑前后端测试。
[ ] OpenAPI schema 可导出。
[ ] 前端 typed client 可生成。
[ ] 结构化日志含 trace_id。
```

---

## 13. 优先级排序

### P0：必须马上做

```text
1. 后端目录 domains/platform。
2. routes.py 拆分。
3. RESOURCE_CONFIG 按领域拆分。
4. PostgreSQL 正式化。
5. Docker Compose。
6. 权限 policy.can 基础版。
```

### P1：高收益

```text
1. Outbox。
2. Celery。
3. 库存流水 + 余额。
4. Motion Design System。
5. 登录页和 Dashboard 视觉重做。
6. TanStack Query。
7. OpenAPI typed client。
```

### P2：企业级能力

```text
1. Workflow Center。
2. 数据范围和字段权限。
3. 报表 Read Model。
4. SSE/WebSocket。
5. OpenTelemetry。
6. Playwright 业务闭环。
```

### P3：高级展示与 AI

```text
1. ReactBits Islands。
2. Three.js 数字孪生。
3. pgvector RAG。
4. AI Agent 工具平台。
5. Temporal。
6. ClickHouse/Doris。
```

---

## 14. 推荐第一批 Codex Prompt

### Prompt 1：后端结构初始化

```text
请按照 PLAN.md 的 Phase 1，先建立 backend/app/platform 与 backend/app/domains 目录结构。不要迁移全部业务，只创建结构、__init__.py、ResourceRegistry 雏形，并保证现有应用仍能启动。完成后运行后端测试，并输出修改文件列表。
```

### Prompt 2：拆 RESOURCE_CONFIG

```text
请找到当前后端集中式 RESOURCE_CONFIG，将其按 identity、inventory、sales、procurement、finance 拆分到 domains/*/resources.py。新增 ResourceRegistry，并让原 generic CRUD 通过 registry 获取配置。保持原接口 URL 兼容，新增测试验证资源 key 不重复。
```

### Prompt 3：Outbox 初版

```text
请实现 PLAN.md 中的 Outbox 初版：新增 domain_events 模型与迁移，新增 platform/events/outbox.py、event_bus.py、registry.py。先不要接 RabbitMQ，只实现数据库 Outbox。将销售订单确认 use case 改为写入 SalesOrderConfirmed 事件，并添加测试。
```

### Prompt 4：前端 Motion System

```text
请按照 PLAN.md 的前端部分，新建 frontend/src/styles/tokens、effects、components 目录，并新增 SceneBackgroundComponent、nexusSpotlight 指令、reveal 指令。先不要重做所有页面，只在登录页接入 SceneBackground 和 glass card，保持登录功能不变。
```

### Prompt 5：Dashboard 视觉升级

```text
请重做运营首页为工业智能指挥中心风格：使用 Bento Grid、Spotlight Metric Cards、Count-up 数字、业务流程流光线。数据先接现有 dashboard API，如果接口缺失则使用 typed fallback，并标注 TODO。必须支持 prefers-reduced-motion。
```

---

## 15. 最终结论

本计划的核心不是“换技术栈”，而是把 NEXUS-PRIME 升级成：

```text
架构上：
领域驱动、模块化、事件驱动、权限统一、流程独立、数据分层。

前端上：
Angular 企业级业务系统 + 高级 Motion Design System + ReactBits 风格视觉 + 可选 React 动效岛。

后端上：
Flask 模块化单体 + Celery/Outbox + PostgreSQL/Redis + Policy Engine + Workflow Center。

AI 上：
RAG + Agent + 工具调用 + 权限校验 + 人工确认 + 审计。

工程上：
Docker + CI/CD + OpenAPI + Playwright + pytest + OpenTelemetry。
```

执行顺序必须是：

```text
先稳架构
再解耦业务
再升级前端体验
再强化数据与 AI
最后做服务化和高级基础设施
```

不要追求一次完成。每一个阶段都必须能运行、能测试、能回滚。
