# NEXUS Prime 最终截图审核报告

## 1. 审核结论

本报告用于证明最终交付截图不是静态摆图，而是由真实浏览器登录后访问业务页面生成。最新截图与布局验收覆盖桌面端和移动端 33 条业务路由，共 66 个页面检查，失败数为 0。本轮新增全量页面成熟度、页面级现场图、真实度、工作流密度、当班交接、业务数据密度、工作流点击、顶部全局操作和更多菜单专项审核，确认核心业务页在桌面与移动端均具备页面本体现场图、可点击工作流入口、责任人交接动作、业务数据行、可用搜索/创建/通知/设置/经营分析入口、可打开的更多模块入口、无横向溢出和无文字截断；模块地图交互审核继续通过。

| 项目 | 结果 |
| --- | --- |
| 桌面视口 | 1440 x 950 |
| 移动视口 | 390 x 844 |
| 覆盖路由 | 33 条 |
| 页面检查 | 66 项 |
| 失败项 | 0 |
| 横向溢出 | 0 |
| 可见文字重叠 | 0 |
| 图表尺寸异常 | 0 |
| Dock 遮挡图表 | 0 |
| ECharts 布局 guard | 已启用 |

## 2. 证据位置

| 证据 | 路径 |
| --- | --- |
| 最新完整质量闸门布局报告 | `output/playwright/layout-audit-1781497856364/report.json` |
| 最新图表审计报告 | `output/playwright/chart-audit-1781497812317/report.json` |
| 最新全量页面成熟度审计报告 | `output/playwright/completeness-audit-1781022883061/report.json` |
| 最新全量页面成熟度截图目录 | `output/playwright/completeness-audit-1781022883061/` |
| 最新页面级现场图、真实度、工作流密度、交接与数据密度审核报告 | `output/playwright/experience-audit-1781018842775/report.json` |
| 最新页面级现场图、真实度、工作流密度、交接与数据密度截图目录 | `output/playwright/experience-audit-1781018842775/` |
| 最新工作流点击专项审核报告 | `output/playwright/workflow-link-audit-1781019971361/report.json` |
| 最新工作流点击专项截图目录 | `output/playwright/workflow-link-audit-1781019971361/` |
| 最新顶部全局操作专项审核报告 | `output/playwright/topbar-operations-audit-1781024167045/report.json` |
| 最新顶部全局操作专项截图目录 | `output/playwright/topbar-operations-audit-1781024167045/` |
| 最新更多菜单专项审核报告 | `output/playwright/more-menu-audit-1781023974604/report.json` |
| 最新更多菜单专项截图目录 | `output/playwright/more-menu-audit-1781023974604/` |
| 最新模块地图交互专项审核报告 | `output/playwright/shell-interaction-1781497836740/report.json` |
| 最新模块地图交互截图目录 | `output/playwright/shell-interaction-1781497836740/` |
| 最新供应商协同专项审核报告 | `output/playwright/supplier-collaboration-1781009953815/report.json` |
| 最新供应商协同专项截图目录 | `output/playwright/supplier-collaboration-1781009953815/` |
| 最新关键页面网页取样审核报告 | `output/playwright/web-review-1780997929715/report.json` |
| 最新关键页面网页取样截图目录 | `output/playwright/web-review-1780997929715/` |
| 最新采购协同控制台审核报告 | `output/playwright/procurement-control-upgrade-1780996622570/report.json` |
| 最新采购协同控制台截图目录 | `output/playwright/procurement-control-upgrade-1780996622570/` |
| 最新总览作战台升级审核报告 | `output/playwright/overview-command-upgrade-1780992882786/report.json` |
| 最新总览作战台升级截图目录 | `output/playwright/overview-command-upgrade-1780992882786/` |
| 最新核心页面人工审核报告 | `output/playwright/manual-page-review-1780936841067/report.json` |
| 最新关键页面网页复审报告 | `output/playwright/web-review-1780997929715/report.json` |
| 最新关键页面网页复审截图目录 | `output/playwright/web-review-1780997929715/` |
| 最新工作流执行层审核报告 | `output/playwright/workflow-command-review-1780934295879/report.json` |
| 最新工作流执行层截图目录 | `output/playwright/workflow-command-review-1780934295879/` |
| 最新部署就绪审核报告 | `output/playwright/deployment-readiness-review-1780935781436/report.json` |
| 最新部署就绪截图目录 | `output/playwright/deployment-readiness-review-1780935781436/` |
| 最新部署就绪与 ERP 成熟度专项审核报告 | `output/playwright/deployment-readiness-audit-1781498047746/report.json` |
| 最新部署就绪与 ERP 成熟度专项截图目录 | `output/playwright/deployment-readiness-audit-1781498047746/` |
| 最新部署任务点击流报告 | `output/playwright/deployment-task-flow-1780937731840/report.json` |
| 最新部署任务点击流截图目录 | `output/playwright/deployment-task-flow-1780937731840/` |
| 最新通知任务完成流报告 | `output/playwright/notification-task-complete-1780939318650/report.json` |
| 最新通知任务完成流截图目录 | `output/playwright/notification-task-complete-1780939318650/` |
| 最新任务队列网页审核报告 | `output/playwright/task-queue-review-1780941937011/report.json` |
| 最新任务队列网页截图目录 | `output/playwright/task-queue-review-1780941937011/` |
| 最新集成治理网页审核报告 | `output/playwright/integration-governance-review-1780942978805/report.json` |
| 最新集成治理截图目录 | `output/playwright/integration-governance-review-1780942978805/` |
| 最新数据质量治理网页审核报告 | `output/playwright/data-quality-governance-1780969703241/report.json` |
| 最新数据质量治理截图目录 | `output/playwright/data-quality-governance-1780969703241/` |
| 最新质量检验治理网页审核报告 | `output/playwright/quality-inspection-governance-1780989292960/report.json` |
| 最新质量检验治理截图目录 | `output/playwright/quality-inspection-governance-1780989292960/` |
| 最新规则治理网页审核报告 | `output/playwright/rules-governance-1780973553475/report.json` |
| 最新规则治理截图目录 | `output/playwright/rules-governance-1780973553475/` |
| 最新规则决策表截图报告 | `output/playwright/rules-decision-table-1780973745905/report.json` |
| 最新规则决策表截图目录 | `output/playwright/rules-decision-table-1780973745905/` |
| 最新预算成本治理网页审核报告 | `output/playwright/budget-governance-1780976362599/report.json` |
| 最新预算成本治理截图目录 | `output/playwright/budget-governance-1780976362599/` |
| 最新预算成本二次网页复审报告 | `output/playwright/webpage-review-1780976875726/report.json` |
| 最新预算成本二次复审截图目录 | `output/playwright/webpage-review-1780976875726/` |
| 最新产能计划治理网页审核报告 | `output/playwright/capacity-governance-1780979251443/report.json` |
| 最新产能计划治理截图目录 | `output/playwright/capacity-governance-1780979251443/` |
| 最新设备可靠性治理网页审核报告 | `output/playwright/maintenance-reliability-1780984911955/report.json` |
| 最新设备可靠性治理截图目录 | `output/playwright/maintenance-reliability-1780984911955/` |
| 最新移动扫码终端治理网页审核报告 | `output/playwright/mobile-terminal-governance-1780982319037/report.json` |
| 最新移动扫码终端治理截图目录 | `output/playwright/mobile-terminal-governance-1780982319037/` |
| 最新全量截图采集目录 | `output/playwright/layout-audit-1781497856364/` |
| 最新亮色主题截图目录 | `output/playwright/light-captures-1780922557950/` |
| 最终交付截图目录 | `docs/images/final/` |
| 最终 Word 报告 | `docs/final-delivery-report.docx` |
| 交付资产审计 | `output/quality-gate/delivery-assets.json` |

