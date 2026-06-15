# NEXUS Prime 项目交付报告

学生：庄颂  
学号：20241334  
项目：NEXUS Prime 制造业仓配经营管理信息系统  
交付日期：2026-06-15

## 1. 交付范围

NEXUS Prime 已整理为前后端分离项目。运行、构建和部署路径为 `backend/` 与 `frontend/`；`legacy/monolith-flask/` 保留为旧版 Flask/Jinja2 单体快照，用于说明升级前后的架构差异，不参与新版构建、测试和部署。系统覆盖制造企业的库存、采购、履约、应收、盘点、报表、文件、公告、通知、经营分析、权限与审计链路。

本次交付重点包括：

- 项目目录整理与运行边界统一。
- Angular SPA 与 Flask REST API 分离。
- 页面布局、图标居中、Dock、主题、头像、通知、文件详情、AI 设置、报表区域以及首页/登录/注册流程完善。
- 首页图片墙、登录页、注册页在桌面和移动端重新截图验收，入口样式稳定层已修复到最终覆盖位置。
- 业务页真实图片覆盖扩展到仓配、采购、履约、财务、分析、文件、审计、客户服务和工程现场，图片全部落在 `frontend/public/images/`，部署时不依赖远程图床。
- 应用外壳增加“当前闭环”和“执行信号”，按仓配、采购、履约、财务和分析域展示下一步动作、关键 KPI 与可点击业务入口。
- 首页新增并继续升级“每日制造经营作战流”，由 `/api/v1/manufacturing/workflow-board` 实时聚合库存、补货、采购、收货、履约、回款、报表和审计阶段，展示健康分、阻塞点、SLA、负责人、跨模块交接、班次动作队列、角色指挥席、现场事件流、前后端 API 合同、微服务边界和部署前检查。
- 设置页新增“部署就绪与 ERP 成熟度验收控制台”，由 `/api/v1/operations/deployment-readiness` 聚合健康检查、微服务目录、环境变量边界、部署脚本、运行时配置、能力域地图、微服务拓扑、成熟度维度和交付证据链，展示上线就绪分、动态检查、ERP 成熟度、微服务拆分快照和可复制 runbook；关注项可通过 `/api/v1/operations/deployment-readiness/task` 一键写入通知中心和审计日志，并在通知中心通过 `/api/v1/notifications/complete` 处理完成。
- 任务异常中心新增“当班任务队列”，由 `/api/v1/operations/task-queue` 聚合未读通知、部署预检、库存预警和采购审批，按 P0 优先、同优先级可执行动作优先排序；页面直接提供“处理完成”和“创建任务”，形成发现、派发、处理、审计的闭环。
- 盘点链路补齐从创建计划、开始盘点、扫码录入到完成调整的端到端接口校验，周期/全量盘点可自动生成仓库内盘点明细。
- 企业演示数据库已按课程展示需要翻倍，业务数据规模和截图均重新同步。
- Supabase PostgreSQL 与 Vercel 前后端部署准备。
- 一键部署脚本、预检脚本、数据库同步脚本与最终文档。
- 新增全流程质量闸门，统一执行报告生成、数据审计、前后端测试、生产构建、图表审计、布局审计、部署预检和交付资产审计。
- 新增交付资产审计，自动复核 DOCX 报告是否滞后、截图尺寸、Markdown 图片引用、ER 图、前端真实图片登记和旧版快照保留。
- AI 经营分析台和同类业务页完成最终排版稳定修复，布局审计新增可见文字几何重叠检测，覆盖图表头、KPI 卡、个人信息、AI 消息流、长 API 地址和移动端换行。
- 集成监控升级为服务目录视图，后端返回平台、供应链、营收和分析域的服务契约、依赖、SLO、记录吞吐和微服务拆分就绪度。
- 集成监控 Runbook 状态抽象为计算属性，模板不再重复读取可空对象，Angular 21 生产构建已清零模板诊断警告。
- 集成监控继续升级为“服务治理指挥层”，按 SLO、错误预算、OpenTelemetry 三类观测信号、契约覆盖和依赖风险生成治理队列，点击“创建任务”会通过 `/api/v1/operations/integrations/resync` 写入通知和审计，并进入任务异常中心。
- 数据质量中心升级为“数据治理工作台”，由 `/api/v1/operations/data-quality` 从后端权威聚合主数据、仓配、采购、履约和财务质量维度，返回质量评分、失败测试、整改队列、负责人、SLA、Runbook 和血缘链路；点击“创建首要整改”会通过 `/api/v1/operations/data-quality/remediation` 写入通知、审计并进入任务异常中心。
- 规则引擎中心升级为“规则治理工作台”，由 `/api/v1/operations/rules` 返回 DMN 风格决策表、hit policy、输入/输出列、命中行、风险队列、负责人、SLA、Runbook 和规则微服务边界；点击“创建首要复核”会通过 `/api/v1/operations/rules/review` 写入通知、审计并进入任务异常中心。
- 预算成本中心升级为“预算成本治理台”，由 `/api/v1/operations/costs` 返回预算、实际消耗、采购承诺、可用预算、成本中心、差异复核队列、预算瀑布、库存成本结构、服务边界和 Runbook；点击“创建首要复核”会通过 `/api/v1/operations/costs/review` 写入通知、审计并进入任务异常中心。
- 产能计划中心升级为“产能治理工作台”，由 `/api/v1/operations/capacity` 返回销售需求、采购供给、物料齐套、仓库释放、工作中心负载、瓶颈队列、班次计划、服务边界和 Runbook；点击“创建首要复核”会通过 `/api/v1/operations/capacity/review` 写入通知、审计并进入任务异常中心。
- 设备维护中心升级为“设备可靠性治理工作台”，由 `/api/v1/operations/maintenance` 返回资产线、维护工单候选、MRO 关键备件、维修人员、停机窗口、维护流程、设备微服务边界和 Runbook；点击队列内“创建工单”会通过 `/api/v1/operations/maintenance-workorder` 写入通知、审计并进入任务异常中心。
- 移动扫码终端升级为“移动现场治理工作台”，由 `/api/v1/operations/mobile-terminal` 返回收货、盘点、发货、异常复核四条泳道、扫码队列、设备会话、库区覆盖、扫码到审计流程、移动微服务边界和现场 Runbook；点击队列内“创建任务”会通过 `/api/v1/operations/mobile-terminal/task` 写入通知、审计并进入任务异常中心。
- 采购页升级为“采购与供应商协同控制台”，由 `/api/v1/operations/procurement-control` 返回需求补货、审批承诺、供应商确认、到货质检、预算暴露、服务边界和部署检查；控制队列可通过 `/api/v1/operations/procurement-control/task` 创建采购协同任务并写入通知与审计。
- 供应商绩效页升级为“供应商协同与资质风险工作台”，由 `/api/v1/operations/supplier-collaboration` 返回资质准入、交付 SLA、质量 CAPA、商务集中度、供应商 360、到货窗口、服务边界和部署检查；协同队列可通过 `/api/v1/operations/supplier-collaboration/task` 创建通知任务并写入审计。
- 新增 `frontend/src/motion-system.scss` 作为统一动效系统，补齐路由入场、Hero 揭示、卡片 spotlight、按钮按压、Dock 弹性、图表唤醒和 `prefers-reduced-motion` 无障碍兜底。
- 应用壳层增加 requestAnimationFrame 节流的 pointer spotlight 坐标写入，业务卡片、Dock、上下文卡、记录行和操作入口可以根据鼠标位置产生边缘光和轻微物理反馈。
- 壳层交互专项审计纳入质量闸门，自动验证更多模块、模块跳转、Escape 关闭、桌面/移动横向溢出、控制台错误和 spotlight 坐标写入。
- 新增 `frontend/src/experience-polish.scss` 作为最终质感收口层，专门处理移动端动作按钮居中、采购审批工作卡状态/金额层级和管线按钮高光，避免继续扩大历史全局样式文件。
- 新增 `frontend/src/workflow-board.scss` 作为作战流样式层，独立维护阶段卡、阻塞点、交接条、角色视图、角色指挥席、现场事件流、前后端 API 合同、P0/P1/P2 动作队列、服务边界、部署检查、语义状态色、staggered entry、队列 shimmer 和 reduced-motion。
- 新增 `frontend/src/deployment-readiness.scss` 作为上线就绪样式层，独立维护设置页就绪分、检查项、任务按钮、服务域快照、部署运行手册、状态色和 reduced-motion。
- 新增 `docs/frontend-upgrade-research-notes.md`，记录 Ant Design、Material Motion、Atlassian Motion 等资料参考、skills 使用记录、本轮工作流 API 和部署前影响。

