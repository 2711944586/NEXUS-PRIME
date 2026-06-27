# NEXUS Prime 生产就绪升级报告

日期：2026-06-28  
项目：NEXUS Prime 制造业 ERP 管理信息系统  
目标：把登录后的主页面和业务页从“堆叠式驾驶舱”重构为简洁、真实、有业务流的 ERP 工作台。

## 1. 本轮结论

本轮已完成登录后体验的减法重构：应用壳层不再在每个页面强制插入执行总账、资源工作台、证据带和右侧上下文，页面主体回到“一个页面只做一个业务对象”的结构。总览页从原先超长的多图表拼贴改为控制塔快照，保留真实现场照片、核心 KPI、六步业务闭环、经营趋势、当班待办和模块边界。

核心结果：

- 首页、登录页、注册页的高质感工业照片语言已延伸到登录后页面。
- 登录后导航收敛为核心模块入口，其它页面进入“更多模块”。
- 总览页由 1200 多行复杂模板压缩为清晰的 ERP 控制塔组件。
- 页面继续使用真实后端接口：`erp/control-tower`、`manufacturing/command-center`、`manufacturing/workflow-board`。
- Angular 生产构建已通过，后端 207 个 pytest 已通过。
- 33 条登录后业务路由完成桌面与移动端截图，`docs/images/final/pages/manifest.json` 记录 66 条截图索引。
- 图片审计确认 37 张本地 JPG、25 个页面实际使用图片来源，无远程图片、无 generic alt、无 broken image。
- GitHub ERP skill 已安装并手动调用学习：`saas-erp-system-design`、`database-design-engineering`、`microservices-architecture`、`deployment-release-engineering`。

## 2. GitHub ERP Skill 使用记录

用户要求在 GitHub 搜索 ERP 相关 skill，自行下载学习并调用。本轮已完成：

| 动作 | 结果 |
| --- | --- |
| GitHub 搜索 | 检索到 ERP/SaaS、SAP ERP 连接器、ERPNext/Frappe 等相关 skill 来源。 |
| 采用来源 | `peterbamuhigire/skills-web-dev`。 |
| 已安装 skill | `saas-erp-system-design`、`modular-saas-architecture`、`multi-tenant-saas-architecture`、`database-design-engineering`、`microservices-architecture`、`deployment-release-engineering`。 |
| 本轮调用方式 | 已直接读取本地 `SKILL.md`，并按 ERP 业务生命周期、数据库边界、微服务边界和发布工程清单应用到页面减法、审计和文档。 |

ERP skill 的关键设计准则已落实到本项目：

- ERP 页面不能只做 CRUD 卡片，必须围绕业务对象生命周期组织。
- 重要流程要有状态：草稿、审批、执行、入账/归档、撤销/修正。
- 交易、配置、主数据、审计、报表投影要区分。
- 当前系统保守采用“微服务就绪的模块化单体”，不假装已经拆成分布式微服务。
- 页面不再把所有模块内容堆到同一屏，主流程入口交给对应模块处理。

## 3. 视觉与信息架构减法

### 原问题

登录后页面存在以下问题：

- 全局 shell 在每个页面插入多套重复内容，造成页面像调试面板。
- 总览页重复出现健康度、流程、风险、图表、证据和角色指挥席。
- 小卡片过多，视觉焦点被稀释，首屏无法判断下一步动作。
- 真实图片资源已经存在，但很多业务页没有形成统一的工业现场质感。
- 导航入口太多，用户不知道应该先处理哪个模块。

### 本轮修改

| 文件 | 修改 |
| --- | --- |
| `frontend/src/app/shell/app-shell.component.ts` | 删除默认渲染的 workflow strip、execution ledger、page evidence、resource workbench、context panel。 |
| `frontend/src/app/pages/command-center.page.ts` | 重写总览页为轻量 ERP 控制塔。 |
| `frontend/src/app/core/navigation.ts` | 顶部只保留核心模块入口：运营、物料、采购、履约、应收、报表。 |
| `frontend/src/styles/_erp-simplified-workspace.scss` | 新增登录后统一质感层：真实图片 hero、简洁卡片、单列壳层、清晰响应式。 |
| `frontend/src/styles.scss` | 将新样式层放到最后加载，覆盖旧的杂乱样式。 |

## 4. 前端代码解析

### 应用壳层

`AppShellComponent` 现在只负责：

- 顶部品牌、搜索、健康状态、刷新、主题、头像和退出。
- 核心 Dock 导航。
- 当前路由页面的 `<router-outlet />`。
- “更多模块”面板。

它不再负责把业务上下文强行展示在所有页面中。这样后续维护时，采购页只维护采购，销售页只维护销售，报表页只维护报表。

### 总览页

`CommandCenterPage` 现在只保留 6 个信息层：

1. 真实现场图和 ERP 控制塔标题。
2. 经营控制分。
3. 低库存、待审批采购、逾期应收、库存水位 4 个 KPI。
4. 库存信号到经营归档的 6 步业务流。
5. 经营趋势图和当班待办。
6. ERP 模块边界和真实工作流照片。

数据仍来自后端：

```text
GET /api/v1/erp/control-tower
GET /api/v1/manufacturing/command-center
GET /api/v1/manufacturing/workflow-board
```

### 样式层

`_erp-simplified-workspace.scss` 是本轮主要视觉维护点。它做了三件事：

- 把登录后工作区改成单列主内容布局。
- 给各业务 hero 绑定真实工业图片，例如仓配、采购、履约、质量、售后、预算。
- 对总览页提供专属控制塔、KPI、流程、图表、待办和证据图样式。

后续如果继续优化业务页，优先在这个文件中调全局质感，再进入具体页面组件。