说明：`output/playwright/` 是本地审核输出，可用 `scripts/clean-workspace.ps1` 清理；正式交付引用的稳定截图保存在 `docs/images/final/`。

## 3. 核心截图

### 暗色总览

![暗色总览](images/final/final-dark-overview.png)

### 暗色采购审批

![暗色采购审批](images/final/final-dark-procurement.png)

### 亮色总览

![亮色总览](images/final/final-light-overview.png)

### 亮色采购审批

![亮色采购审批](images/final/final-light-procurement.png)

### 移动端总览

![移动端总览](images/final/final-mobile-light-overview.png)

### 供应商协同

![供应商协同](images/final/final-dark-supplier-collaboration.png)

### 移动端供应商协同

![移动端供应商协同](images/final/final-mobile-supplier-collaboration.png)

### 模块地图交互与真实现场图

本轮交互截图位于 `output/playwright/shell-interaction-1781497836740/`：

| 截图 | 路径 |
| --- | --- |
| 桌面总览首屏 | `output/playwright/shell-interaction-1781497836740/desktop-01-overview.png` |
| 桌面顶部更多模块面板 | `output/playwright/shell-interaction-1781497836740/desktop-02-topbar-panel.png` |
| 桌面 dock 更多模块面板 | `output/playwright/shell-interaction-1781497836740/desktop-03-dock-panel.png` |
| 移动端总览首屏 | `output/playwright/shell-interaction-1781497836740/mobile-01-overview.png` |
| 移动端更多模块面板 | `output/playwright/shell-interaction-1781497836740/mobile-02-topbar-panel.png` |
| 移动端 Dock 更多模块面板 | `output/playwright/shell-interaction-1781497836740/mobile-03-dock-panel.png` |

该审核使用真实登录态打开 `/app/overview`，校验模块面板在桌面与移动视口内可见，Escape 可关闭，模块链接可跳转到 `/app/metrics`。桌面顶部、桌面 Dock、移动顶部和移动 Dock 面板均展示 32 个模块、12 张真实业务现场图、3 张指挥卡和 9 个模块分组；横向溢出、文字截断、越界元素、控制台错误、异常请求和 HTTP 4xx/5xx 均为 0。

### 顶部全局操作闭环

本轮新增专项截图位于 `output/playwright/topbar-operations-audit-1781024167045/`：

| 截图 | 路径 |
| --- | --- |
| 桌面搜索静态建议 | `output/playwright/topbar-operations-audit-1781024167045/desktop-01-search-suggestions.png` |
| 桌面搜索后端结果 | `output/playwright/topbar-operations-audit-1781024167045/desktop-02-search-results.png` |
| 桌面快捷创建 | `output/playwright/topbar-operations-audit-1781024167045/desktop-03-quick-create.png` |
| 移动端快捷创建 | `output/playwright/topbar-operations-audit-1781024167045/mobile-03-quick-create.png` |

该审核使用真实登录态打开 `/app/overview`，桌面端验证搜索焦点展示 6 条静态建议，输入 `MFG` 后调用 `/api/v1/search` 返回 5 条物料结果，并点击首条跳转到 `/app/inventory/products/1`；快捷创建展示 5 个业务动作并跳转到 `/app/inventory/replenishment`；同步运营数据请求 `/manufacturing/command-center` 和 `/health` 均返回 200 且出现成功反馈。桌面与移动端均真实点击服务健康、经营分析、全局设置、通知中心和个人工作台入口，分别跳转到 `/app/integrations`、`/app/ai`、`/app/settings`、`/app/notifications` 和 `/app/profile`；移动端搜索与同步按响应式设计隐藏。控制台错误、有效失败请求、HTTP 4xx/5xx、横向溢出、文字截断和越界元素均为 0。

### 更多菜单与快捷创建专项