课程任务书对应关系：

| 要求 | 本项目实现 |
| --- | --- |
| Flask 后端 REST API | `backend/app/api/` 统一提供 `/api/v1` JSON 接口。 |
| Angular 17+ SPA | `frontend/` 使用 Angular 21 standalone components、Router、Guard、Interceptor。 |
| 用户认证与权限 | HttpOnly Cookie、CSRF、管理员和普通成员权限差异。 |
| CRUD、搜索、分页、详情 | 物料、采购、销售、应收、盘点、报表、文件、通知等页面均提供列表、搜索、分页和详情入口。 |
| 数据库关联 | 用户/角色/部门、商品/分类/供应商/标签、订单/明细、应收/收款、文章/评论等关联。 |
| 统计图表与文件上传 | ECharts 交互图表、报表生成、文件上传下载、头像上传。 |
| 报告与演示视频 | `docs/final-delivery-report.docx`、`docs/final-completion-audit.md`、`docs/final-screenshot-report.md`、`docs/final-video-script.md` 与截图清单。 |

## 2. 目录规范

```text
nexus_prime/
├── backend/                 # Flask REST API
│   ├── app/api/             # /api/v1 接口
│   ├── app/models/          # SQLAlchemy 数据模型
│   ├── app/services/        # 业务服务
│   ├── migrations/          # Alembic 迁移
│   ├── scripts/             # 数据同步工具
│   ├── tests/               # 后端测试
│   ├── server.py            # Vercel Flask 入口
│   └── vercel.json          # 后端 Vercel 配置
├── frontend/                # Angular 21 SPA
│   ├── src/app/core/        # API、认证、主题、导航
│   ├── src/app/shell/       # 应用外壳、顶部栏、Dock
│   ├── src/app/pages/       # 业务页面与详情页
│   ├── src/motion-system.scss     # 统一动效系统
│   ├── src/experience-polish.scss # 最终体验精修层
│   ├── src/workflow-board.scss    # 每日制造经营作战流
│   ├── src/deployment-readiness.scss # 部署就绪、ERP 成熟度与任务闭环
│   ├── public/runtime-config.example.js
│   └── vercel.json
├── docs/                    # 报告、截图、部署说明、讲稿
├── legacy/                  # 旧版 Flask/Jinja2 单体对照快照
└── scripts/                 # 本地启动、清理、质量闸门、预检、部署脚本
```

运行项目不得依赖任何历史归档。`legacy/monolith-flask/` 只作为报告证据和迁移对照保留，运行产物、缓存、截图临时目录、构建产物和环境变量文件已由 `.gitignore` 排除。

## 3. 架构说明

前端采用 Angular 21 Standalone Components、PrimeNG 21、Lucide、ECharts 和 RxJS。首页、登录页和注册流程的样式已独立到 `frontend/src/auth-entry.scss`，业务页面由 `frontend/src/styles.scss` 的统一设计系统和稳定层负责，跨页面动效进入 `frontend/src/motion-system.scss`，最终交互与移动端精修进入 `frontend/src/experience-polish.scss`，每日作战流进入 `frontend/src/workflow-board.scss`，部署就绪、ERP 成熟度和服务拓扑验收进入 `frontend/src/deployment-readiness.scss`。跨页面业务闭环由 `frontend/src/app/core/workflow-blueprints.ts` 管理，图片资产由 `frontend/src/app/core/visual-assets.ts` 统一登记，壳层根据当前 URL 自动切换闭环、执行信号、下一步入口和现场照片。后端采用 Flask 3、SQLAlchemy、Flask-Migrate、Flask-CORS、pytest、ReportLab 和可选 Cloudinary 存储。

认证方式为 HttpOnly Cookie + CSRF Token。登录后后端设置访问 Cookie 和 CSRF Cookie，前端在写请求中携带 `X-CSRF-Token`，后端按用户角色和权限点校验业务动作。

数据库本地使用 `backend/instance/` 下的 SQLite 运行文件，运行数据库不提交到仓库；生产目标为 Supabase PostgreSQL。迁移由 `flask db upgrade` 执行，现有 SQLite 数据可通过 `backend/scripts/sync_sqlite_to_postgres.py` 同步至 Supabase。

旧版对照快照位于 `legacy/monolith-flask/`。旧版报告写明部署目标为 Railway，Flask 同时承担路由、数据库访问、Jinja2 模板渲染、表单校验、上传和页面展示。新版将这些职责拆分为 Angular SPA、Flask REST API、SQLAlchemy 服务层、Cloudinary/本地专用上传目录和 Supabase PostgreSQL 部署目标。

| 旧版能力 | 新版实现 |
| --- | --- |
| Flask route 直接渲染 HTML | `/api/v1` JSON API + Angular Router 页面 |
| Jinja2 模板和 Bootstrap 页面 | Angular 21 Standalone Components + PrimeNG + ECharts |
| Flask-Login session | HttpOnly Cookie + CSRF Cookie + Angular Guard/Interceptor |
| Railway 部署目标 | 前端 Vercel、后端 Vercel/独立 Flask、数据库 Supabase PostgreSQL |
| 上传文件在运行目录混放 | `UPLOAD_FILES_FOLDER`、`UPLOAD_AVATARS_FOLDER`、`UPLOAD_LIBRARY_FOLDER` 三类专用目录，生产使用 Cloudinary |
| 旧版截图留白和少量演示数据 | 本地真实图片、交互图表、企业级数据审计和 Playwright 截图清单 |

新版 API 已清理不必要的 `*-legacy` 兼容别名；旧版代码只在 `legacy/` 中作为参考资料保留，避免活跃后端继续暴露旧路径。

本轮继续升级还补齐了交付工程化链路：`scripts/quality-gate.ps1` 作为总质量闸门，`scripts/audit-api-contracts.py` 负责前后端 API 契约审计，`frontend/scripts/shell-interaction-audit.mjs` 负责顶部栏、Dock、更多模块和 spotlight 交互审计，`scripts/audit-delivery-assets.py` 作为报告和截图资产审计，`scripts/generate_final_report_docx.py` 负责从 Markdown 同步生成 DOCX。这样从旧版迁移到新版后，项目不再只依靠“手工看页面”，而是用可重复脚本检查架构、接口、数据、页面、部署和报告是否一致。

