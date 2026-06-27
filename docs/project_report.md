# NEXUS Prime 前后端分离 ERP 项目汇报报告

学生：庄颂
学号：20241334
项目名称：NEXUS Prime 制造业 ERP 管理信息系统
技术路线：Angular 21 + Flask REST API + SQLAlchemy
更新日期：2026-06-28

## 一、项目背景

制造企业的日常经营不是单一 CRUD 页面能够覆盖的。库存水位、采购承诺、销售发货、应收回款、盘点差异、质量问题、产能瓶颈、设备维护和合同回款会互相影响。NEXUS Prime 的目标是把这些业务放到一个前后端分离的 ERP 工作台中，让用户能够从一个页面跳转到相关业务闭环，并且每个动作都能通过后端 API、通知和审计日志留痕。

旧版系统是 Flask/Jinja2 单体页面，适合课程早期开发，但页面渲染、表单、后端逻辑和数据库访问耦合较重。新版将旧版保留在 `legacy/monolith-flask/` 作为对照，活跃系统改为 Angular SPA + Flask REST API。

## 二、需求与实现范围

系统实现了以下业务模块：

- 身份与权限：用户、角色、部门、权限矩阵、登录审计。
- 主数据：商品、分类、客户、供应商、标签。
- 库存仓配：库存数量、库存流水、仓库、补货建议、仓配流向、调度。
- 采购协同：采购订单、采购明细、到货、供应商绩效、采购任务。
- 销售履约：销售订单、销售明细、发货调度、客户窗口。
- 财务应收：应收账款、收款、信用、对账。
- 盘点：盘点计划、盘点明细、差异和历史。
- 扩展运营：质量、产能、设备、合同、售后、规则、集成、预算、移动扫码。
- 协作与分析：通知、报表、文件、公告、AI 经营分析、审计日志。

所有主要业务页面均有真实后端数据、分页/搜索/动作入口、桌面和移动端截图。

2026-06-28 追加升级：根据 GitHub ERP skill `saas-erp-system-design` 的原则，对登录后的主页面做减法。全局壳层只保留顶栏、核心模块导航和当前页面；总览页重写为轻量 ERP 控制塔；其它页面不再被全局工作流和证据面板挤压，保持“一个页面只处理一个业务对象”。

## 三、总体架构

```text
Angular 21 SPA
  Router / Guard / Interceptor / AppShell / PrimeNG / ECharts
          |
          | JSON + HttpOnly Cookie + CSRF
          v
Flask REST API /api/v1
  API Routes / Domain Resources / Application Services / Audit
          |
          v
SQLAlchemy ORM + Alembic
  SQLite demo database, PostgreSQL/Supabase-ready
```

本项目采用微服务就绪的模块化单体架构。也就是说，当前系统仍以一个 Flask API 进程运行，保证课程演示和本地开发简单可靠；同时代码按库存、采购、销售、财务、流程、报表、AI、通知、身份等能力域划分，后续可以继续拆分为真正独立部署的微服务。

## 四、前端设计

前端使用 Angular 21 Standalone Components。页面结构分为：

- `core/`：API 服务、认证、主题、模型、导航和可视资产。
- `shell/`：顶栏、核心 Dock、模块面板。
- `pages/`：业务页面和详情页。
- `styles/`：企业主题、亮色修复、页面稳定层。

本轮升级重点解决了原页面的几个明显问题：

- 亮色模式大量黑灰块和低对比文字已经修复。
- 导航收敛为核心 Dock，更多业务入口进入模块面板，避免首屏堆叠过多入口。
- 取消不必要的页面入场动画和仓配流向动画，避免页面晃动。
- 页面字体层级、按钮高度、卡片半径、记录行和动作条统一。
- 仓配、调度、质量、产能、移动扫码等页面补齐业务动作和摘要，不再像草稿页。

代表页面：

![亮色总览](images/final/final-light-overview.png)

![暗色采购](images/final/final-dark-procurement.png)

![移动总览](images/final/final-mobile-light-overview.png)

全部页面截图见 `docs/final-screenshot-report.md`。

## 五、后端设计

后端使用 Flask REST API 和 SQLAlchemy。API 统一前缀为 `/api/v1`，列表接口支持分页、搜索和排序，动作接口负责写入业务结果、通知和审计。