本轮新增专项截图位于 `output/playwright/more-menu-audit-1781023974604/`：

| 截图 | 路径 |
| --- | --- |
| 桌面快捷创建打开态 | `output/playwright/more-menu-audit-1781023974604/desktop-01-quick-create-open.png` |
| 桌面顶部更多模块面板 | `output/playwright/more-menu-audit-1781023974604/desktop-02-topbar-module-panel.png` |
| 桌面 Dock 更多模块面板 | `output/playwright/more-menu-audit-1781023974604/desktop-02-dock-module-panel.png` |
| 移动端快捷创建打开态 | `output/playwright/more-menu-audit-1781023974604/mobile-01-quick-create-open.png` |
| 移动端更多模块面板 | `output/playwright/more-menu-audit-1781023974604/mobile-02-topbar-module-panel.png` |

该审核使用真实登录态在桌面与移动视口验证顶部“创建”和“更多模块”按钮的 `aria-expanded`、`aria-controls`、菜单/对话框角色、焦点落点、外部点击关闭、Escape 关闭和真实跳转。桌面快捷创建展示 5 个动作并跳转 `/app/inventory/replenishment`；桌面顶部与 Dock 更多模块均展示 32 个模块、12 张现场图、3 张指挥卡和 9 个模块分组，并跳转 `/app/reports`；移动端顶部更多模块同样通过，移动 Dock 入口按响应式隐藏。控制台错误、有效失败请求、HTTP 4xx/5xx、nowrap 截断和越界元素均为 0。

### 全量页面成熟度审计

本轮新增全量成熟度报告位于 `output/playwright/completeness-audit-1781022883061/report.json`，截图目录位于 `output/playwright/completeness-audit-1781022883061/`。

该审核使用真实登录态覆盖 33 条路由，并在桌面 1440 x 950 与移动 390 x 844 两个视口执行 66 次页面检查。审计项包括 API 运行时配置、H1、Shell 与页面现场图、工作流链接、当班交接动作、业务数据行、操作表面、正文密度、死链、临时文案、nowrap 截断、越界元素、控制台错误、异常请求和 HTTP 4xx/5xx。结果为失败数 0，横向溢出 0，死链 0，nowrap 截断 0，越界元素 0，控制台错误 0，有效失败请求 0，HTTP 4xx/5xx 响应 0。`/app/service` 桌面与移动端业务数据行均达到 10 行；`/app/integrations` 桌面与移动端临时文案命中均为 0；交付运行时配置已恢复为 `apiBaseUrl: ""`，交付资产审计 `output/quality-gate/delivery-assets.json` 无失败项。

### 页面级现场图、真实度、工作流密度、当班交接与数据密度

本轮新增专项截图位于 `output/playwright/experience-audit-1781018842775/`：

| 截图 | 路径 |
| --- | --- |
| 桌面总览真实度取样 | `output/playwright/experience-audit-1781018842775/desktop-overview.png` |
| 移动总览真实度取样 | `output/playwright/experience-audit-1781018842775/mobile-overview.png` |

该审核使用真实登录态抽查 `/app/overview`、`/app/inventory/stock`、`/app/procurement/orders`、`/app/quality`、`/app/sales/orders`、`/app/finance/receivables`、`/app/integrations` 和 `/app/reports`。桌面和移动共 16 次检查全部通过：每个抽查页至少 3 张页面级现场图、至少 3 个工作流入口、至少 3 条当班交接动作、至少 12 行业务数据、至少 18 个可操作/数据表面；横向溢出、文字截断、越界元素、控制台错误、有效失败请求和 HTTP 4xx/5xx 均为 0。桌面端每个抽查页可见 4 张页面级现场图，移动端每个抽查页可见 3 张页面级现场图；质量检验页业务数据行保持 59 行，集成治理页业务数据行保持 57 行。

### 工作流点击闭环

本轮新增点击专项报告位于 `output/playwright/workflow-link-audit-1781019971361/report.json`。

该审核使用真实登录态抽查 `/app/overview`、`/app/inventory/stock`、`/app/procurement/orders`、`/app/quality`、`/app/sales/orders`、`/app/finance/receivables`、`/app/integrations` 和 `/app/reports`，并在桌面与移动端真实点击页面现场、现场证据、当班交接、执行信号、闭环节点和下一步入口。桌面端每个抽查页可见 21-22 个工作流链接，移动端每个抽查页可见 9 个工作流链接；死链 0、必需分组缺失 0、点击失败 0、控制台错误 0、有效失败请求 0、HTTP 4xx/5xx 为 0。

### 作战流执行层

本轮新增截图位于 `output/playwright/workflow-command-review-1780934295879/`：

| 截图 | 路径 |
| --- | --- |
| 桌面班次执行控制层 | `output/playwright/workflow-command-review-1780934295879/desktop-workflow-command-deck.png` |
| 桌面阻塞筛选 | `output/playwright/workflow-command-review-1780934295879/desktop-overview-blocked-filter.png` |
| 移动班次执行控制层 | `output/playwright/workflow-command-review-1780934295879/mobile-workflow-command-deck-top.png` |
| 移动阻塞筛选 | `output/playwright/workflow-command-review-1780934295879/mobile-overview-blocked-filter.png` |

该审核使用真实登录态打开 `/app/overview`，校验默认 8 个阶段、6 个当班动作、4 个服务边界、4 项部署检查、1 个 P0 阻塞动作，并点击“阻塞”筛选确认桌面与移动端都能聚焦阻塞阶段。

### 总览作战台角色、事件与合同层

本轮新增网页审核截图位于 `output/playwright/overview-command-upgrade-1780992882786/`：