本轮安全与架构收口包括：上传扩展名、MIME、文件头和 Office Zip 内部结构校验统一收敛到 `backend/upload_policy.py`，`save_file()` 和 `/api/v1/files/upload` 共用同一策略；部署脚本新增敏感命令日志脱敏，避免 `VERCEL_TOKEN`、`DATABASE_URL`、Redis、Cloudinary secret 和 AI Key 出现在控制台；登录接口增加同 IP + 邮箱维度失败限流，未知邮箱也计入窗口并写入审计，生产环境要求 Redis/Upstash 共享缓存让限流跨实例生效；登录和注册响应体不再返回可读 JWT，HttpOnly Cookie 继续作为登录凭证来源；全局搜索、运营待办和运营异常已按普通用户/管理员边界过滤附件和通知。

核心 ER 图：

![ER 图](images/final/er-diagram.svg)

## 4. 前端整理结果

前端页面统一使用应用外壳：顶部命令栏、居中 Dock、更多页面入口、通知入口、全局设置、主题切换、用户入口和上下文洞察。所有核心页面均具备可滚动布局、分页或跳转、搜索入口、详情页入口和业务动作入口。

主要修复点：

- Dock 不再占用主体区域，名称浮现和更多页面入口保持一致。
- 页面图标、PrimeIcons、Lucide 图标和按钮内容统一居中。
- 首页、登录页、注册流程、个人工作台、AI 分析、文件详情、设置页、报表页完成视觉统一。
- AI 分析页已针对结构化摘要、行动队列、服务设置、诊断卡片、聊天消息、长模型名和长 Base URL 做最终换行与栅格兜底，避免文本互压、横向撑爆和移动端按钮挤压。
- 概览、经营指标、内容中心、个人工作台等共享 KPI/图表头组件已统一行距、最小高度和可换行规则，避免标签与数值重叠。
- 首页真实图片墙高度固定，登录和注册卡片居中，浅色模式文字对比通过截图复核。
- 新增 5 张真实业务现场图：仓库拣货、工厂工程师、经营复盘、客户支持、档案资料；并与既有收货月台、扫码、叉车、财务和控制台图片一起映射到所有核心业务域。
- 业务 Hero 背景改为 CSS 变量稳定层：采购/供应商使用收货月台，履约/调度/服务使用叉车月台，仓配/补货使用仓库现场，盘点/移动端使用扫码现场，财务使用应收分析，报表/AI/规则/接口使用分析会议，文件/内容/审计/权限使用档案资料。
- 右侧上下文面板增加“执行信号”，当前页面可直接看到库存水位、待审批采购、履约单、逾期应收、数据质量、审计追溯等指标和入口，不再停留在静态演示说明。
- 总览页增加“每日制造经营作战流”：阶段卡展示库存信号、补货建议、采购审批、收货入库、销售履约、应收回款、报表归档、审计追溯，并给出负责人、SLA、进度、阻塞点、P0/P1/P2 动作队列、证据留痕和可点击处理入口；本轮继续加入 5 个角色指挥席、真实业务事件时间线和 4 个运行时 API 合同，让总览页同时解释人、事、接口和服务边界。
- 头像动画改为低干扰动效，个人资料、偏好和头像上传通过 API 落库；本地清理脚本默认保留头像目录，生产 Serverless 环境未配置持久化存储时会拒绝上传并提示配置。
- AI 分析页增加服务模式、Base URL、模型、API Key 保存和诊断。
- 文件详情页增加信息区、关联区、下载动作和真实文件接口。
- 注册页的《服务许可》《隐私说明》《数据使用范围》由 `/auth/register-policy` 返回结构化条款，用户可展开阅读后再勾选确认。
- 全局设置页可控制主题、密度、默认工作区、图表动效、Dock 标签和上下文面板，并提供 Vercel、Supabase、Cloudinary、DeepSeek 的密钥获取入口、动态上线就绪分、部署前检查、微服务拆分快照、可复制部署 runbook 和部署预检任务创建。
- 通知中心任务卡升级为可执行工作卡：主体进入详情，“来源”回到业务页面，“处理完成”会回写通知状态和审计日志；部署预检任务的来源回到全局设置中心。
- 动效系统采用现有 Angular + CSS 能力实现，不额外引入 GSAP。原因是本项目是高密度 ERP 管理台，不是营销落地页；统一 CSS 动效能覆盖全部业务页，包体和部署复杂度更低，也更容易和 Playwright 布局审计、Vercel 构建保持稳定。
- `motion-system.scss` 统一定义 `--motion-fast`、`--motion-base`、`--motion-slow`、`--motion-ease-standard`、`--motion-ease-spring` 等动效 token，所有新增动效都走 transform、opacity、filter 和 box-shadow，不使用会造成重排的 top/left/width/height。
- 页面进入采用 `nexusRouteReveal`、`nexusHeroReveal`、`nexusSurfaceReveal`、`nexusChartWake` 四级节奏：先让路由主体浮入，再让 Hero 和业务卡片分层出现，最后图表唤醒，避免管理台页面一次性“硬切”。
- 业务卡片 spotlight 通过壳层的 pointermove 事件写入 `--spotlight-x` 和 `--spotlight-y`，CSS 只在 hover 时展示局部径向高光；事件使用 requestAnimationFrame 节流，并在 `ngOnDestroy` 中清理监听器和待执行帧。
- `experience-polish.scss` 位于样式链最后，只承接“真实浏览器截图后发现的精修项”：移动端主动作按钮保持图标+文字整体居中，采购审批队列由厚重状态条改为状态胶囊、单号、供应商/仓库和金额的双列工作卡，采购管线按钮增加轻量高光反馈。
- 无障碍方面保留 `prefers-reduced-motion: reduce`：用户系统开启减少动态效果时，路由、Hero、卡片、Dock、图表入场和 hover transform 都会被停用或降到近零时长。

本次前端升级使用和参考的 Codex skills：

| Skill | 用途 | 落地结果 |
| --- | --- | --- |
| `frontend-design` | 定义动效 token、审查色彩/层级/交互节奏 | 建立“工业控制台精准动效”方向，避免炫技式动画影响业务效率。 |
| `frontend-ui-engineering` | 保证可访问性、响应式、状态和测试可维护 | 动效只影响 transform/opacity，保留 focus-visible 和 reduced-motion。 |
| `redesign-existing-projects` | 审计现有项目的通用 UI 弱点 | 补齐 hover、pressed、spotlight、页面入场、真实材质纹理、移动端按钮居中和采购工作卡层级。 |
| `gpt-taste` | 参考高级动效范式 | 选取“分层入场、卡片物理反馈、图片缩放、表面质感”，未引入 GSAP 以控制 ERP 包体和部署风险。 |
| `skill-installer` | 查询和安装可用技能 | 当前 curated skills 未提供 Angular ERP 动画专项 skill；2026-06-09 已安装 `figma-generate-design`，用于后续有 Figma 文件时生成/同步设计屏。 |
| `figma-generate-design` | 设计资产方向补充 skill | 已下载到本机 skills 目录；当前项目没有 Figma URL/MCP 上下文，因此本轮不调用 Figma 写入，只把本地 Angular 页面作为权威交付。 |
| `playwright` | 浏览器级截图与布局核验 | 用真实浏览器复核桌面/移动页面、控制台、网络状态和截图。 |

