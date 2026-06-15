# 前端与工作流升级研究记录

日期：2026-06-08 至 2026-06-09

## 1. 参考资料

本轮设计优化参考了以下公开资料，并把原则落到代码：

| 来源 | 采用原则 | 落地位置 |
| --- | --- | --- |
| SAP Fiori Design Principles：<https://experience.sap.com/fiori-design-web/design-principles/> | 企业应用应角色化、适配不同设备，并围绕用户当下任务组织内容。 | 总览页新增 5 个 `role_command_center` 责任座席，把运营、仓配采购、履约、财务风控和经营分析拆成可执行视角。 |
| Microsoft Dynamics 365 Procurement and sourcing overview：<https://learn.microsoft.com/en-us/dynamics365/supply-chain/procurement/procurement-sourcing-overview> | 采购应覆盖需求、审批、供应商选择、采购订单、收货、发票与付款，并按业务政策配置工作流。 | 采购页新增 `/operations/procurement-control` 合同，把补货、审批、供应商确认、收货质检、预算承诺和绩效回写放到同一控制台。 |
| Oracle Fusion Cloud Procurement：<https://www.oracle.com/erp/procurement/> | 采购工作台应集中采购状态、供应商、金额、异常和供应商协同能力。 | 采购控制台新增控制队列、供应商风险卡、到货窗口、服务边界和部署检查，采购风险项可创建通知任务并进入审计。 |
| Microsoft Fluent 2 Motion：<https://fluent2.microsoft.design/motion> | 动效应表达反馈、层级和连续性，避免让用户失去对状态变化的理解。 | 工作流新增角色座席、事件流和 API 合同卡的统一 spotlight、入场和 hover 反馈。 |
| Ant Design Data Display：<https://ant.design/docs/spec/data-display/> | 数据展示应按重要性、操作频率和关联程度组织，先给用户最需要处理的对象。 | 新增“每日制造经营作战流”，把库存、补货、采购、收货、履约、回款、报表、审计按真实业务顺序排布。 |
| Material Design Motion：<https://m3.material.io/styles/motion/overview> | 动效必须表达状态变化和空间关系，不能干扰任务完成。 | `motion-system.scss` 与 `workflow-board.scss` 只使用 transform、opacity、filter、box-shadow 和进度填充。 |
| Material Easing and Duration：<https://m3.material.io/styles/motion/easing-and-duration/overview> | 桌面交互应使用短时长、自然 easing，避免拖慢操作。 | `--motion-fast`、`--motion-base`、`--motion-ease-standard`、`--motion-ease-spring`。 |
| Atlassian Motion：<https://atlassian.design/foundations/motion/> | 企业工具动效应帮助用户理解反馈、层级和状态。 | 工作流阶段卡、阻塞点、交接条使用进入动画、hover 反馈和 reduced-motion 兜底。 |
| IBM Carbon Dashboards：<https://v10.carbondesignsystem.com/data-visualization/dashboards/> | 仪表盘应围绕决策层级、关键状态和可行动指标组织，不把图表当装饰。 | 新增班次执行控制层、动作队列、部署检查和服务边界，把总览从 KPI 展示升级为可执行控制台。 |
| PrimeNG Button：<https://primeng.org/button> | 企业后台写操作需要明确 loading/disabled 状态，避免重复提交。 | 设置页部署检查项的“创建任务”按钮使用 loading 与禁用状态，等待接口返回后恢复。 |
| PrimeNG Toast：<https://primeng.org/toast> | 页面内写操作应给出非阻塞反馈，不使用浏览器 alert。 | 部署预检任务创建成功/失败都通过 MessageService toast 反馈。 |
| Angular Signals：<https://angular.dev/guide/signals> | 轻量页面状态可用 signal/computed 管理，避免为局部按钮状态引入新状态库。 | `deploymentTaskCreating`、`deploymentTaskCreated` 与部署检查 computed 沿用设置页信号状态。 |
| Vercel Environment Variables：<https://vercel.com/docs/environment-variables> | 前端公开变量和后端敏感变量必须分离，敏感值写入后端项目。 | 设置页新增动态部署就绪看板，检查 `NEXUS_API_BASE_URL`、`DATABASE_URL`、`SECRET_KEY` 等边界。 |
| Supabase Database Connection：<https://supabase.com/docs/guides/database/connecting-to-postgres> | 生产数据库连接串应从 Supabase 项目连接信息获取，并优先使用适合部署环境的连接模式。 | 部署就绪 API 检查 `DATABASE_URL`，部署手册继续要求 Supabase PostgreSQL Pooler URL。 |
| Google SRE Workbook - Implementing SLOs：<https://sre.google/workbook/implementing-slos/> | 服务治理应围绕 SLI/SLO、错误预算和用户影响，而不是只看“是否在线”。 | 集成监控新增错误预算、SLO 延迟和 P0/P1/P2 治理队列。 |
| OpenTelemetry Signals：<https://opentelemetry.io/docs/concepts/signals/> | 观测体系需要 metrics、logs、traces 等信号共同支撑故障定位。 | `/operations/integrations` 返回 Metrics/Logs/Traces 覆盖率和信号缺口。 |
| Atlassian Incident Management Runbooks：<https://www.atlassian.com/incident-management/incident-response/runbook> | 事故处理要把 runbook、owner 和后续动作变成可执行任务。 | 集成治理项可一键创建接口重同步任务，并进入通知与当班任务队列。 |
| OpenMetadata Data Quality：<https://docs.open-metadata.org/latest/how-to-guides/data-quality-observability/quality> | 数据质量应由测试、失败项、覆盖率和可追踪证据驱动，而不是只显示人工评分。 | `/operations/data-quality` 返回失败测试、维度覆盖、整改队列和测试套件。 |
| Google SRE Workbook - Alerting on SLOs：<https://sre.google/workbook/alerting-on-slos/> | 告警应按用户影响、阈值和持续性排序，避免让队列充满噪声。 | 数据质量整改队列按 P0/P1 和影响记录数进入前屏，只有可执行治理项生成任务。 |
| Camunda DMN Decision Table Hit Policy：<https://docs.camunda.org/manual/latest/reference/dmn/decision-table/hit-policy/> | 决策表需要明确输入、输出、规则行和 hit policy，才能解释为什么命中。 | `/operations/rules` 返回 DMN 风格 `decision_table`、`hit_policy`、输入列、输出列和命中行。 |
| Drools Decision Tables：<https://docs.drools.org/latest/drools-docs/drools/language-reference/index.html#decision-tables-con_drl-rules> | 企业规则不应藏在页面文案中，应有可复核的规则表、条件和动作输出。 | 规则引擎页从“规则列表”升级为决策表、风险队列和复核任务工作台。 |
| Atlassian Incident Escalation Policies：<https://support.atlassian.com/opsgenie/docs/create-and-manage-escalation-policies/> | 风险项需要 owner、SLA 和升级路径，避免停留在告警数字。 | 规则复核队列返回 owner、SLA、priority、escalation 和 runbook，并可创建任务。 |