核心设计：

- `app/api/` 维护 REST API 和业务聚合接口。
- `app/domains/` 记录能力域资源，支持后续微服务拆分。
- `app/services/` 承载业务逻辑，例如报表、库存、工作流、AI、文件、通知等。
- `app/models/` 保存 SQLAlchemy 模型。
- `migrations/` 管理 Alembic 数据库迁移。
- `tests/` 覆盖 API、认证、配置、事件、文件、库存、盘点、报表、工作流和服务层。

本轮修复了本地 SQLite 缺表、AI 草稿/结构化分析接口错误，并将多个重接口改为分页和异步分析加载，保证前端主内容先渲染。

## 六、数据库设计

数据库超过课程基础要求，包含身份、主数据、库存、采购、销售、财务、盘点、工作流、内容、报表、AI、通知和审计等实体。

ER 图源文件位于 `docs/er.mmd`，渲染图如下：

![ER 图](images/final/er-diagram.svg)

核心关系示例：

- `auth_roles` 一对多 `auth_users`。
- `biz_categories` 一对多 `biz_products`。
- `biz_products` 与 `stock_warehouses` 通过 `stock_quantities` 形成库存关系。
- `purchase_orders` 一对多 `purchase_order_items`，并关联供应商和收货仓库。
- `trade_orders` 一对多 `trade_order_items`，并关联客户和销售人员。
- `finance_receivables` 一对多 `finance_payments`，形成应收到收款闭环。
- `stock_takes` 一对多 `stock_take_items`，形成盘点闭环。
- `workflow_definitions`、`workflow_instances`、`workflow_tasks`、`workflow_logs` 支撑审批和复核。

## 七、演示数据

当前本地演示库状态：

| 数据 | 数量 |
| --- | ---: |
| 用户 | 15001 |
| 商品 | 57608 |
| 销售订单 | 100803 |
| 库存流水 | 111360 |
| 采购单 | 46803 |
| 应收账款 | 80640 |
| 收款记录 | 70560 |
| 通知 | 32424 |
| 报表 | 16200 |
| 文件 | 7200 |
| 审计日志 | 6004 |

这些数据支撑截图、分页、搜索、详情和业务动作演示，避免页面只有空壳。

## 八、测试与验收

本轮验收结果：

| 验收项 | 结果 |
| --- | --- |
| 前端主题对比审计 | 通过 |
| 前端布局审计 | 通过，66 个页面检查 |
| API 合同审计 | 通过，16 个资源、155 条路由 |
| 工作流链接审计 | 通过 |
| 页面完整度审计 | 通过，33 条路由桌面/移动失败数 0 |
| Shell 交互审计 | 通过 |
| Angular 生产构建 | 通过 |
| 后端 pytest | 207 passed |
| Alembic 迁移检查 | 通过 |

关键命令：

```powershell
cd frontend
npm run audit:theme-contrast
npm run audit:layout
npm run audit:api-contract
npm run audit:workflow-links
npm run audit:completeness
npm run audit:shell
npm run build
```

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
..\venv\Scripts\python.exe -m flask db upgrade
..\venv\Scripts\python.exe -m flask status
```

## 九、项目亮点

- 前后端分离清晰，Angular 页面不直接依赖数据库。
- 后端 API 合同经过脚本审计，前后端路径可追踪。
- 页面不是纯展示，采购、调度、质量、产能、移动扫码等页面都有动作闭环。
- 数据规模足够支撑真实分页、搜索、列表和图表。
- 亮色、暗色、桌面和移动均通过自动化审计。
- ER 图、截图、报告、讲稿和 README 均与当前代码同步。
- 架构选择保守真实：当前是模块化单体，但具备继续拆分微服务的边界。

## 十、总结

NEXUS Prime 已从旧版单体页面升级为一个可运行、可测试、可截图、可部署的前后端分离 ERP 系统。系统不仅满足课程中 Flask + Angular + 数据库 + 登录权限 + CRUD + 图表 + 文件 + 报告的要求，也补齐了企业后台常见的业务闭环、数据规模、接口契约、审计、移动端适配和可维护性要求。