## 5. 后端整理结果

后端运行入口统一为 `backend/run.py`，Vercel 入口为 `backend/server.py`。API 前缀统一为 `/api/v1`，列表接口支持分页、搜索、排序和筛选。核心业务动作写入审计日志。

主要接口：

- `/auth/login`、`/auth/register`、`/auth/me`、`/auth/logout`
- `/auth/register-policy`
- `/manufacturing/command-center`
- `/manufacturing/workflow-board`
- `/operations/deployment-readiness`
- `/operations/deployment-readiness/task`
- `/operations/task-queue`
- `/operations/integrations/resync`
- `/operations/data-quality`
- `/operations/data-quality/remediation`
- `/operations/rules`
- `/operations/rules/review`
- `/operations/costs`
- `/operations/costs/review`
- `/operations/capacity`
- `/operations/capacity/review`
- `/operations/maintenance`
- `/operations/maintenance-workorder`
- `/operations/mobile-terminal`
- `/operations/mobile-terminal/task`
- `/notifications/complete`
- `/analytics/executive`
- `/me/profile`、`/me/avatar`、`/me/preferences`
- `/files/upload`、`/files/<id>/download`
- `/ai/chat`、`/ai/settings`、`/ai/diagnostics`
- `/reports/generate/<type>`
- `/procurement/orders/<id>/approve`
- `/sales/orders/<id>/transition`
- `/finance/receivables/<id>/payment`
- `/stocktakes/<id>/count`
- `/finance/receivables/<id>/reminder`

生产环境中，后端日志输出到 stdout；Serverless 场景下运行目录可由 `NEXUS_RUNTIME_DIR` 指定，默认使用 `/tmp/nexus-prime`。

本次架构维护已删除 `/operations/dispatch-task-legacy` 与 `/operations/data-quality-notice-legacy` 旧兼容别名，前端统一使用 `/operations/dispatch-task` 与 `/operations/data-quality-notice`，API 手册同步更新，测试覆盖旧别名返回 404。

## 5.1 优质代码说明

以下代码是本项目从课程演示系统升级为行业级 ERP 管理台的关键支撑：

| 文件 | 说明 |
| --- | --- |
| `frontend/src/motion-system.scss` | 全局动效系统。集中维护 motion token、页面入场、卡片 spotlight、按钮按压、Dock 弹性、图表唤醒和 reduced-motion，避免每个页面重复写动画。 |
| `frontend/src/experience-polish.scss` | 最终体验精修层。放在样式链最后，只处理跨页面动作按钮、移动端触控节奏、采购审批工作卡和管线 hover 高光，不承接业务逻辑。 |
| `frontend/src/workflow-board.scss` | 每日作战流样式层。集中维护阶段卡、阻塞点、交接条、角色视图、角色指挥席、现场事件流、前后端 API 合同、班次动作队列、服务边界、部署检查、语义状态色、任务动效和 reduced-motion，让新增工作流不继续膨胀全局样式。 |
| `frontend/src/deployment-readiness.scss` | 部署就绪与成熟度样式层。集中维护设置页上线就绪分、动态检查项、ERP 成熟度维度、能力域地图、服务拓扑节点、交付证据、任务按钮、服务域快照、运行时条和部署 runbook，让部署前工作变成可视化控制台。 |
| `frontend/src/app/pages/settings.page.ts` | 设置页控制台。接入部署就绪检查项创建任务，并展示 ERP 成熟度、能力域、服务拓扑和交付证据；attention/blocked 项可直接进入通知中心和审计链路，ready 项保持只读。 |
| `frontend/src/app/pages/operations-tasks.page.ts` | 任务异常中心。接入 `/operations/task-queue`，把通知、部署预检、库存和采购统一成当班队列，支持处理完成、创建部署任务和来源跳转，并在桌面/移动端稳定展示 12 条优先任务。 |
| `frontend/src/app/pages/integration-monitor.page.ts` | 集成监控治理台。展示服务契约、观测信号、错误预算和治理队列，治理项可直接创建接口重同步通知任务，并从任务异常中心继续处理。 |
| `frontend/src/app/pages/data-quality.page.ts` | 数据质量治理台。消费后端质量合同，展示维度评分、失败测试、整改队列、Runbook、血缘链路和测试套件，可直接创建整改任务进入通知与任务队列。 |
| `frontend/src/app/pages/rules-engine.page.ts` | 规则治理工作台。消费后端规则合同，展示规则健康、DMN 决策表、输入/输出列、命中行、风险队列、服务边界和复核任务创建。 |
| `frontend/src/app/pages/procurement.page.ts` | 采购与供应商协同控制台。并行读取采购单列表与 `/operations/procurement-control`，展示 6 条采购泳道、协同任务队列、到货窗口、供应商风险、采购流程、服务边界和部署检查，并把控制任务推入通知与任务队列。 |
| `frontend/src/app/pages/capacity-planning.page.ts` | 产能治理工作台。消费后端产能合同，展示需求/供给/齐套/释放能力、工作中心负载、瓶颈复核队列、班次计划、服务边界和 Runbook，并把复核任务推入任务异常中心。 |
| `frontend/src/app/pages/maintenance.page.ts` | 设备可靠性治理工作台。消费后端维护合同，展示资产线、维护工单候选、MRO 关键备件、维修人员、停机窗口、维护流程、服务边界和 Runbook，并把维护工单推入任务异常中心。 |
| `frontend/src/app/pages/mobile-terminal.page.ts` | 移动现场治理工作台。消费后端移动终端合同，展示四条扫码泳道、40 条现场队列、设备会话、库区覆盖、扫码流程、服务边界和现场执行手册，并把扫码任务推入任务异常中心。 |
| `frontend/src/app/pages/notifications.page.ts` | 通知任务中心。任务卡拆成详情、来源和处理完成三段动作，让部署预检、库存预警、审批提醒等通知从消息展示进入可执行闭环。 |
| `frontend/src/app/shell/app-shell.component.ts` | 应用壳层。统一顶部命令栏、Dock、搜索、服务健康、快捷创建、上下文洞察、当前闭环和 pointer spotlight 坐标写入，是前端从普通页面集合升级为工作台体验的核心。 |
| `frontend/src/app/core/navigation.ts` | 导航配置中心。所有主 Dock、更多模块、分组、图标、颜色和快速动作都集中在配置中，页面增删不需要改壳层模板。 |
| `frontend/src/app/core/workflow-blueprints.ts` | 业务闭环蓝图。按仓配、采购、履约、财务和分析域定义流程节点、现场图、摘要和下一步动作，支撑右侧上下文面板。 |
| `frontend/src/app/core/models.ts` | 前端 API 合同模型。新增 `ProcurementControlPayload` 及采购泳道、审批项、到货窗口、供应商风险、补货候选、控制任务、服务边界和部署检查类型，让采购页不再依赖隐式 `any`。 |
| `frontend/src/app/core/api-url.ts` | API 地址统一处理。前端只依赖运行时 `NEXUS_API_BASE_URL`，避免页面硬编码本地或生产域名。 |
| `backend/app/services/service_catalog.py` | 微服务就绪视图。用服务目录、契约、依赖、SLO、错误预算、OpenTelemetry 信号、数据对象和 runbook 生成 `/operations/integrations` 页面数据，说明当前单体 API 如何按业务域演进到微服务边界。 |
| `backend/app/services/purchase_service.py` | 采购协同聚合服务。从采购单、采购明细、供应商绩效、补货建议、库存预警、通知、物料、供应商和仓库生成采购控制合同，输出控制分、6 条泳道、审批队列、到货窗口、供应商风险、补货候选、服务边界、部署检查和任务创建上下文。 |
| `backend/app/services/data_quality_service.py` | 数据质量治理服务。从真实数据库聚合主数据、仓配、采购、履约和财务质量问题，生成评分、失败测试、整改队列、SLA、Runbook 和血缘链路；针对十万级本地库使用线性 distinct 统计避免慢查询。 |
| `backend/app/services/rules_service.py` | 规则治理服务。从真实数据库聚合库存、采购、应收、报表和审计规则，生成 DMN 风格决策表、风险队列、负责人、SLA、Runbook、服务边界和监控指标。 |
| `backend/app/services/capacity_service.py` | 产能治理服务。从销售订单、采购到货、物料水位、仓库利用率和工作中心生成产能合同，输出负载曲线、瓶颈队列、班次计划、服务边界和复核上下文。 |
| `backend/app/services/maintenance_service.py` | 设备可靠性治理服务。从物料、库存、库存预警、附件、库存流水和通知聚合维护合同，输出可靠性评分、资产线、工单队列、备件覆盖、维修人员、停机窗口、服务边界和 Runbook。 |
| `backend/app/services/mobile_terminal_service.py` | 移动终端治理服务。从库存预警、采购到货、盘点和发货现场生成扫码任务合同，输出泳道、队列、设备会话、库区覆盖、扫码流程、服务边界和现场执行手册。 |
| `backend/app/services/deployment_service.py` | 部署就绪与 ERP 成熟度聚合服务。复用健康检查、服务目录、仓库部署资产和环境边界，生成 `/operations/deployment-readiness`，前端只展示状态、证据、能力域、拓扑和动作，不暴露 secret。 |
| `backend/app/api/experience.py` | 运营体验 API。提供 `/operations/task-queue`、`/operations/procurement-control`、`/operations/procurement-control/task`、`/operations/deployment-readiness/task`、`/operations/integrations/resync`、`/operations/data-quality/remediation`、`/operations/rules/review`、`/operations/costs/review`、`/operations/capacity/review`、`/operations/maintenance-workorder` 和 `/operations/mobile-terminal/task`，把采购协同、部署预检、服务治理、数据质量、规则、预算、产能、设备维护和移动扫码关注项创建为通知并写入审计。 |
| `backend/app/api/notifications.py` | 通知任务 API。新增 `/notifications/complete`，把通知标记为已处理并写入 `complete_task` 审计日志，记录来源页面和处理说明。 |
| `backend/app/services/analytics_service.py` | 经营聚合服务。本轮新增并扩展 `manufacturing_workflow_board_payload()`，从真实数据库计算 8 个工作流阶段、阻塞点、交接关系、角色视图、5 个角色指挥席、12 条业务事件流、4 个前后端 API 合同、当班动作队列、服务边界和部署前检查，前端只消费 REST API。 |
| `backend/upload_policy.py` | 上传安全策略。统一扩展名、MIME、危险类型、文件头和 Office Zip 结构校验，避免头像、附件和资料库入口策略不一致。 |
| `scripts/quality-gate.ps1` | 全流程质量闸门。串联 DOCX 生成、数据审计、后端测试、前端测试、构建、API 契约、图表、壳层交互、布局、部署预检和交付资产审计。 |
| `scripts/audit-api-contracts.py` | 前后端契约审计。直接读取 Flask 运行时 `url_map` 和 Angular `ApiService` 使用点，防止前端调用不存在的接口。 |
| `scripts/audit-delivery-assets.py` | 交付资产审计。校验截图尺寸、Markdown 图片、ER 图、DOCX 新旧、真实图片登记和部署文档完整性。 |