## 5. 后端与数据库说明

当前后端已经是 Flask REST API，前端通过 `/api/v1` 访问，不直接读数据库。数据库由 SQLAlchemy 模型和 Alembic 迁移维护。

核心路径：

- `backend/app/api/`：REST 路由和聚合接口。
- `backend/app/domains/`：微服务就绪能力域。
- `backend/app/models/`：身份、库存、采购、销售、财务、盘点、内容、报表、AI、通知、审计等模型。
- `backend/app/services/`：业务服务和应用逻辑。
- `backend/migrations/`：数据库迁移。
- `backend/tests/`：后端测试。

ER 图：

- 源文件：`docs/er.mmd`
- 图片：`docs/images/final/er-diagram.svg`
- 截图：`docs/images/final/er-diagram.png`

![ER 图](images/final/er-diagram.svg)

主要闭环：

- 物料和仓库通过库存数量、库存余额、库存流水、补货建议连接。
- 补货建议可以转采购单，采购单推进审批、到货、质检和入库。
- 销售订单推进发货后进入应收，应收再通过收款、信用释放和对账完成财务闭环。
- 盘点单、盘点明细、盘点历史形成库存修正与审计链路。
- 通知、审计、报表和 AI 分析作为横向平台能力，不污染交易模型。

## 6. 微服务与可维护性边界

本项目当前不把微服务写成口号。当前部署仍是一个 Flask API，但代码已按以下边界组织：

| 未来服务 | 当前边界 | 拆分条件 |
| --- | --- | --- |
| Identity/Auth | 用户、角色、权限、会话、CSRF | 多租户、SSO、统一身份中心。 |
| Inventory | 物料、仓库、库存流水、补货、盘点 | 库存写入吞吐独立增长，需要锁库存服务。 |
| Procurement | 采购单、供应商绩效、收货窗口 | 采购审批和供应商门户独立上线。 |
| Sales/Fulfillment | 销售订单、发货、客户窗口 | 履约链路与库存事件异步化。 |
| Finance | 应收、收款、信用、对账 | 财务权限、审计和报表独立治理。 |
| Reports/AI | 报表任务、AI 会话、行动草稿 | 任务队列、限流、模型网关独立伸缩。 |
| Files/Content | 文件、公告、附件、知识库 | 对象存储、CDN、扫描和下载审计独立治理。 |

## 7. 页面操作路径

推荐演示流程：

1. 打开首页，展示真实工业视觉和品牌质感。
2. 进入登录页，使用 `admin@nexus.com / admin123`。
3. 进入 `/app/overview`，先看经营控制分和 4 个核心 KPI。
4. 点击“处理低库存”，进入 `/app/inventory/replenishment`。
5. 点击“审批采购”，进入 `/app/procurement/orders`。
6. 进入 `/app/sales/orders`，展示发货和应收联动。
7. 进入 `/app/finance/receivables`，展示账龄、收款、信用风险。
8. 进入 `/app/reports`，展示报表生成和归档。
9. 打开更多模块，展示质量、产能、设备、合同、售后、集成、移动扫码等扩展能力。
10. 最后打开 `docs/images/final/er-diagram.svg` 和本报告说明架构。

## 8. 验证记录

本轮已执行并通过：

```powershell
cd frontend
npm run audit:layout
npm run audit:workflow-links
npm run audit:completeness
npm run audit:visual-assets
npm run audit:theme-contrast
npm run audit:shell
npm run audit:charts
npm run audit:api-contract
npm run audit:topbar
npm run audit:more-menus
npm run audit:supplier
npm run audit:deployment-readiness
npm run api:check
npm run build
npm run capture:final-screenshots
```

结果：全部通过。最终截图脚本刷新了 `docs/images/final/`，截图索引为 66 条，页面截图目录含 102 张 PNG。

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
```

结果：`207 passed`。

最新审计证据：

| 审计 | 报告 |
| --- | --- |
| 布局 | `output/playwright/layout-audit-1782581461815/report.json` |
| 工作流链接 | `output/playwright/workflow-link-audit-1782581643833/report.json` |
| 完整度 | `output/playwright/completeness-audit-1782581707771/report.json` |
| 真实图片 | `output/playwright/visual-assets-audit-1782581940592/report.json` |
| 主题对比 | `output/playwright/theme-contrast-audit-1782582039323/report.json` |
| Shell 交互 | `output/playwright/shell-interaction-1782582085025/report.json` |
| API 合同 | `output/playwright/api-contract-audit-1782582119272/report.json` |
| 顶部栏 | `output/playwright/topbar-operations-audit-1782582129058/report.json` |
| 更多菜单 | `output/playwright/more-menu-audit-1782582228527/report.json` |
| 供应商专项 | `output/playwright/supplier-collaboration-1782582291918/report.json` |
| 部署准备 | `output/playwright/deployment-readiness-audit-1782582343660/report.json` |

## 9. 交付文件索引

| 文件 | 用途 |
| --- | --- |
| `README.md` | 项目总说明和运行命令。 |
| `docs/final-delivery-report.md` | 最终交付报告。 |
| `docs/project_report.md` | 课程项目汇报。 |
| `docs/production-upgrade-report-2026-06-28.md` | 本轮生产就绪升级报告。 |
| `docs/operator-guide.md` | 操作指南。 |
| `docs/code-review-production-readiness.md` | Code review 和风险修复记录。 |
| `docs/deployment-mainland-cn.md` | 中国大陆前后端分离部署指南。 |
| `docs/final-video-script.md` | 讲解视频稿。 |
| `docs/er.mmd` | ER 图源文件。 |
| `docs/images/final/` | 截图和 ER 图图片。 |