| 截图 | 路径 |
| --- | --- |
| 桌面总览首屏 | `output/playwright/overview-command-upgrade-1780992882786/desktop-overview-full.png` |
| 桌面作战流角色事件合同层 | `output/playwright/overview-command-upgrade-1780992882786/desktop-workflow-board.png` |
| 移动端总览首屏 | `output/playwright/overview-command-upgrade-1780992882786/mobile-overview-full.png` |
| 移动端作战流角色事件合同层 | `output/playwright/overview-command-upgrade-1780992882786/mobile-workflow-board.png` |

该审核使用真实登录态打开 `/app/overview`，确认后端 `/manufacturing/workflow-board` 合同已经渲染 5 个角色指挥席、8 条现场事件、4 个前后端 API 合同和 8 个跨模块阶段；桌面与移动端 `bodyOverflowX=0`，文字撑破、越界卡片、控制台错误、有效失败请求和 HTTP 4xx/5xx 均为 0。角色座席已从挤压双列修正为宽卡单列，领域标签不再出现单字竖排。

### 部署就绪与 ERP 成熟度看板

本轮新增截图位于 `output/playwright/deployment-readiness-review-1780935781436/`：

| 截图 | 路径 |
| --- | --- |
| 桌面部署就绪看板 | `output/playwright/deployment-readiness-review-1780935781436/desktop-deployment-readiness.png` |
| 移动部署就绪看板顶部 | `output/playwright/deployment-readiness-review-1780935781436/mobile-deployment-readiness-top.png` |
| 移动部署就绪检查项 | `output/playwright/deployment-readiness-review-1780935781436/mobile-deployment-readiness.png` |
| 桌面部署就绪与 ERP 成熟度全页 | `output/playwright/deployment-readiness-audit-1781498047746/desktop-deployment-readiness.png` |
| 移动部署就绪与 ERP 成熟度全页 | `output/playwright/deployment-readiness-audit-1781498047746/mobile-deployment-readiness.png` |

该审核使用真实登录态打开 `/app/settings`，校验上线就绪分、至少 10 项动态部署检查、至少 3 个微服务域、5 条 runbook、3 条运行时快照、6 个 Token 入口，并确认桌面与移动端均无控制台错误、接口错误和横向溢出。最新专项审核 `output/playwright/deployment-readiness-audit-1781498047746/report.json` 继续校验 ERP 成熟度 91%、6 个成熟度维度、4 个能力域、8 个服务拓扑节点、8 个交付证据卡、0 个 secret 泄露候选、0 横向溢出、0 控制台错误和 0 HTTP 错误。

### 部署预检任务闭环

本轮新增点击流截图位于 `output/playwright/deployment-task-flow-1780937731840/`：

| 截图 | 路径 |
| --- | --- |
| 创建任务前部署检查项 | `output/playwright/deployment-task-flow-1780937731840/before-task-create.png` |
| 创建任务后成功反馈 | `output/playwright/deployment-task-flow-1780937731840/after-task-create.png` |
| 通知中心首屏 | `output/playwright/deployment-task-flow-1780937731840/notifications-after-task.png` |
| 通知任务行 | `output/playwright/deployment-task-flow-1780937731840/notifications-task-row.png` |
| 移动部署任务按钮 | `output/playwright/deployment-task-flow-1780937731840/mobile-deployment-task-buttons.png` |

该审核使用真实登录态打开 `/app/settings`，点击第一条 attention 部署检查项的“创建任务”，确认 `POST /api/v1/operations/deployment-readiness/task` 返回 201；随后进入 `/app/notifications`，确认任务列表出现“部署预检任务 - 前端 API 地址”。浏览器控制台错误数为 0，HTTP 4xx/5xx 响应数为 0，通知中心横向溢出为 0。

### 通知任务处理闭环

本轮新增点击流截图位于 `output/playwright/notification-task-complete-1780939318650/`：

| 截图 | 路径 |
| --- | --- |
| 设置页创建部署任务 | `output/playwright/notification-task-complete-1780939318650/settings-task-created.png` |
| 通知任务处理前 | `output/playwright/notification-task-complete-1780939318650/notification-task-before-complete.png` |
| 来源回到设置页 | `output/playwright/notification-task-complete-1780939318650/notification-source-settings.png` |
| 通知任务处理后 | `output/playwright/notification-task-complete-1780939318650/notification-task-after-complete.png` |
| 移动端通知任务动作 | `output/playwright/notification-task-complete-1780939318650/mobile-notification-task-actions.png` |

该审核使用真实登录态从设置页创建部署预检任务，进入 `/app/notifications` 点击“来源”回到 `/app/settings`，再回到通知中心点击“处理完成”，确认 `POST /api/v1/notifications/complete` 返回 200，任务卡显示“已处理”。浏览器控制台错误数为 0，HTTP 4xx/5xx 响应数为 0，桌面与移动端横向溢出均为 0。

### 任务异常中心当班队列

本轮新增网页审核截图位于 `output/playwright/task-queue-review-1780941937011/`：

| 截图 | 路径 |
| --- | --- |
| 桌面任务队列初始状态 | `output/playwright/task-queue-review-1780941937011/desktop-task-queue-before.png` |
| 创建部署预检任务后 | `output/playwright/task-queue-review-1780941937011/desktop-task-queue-after-create.png` |
| 处理通知任务后 | `output/playwright/task-queue-review-1780941937011/desktop-task-queue-after-complete.png` |
| 移动端任务队列 | `output/playwright/task-queue-review-1780941937011/mobile-task-queue.png` |

该审核使用真实登录态打开 `/app/tasks`，确认当班任务队列前屏展示 12 条任务，部署预检“创建任务”返回 201，新增通知“处理完成”返回 200。桌面与移动端横向溢出均为 0，控制台错误数为 0，异常请求数为 0，HTTP 4xx/5xx 响应数为 0。

### 集成治理指挥层

本轮新增网页审核截图位于 `output/playwright/integration-governance-review-1780942978805/`：