## 2. Skills 使用记录

| Skill | 本轮用途 |
| --- | --- |
| `frontend-design` | 确定“工业运营作战流”方向：密集、真实、可操作，而不是营销式 Hero。 |
| `frontend-ui-engineering` | 控制组件状态、语义链接、响应式栅格、focus 和 reduced-motion。 |
| `redesign-existing-projects` | 审计现有页面仍偏展示型的问题，补齐功能型工作流面板。 |
| `skill-installer` | 查询可安装技能清单；curated 列表没有新的 Angular ERP 前端/动画专项 skill。2026-06-09 已安装最接近设计资产方向的 `figma-generate-design`，但本项目没有 Figma URL/MCP 上下文，本轮仍以本地 Angular 代码落地。 |
| `gpt-taste` | 采用其中关于密集 bento、错落动效、横向扫描和按钮对比度的思想，但不套用营销页 AIDA/GSAP，因为 ERP 控制台应优先服务重复作业效率。 |
| `playwright` | 后续用于真实浏览器截图、布局审计和控制台检查。 |

`skill-installer` 查询结果：curated 可安装列表包含 `figma-*`、`cloudflare-deploy`、`vercel-deploy`、`playwright` 等通用技能，没有新的 Angular ERP 前端/动画专项技能；experimental 路径当前返回 `Skills path not found`。2026-06-09 已执行安装：