## 6. 数据与流程

系统数据覆盖用户、角色、权限、部门、商品、客户、供应商、仓库、库存、采购单、销售单、应收、收款、盘点、通知、报表、文章、评论、文件、分析会话和审计日志。

仓库不提交运行数据库。以下规模为 `seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 可复现生成并通过严格审计的演示库结果：

| 数据项 | 数量 |
| --- | ---: |
| 用户 | 15001 |
| 商品 | 57608 |
| 销售订单 | 100803 |
| 库存流水 | 111360 |
| 采购单 | 46803 |
| 应收账款 | 80640 |
| 收款记录 | 70560 |
| 盘点单 | 2400 |
| 通知 | 32423 |
| 报表 | 16200 |
| 文章 | 16200 |
| 评论 | 21600 |
| 文件 | 7200 |
| 审计日志 | 4791 |

核心业务闭环：

```text
低库存信号 -> 补货建议 -> 采购审批 -> 收货入库 -> 销售发货
-> 应收生成 -> 收款释放信用 -> 报表归档 -> 通知与审计留痕
```

本次补齐后的页面工作流：

| 闭环 | 前端入口 | 真实动作 |
| --- | --- | --- |
| 仓配现场 | 物料、仓配流向、补货建议、移动终端、盘点中心 | 低库存生成建议，扫码盘点写入盘点明细，完成后形成差异调整。 |
| 采购到货 | 补货建议、采购协同控制台、质量、收货、供应商绩效、预算成本 | 后端聚合补货、审批、供应商确认、到货质检和预算暴露，控制队列可创建采购协同任务，采购提交/审批/收货均走权限和审计。 |
| 销售履约 | 客户、销售订单、调度、应收、服务 | 订单状态按待付款、待发货、已发货、已完成流转，并联动库存与应收。 |
| 现金信用 | 应收、信用、合同、预算、报表 | 收款回写应收，催款进入通知中心，报表生成后归档。 |
| 产能计划 | 产能计划、采购补货、仓配流向、任务异常 | 后端聚合销售需求、采购供给、物料齐套和仓库释放能力，瓶颈项可创建产能复核任务并写入审计。 |
| 分析治理 | AI、规则、接口、数据质量、审计 | 经营分析定位风险，规则/接口/数据质量/审计承接治理闭环。 |

集成治理闭环：

```text
服务目录 -> 契约清单 -> 依赖链路 -> SLO/延迟对比
-> 风险服务识别 -> 重同步任务 -> 通知与审计留痕
```

数据质量治理闭环：

```text
数据库体检 -> 维度评分 -> P0/P1 整改队列 -> 创建整改任务
-> 通知中心与审计日志 -> 任务异常中心跟踪 -> 刷新质量体检
```

该闭环覆盖主数据完整性、库存库位、采购状态与明细、销售明细、应收逾期和订单追溯。真实本地十万级演示库下，`/api/v1/operations/data-quality` 最近一次接口复核约 374ms 返回，避免页面一次性拉取 5 个资源列表再在前端临时计算。

采购协同治理闭环：

```text
低库存与补货候选 -> 采购审批 -> 供应商确认 -> 到货窗口
-> 质量放行 -> 预算承诺 -> 协同任务 -> 通知与审计留痕
```

该闭环由 `/api/v1/operations/procurement-control` 提供后端权威合同，前端只负责呈现和触发任务；本轮浏览器复审确认采购页桌面和移动端都无横向溢出、文字撑破、越界元素、控制台错误和 HTTP 4xx/5xx。

重建本地数据：

```powershell
cd backend
$env:FLASK_APP="run.py"
..\venv\Scripts\python.exe -m flask seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334
..\venv\Scripts\python.exe -m flask audit-enterprise-data --strict
```

## 7. 部署准备

前端 Vercel 项目根目录为 `frontend/`：

```text
Framework Preset: Angular
Build Command: npm run build
Output Directory: dist/frontend/browser
Environment: NEXUS_API_BASE_URL=https://<backend-project>.vercel.app/api/v1
```

后端 Vercel 项目根目录为 `backend/`：

```text
Framework: Flask
Entry: server.py
Health: /api/v1/health
```

Supabase PostgreSQL 连接串必须使用：

```text
postgresql://...supabase.com:6543/postgres?sslmode=require
```

一键部署脚本：

```powershell
.\scripts\deploy-supabase-vercel.ps1 `
  -DatabaseUrl "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" `
  -BackendProjectName "nexus-prime-api" `
  -FrontendProjectName "nexus-prime-web" `
  -SeedRemoteWhenEmpty `
  -DemoAdminPassword "replace-with-demo-admin-password" `
  -DemoUserPassword "replace-with-demo-user-password" `
  -SecretKey "replace-with-at-least-32-random-characters" `
  -CloudinaryUrl "cloudinary://api_key:api_secret@cloud_name" `
  -RedisUrl "redis://cache.example.com:6379/0"
```