| 截图 | 路径 |
| --- | --- |
| 桌面服务治理指挥层 | `output/playwright/integration-governance-review-1780942978805/desktop-integration-governance.png` |
| 创建接口重同步任务后 | `output/playwright/integration-governance-review-1780942978805/desktop-integration-after-task-create.png` |
| 任务队列接收接口任务 | `output/playwright/integration-governance-review-1780942978805/desktop-task-queue-integration-task.png` |
| 移动端服务治理指挥层 | `output/playwright/integration-governance-review-1780942978805/mobile-integration-governance.png` |

该审核使用真实登录态打开 `/app/integrations`，确认服务治理层展示 8 个治理项、观测覆盖 94%、Metrics/Logs/Traces 信号覆盖、错误预算和服务来源；点击第一条治理项“创建任务”后，`POST /api/v1/operations/integrations/resync` 返回 201，并在 `/app/tasks` 出现 P0“接口重同步任务 - 应收与信用服务”。桌面与移动端横向溢出均为 0，控制台错误数为 0，异常请求数为 0，HTTP 4xx/5xx 响应数为 0。

### 数据质量治理工作台

本轮新增网页审核截图位于 `output/playwright/data-quality-governance-1780969703241/`：

| 截图 | 路径 |
| --- | --- |
| 桌面数据质量治理工作台 | `output/playwright/data-quality-governance-1780969703241/desktop-data-quality.png` |
| 创建整改任务后的任务队列 | `output/playwright/data-quality-governance-1780969703241/desktop-tasks-after-remediation.png` |
| 移动端数据质量治理工作台 | `output/playwright/data-quality-governance-1780969703241/mobile-data-quality.png` |

该审核使用真实登录态打开 `/app/data-quality`，确认页面展示“质量测试、责任人和整改 SLA”、质量问题队列、整改运行手册和数据血缘链路；点击“创建首要整改”后，`POST /api/v1/operations/data-quality/remediation` 返回 201，并在 `/app/tasks` 出现“数据质量整改 - 采购单停留在草稿或待审批”。桌面与移动端横向溢出均为 0，控制台错误数为 0，异常请求数为 0，HTTP 4xx/5xx 响应数为 0。

### 质量检验治理工作台

本轮新增网页审核截图位于 `output/playwright/quality-inspection-governance-1780989292960/`：

| 截图 | 路径 |
| --- | --- |
| 桌面质量检验治理台 | `output/playwright/quality-inspection-governance-1780989292960/desktop-quality-ready.png` |
| 创建质量检验任务后 | `output/playwright/quality-inspection-governance-1780989292960/desktop-quality-after-task.png` |
| 任务队列接收质量检验任务 | `output/playwright/quality-inspection-governance-1780989292960/desktop-tasks-quality-task.png` |
| 移动端质量检验治理台 | `output/playwright/quality-inspection-governance-1780989292960/mobile-quality-ready.png` |

该审核使用真实登录态打开 `/app/quality`，确认页面消费 `/operations/quality-inspection` 的后端权威质量检验合同，展示 4 条检验泳道、14 条检验队列、8 张供应商质量卡、4 个缺陷分类、10 个检验批、8 份质量证据、4 个服务边界、4 条质量流程和 4 条 Runbook；点击队列内“创建任务”后，`POST /api/v1/operations/quality-inspection` 返回 201，并在 `/app/tasks` 出现质量检验任务。质量评分已按待决策批次、低水位物料、未闭环任务和供应商风险动态计算，本次为 65.3%，不再把待检风险显示成满分。桌面与移动端横向溢出均为 0，细小按钮问题为 0，控制台错误数、异常请求数和 HTTP 4xx/5xx 响应数均为 0。

### 关键页面网页取样复审

本轮新增网页取样审核截图位于 `output/playwright/web-review-1780997929715/`：

| 截图 | 路径 |
| --- | --- |
| 桌面总览首屏 | `output/playwright/web-review-1780997929715/desktop-overview-viewport.png` |
| 桌面采购协同控制台首屏 | `output/playwright/web-review-1780997929715/desktop-procurement-viewport.png` |
| 移动端总览首屏 | `output/playwright/web-review-1780997929715/mobile-overview-viewport.png` |
| 移动端采购协同控制台首屏 | `output/playwright/web-review-1780997929715/mobile-procurement-viewport.png` |

该审核使用真实登录态打开 `/app/overview`、`/app/procurement/orders`、`/app/sales/orders`、`/app/inventory/stock`、`/app/finance/receivables` 和 `/app/reports`，桌面与移动端共 12 次取样。结果为失败数 0，横向溢出 0，文字撑破 0，越界元素 0，控制台错误 0，HTTP 4xx/5xx 响应 0；桌面和移动端均保留真实工业现场图片、业务动作入口、图表和经营账本。

### 采购协同控制台

本轮新增网页审核截图位于 `output/playwright/procurement-control-upgrade-1780996622570/`：

| 截图 | 路径 |
| --- | --- |
| 桌面采购协同控制台首屏 | `output/playwright/procurement-control-upgrade-1780996622570/desktop-procurement-viewport.png` |
| 桌面采购协同控制台全页 | `output/playwright/procurement-control-upgrade-1780996622570/desktop-procurement-full.png` |
| 移动端采购协同控制台首屏 | `output/playwright/procurement-control-upgrade-1780996622570/mobile-procurement-viewport.png` |
| 移动端采购协同控制台全页 | `output/playwright/procurement-control-upgrade-1780996622570/mobile-procurement-full.png` |

该审核使用真实登录态打开 `/app/procurement/orders`，确认页面消费 `/operations/procurement-control` 的后端权威采购协同合同，展示 6 条采购泳道、8 张前屏控制任务卡、6 个到货窗口、6 张供应商风险卡、5 个服务边界、4 个部署检查、2 个图表和 12 行采购账本；桌面与移动端横向溢出均为 0，文字撑破和越界卡片均为 0，控制台错误数和 HTTP 4xx/5xx 响应数均为 0。