```powershell
python C:\Users\13561\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo openai/skills --path skills/.curated/figma-generate-design
```

安装结果：`Installed figma-generate-design to C:\Users\13561/.codex\skills\figma-generate-design`。该 skill 需要重启 Codex 才能作为会话技能自动出现；当前项目未提供 Figma 文件，因此本轮继续使用已加载的前端设计技能，并把效果落到代码和浏览器截图。

## 3. 本轮新增功能

新增后端 API：

```text
GET /api/v1/manufacturing/workflow-board
GET /api/v1/operations/deployment-readiness
POST /api/v1/operations/deployment-readiness/task
GET /api/v1/operations/task-queue
POST /api/v1/operations/integrations/resync
GET /api/v1/operations/data-quality
POST /api/v1/operations/data-quality/remediation
GET /api/v1/operations/rules
POST /api/v1/operations/rules/review
GET /api/v1/operations/procurement-control
POST /api/v1/operations/procurement-control/task
POST /api/v1/notifications/complete
```

该接口由 `backend/app/services/analytics_service.py` 的 `manufacturing_workflow_board_payload()` 生成，按当前数据库实时聚合：

- 库存信号
- 补货建议
- 采购审批
- 收货入库
- 销售履约
- 应收回款
- 报表归档
- 审计追溯

返回数据包括：

- `summary`：健康分、关注数、阻塞数、下一步动作。
- `stages`：8 个阶段的负责人、SLA、进度、状态、记录样本和跳转路径。
- `handoffs`：阶段之间的跨模块交接。
- `bottlenecks`：当前阻塞和关注点。
- `action_queue`：按 P0/P1/P2 输出当班开放动作、负责人、SLA、证据和业务跳转路径。
- `service_boundaries`：把制造聚合、库存补货、采购履约、财务风控拆成可演进的微服务边界。
- `deployment_checks`：把认证审计、报表文件、通知待办、回款写入作为部署前可视化检查项。
- `role_views`：运营负责人、仓配采购、财务分析三类角色视图。
- `role_command_center`：5 个责任座席，包含 owner、workload、primary_metric、readiness、next_action、evidence 和 domains。
- `execution_events`：从库存预警、补货建议、采购、履约、应收、收款、报表和审计中抽取最近事件流。
- `data_contracts`：列出 `/manufacturing/command-center`、`/manufacturing/workflow-board`、`/health/ready` 和报表生成接口，说明前后端消费者、后端 provider、payload 和 readiness。

`/operations/deployment-readiness` 由 `backend/app/services/deployment_service.py` 生成，聚合：

- `/health` 的数据库、存储、AI、缓存和 Cookie/CORS 状态。
- `/operations/integrations` 的微服务目录、契约覆盖、依赖、部署单元和数据存储。
- 仓库部署资产：`frontend/vercel.json`、`backend/vercel.json`、`runtime-config.js`、部署脚本和质量闸门。
- 前后端边界：前端只允许公开 API 地址，后端保留数据库、密钥、AI 和存储 secret。

`/operations/deployment-readiness/task` 位于 `backend/app/api/experience.py`，接收检查项 `key`、`label`、`scope`、`status`、`evidence` 和 `action`，创建 `related_type='deployment_readiness'` 的系统通知，并写入 `operations / deployment_readiness_task` 审计日志。接口不接收、不返回任何真实 secret 值。

`/notifications/complete` 位于 `backend/app/api/notifications.py`，把通知任务标记为已处理，写入 `notifications / complete_task` 审计日志，并记录来源页面和处理说明。该接口让部署预检、库存预警、审批提醒等通知不再只是消息流，而能进入可追溯的处理闭环。

