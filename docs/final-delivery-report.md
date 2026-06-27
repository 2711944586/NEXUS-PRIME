# NEXUS Prime 项目最终交付报告

学生：庄颂
学号：20241334
项目：NEXUS Prime 制造业 ERP 管理信息系统
交付日期：2026-06-28

## 1. 交付结论

NEXUS Prime 已完成从旧版 Flask/Jinja2 单体快照到前后端分离 ERP 系统的升级。当前活跃系统由 Angular 21 SPA 和 Flask REST API 组成，覆盖制造企业的主数据、库存、仓配、采购、销售履约、财务应收、盘点、质量、产能、设备、合同、售后、规则、集成、报表、文件、内容、通知、AI 分析、权限和审计。

本轮重点修复了亮色主题中灰黑低对比问题、导航栏拉长问题、页面动画过多问题、移动端排版不稳定、业务页信息密度不足、部分页面只像草稿、接口慢查询阻塞前端和后端本地数据库缺表问题。2026-06-28 追加完成登录后主页面减法重构：shell 不再把执行总账、证据带、资源工作台和上下文面板塞进所有路由，总览页重写为轻量 ERP 控制塔，后续页面统一延续首页/登录页的真实工业图片质感。

![亮色运营控制塔](images/final/final-light-overview.png)

## 2. 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Angular 21、Standalone Components、PrimeNG 21、PrimeIcons、Lucide、ECharts、RxJS |
| 后端 | Flask REST API、SQLAlchemy、Flask-Migrate、Flask-CORS、pytest |
| 数据 | 本地 SQLite 演示库，PostgreSQL/Supabase-ready |
| 认证 | HttpOnly Cookie、CSRF Cookie、Angular Guard、后端权限校验 |
| 可视化 | ECharts、Playwright 截图、Graphviz ER 图 |
| 工程化 | OpenAPI/接口审计、布局审计、主题对比审计、工作流链接审计、Shell 交互审计、207 个后端测试 |

## 3. 架构升级

系统采取“微服务就绪的模块化单体”架构。当前不是把项目硬拆成多个部署单元，而是按 ERP 业务域整理边界，让库存、采购、销售、财务、流程、报表、AI、通知、身份和内容等上下文拥有清晰模型、服务和 API 合同。后续如果要真正拆分微服务，可以基于这些 bounded contexts 继续抽出独立服务、队列和数据库边界。

```text
Angular 21 SPA
  Router / Guard / Interceptor / Shell / Pages / Design System
          |
          | JSON API + Cookie + CSRF
          v
Flask /api/v1
  API Blueprints / Application Services / Resource Registry / Audit
          |
          v
SQLAlchemy Models + Alembic Migrations
```

架构改造要点：

- 前端只负责页面、交互、路由、主题和数据呈现，不直接持有数据库逻辑。
- 后端统一暴露 `/api/v1`，列表接口支持分页、搜索和排序，动作接口写入通知与审计。
- `backend/app/domains/` 记录能力域，`ResourceRegistry` 统一资源注册，保留旧路径兼容但不继续扩散旧式路由。
- 应用壳层从“全局大而全驾驶舱”收敛为顶栏 + 核心 Dock + 当前页面 + 更多模块面板。
- 前端样式新增 `frontend/src/styles/_enterprise-upgrade.scss`，集中处理亮色对比、无动画、紧凑导航、移动端排版和企业后台密度。
- 慢接口拆分为主数据先渲染、分析数据后加载，避免采购、合同、任务等页面等待大聚合接口后才显示。

## 4. 数据库与 ER 图

ER 源文件：`docs/er.mmd`
渲染文件：`docs/images/final/er-diagram.svg`、`docs/images/final/er-diagram.png`

![ER 图](images/final/er-diagram.svg)

主要实体关系：

- 用户、角色、权限、部门构成身份域。
- 商品、分类、标签、客户/供应商构成主数据域。
- 商品与仓库通过库存数量、库存余额、库存流水、库存预警和补货建议连接。
- 采购订单、采购明细、供应商绩效与仓库收货连接。
- 销售订单、销售明细、应收、收款、信用、对账单连接形成销售到回款闭环。
- 盘点单、盘点明细、盘点历史连接库存调整链路。
- 工作流定义、实例、任务和日志支撑审批/复核。
- 文章、评论、附件、报表、通知、AI 会话和审计日志支撑协作和可追溯。

## 5. 数据规模

`flask status` 输出确认当前演示库不是空壳：

| 数据 | 数量 |
| --- | ---: |
| 用户 | 15001 |
| 商品 | 57608 |
| 销售订单 | 100803 |
| 仓库 | 4 |
| 库存流水 | 111360 |
| 采购单 | 46803 |
| 应收账款 | 80640 |
| 收款记录 | 70560 |
| 盘点单 | 2400 |
| 通知 | 32424 |
| 报表 | 16200 |
| 文章 | 16200 |
| 评论 | 21600 |
| 文件 | 7200 |
| 审计日志 | 6004 |

## 6. 功能完成度