### 供应商协同与资质风险工作台

本轮新增网页审核截图位于 `output/playwright/supplier-collaboration-1781009953815/`，并已稳定沉淀到 `docs/images/final/`：

| 截图 | 路径 |
| --- | --- |
| 桌面供应商协同首屏 | `output/playwright/supplier-collaboration-1781009953815/desktop-supplier-collaboration-viewport.png` |
| 桌面供应商协同全页 | `output/playwright/supplier-collaboration-1781009953815/desktop-supplier-collaboration-full.png` |
| 移动端供应商协同首屏 | `output/playwright/supplier-collaboration-1781009953815/mobile-supplier-collaboration-viewport.png` |
| 移动端供应商协同全页 | `output/playwright/supplier-collaboration-1781009953815/mobile-supplier-collaboration-full.png` |
| 最终桌面稳定截图 | `docs/images/final/final-dark-supplier-collaboration.png` |
| 最终移动稳定截图 | `docs/images/final/final-mobile-supplier-collaboration.png` |

该审核使用真实登录态打开 `/app/suppliers/performance`，确认 `/operations/supplier-collaboration` 返回 200，页面展示 5 条协同泳道、8 个可派发任务、8 张供应商 360 卡、8 个到货窗口、5 个服务边界、4 个部署检查、5 个流程节点、80 行供应商账本和 2 个图表。桌面与移动端横向溢出、文字撑破、越界卡片、可见重叠、控制台错误、有效失败请求和 HTTP 4xx/5xx 响应均为 0。

### 规则治理工作台

本轮新增网页审核截图位于 `output/playwright/rules-governance-1780973553475/` 和 `output/playwright/rules-decision-table-1780973745905/`：

| 截图 | 路径 |
| --- | --- |
| 桌面规则治理工作台 | `output/playwright/rules-governance-1780973553475/desktop-rules-before.png` |
| 创建复核任务后的规则页 | `output/playwright/rules-governance-1780973553475/desktop-rules-after-review.png` |
| 任务队列接收规则复核任务 | `output/playwright/rules-governance-1780973553475/desktop-tasks-rule-review.png` |
| 移动端规则治理工作台 | `output/playwright/rules-governance-1780973553475/mobile-rules-before.png` |
| 桌面规则决策表可见截图 | `output/playwright/rules-decision-table-1780973745905/desktop-decision-table.png` |

该审核使用真实登录态打开 `/app/rules`，确认页面展示规则健康、DMN 决策表、输入/输出列、命中行、风险决策队列、规则微服务拆分面和闭环链路；点击“创建首要复核”后，`POST /api/v1/operations/rules/review` 返回 201，并在 `/app/tasks` 出现“规则复核”。桌面与移动端横向溢出均为 0，控制台错误数为 0，HTTP 4xx/5xx 响应数为 0。

### 产能计划治理中心

本轮新增网页审核截图位于 `output/playwright/capacity-governance-1780979251443/`：

| 截图 | 路径 |
| --- | --- |
| 桌面产能计划中心 | `output/playwright/capacity-governance-1780979251443/desktop-capacity-before.png` |
| 创建产能复核任务后 | `output/playwright/capacity-governance-1780979251443/desktop-capacity-after-review.png` |
| 任务队列接收产能复核任务 | `output/playwright/capacity-governance-1780979251443/desktop-tasks-capacity-review.png` |
| 移动端产能计划中心 | `output/playwright/capacity-governance-1780979251443/mobile-capacity-before.png` |

该审核使用真实登录态打开 `/app/capacity`，确认页面消费 `/operations/capacity` 的后端权威产能合同，展示需求、供给、齐套、释放能力、4 个工作中心、4 条瓶颈队列、4 个服务边界和 4 条 Runbook；点击“创建首要复核”后，`POST /api/v1/operations/capacity/review` 返回 201，并在 `/app/tasks` 出现“装配履约窗口产能复核”。桌面图表/图标节点 25 个、移动端 17 个，图表模式按钮宽度 `[72,72,72]` 已确认紧凑，成功 Toast 位于顶部导航下方，桌面与移动端横向溢出均为 0，控制台错误数、异常请求数和 HTTP 4xx/5xx 响应数均为 0。

### 设备可靠性治理工作台

本轮新增网页审核截图位于 `output/playwright/maintenance-reliability-1780984911955/`：

| 截图 | 路径 |
| --- | --- |
| 桌面设备可靠性治理台 | `output/playwright/maintenance-reliability-1780984911955/desktop-maintenance-ready.png` |
| 创建设备维护工单后 | `output/playwright/maintenance-reliability-1780984911955/desktop-maintenance-after-workorder.png` |
| 任务队列接收维护工单 | `output/playwright/maintenance-reliability-1780984911955/desktop-tasks-maintenance-workorder.png` |
| 移动端设备可靠性治理台 | `output/playwright/maintenance-reliability-1780984911955/mobile-maintenance-ready.png` |

该审核使用真实登录态打开 `/app/maintenance`，确认页面消费 `/operations/maintenance` 的后端权威设备可靠性合同，展示 4 条资产线、10 条维护工单候选、10 条 MRO 关键备件、4 名维修人员、4 个停机窗口、4 个设备微服务边界、4 条维护流程和 4 条 Runbook；点击队列内“创建设备维护工单”后，`POST /api/v1/operations/maintenance-workorder` 返回 201，并在 `/app/tasks` 出现“设备维护工单 - 工控屏面板 A型-0004备件保障复核”。本轮同时修复成功 Toast 关闭按钮触控尺寸和任务/通知长标题移动端换行问题，复审确认 `tinyButtonIssues=0`、维护队列主按钮最小高度 60px、全站布局审计 66 项通过，桌面与移动端横向溢出均为 0，控制台错误数、异常请求数和 HTTP 4xx/5xx 响应数均为 0。