`/operations/task-queue` 位于 `backend/app/api/experience.py`，聚合未读通知、部署预检 attention/blocked 项、活跃库存预警和待审批采购单。接口按 P0 优先、同优先级可执行动作优先排序，返回 `summary`、`items`、`source_path`、`detail_path`、`action_kind` 和任务 payload，让任务异常中心能直接完成通知、创建部署任务或跳转到业务来源。

`/operations/integrations/resync` 继续保留为集成治理任务入口，并升级为接收 `service_id`、`owner`、`priority`、`evidence` 和 `action`。它把服务治理项创建为 `related_type='integration'` 的通知，写入 `operations / integration_resync` 审计日志；任务队列会把这类通知映射回 `/app/integrations`。

`/operations/data-quality` 位于 `backend/app/services/data_quality_service.py`，从真实数据库聚合主数据、仓配、采购、履约和财务维度，返回评分、失败测试、整改队列、负责人、SLA、Runbook、血缘链路和测试套件。真实本地十万级演示库下，慢查询已从缺少明细的相关子查询改成线性 distinct 统计，接口最近一次复核约 374ms 返回。

`/operations/data-quality/remediation` 位于 `backend/app/api/experience.py`，接收 `issue_id`、`owner`、`priority`、`sla`、`evidence`、`action` 和 `path`，创建 `related_type='quality'` 的通知并写入 `operations / data_quality_remediation` 审计日志；任务队列会把这类通知映射回 `/app/data-quality`。

`/operations/rules` 位于 `backend/app/services/rules_service.py`，从真实数据库聚合库存、采购、应收、报表和审计规则，返回规则健康、DMN 风格决策表、输入/输出列、命中行、风险队列、负责人、SLA、Runbook、服务边界和监控指标。

`/operations/rules/review` 位于 `backend/app/api/experience.py`，接收 `rule_id`、`owner`、`priority`、`sla`、`evidence`、`action` 和 `path`，创建 `related_type='rules'` 的系统通知并写入 `operations / rules_review` 审计日志；任务队列会把这类通知映射回 `/app/rules`。

`/operations/procurement-control` 位于 `backend/app/services/purchase_service.py`，从采购单、补货建议、供应商绩效、库存预警和采购协同任务实时聚合采购控制台合同，返回控制分、P0/P1、补货候选、审批队列、收货窗口、供应商风险、端到端流程、微服务边界、部署检查和 Runbook。

`/operations/procurement-control/task` 位于 `backend/app/api/experience.py`，接收 `queue_item_id`、`purchase_id`、`supplier_id`、`owner`、`priority`、`sla`、`evidence`、`action` 和 `path`，创建 `related_type='procurement_control'` 的采购协同通知并写入 `operations / procurement_control_task` 审计日志；任务来源会映射回 `/app/procurement/orders`。

新增前端能力：