脚本会执行预检、迁移、空库状态校验、后端发布、前端发布和健康检查。真实生产部署前需确认 Vercel CLI 已登录或设置 `VERCEL_TOKEN`；同步已有 SQLite 或清空远程库仅限可丢弃演练环境。

## 8. 本地验收

完整完成度审计见 `docs/final-completion-audit.md`。该审计按用户目标逐项列出前端升级、动画、前后端分离、微服务准备、部署、清理、功能、页面、真实度、截图、代码讲解、功能说明和 ER 图的证据。

建议验收命令：

```powershell
.\scripts\quality-gate.ps1
```

快速复核报告、截图、ER 图、真实图片和部署资料：

```powershell
.\scripts\quality-gate.ps1 -SkipBackendTests -SkipFrontendTests -SkipBuild -SkipLayoutAudit
```

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest -q
```

```powershell
cd frontend
npm test -- --watch=false
npm run build
npm run audit:charts
npm run audit:layout
```

```powershell
$env:NEXUS_API_BASE_URL="https://nexus-prime-api.vercel.app/api/v1"
$env:FRONTEND_ORIGIN="https://nexus-prime-web.vercel.app"
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
$env:CORS_ORIGINS=$env:FRONTEND_ORIGIN
$env:AUTH_COOKIE_SECURE="true"
$env:AUTH_COOKIE_SAMESITE="None"
$env:SECRET_KEY="replace-with-at-least-32-random-characters"
$env:CLOUDINARY_URL="cloudinary://api_key:api_secret@cloud_name"
$env:CACHE_TYPE="RedisCache"
$env:REDIS_URL="redis://cache.example.com:6379/0"
$env:CACHE_REDIS_URL=$env:REDIS_URL
.\scripts\preflight.ps1 -SkipApiProbe
```

2026-06-09 已完成完整质量闸门复核：`scripts/quality-gate.ps1` 全量通过，串联报告生成、企业数据审计、后端测试、前端测试、生产构建、前后端 API 契约审计、图表审计、布局审计、部署预检和交付资产审计。2026-06-10 补充完成部署就绪与 ERP 成熟度专项审计，并把 `audit:deployment-readiness` 纳入质量闸门。2026-06-15 追加壳层交互审计，把顶部栏、Dock、更多模块和 spotlight 坐标写入纳入自动检查；同日复跑后端测试、前端测试和生产构建均通过。本轮复核覆盖部署预检任务闭环、通知完成闭环、任务异常中心当班队列、集成治理指挥层、数据质量治理工作台、质量检验治理台、供应商协同工作台、规则治理工作台、预算成本治理台、产能计划治理台、设备可靠性治理台、移动扫码终端治理台、采购协同控制台和总览作战台角色/事件/API 合同层。浏览器审计会临时写入本地 API 地址，脚本已在部署预检前和退出时恢复 `frontend/public/runtime-config.js` 为空 fallback，避免本地地址进入交付状态。

| 检查项 | 结果 |
| --- | --- |
| 数据扩容 | `seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 可重建大规模演示库。 |
| 数据状态 | 2026-06-15 `flask status` 显示用户 15001、商品 57608、销售订单 100803、文件 7200、审计日志 4791；数据库文件不提交。 |
| 数据审计 | `flask audit-enterprise-data --strict` 全部 OK。 |
| 微服务就绪 | `/api/v1/operations/integrations` 返回服务契约、依赖链路、域汇总、观测信号、错误预算、治理队列和平均就绪度。 |
| 总览作战台合同 | `/api/v1/manufacturing/workflow-board` 返回 8 个工作流阶段、5 个角色指挥席、12 条事件流、4 个前后端 API 合同、服务边界和部署前检查；`output/playwright/overview-command-upgrade-1780992882786/report.json` 证明桌面/移动横向溢出和控制台错误为 0。 |
| 采购协同控制台 | `/api/v1/operations/procurement-control` 返回控制分、6 条采购泳道、审批队列、到货窗口、供应商风险、补货候选、服务边界和部署检查；`/api/v1/operations/procurement-control/task` 可把控制项创建为通知任务并写入审计。 |
| 供应商协同控制台 | `/api/v1/operations/supplier-collaboration` 返回网络评分、资质准入、交付 SLA、质量 CAPA、商务集中度、供应商 360、到货窗口、服务边界和部署检查；`/api/v1/operations/supplier-collaboration/task` 可把协同项创建为通知任务并写入审计。 |
| 数据质量治理 | `/api/v1/operations/data-quality` 返回后端权威质量评分、维度覆盖、失败测试、整改队列、Runbook 和血缘链路；`/api/v1/operations/data-quality/remediation` 可把治理项创建为通知任务并写入审计。 |
| 规则治理 | `/api/v1/operations/rules` 返回规则健康、DMN 决策表、风险队列、服务边界和 Runbook；`/api/v1/operations/rules/review` 可把规则复核项创建为通知任务并写入审计。 |
| 预算成本治理 | `/api/v1/operations/costs` 返回预算、实际、采购承诺、可用预算、成本中心、差异队列、服务边界和 Runbook；`/api/v1/operations/costs/review` 可把预算差异创建为通知任务并写入审计。 |
| 产能计划治理 | `/api/v1/operations/capacity` 返回需求、供给、齐套、释放能力、工作中心、瓶颈队列、服务边界和 Runbook；`/api/v1/operations/capacity/review` 可把产能瓶颈创建为通知任务并写入审计。 |
| 设备可靠性治理 | `/api/v1/operations/maintenance` 返回资产线、维护工单候选、MRO 备件、维修人员、停机窗口、维护流程、服务边界和 Runbook；`/api/v1/operations/maintenance-workorder` 可把维护工单创建为通知任务并写入审计。 |
| 移动扫码终端治理 | `/api/v1/operations/mobile-terminal` 返回四条现场泳道、扫码队列、设备会话、库区覆盖、扫码流程、服务边界和 Runbook；`/api/v1/operations/mobile-terminal/task` 可把现场扫码项创建为通知任务并写入审计。 |
| 部署就绪与 ERP 成熟度看板 | `/api/v1/operations/deployment-readiness` 返回前端/后端边界、环境变量状态、健康探针、存储、AI、缓存、CORS、服务目录、能力域地图、微服务拓扑、成熟度维度、交付证据和 runbook；`/api/v1/operations/deployment-readiness/task` 可把关注项创建为通知任务并写入审计。 |
| 任务异常中心 | `/api/v1/operations/task-queue` 返回通知、部署、库存、采购统一当班队列；桌面和移动端均显示 12 条优先任务，可创建部署预检任务并处理通知。 |
| 页面截图 | `docs/images/final/` 已按最新页面和翻倍数据重新截图，并新增供应商协同桌面/移动稳定截图。 |
| 开发端口审查 | 4200 与备用 4300 均验证入口页图片墙不再撑爆，CORS 默认开发端口覆盖 4200-4230 与 4300-4310。 |
| 注册页复核 | 最新 4200 样式复核通过，注册模式为单卡居中，左侧说明面板隐藏，横向溢出为 0。 |
| 后端测试 | 2026-06-15 `python -m pytest -q` 46 项通过，包含盘点周期创建、扫码录入、完成调整、上传策略、登录限流、Cookie-only 认证、权限边界、部署预检任务通知和采购协同任务通知。 |
| 前端测试 | 2026-06-15 `npm test -- --watch=false` 6 个测试文件、19 个用例通过。 |
| 前端构建 | 2026-06-15 `npm run build` 生产构建通过，Angular 21 模板诊断警告已清零，输出 `frontend/dist/frontend/browser`。 |
| API 契约审计 | 2026-06-15 `scripts/audit-api-contracts.py` 通过，212 个前端接口使用全部匹配后端 116 个运行时路由和 31 个资源配置。 |
| 壳层交互审计 | 2026-06-15 `npm run audit:shell` 通过，桌面/移动更多模块、模块跳转、Escape 关闭、控制台错误、4xx/5xx、横向溢出和 spotlight 坐标写入均通过；报告落在 `output/playwright/shell-interaction-1781497836740/report.json`。 |
| 图表审计 | 2026-06-15 `npm run audit:charts` 36 个页面文件通过，最新报告落在 `output/playwright/chart-audit-1781497812317/report.json`。 |
| 布局审计 | 2026-06-15 `npm run audit:layout` 66 个桌面/移动页面检查通过，最新报告落在 `output/playwright/layout-audit-1781497856364/report.json`。 |
| 部署就绪与 ERP 成熟度专项审计 | 2026-06-15 `npm run audit:deployment-readiness` 通过，最新报告落在 `output/playwright/deployment-readiness-audit-1781498047746/report.json`；ERP 成熟度 91%，覆盖 6 个成熟度维度、4 个能力域、8 个拓扑节点、8 个交付证据卡，secret 泄露候选、横向溢出、控制台错误和 HTTP 错误均为 0。 |
| 部署任务点击流 | `output/playwright/deployment-task-flow-1780937731840/report.json` 证明设置页点击部署预检任务后返回 201，通知中心出现“部署预检任务 - 前端 API 地址”，控制台错误和 4xx/5xx 响应均为 0。 |
| 通知任务完成流 | `output/playwright/notification-task-complete-1780939318650/report.json` 证明部署任务创建 201、来源跳回 `/app/settings`、处理完成 200、任务卡显示“已处理”，控制台错误和 4xx/5xx 响应均为 0。 |
| 任务队列网页审核 | `output/playwright/task-queue-review-1780941937011/report.json` 证明 `/app/tasks` 桌面和移动端横向溢出为 0，队列前屏有 12 条任务，创建部署任务返回 201，处理通知返回 200，控制台错误、异常请求和 4xx/5xx 均为 0。 |
| 集成治理网页审核 | `output/playwright/integration-governance-review-1780942978805/report.json` 证明 `/app/integrations` 桌面和移动端横向溢出为 0，服务治理层有 8 个治理项，创建接口重同步任务返回 201，并在任务异常中心出现 P0 接口重同步任务。 |
| 数据质量治理网页审核 | `output/playwright/data-quality-governance-1780969703241/report.json` 证明 `/app/data-quality` 桌面和移动端横向溢出为 0，展示质量合同、整改队列、Runbook 和血缘链路，创建整改任务返回 201，并在任务异常中心出现“数据质量整改”任务。 |
| 质量检验治理网页审核 | `output/playwright/quality-inspection-governance-1780989292960/report.json` 证明 `/app/quality` 桌面和移动端横向溢出为 0，展示检验批、供应商质量、缺陷分类、使用决策、质量证据、服务边界和 Runbook，创建质量检验任务返回 201，并进入任务异常中心。 |
| 采购协同控制台网页审核 | `output/playwright/procurement-control-upgrade-1780996622570/report.json` 证明 `/app/procurement/orders` 桌面和移动端横向溢出为 0，展示 6 条采购泳道、8 张控制任务卡、6 个到货窗口、6 张供应商风险卡、5 个服务边界、4 个部署检查、2 个图表和 12 行采购账本，创建采购协同任务返回 201 并写入审计。 |
| 供应商协同专项审核 | `output/playwright/supplier-collaboration-1781009953815/report.json` 证明 `/app/suppliers/performance` 桌面和移动端横向溢出为 0，展示 5 条协同泳道、8 个任务、8 张供应商 360、8 个到货窗口、5 个服务边界、4 个部署检查、80 行账本和 2 个图表。 |
| 规则治理网页审核 | `output/playwright/rules-governance-1780973553475/report.json` 证明 `/app/rules` 桌面和移动端横向溢出为 0，展示 2 行决策表、4 条复核队列、5 个服务边界，创建规则复核任务返回 201，并在任务异常中心出现“规则复核”任务。 |
| 规则决策表截图审核 | `output/playwright/rules-decision-table-1780973745905/report.json` 证明决策表输入 3 列、输出 2 列、横向溢出 0、控制台错误和 4xx/5xx 均为 0。 |
| 预算成本治理网页审核 | `output/playwright/budget-governance-1780976362599/report.json` 证明 `/app/budget` 桌面和移动端横向溢出为 0，展示 4 个成本中心、4 条预算差异复核队列、4 个服务边界和 4 条 Runbook，创建预算复核任务返回 201，并在任务异常中心出现“经营毛利护栏预算差异复核”。 |
| 预算成本二次网页复审 | `output/playwright/webpage-review-1780976875726/report.json` 证明成功 Toast 已下移到顶部导航下方，`toastBelowTopbar=true`，桌面和移动端控制台错误、异常请求和 HTTP 4xx/5xx 均为 0。 |
| 产能计划治理网页审核 | `output/playwright/capacity-governance-1780979251443/report.json` 证明 `/app/capacity` 桌面和移动端横向溢出为 0，展示 4 个工作中心、4 条瓶颈复核队列、4 个服务边界和 4 条 Runbook，创建产能复核任务返回 201，并在任务异常中心出现“装配履约窗口产能复核”。 |
| 设备可靠性治理网页审核 | `output/playwright/maintenance-reliability-1780984911955/report.json` 证明 `/app/maintenance` 桌面和移动端横向溢出为 0，展示 4 条资产线、10 条维护工单候选、10 条 MRO 关键备件、4 名维修人员、4 个停机窗口、4 个服务边界和 4 条 Runbook，创建设备维护工单返回 201，并在任务异常中心出现“设备维护工单 - 工控屏面板 A型-0004备件保障复核”。 |
| 移动扫码终端治理网页审核 | `output/playwright/mobile-terminal-governance-1780982319037/report.json` 证明 `/app/mobile-terminal` 桌面和移动端横向溢出为 0，展示 4 条现场泳道、40 条扫码队列、4 个设备会话、4 个库区覆盖、4 个服务边界和 4 条 Runbook，创建现场扫码任务返回 201，并在任务异常中心出现“现场扫码任务 - 铜排连接件 A型-0051”。 |
| 关键页面网页复审 | `output/playwright/web-review-1780997929715/report.json` 证明总览、采购、履约、仓配流向、应收和报表 12 个桌面/移动页面有效失败请求、控制台错误、HTTP 4xx/5xx、文字撑破、越界元素和横向溢出均为 0。 |
| AI 页面复核 | `/app/ai` 桌面和移动均无横向溢出、无文字几何重叠、无图表尺寸异常，长文本和长配置项均可换行。 |
| 同类页面复核 | `/app/overview`、`/app/metrics`、`/app/content/articles`、`/app/profile` 的标签/数值重叠已清零。 |
| 双主题巡检 | 亮色/暗色共 66 个页面主题检查通过，覆盖横向溢出、文本撑破、图表尺寸、Hero 本地图片加载和 ECharts 布局 guard。 |
| 核心业务截图 | 总览、采购、履约、应收、盘点、报表和移动端已重新截图，新增暗色/亮色两套截图。 |
| 部署预检 | `scripts/preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests` 通过，旧托管平台配置、Supabase、Cookie、Cloudinary 和 Redis 共享限流缓存均通过。 |
| 交付质量闸门 | `scripts/quality-gate.ps1` 全量通过，可串联报告生成、数据审计、测试、构建、API 契约、图表、布局、部署预检和交付资产审计。 |
| 报告资产审计 | `scripts/audit-delivery-assets.py` 通过，`output/quality-gate/delivery-assets.json` 中 failures=0、warnings=0。 |