| 功能 | 完成情况 |
| --- | --- |
| 登录/注册 | 独立入口、亮/暗主题、注册协议、角色区分 |
| 运营首页 | KPI、风险、工作流、服务边界、图表、现场证据 |
| 库存 | 商品、库存、仓配流向、补货建议、库存流水 |
| 采购 | 采购审批、供应商协同、到货、预算暴露、任务创建 |
| 销售 | 客户订单、发货调度、应收联动 |
| 财务 | 应收账龄、回款、信用、冻结/释放 |
| 盘点 | 计划、扫码、差异、调整 |
| 调度 | 仓配调度、补货、盘点、报表快捷闭环 |
| 质量/产能/设备 | 检验批、缺陷、齐套、瓶颈、维护工单 |
| 合同/售后/规则 | 合同回款、服务工单、决策表和复核队列 |
| 集成/预算 | 服务 SLO、依赖、错误预算、成本差异 |
| 文件/内容 | 文件列表、详情、公告、知识库、附件 |
| AI 分析 | 经营诊断、会话、草稿动作、结构化分析 |
| 通知/审计 | 任务通知、完成处理、操作审计 |
| 设置/个人 | 主题、密度、部署就绪、偏好和资料 |

## 7. 前端升级

本轮前端重点：

- 亮色主题重新定义高对比 token，避免黑灰块突兀和低对比文字。
- 桌面导航收敛为 88px 左侧紧凑 Dock，移动端为 sticky 紧凑导航，不再拉长顶部栏。
- 取消路由入场、卡片扫光、仓配线条等不必要动画，保留可访问的静态反馈。
- 统一页面字体层级、按钮尺寸、卡片半径、记录行和动作条样式。
- 给质量、产能、移动扫码、仓配、调度等页面补齐业务动作入口和执行摘要。
- `/app/inventory/stock` 增加仓配执行快线，移动端也能直接进入调度、补货、盘点、采购、销售、移动扫码、资料和报表。
- 全页面截图覆盖桌面和移动视口，见 `docs/final-screenshot-report.md`。

## 8. 后端升级

本轮后端重点：

- 本地 SQLite 缺表修复，并将 Alembic 状态与当前 schema 对齐。
- AI 草稿、结构化分析接口 500 问题修复。
- 前端运行时配置指向 `http://127.0.0.1:5001/api/v1`，API 合同审计确认前后端路径相通。
- 销售、采购、库存、盘点、文章、客户、应收等列表降为分页小批量请求，减少首屏阻塞。
- 采购页、合同页、任务页拆分慢分析接口，核心列表先显示。
- 后端 207 个测试通过，覆盖认证、API、事件、报表、工作流、文件授权、库存、盘点、通知、OpenAPI、配置和服务层。

## 9. 截图交付

核心截图目录：`docs/images/final/`
所有页面截图索引：`docs/images/final/pages/manifest.json`
截图报告：`docs/final-screenshot-report.md`

代表截图：

![暗色采购协同](images/final/final-dark-procurement.png)

![移动端总览](images/final/final-mobile-light-overview.png)

![Dock 模块面板](images/final/dock.png)

## 10. 验证结果

| 命令 | 结果 |
| --- | --- |
| `npm run audit:theme-contrast` | 通过 |
| `npm run audit:layout` | 通过，66 个页面检查 |
| `npm run audit:api-contract` | 通过，16 个资源、155 条后端路由 |
| `npm run audit:workflow-links` | 通过 |
| `npm run audit:completeness` | 通过，33 条路由桌面/移动失败数 0 |
| `npm run audit:visual-assets` | 通过，37 张本地 JPG、25 个页面实际使用来源 |
| `npm run audit:shell` | 通过 |
| `npm run audit:charts` | 通过，37 个页面文件 |
| `npm run audit:topbar` | 通过 |
| `npm run audit:more-menus` | 通过 |
| `npm run audit:supplier` | 通过 |
| `npm run audit:deployment-readiness` | 通过 |
| `npm run api:check` | 通过 |
| `npm run build` | 通过 |
| `..\venv\Scripts\python.exe -m pytest` | 207 passed |
| `npm run capture:final-screenshots` | 完成，66 条截图索引、102 张页面 PNG |

## 11. 可维护性

- 前端新增截图采集脚本 `frontend/scripts/capture-final-screenshots.mjs`，可复现交付截图。
- 亮色/导航/动画/排版修复集中在 `_enterprise-upgrade.scss`，本轮登录后减法和真实图片质感集中在 `_erp-simplified-workspace.scss`，避免散落在各页面。
- 各业务页保留独立组件，页面内只做展示和动作调用，数据请求走 `ApiService`。
- 后端按领域继续演进，测试覆盖服务层和路由合同。
- 报告、截图、ER 图、视频讲稿和 README 均在 `docs/` 中可直接检查。
- 本轮新增 `docs/production-upgrade-report-2026-06-28.md`、`docs/operator-guide.md` 和 `docs/code-review-production-readiness.md`。

## 12. 复现命令

```powershell
cd frontend
$env:NEXUS_LOCAL_API_BASE_URL='http://127.0.0.1:5001/api/v1'
node scripts/write-runtime-config.mjs --local
$env:NEXUS_AUDIT_BASE_URL='http://127.0.0.1:4200'
$env:NEXUS_AUDIT_API_BASE_URL='http://127.0.0.1:5001/api/v1'
npm run audit:theme-contrast
npm run audit:layout
npm run audit:api-contract
npm run audit:workflow-links
npm run audit:completeness
npm run audit:visual-assets
npm run audit:shell
npm run audit:charts
npm run audit:topbar
npm run audit:more-menus
npm run audit:supplier
npm run audit:deployment-readiness
npm run api:check
npm run build
npm run capture:final-screenshots
```

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask db upgrade
..\venv\Scripts\python.exe -m flask status
```