- `frontend/src/app/core/models.ts` 增加 `OperationsWorkflowBoard` 类型。
- `frontend/src/app/pages/command-center.page.ts` 接入 `manufacturing/workflow-board`。
- 总览页新增“每日制造经营作战流”面板，可直接跳转到对应业务模块。
- 工作流面板新增“班次执行控制层”：展示班次窗口、指挥角色、开放动作数、证据留痕、P0/P1/P2 动作队列、可拆分服务边界和部署前检查。
- 工作流面板继续新增“角色指挥席、现场事件流、前后端 API 合同”：展示 5 个责任座席、8 条最近事件和 4 个运行时接口合同。
- 工作流阶段新增“全部 / 关注 / 阻塞”筛选，默认保持 8 阶段完整链路，问题处理时可快速聚焦阻塞阶段。
- `frontend/src/workflow-board.scss` 独立维护新面板的布局、状态色、动效、响应式和 reduced-motion。
- `frontend/src/deployment-readiness.scss` 独立维护设置页动态上线就绪看板，避免继续膨胀全局样式。
- 设置页新增“上线就绪分、动态检查、微服务拆分快照、部署 runbook”，不再只是静态 Token 链接。
- 设置页 attention/blocked 部署检查项新增“创建任务”，成功后显示通知中心入口，把部署准备从状态阅读推进到通知和审计闭环。
- 通知中心任务卡新增“详情 / 来源 / 处理完成”，部署预检任务的来源回到 `/app/settings`，处理完成后显示已处理并落审计日志。
- 任务异常中心新增“当班任务队列”：接入 `/operations/task-queue`，前屏展示 12 条优先任务，通知任务可“处理完成”，部署预检可“创建任务”，库存和采购保留来源/详情跳转。
- 集成监控新增“服务治理指挥层”：展示观测覆盖、Metrics/Logs/Traces 信号、错误预算、SLO、契约覆盖和治理队列，治理项可创建接口重同步任务并进入当班任务队列。
- 数据质量中心新增“数据治理工作台”：消费 `/operations/data-quality` 权威合同，展示维度覆盖、失败测试、整改队列、Runbook、血缘链路和测试套件，治理项可创建整改任务并进入当班任务队列。
- 规则引擎中心新增“规则治理工作台”：消费 `/operations/rules` 权威合同，展示规则健康、DMN 决策表、输入/输出列、命中行、复核队列、规则微服务拆分面和闭环链路，治理项可创建复核任务并进入当班任务队列。
- 采购补货中心新增“采购与供应商协同控制台”：消费 `/operations/procurement-control` 权威合同，展示 6 条采购泳道、18 条控制队列、6 个到货窗口、6 张供应商风险卡、5 个服务边界、4 项部署检查和端到端流程，队列项可创建采购协同任务并进入通知与审计。
- `frontend/src/motion-system.scss` 与应用壳层 pointer spotlight 已覆盖新工作流卡片。

## 4. 设计升级点

- 从静态 KPI 展示升级为“下一步动作”驱动：用户能看到哪个阶段阻塞、谁负责、SLA 是什么、应该点哪里处理。
- 从“阶段看板”升级为“班次执行台”：用户能看到开放动作、优先级、证据、服务归属和上线检查，不需要离开总览页判断谁该处理什么。
- 从单页面视觉升级为前后端分离工作流：总览页不是写死流程图，而是读取 Flask REST API 聚合结果。
- 从单色科技感升级为语义状态系统：绿色表示完成，蓝色表示待命，琥珀表示关注，玫红表示阻塞。
- 从泛动画升级为任务动效：阶段卡 staggered entry、进度条 fill、动作队列 shimmer、hover spotlight、按钮 pressed feedback，全部支持 reduced-motion。
- 从“看起来像 ERP”升级为“能解释 ERP 工作流”：后端测试会造出真实采购、履约、应收、补货、报表和审计数据验证 API。
- 从“部署说明页”升级为“部署前控制台”：设置页读取后端聚合结果，实时展示数据库、密钥、存储、AI、缓存、CORS、微服务目录和脚本资产是否就绪。
- 从“部署前控制台”继续升级为“部署前任务闭环”：attention/blocked 项可以创建系统通知，责任人能在通知中心看到具体证据和执行命令，审计日志保留创建记录。
- 从“通知列表”升级为“任务收件箱”：通知卡不再只有详情链接，而是提供来源跳转和处理完成，保证任务能从发现、派发、处理到审计留痕。
- 从“任务页只看异常”升级为“当班任务处理台”：任务队列把通知、部署、库存和采购统一成同一张工作清单，优先露出可点击的处理动作，避免真正能闭环的按钮被普通跳转任务挤出前屏。
- 从“集成页面只读监控”升级为“服务治理指挥层”：服务风险按 SLO、错误预算、观测信号和契约覆盖排序，责任人可以直接创建治理任务，任务继续进入通知/审计链路。
- 从“前端自算质量分”升级为“后端权威数据治理”：质量判断从页面内 `forkJoin` 多资源列表迁移到后端服务层，页面只展示合同、创建任务和承接审计证据。
- 从“规则列表”升级为“决策治理”：规则判断从页面内临时数组迁移到后端服务层，页面展示 DMN 决策表、风险队列、负责人、SLA、服务边界和任务创建闭环。
- 从“采购列表”升级为“供应商协同控制台”：采购判断从页面内状态列表迁移到后端服务层，页面展示补货、审批、收货、质检、预算、供应商风险和上线检查，并能创建采购协同任务。