## 9. 截图清单

完整截图审核结论、路由覆盖矩阵和复现命令见 `docs/final-screenshot-report.md`。该报告基于 Playwright 登录后的真实桌面/移动访问结果，覆盖 33 条业务路由、66 个页面检查，失败数为 0。

### 9.1 入场页

![入场页](images/final/entry.png)

### 9.2 登录页

![登录页](images/final/login.png)

### 9.3 注册流程

![注册流程](images/final/register.png)

### 9.4 登录后首页

![登录后首页](images/final/after-login.png)

### 9.5 运营概览

![运营概览](images/final/overview.png)

### 9.6 Dock 与命令区

![Dock](images/final/dock.png)

### 9.7 命令菜单

![命令菜单](images/final/command.png)

### 9.8 AI 经营分析

![AI 经营分析](images/final/ai.png)

### 9.9 AI 设置与诊断

![AI 设置与诊断](images/final/ai-fix.png)

### 9.10 全局设置

![全局设置](images/final/settings.png)

### 9.11 个人工作台

![个人工作台](images/final/profile.png)

### 9.12 文件中心

![文件中心](images/final/files.png)

### 9.13 文件详情

![文件详情](images/final/file-detail.png)

### 9.14 报表工作室

![报表工作室](images/final/reports.png)