### 移动扫码终端治理工作台

本轮新增网页审核截图位于 `output/playwright/mobile-terminal-governance-1780982319037/`：

| 截图 | 路径 |
| --- | --- |
| 桌面移动扫码终端治理台 | `output/playwright/mobile-terminal-governance-1780982319037/desktop-mobile-terminal-ready.png` |
| 创建现场扫码任务后 | `output/playwright/mobile-terminal-governance-1780982319037/desktop-mobile-terminal-after-task.png` |
| 任务队列接收现场扫码任务 | `output/playwright/mobile-terminal-governance-1780982319037/desktop-tasks-mobile-task.png` |
| 移动端移动扫码终端治理台 | `output/playwright/mobile-terminal-governance-1780982319037/mobile-mobile-terminal-ready.png` |

该审核使用真实登录态打开 `/app/mobile-terminal`，确认页面消费 `/operations/mobile-terminal` 的后端权威移动现场合同，展示 4 条现场泳道、40 条扫码队列、4 台设备会话、4 个库区覆盖、4 条扫码到审计流程、4 个移动微服务边界和 4 条现场执行手册；点击队列内“创建任务”后，`POST /api/v1/operations/mobile-terminal/task` 返回 201，并在 `/app/tasks` 出现“现场扫码任务 - 铜排连接件 A型-0051”。本轮同时修复扫码队列主选择按钮高度过低的问题，复审确认 `tinyButtonIssues=0`、队列主按钮最小高度 60px，桌面与移动端横向溢出均为 0，控制台错误数、异常请求数和 HTTP 4xx/5xx 响应数均为 0。

### 预算成本治理中心

本轮新增网页审核截图位于 `output/playwright/budget-governance-1780976362599/` 和 `output/playwright/webpage-review-1780976875726/`：

| 截图 | 路径 |
| --- | --- |
| 桌面预算成本中心 | `output/playwright/budget-governance-1780976362599/desktop-budget-before.png` |
| 创建成本复核任务后 | `output/playwright/budget-governance-1780976362599/desktop-budget-after-review.png` |
| 任务队列接收预算复核任务 | `output/playwright/budget-governance-1780976362599/desktop-tasks-budget-review.png` |
| 移动端预算成本中心 | `output/playwright/budget-governance-1780976362599/mobile-budget-before.png` |
| Toast 修复后二次复审 | `output/playwright/webpage-review-1780976875726/desktop-budget-after-review.png` |

该审核使用真实登录态打开 `/app/budget`，确认页面展示预算、实际消耗、采购承诺、可用预算、成本中心、差异队列、预算瀑布、库存成本结构、服务边界和 Runbook；点击“创建首要复核”后，`POST /api/v1/operations/costs/review` 返回 201，并在 `/app/tasks` 出现“经营毛利护栏预算差异复核”。二次网页复审同时确认成功 Toast 已从顶部导航下移到 98px，`toastBelowTopbar=true`，桌面与移动端横向溢出均为 0，控制台错误数、异常请求数和 HTTP 4xx/5xx 响应数均为 0。

## 4. 截图覆盖矩阵

| 路由 | 桌面图表 | 移动图表 | 横向溢出 |
| --- | ---: | ---: | ---: |
| `/app/overview` | 14 | 14 | 0 |
| `/app/metrics` | 6 | 6 | 0 |
| `/app/tasks` | 4 | 4 | 0 |
| `/app/inventory/products` | 4 | 4 | 0 |
| `/app/inventory/stock` | 2 | 2 | 0 |
| `/app/inventory/replenishment` | 2 | 2 | 0 |
| `/app/sales/orders` | 2 | 2 | 0 |
| `/app/procurement/orders` | 2 | 2 | 0 |
| `/app/suppliers/performance` | 4 | 4 | 0 |
| `/app/dispatch` | 2 | 2 | 0 |
| `/app/data-quality` | 2 | 2 | 0 |
| `/app/quality` | 2 | 2 | 0 |
| `/app/customers` | 4 | 4 | 0 |
| `/app/capacity` | 2 | 2 | 0 |
| `/app/maintenance` | 2 | 2 | 0 |
| `/app/contracts` | 2 | 2 | 0 |
| `/app/service` | 2 | 2 | 0 |
| `/app/rules` | 4 | 4 | 0 |
| `/app/integrations` | 4 | 4 | 0 |
| `/app/budget` | 6 | 6 | 0 |
| `/app/mobile-terminal` | 2 | 2 | 0 |
| `/app/finance/receivables` | 2 | 2 | 0 |
| `/app/finance/credits` | 2 | 2 | 0 |
| `/app/stocktakes` | 2 | 2 | 0 |
| `/app/reports` | 12 | 12 | 0 |
| `/app/files` | 4 | 4 | 0 |
| `/app/content/articles` | 2 | 2 | 0 |
| `/app/system/users` | 2 | 2 | 0 |
| `/app/system/audit` | 2 | 2 | 0 |
| `/app/notifications` | 4 | 4 | 0 |
| `/app/ai` | 12 | 12 | 0 |
| `/app/profile` | 6 | 6 | 0 |
| `/app/settings` | 0 | 0 | 0 |

## 5. 本轮视觉验收重点