## 5. 验证命令

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_api.py::test_manufacturing_workflow_board_contract -q
venv\Scripts\python.exe -m pytest backend\tests\test_api.py::test_competitive_experience_api_paths -q
venv\Scripts\python.exe -m pytest backend\tests\test_api.py::test_procurement_control_contract_and_task -q
venv\Scripts\python.exe -m pytest backend\tests\test_api.py -q -k operations_exceptions_preferences_and_audit
cd frontend
npm run build
npm run audit:charts
npm run audit:layout
venv\Scripts\python.exe scripts\audit-api-contracts.py
npm test -- --watch=false
```

总览作战台升级专项浏览器证据：

```text
output/playwright/overview-command-upgrade-1780992882786/report.json
```

该报告证明 `/app/overview` 在桌面和移动端均渲染 5 个角色座席、8 条事件、4 个 API 合同和 8 个工作流阶段；横向溢出、可见文本撑破、越界卡片、控制台错误、异常请求和 HTTP 4xx/5xx 均为 0。

规则治理专项浏览器证据：

```text
output/playwright/rules-governance-1780973553475/report.json
output/playwright/rules-decision-table-1780973745905/report.json
```

采购协同控制台专项浏览器证据：

```text
output/playwright/procurement-control-upgrade-1780996622570/report.json
```

该报告证明 `/app/procurement/orders` 在桌面和移动端均渲染 6 条采购泳道、8 张前屏控制任务卡、6 个到货窗口、6 张供应商风险卡、5 个服务边界、4 个部署检查、2 个图表和 12 行采购账本；桌面与移动端 `bodyOverflowX=0`，文字撑破、越界卡片、控制台错误和 HTTP 4xx/5xx 均为 0。

最新关键页面网页取样复审：

```text
output/playwright/web-review-1780997929715/report.json
```

该报告证明 `/app/overview`、`/app/procurement/orders`、`/app/sales/orders`、`/app/inventory/stock`、`/app/finance/receivables` 和 `/app/reports` 在桌面与移动端共 12 次打开均失败数 0；横向溢出、文字撑破、越界元素、控制台错误和 HTTP 4xx/5xx 均为 0。

## 6. 部署前影响

- 新增 API 仍在 `/api/v1` 下，继续使用 HttpOnly Cookie + CSRF 认证边界。
- 前端只通过 `ApiService` 访问后端，不直连数据库或泄露后端密钥。
- 新样式文件已写入 `frontend/angular.json`，Vercel 构建会自动打入生产 bundle。
- API 契约审计会识别 `manufacturing/workflow-board`、`operations/deployment-readiness`、`operations/deployment-readiness/task` 和 `operations/task-queue`，若后端路由缺失会失败。
- 集成治理任务仍使用 `/operations/integrations/resync`，前端只传服务 id、责任人、证据和动作，不传任何密钥或数据库连接。
- 数据质量治理任务使用 `/operations/data-quality/remediation`，前端只传 issue id、责任人、优先级、SLA、证据、动作和来源路径，不传数据库连接或任何 secret。
- 采购协同任务使用 `/operations/procurement-control/task`，前端只传队列项、采购单/供应商引用、负责人、优先级、SLA、证据、动作和来源路径；审批、收货和补货转采购仍走原领域动作接口，避免前端直接改采购状态或库存。
- 设置页部署就绪看板不会读取真实密钥值，只展示配置边界、状态、证据和修复动作，避免把 secret 暴露给前端。
- 部署预检任务接口只保存状态、证据和动作文本，通知内容可用于跟进，但不得包含数据库密码、Token、AI Key 或 Cloudinary secret。
- 通知完成接口只更新通知处理状态和审计日志，不改变业务源对象状态；涉及采购、库存、应收等业务实体时仍应回到对应业务页面执行真实业务动作。
- 任务队列接口只聚合任务摘要和业务来源路径，不返回生产密钥；部署类 payload 仍只包含 key、label、scope、status、evidence 和 action，不能携带数据库密码、Token、AI Key 或 Cloudinary secret。
