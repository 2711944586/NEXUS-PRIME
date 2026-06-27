# NEXUS Prime 讲解视频稿

建议时长：6 分钟
展示方式：浏览器 + 终端 + 文档截图
本地地址：`http://127.0.0.1:4200`

## 0:00 - 0:30 开场

大家好，我是庄颂，学号 20241334。本次展示的是 NEXUS Prime 制造业 ERP 管理信息系统。

系统采用前后端分离架构：前端是 Angular 21 SPA，后端是 Flask REST API，数据库本地使用 SQLite，生产方向支持 PostgreSQL/Supabase。系统覆盖库存、仓配、采购、销售、应收、盘点、质量、产能、设备、合同、售后、规则、集成、报表、文件、通知、AI 分析、权限和审计。

## 0:30 - 1:05 项目结构与架构

展示项目目录。

`backend/` 是 Flask API，包含模型、服务、接口、迁移和测试。
`frontend/` 是 Angular 前端，包含核心服务、应用外壳和业务页面。
`docs/` 放最终报告、ER 图、截图和讲稿。
`legacy/monolith-flask/` 是旧版 Flask/Jinja2 单体对照，不参与新版运行。

说明架构：前端通过 `/api/v1` 调用后端，登录使用 HttpOnly Cookie 和 CSRF。后端采用微服务就绪的模块化单体，先按库存、采购、销售、财务、流程、报表、AI 等 bounded contexts 整理边界，后续可以继续拆成真正的微服务。

## 1:05 - 1:35 登录与主题

打开入口页、登录页和注册页。

本地演示账号：

```text
admin@nexus.com / admin123
```

说明本轮按 GitHub ERP skill 重新做了“减法”：登录后不再把所有工作流、证据、资源和上下文塞到每个页面，而是只保留顶栏、核心模块 Dock 和当前页面。切换亮色和暗色，展示文字、按钮、真实工业图片和页面 hero 在两种主题下都能清楚阅读。

## 1:35 - 2:25 运营控制塔

进入 `/app/overview`。

说明顶部是命令栏，核心 Dock 只放最常用路径：运营、物料、采购、履约、应收、报表。页面主体是重新精简后的 ERP 控制塔，只保留经营控制分、低库存、待审批采购、逾期应收、库存水位、六步业务闭环、经营趋势和当班待办。点击“更多模块”，展示其它业务页面入口。

展示 `docs/images/final/final-light-overview.png` 和新的页面截图，说明这些截图由 Playwright 自动采集。

## 2:25 - 3:25 核心业务闭环

依次展示几个页面：

1. `/app/inventory/stock` 仓配流向图：展示仓库网络、库存流水、低水位、执行快线。移动端也能直接进入调度、补货、盘点、采购、销售、移动扫码、资料和报表。
2. `/app/procurement/orders` 采购协同：展示审批、供应商确认、到货收货和采购任务。
3. `/app/sales/orders` 销售履约：展示客户订单、发货调度和应收联动。
4. `/app/finance/receivables` 应收风控：展示账龄、回款、催收和信用风险。
5. `/app/stocktakes` 盘点中心：展示盘点计划、扫码录入、差异处理。

说明这些不是静态页面，列表数据来自后端，动作会写入通知和审计。

## 3:25 - 4:15 扩展 ERP 能力

快速展示：

- `/app/quality` 质量检验中心。
- `/app/capacity` 产能计划中心。
- `/app/maintenance` 设备维护中心。
- `/app/contracts` 合同回款中心。
- `/app/rules` 规则引擎中心。
- `/app/integrations` 集成监控中心。
- `/app/mobile-terminal` 移动扫码终端。

说明这些页面不再和总览页抢信息密度，每个页面只处理自己的业务对象：质量页处理检验批，产能页处理瓶颈，设备页处理工单，合同页处理回款，移动端处理扫码任务。

## 4:15 - 4:55 文件、报表、AI 与审计

打开 `/app/reports`，展示报表模板、生成队列和图表预览。
打开 `/app/files` 和文件详情，展示文件列表、详情、关联对象和下载区域。
打开 `/app/ai`，展示经营分析、会话、诊断和草稿动作。
打开 `/app/system/audit`，说明登录、上传、任务、报表和业务动作都会留痕。

## 4:55 - 5:25 ER 图与数据规模

打开 `docs/images/final/er-diagram.svg`。

说明数据库包含身份、主数据、库存、采购、销售、财务、盘点、工作流、内容、报表、AI、通知和审计等实体。

展示终端命令：

```powershell
cd backend
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask status
```

说明当前演示库有 15001 个用户、57608 个商品、100803 个销售订单、111360 条库存流水、46803 个采购单、80640 条应收账款和 6004 条审计日志，数据量足以支撑真实分页、搜索和图表。

## 5:25 - 5:50 自动化验证

展示验证命令和结果：

```powershell
cd frontend
npm run audit:theme-contrast
npm run audit:layout
npm run audit:api-contract
npm run audit:workflow-links
npm run audit:completeness
npm run audit:visual-assets
npm run audit:shell
npm run audit:topbar
npm run audit:more-menus
npm run audit:deployment-readiness
npm run api:check
npm run build
```

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
```

说明结果：Angular 生产构建通过；主题、布局、真实图片、API 合同、工作流、页面完整度、顶部栏、更多菜单、部署准备和 Shell 交互审计全部通过；后端 `207 passed`。截图脚本刷新了 66 条页面截图索引和 102 张页面 PNG。

## 5:50 - 6:00 总结

NEXUS Prime 已经完成从旧版单体页面到前后端分离 ERP 系统的升级。本轮进一步把登录后页面从杂乱的拼贴式驾驶舱改成简洁、有真实图片、有业务流的 ERP 工作台。当前版本是模块化单体，但已经按照微服务就绪思路整理能力域，后续可以继续拆分服务和部署边界。

我的展示到这里，谢谢大家。