- 总览页：真实工业现场图、经营 KPI、业务动作、ECharts 图表和业务账本在桌面端形成完整首屏。
- 全量页面成熟度：33 条路由在桌面与移动双视口共 66 项检查全部通过，所有页面均满足现场图、工作流入口、当班交接、业务数据行、操作表面、内容密度和响应式稳定性要求。
- 更多菜单：顶部“创建”和“更多模块”、桌面 Dock 更多入口均具备展开状态、焦点落点、外部点击关闭、Escape 关闭和真实跳转证据，移动端保留顶部更多入口作为模块地图主入口。
- 服务与集成页：售后服务中心补齐响应就绪业务数据面，集成监控中心将运行探针显示为业务语义标签，避免真实接口名干扰页面成熟度审计。
- 每日制造经营作战流：新增班次指挥、开放动作、证据留痕、P0/P1/P2 执行队列、角色指挥席、现场事件流、前后端 API 合同、服务边界、部署前检查和“全部 / 关注 / 阻塞”筛选。
- 设置页部署就绪：新增上线就绪分、ERP 成熟度验收、能力域地图、微服务拓扑、动态部署检查、微服务拆分快照、交付证据、运行时条和可复制 runbook，生产 secret 只显示状态与动作，不暴露真实值。
- 部署预检任务闭环：attention/blocked 检查项可直接创建系统通知并进入审计日志，设置页不再只是只读部署说明。
- 通知任务完成闭环：任务卡新增详情、来源和处理完成动作，处理结果回写通知状态并留审计证据。
- 任务异常中心：当班队列聚合通知、部署、库存和采购任务，前屏优先露出可执行动作，并完成创建任务到处理完成的真实网页点击流。
- 集成治理：服务目录不再只读，新增 SLO/错误预算/观测信号治理层，治理项可直接创建接口重同步任务并进入当班任务队列。
- 数据质量治理：页面不再由前端临时拼接 5 个资源列表，而是消费 `/operations/data-quality` 的后端权威质量合同，展示维度评分、失败测试、整改 SLA、Runbook、血缘链路，并可创建整改任务进入当班任务队列。
- 质量检验治理：质量页不再由前端临时拼接供应商、采购、库存和附件列表，而是消费 `/operations/quality-inspection` 的后端权威检验合同，展示检验批、供应商质量、缺陷分类、使用决策、质量证据、服务边界和 Runbook；创建检验任务返回 201 并进入任务异常中心。
- 采购协同治理：采购页不再只是审批队列、收货月台和采购账本，而是消费 `/operations/procurement-control` 的后端权威合同，展示补货、审批、供应商确认、收货质检、预算承诺、服务边界和部署检查；控制队列可创建采购协同任务并写入通知与审计。
- 供应商协同治理：供应商绩效页不再只是供应商列表和雷达图，而是消费 `/operations/supplier-collaboration` 的后端权威合同，展示资质准入、交付 SLA、质量 CAPA、商务集中度、供应商 360、服务边界和部署检查；协同项可创建通知任务并进入任务异常中心。
- 规则治理：规则引擎不再只是列表和图表，页面消费 `/operations/rules` 的后端权威规则合同，展示 DMN 决策表、输入/输出列、命中行、复核队列、规则服务边界和闭环链路；创建复核任务返回 201 并进入任务异常中心。
- 产能计划治理：产能页不再由前端临时拼接需求/采购/库存数据，而是消费 `/operations/capacity` 的后端权威产能合同，展示销售需求、采购供给、物料齐套、工作中心负载、瓶颈复核队列、服务边界和 Runbook；创建复核任务返回 201 并进入任务异常中心。
- 设备可靠性治理：设备维护页不再只是备件图表和简单队列，而是消费 `/operations/maintenance` 的后端权威可靠性合同，展示资产线、维护工单、MRO 备件、维修人员、停机窗口、服务边界和 Runbook；创建设备维护工单返回 201 并进入任务异常中心。
- 移动扫码终端治理：页面不再是简单饼图和任务池，而是消费 `/operations/mobile-terminal` 的后端权威移动现场合同，展示收货、盘点、发货、异常复核四条泳道、设备会话、库区覆盖、扫码队列、服务边界和现场 Runbook；创建现场扫码任务返回 201 并进入任务异常中心。
- 预算成本治理：预算成本页不再只是成本图表，页面消费 `/operations/costs` 的后端权威成本合同，展示预算/实际/承诺/可用预算、成本中心、差异复核队列、预算瀑布、库存成本结构、服务边界和 Runbook；创建复核任务返回 201 并进入任务异常中心，Toast 已通过二次网页复审确认不遮挡顶部导航。
- 关键页面网页复审：`/app/overview`、`/app/procurement/orders`、`/app/sales/orders`、`/app/inventory/stock`、`/app/finance/receivables` 和 `/app/reports` 的桌面/移动 12 张截图已复核，HTTP 错误、控制台错误、有效失败请求、文字撑破、越界元素和横向溢出均为 0。
- 采购审批：状态胶囊、采购单号、供应商/仓库和金额重新形成工作卡层级，移动端按钮触控节奏已收口。
- 亮色主题：不是简单反白，保留现场图片、卡片层次和图表可读性。
- 移动端：顶部操作栏、Hero、动作按钮、现场图片、卡片和图表均无横向溢出。
- 动效系统：路由入场、Hero 揭示、卡片 spotlight、按钮按压、Dock 弹性和图表唤醒均受 `prefers-reduced-motion` 约束。

## 6. 复现命令

```powershell
# 完整交付闸门
powershell -ExecutionPolicy Bypass -File scripts\quality-gate.ps1

# 仅布局和截图审核
$env:NEXUS_AUDIT_SCREENSHOTS="all"
cd frontend
npm run audit:layout

# 全量页面成熟度审核
npm run audit:completeness

# 更多菜单和快捷创建专项审核
npm run audit:more-menus

# 供应商协同专项审核
npm run audit:supplier
```

完成截图更新后必须重新运行：

```powershell
venv\Scripts\python.exe scripts\generate_final_report_docx.py
venv\Scripts\python.exe scripts\audit-delivery-assets.py --json-output output\quality-gate\delivery-assets.json
```