### 9.15 移动端

![移动端](images/final/mobile.png)

### 9.16 暗色总览与真实图片墙

![暗色总览](images/final/final-dark-overview.png)

### 9.17 暗色采购审批闭环

![暗色采购审批](images/final/final-dark-procurement.png)

### 9.18 暗色销售履约闭环

![暗色销售履约](images/final/final-dark-fulfillment.png)

### 9.19 暗色应收风控闭环

![暗色应收风控](images/final/final-dark-receivables.png)

### 9.20 暗色盘点扫码闭环

![暗色盘点中心](images/final/final-dark-stocktakes.png)

### 9.21 暗色报表工作室

![暗色报表工作室](images/final/final-dark-reports.png)

### 9.22 亮色运营总览

![亮色运营总览](images/final/final-light-overview.png)

### 9.23 亮色采购审批

![亮色采购审批](images/final/final-light-procurement.png)

### 9.24 亮色应收风控

![亮色应收风控](images/final/final-light-receivables.png)

### 9.25 亮色报表工作室

![亮色报表工作室](images/final/final-light-reports.png)

### 9.26 移动端亮色总览

![移动端亮色总览](images/final/final-mobile-light-overview.png)

### 9.27 移动端暗色盘点

![移动端暗色盘点](images/final/final-mobile-dark-stocktakes.png)

### 9.28 暗色集成监控

![暗色集成监控](images/final/final-dark-integrations.png)

### 9.29 亮色集成监控

![亮色集成监控](images/final/final-light-integrations.png)

### 9.30 供应商协同控制台

![供应商协同控制台](images/final/final-dark-supplier-collaboration.png)

### 9.31 移动端供应商协同

![移动端供应商协同](images/final/final-mobile-supplier-collaboration.png)

## 10. 交付文件

- `README.md`
- `docs/deployment-supabase-vercel.md`
- `docs/api-token-deployment-guide.md`
- `docs/final-completion-audit.md`
- `docs/final-delivery-report.md`
- `docs/final-screenshot-report.md`
- `docs/final-video-script.md`
- `frontend/public/images/image-sources.md`
- `scripts/preflight.ps1`
- `scripts/quality-gate.ps1`
- `scripts/audit-delivery-assets.py`
- `scripts/generate_final_report_docx.py`
- `scripts/deploy-supabase-vercel.ps1`
- `backend/scripts/sync_sqlite_to_postgres.py`
- `backend/server.py`
- `backend/vercel.json`
- `frontend/vercel.json`

## 11. 维护规范

- 新页面必须进入 `frontend/src/app/app.routes.ts` 与 `frontend/src/app/core/navigation.ts`。
- 新业务域必须在 `frontend/src/app/core/workflow-blueprints.ts` 登记闭环节点，并在 `frontend/src/app/core/visual-assets.ts` 统一登记本地图片资产。
- 新 API 必须使用 `/api/v1` 前缀和统一响应结构。
- 写操作必须校验 CSRF、权限并写入审计日志。
- 列表页面必须支持分页、搜索和详情页入口。
- 生产环境密钥只能放在环境变量中，不写入 `vercel.json` 或前端源码。
- 部署脚本输出必须经过脱敏格式化，不能把 Token、数据库连接串、Cloudinary secret 或 AI Key 打到日志。
- 上传入口必须共用 `backend/upload_policy.py`，不得在新路由里重新维护一套 MIME 或扩展名白名单。
- 文件和头像生产环境使用 Cloudinary 或后续接入 Supabase Storage，不依赖 Serverless 本地磁盘；未配置持久化存储时上传接口返回 `persistent_storage_required`。
- 前端不得把用户资料长期写入 `localStorage`，会话状态通过 HttpOnly Cookie、CSRF Cookie 和 `sessionStorage` 中的短期资料缓存恢复。
- 旧平台配置不得回流，预检脚本会阻止旧配置文件和旧域名进入活跃项目。
- 修改最终报告 Markdown 后必须重新生成 DOCX；完整交付前运行 `scripts/quality-gate.ps1`。
- 新增截图、ER 图、前端图片资源或部署文档后必须运行 `scripts/audit-delivery-assets.py`。

