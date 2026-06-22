# NEXUS Prime 制造业管理信息系统

学生：庄颂  
学号：20241334  
项目名：NEXUS Prime

NEXUS Prime 是一个前后端分离的制造业仓配经营管理信息系统。系统围绕物料、仓库、采购、销售、盘点、应收、报表、文件、公告、AI 经营分析、权限和审计建立完整业务闭环，前端使用 Angular 21 + PrimeNG 21 + Lucide + ECharts，后端使用 Flask REST API + SQLAlchemy。当前运行、构建和部署路径为 `backend/` 与 `frontend/`；`legacy/monolith-flask/` 保留为旧版 Flask/Jinja2 单体快照，用于报告对照，不参与新版运行、构建或部署。

## 当前架构

- 前端：Angular 21 Standalone Components、PrimeNG 21、PrimeIcons、Lucide、Angular CDK、ECharts、RxJS、CSS motion system、experience polish layer
- 后端：Flask 3、SQLAlchemy、Flask-Migrate、Flask-CORS、pytest、ReportLab、Cloudinary 持久化上传
- 认证：HttpOnly Cookie + CSRF Token，写请求由前端拦截器自动携带 `X-CSRF-Token`
- 数据：本地 SQLite 由 seed 命令生成，数据库运行文件不提交；生产目标为 Supabase PostgreSQL
- 部署方向：Vercel 托管前端，Flask API 独立运行，数据库使用 Supabase PostgreSQL；本地可用磁盘上传，Vercel/Serverless 生产头像和附件必须配置 Cloudinary 或接入 Supabase Storage

## 项目结构

```text
nexus_prime/
├── backend/
│   ├── app/api/             # /api/v1 REST API、认证、业务动作、聚合接口
│   ├── app/models/          # 用户、物料、库存、采购、销售、财务、内容、审计模型
│   ├── app/services/        # 采购、销售、库存、报表、AI、审计等服务
│   ├── instance/            # 本地 SQLite 运行目录（不提交数据库文件）
│   ├── migrations/          # 数据库迁移
│   ├── scripts/             # SQLite 到 PostgreSQL 数据同步工具
│   ├── storage/uploads/     # 本地上传运行目录
│   ├── tests/
│   ├── server.py            # Vercel Flask 入口
│   ├── vercel.json
│   └── run.py
├── frontend/
│   ├── src/app/core/        # API、认证、主题、模型、导航
│   ├── src/app/shell/       # 顶部命令栏、底部 Dock、上下文洞察
│   ├── src/app/pages/       # 独立业务页面与详情页
│   ├── src/styles.scss      # 全局主题、业务页面和布局稳定层
│   ├── src/auth-entry.scss  # 首页、登录、注册的独立样式层
│   ├── src/motion-system.scss # 路由入场、卡片 spotlight、Dock 弹性和 reduced-motion
│   ├── src/experience-polish.scss # 移动端动作按钮、采购工作卡和质感收口层
│   ├── src/workflow-board.scss # 每日制造经营作战流、角色座席、事件流、API 合同和阶段交接
│   ├── src/deployment-readiness.scss # 设置页上线就绪看板
│   ├── public/runtime-config.example.js
│   └── vercel.json
├── docs/
│   ├── api-token-deployment-guide.md
│   ├── final-completion-audit.md
│   ├── final-delivery-report.md
│   ├── final-screenshot-report.md
│   ├── final-video-script.md
│   ├── project-standards.md
│   ├── deployment-supabase-vercel.md
│   └── images/
├── legacy/
│   └── monolith-flask/      # 旧版 Flask/Jinja2 单体对照快照，不参与新版部署
└── scripts/
    ├── dev.ps1
    ├── install-dependencies.ps1
    ├── clean-workspace.ps1
    ├── quality-gate.ps1
    ├── audit-delivery-assets.py
    ├── generate_final_report_docx.py
    ├── preflight.ps1
    └── deploy-supabase-vercel.ps1
```

## 功能范围

- 运营首页：制造仓配闭环、每日制造经营作战流、班次执行动作队列、角色指挥席、现场事件流、前后端 API 合同、微服务边界、部署前检查、仓库网络、风险队列、交互式经营图谱
- 系统设置：主题/密度/AI 配置、Vercel/Supabase/Cloudinary/DeepSeek 入口、动态上线就绪分、ERP 成熟度验收、能力域地图、微服务拓扑、部署前检查、微服务拆分快照和可复制 runbook
- 物料与成品：物料水位、供应商、批次、库位、低库存建议
- 仓配流向：工厂仓、区域仓、库位热区、出入库流水、调度任务
- 采购协同：补货候选、采购审批、供应商确认、到货收货、质检交接、预算暴露、服务边界、协同任务和供应商绩效
- 销售履约：订单阶段、发货推进、客户窗口、应收联动
- 盘点中心：盘点计划、扫码录入、差异确认、库存调整
- 应收风控：账龄、收款、催款、信用冻结与释放
- 报表工作室：多类报表模板、生成队列、图表预览、归档
- 文件与内容：上传、下载、公告、知识文章、讨论评论
- AI 经营分析：结构化经营摘要、诊断、会话入库、多图表分析
- 系统安全：用户、角色、权限矩阵、审计日志、登录风险
- 扩展页面：经营指标、任务异常、客户、产能、设备、合同、售后、规则、集成、成本、移动扫码终端
- 数据质量治理：后端权威质量体检、主数据/仓配/采购/履约/财务维度评分、整改队列、Runbook、血缘链路和任务异常中心闭环
- 质量检验治理：后端权威检验批、供应商质量、缺陷分类、使用决策、质量证据、服务边界和任务异常中心闭环
- 产能计划治理：后端权威需求/供给/齐套/释放能力合同、工作中心负载、瓶颈复核队列、班次计划、Runbook 和任务异常中心闭环
- 设备可靠性治理：后端权威资产线、维护工单、MRO 备件、维修人员、停机窗口、服务边界、Runbook 和任务异常中心闭环
- 前端质感：统一动效 token、路由入场、Hero 揭示、业务卡片 spotlight、按钮按压反馈、Dock 弹性、图表唤醒、每日作战流阶段卡动效、移动端动作按钮居中、采购工作卡精修和 `prefers-reduced-motion` 无障碍兜底

## 企业数据

仓库不提交 `backend/instance/nexus_prime.db`。首次克隆后通过 seed 命令生成本地演示数据库。

演示数据库规模可通过 `flask status` 验证；低库存到补货、采购审批到收货、销售到应收、收款到应收、公告到讨论、报表到归档均由 seed 数据建立真实关联。

重建数据：

```powershell
cd backend
$env:FLASK_APP="run.py"
python -m flask seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334
python -m flask status
python -m flask audit-enterprise-data --strict
```

本地默认账号仅用于课程演示和截图验收。生产或远程演示库必须通过 `NEXUS_DEMO_ADMIN_PASSWORD`、`NEXUS_DEMO_USER_PASSWORD` 或部署脚本参数设置自定义密码；仓库不提交 SQLite 数据库和 `*.db-wal`、`*.db-shm`。

## 本地运行

一键启动：

```powershell
.\scripts\dev.ps1
```

强制重装依赖后启动：

```powershell
.\scripts\dev.ps1 -Install
```

只检查依赖和将使用的端口，不启动服务：

```powershell
.\scripts\dev.ps1 -CheckOnly
```

已确认依赖存在、只想快速拉起窗口时可跳过等待和自动开浏览器：

```powershell
.\scripts\dev.ps1 -NoInstall -NoWait -NoOpen
```

如果刚执行过纯净化清理并删除了 `venv/` 或 `frontend/node_modules/`，`dev.ps1` 会自动恢复依赖。也可以单独执行：

```powershell
.\scripts\install-dependencies.ps1
```

默认地址：

```text
Frontend: http://127.0.0.1:4200
Backend : http://127.0.0.1:5000/api/v1
```

Docker Compose 一键启动会同时拉起 PostgreSQL、Redis、后端 API、Celery worker 和 Angular 前端：

```powershell
.\scripts\dev.ps1 -Docker -Build
```

只检查 Docker/Compose 入口和端口：

```powershell
.\scripts\dev.ps1 -Docker -CheckOnly
```

等价 Makefile 入口：

```bash
make dev
make logs
make migrate
```

本地演示账号：

```text
admin@nexus.com / admin123
user00001@nexus.com / password123
```

远程部署种子必须使用 `NEXUS_DEMO_ADMIN_PASSWORD` 和 `NEXUS_DEMO_USER_PASSWORD` 自定义密码，部署脚本会拒绝上述本地默认密码。

## 路由

| 路径 | 页面 |
| --- | --- |
| `/auth/login` | 登录与注册入口 |
| `/app/overview` | 制造运营驾驶舱 |
| `/app/metrics` | 经营指标中心 |
| `/app/tasks` | 任务异常中心 |
| `/app/inventory/products` | 物料与成品中心 |
| `/app/inventory/stock` | 仓配流向图 |
| `/app/inventory/replenishment` | 补货建议 |
| `/app/procurement/orders` | 采购补货中心 |
| `/app/suppliers/performance` | 供应商绩效 |
| `/app/quality` | 质量检验中心 |
| `/app/sales/orders` | 销售履约中心 |
| `/app/customers` | 客户经营中心 |
| `/app/stocktakes` | 库存盘点中心 |
| `/app/finance/receivables` | 应收风控中心 |
| `/app/finance/credits` | 信用管理 |
| `/app/reports` | 报表工作室 |
| `/app/files` | 文件中心 |
| `/app/content/articles` | 公告知识库 |
| `/app/notifications` | 通知中心 |
| `/app/ai` | AI 经营分析台 |
| `/app/system/users` | 系统安全中心 |
| `/app/system/audit` | 审计日志 |
| `/app/profile` | 个人工作台 |
| `/app/capacity` | 产能计划 |
| `/app/maintenance` | 设备维护 |
| `/app/contracts` | 合同回款 |
| `/app/service` | 售后服务 |
| `/app/rules` | 规则引擎 |
| `/app/integrations` | 集成监控 |
| `/app/budget` | 预算成本 |
| `/app/mobile-terminal` | 移动扫码终端 |

列表行支持独立详情页，例如 `/app/inventory/products/:id`、`/app/procurement/orders/:id`、`/app/sales/orders/:id`、`/app/finance/receivables/:id`、`/app/reports/:id`。

## 主要 API

| 方法 | URL | 功能 |
| --- | --- | --- |
| GET | `/auth/csrf` | 获取 CSRF Token |
| POST | `/auth/login` | 设置 HttpOnly Cookie 并返回用户摘要 |
| POST | `/auth/register` | 注册账号并建立会话 |
| POST | `/auth/logout` | 清除会话 Cookie |
| GET | `/auth/me` | 当前用户 |
| PUT | `/me/profile` | 更新个人资料 |
| POST | `/me/avatar` | 上传头像 |
| GET/PUT | `/me/preferences` | 主题与工作台偏好 |
| GET | `/manufacturing/command-center` | 运营驾驶舱聚合数据 |
| GET | `/manufacturing/workflow-board` | 每日制造经营作战流、阶段进度、阻塞点、交接关系、动作队列、角色指挥席、现场事件流、前后端 API 合同、服务边界和部署前检查 |
| GET | `/analytics/executive` | 管理指标与图表 |
| GET | `/search?q=` | 全局搜索 |
| POST | `/procurement/orders/<id>/submit` | 提交采购 |
| POST | `/procurement/orders/<id>/approve` | 审批采购 |
| POST | `/procurement/orders/<id>/receive` | 采购收货 |
| POST | `/sales/orders/<id>/transition` | 销售订单流转 |
| POST | `/finance/receivables/<id>/payment` | 记录收款 |
| POST | `/finance/receivables/<id>/reminder` | 创建催款提醒 |
| POST | `/finance/credits/<id>/freeze` | 冻结信用 |
| POST | `/finance/credits/<id>/unfreeze` | 解冻信用 |
| POST | `/replenishment-suggestions/generate` | 生成补货建议 |
| POST | `/replenishment-suggestions/<id>/accept` | 补货转采购 |
| POST | `/stocktakes/create` | 创建盘点 |
| POST | `/stocktakes/<id>/start` | 开始盘点 |
| POST | `/stocktakes/<id>/count` | 录入盘点数量 |
| POST | `/stocktakes/<id>/complete` | 完成盘点 |
| POST | `/reports/generate/<type>` | 生成报表 |
| POST | `/files/upload` | 上传文件 |
| GET | `/files/<id>/download` | 下载文件 |
| GET | `/operations/rules` | 规则治理工作台数据，包含 DMN 决策表、风险队列、负责人、SLA、Runbook 和服务边界 |
| POST | `/operations/rules/review` | 将规则复核项创建为通知任务并写入审计 |
| GET | `/operations/integrations` | 集成监控数据 |
| POST | `/operations/integrations/resync` | 将微服务治理项创建为接口重同步任务并写入通知与审计 |
| GET | `/operations/data-quality` | 数据质量治理体检、维度评分、整改队列、Runbook 和血缘链路 |
| POST | `/operations/data-quality/remediation` | 将数据质量治理项创建为整改任务并写入通知与审计 |
| GET | `/operations/quality-inspection` | 质量检验治理数据，包含检验批、供应商质量、缺陷分类、使用决策、服务边界和 Runbook |
| POST | `/operations/quality-inspection` | 将检验队列项创建为质量检验任务并写入通知与审计 |
| GET | `/operations/procurement-control` | 采购协同控制台数据，包含采购泳道、审批队列、到货窗口、供应商风险、补货候选、服务边界和部署检查 |
| POST | `/operations/procurement-control/task` | 将采购控制项创建为协同通知任务并写入审计 |
| GET | `/operations/task-queue` | 任务异常中心当班队列，聚合通知、部署预检、库存预警和采购审批，并优先暴露可执行动作 |
| GET | `/operations/deployment-readiness` | 部署就绪分、ERP 成熟度验收、能力域地图、微服务拓扑、前后端密钥边界、微服务拆分快照和上线 runbook |
| POST | `/operations/deployment-readiness/task` | 将部署预检关注项写入通知中心和审计日志 |
| GET | `/operations/costs` | 成本预算数据 |
| GET | `/operations/capacity` | 产能计划治理数据，包含需求、供给、齐套、工作中心、瓶颈队列、服务边界和 Runbook |
| POST | `/operations/capacity/review` | 将产能瓶颈复核项创建为通知任务并写入审计 |
| GET | `/operations/maintenance` | 设备可靠性治理数据，包含资产线、维护工单、MRO 备件、维修人员、停机窗口、服务边界和 Runbook |
| POST | `/operations/maintenance-workorder` | 将设备维护工单创建为通知任务并写入审计 |
| GET | `/operations/mobile-terminal` | 移动现场治理数据，包含扫码泳道、任务队列、设备会话、库区覆盖、服务边界和 Runbook |
| POST | `/operations/mobile-terminal/task` | 将现场扫码项创建为通知任务并写入审计 |
| POST | `/notifications/complete` | 完成通知任务并写入审计日志 |
| POST | `/ai/chat` | 经营分析会话 |
| POST | `/ai/analyze/structured` | 结构化经营摘要 |
| POST | `/ai/diagnostics` | 分析服务诊断 |

通用列表接口仍支持 `page`、`page_size`、`q`、`sort` 和 `order` 参数。

## 测试与验收

推荐先跑总质量闸门。它会串联最终报告生成、企业数据审计、后端测试、前端测试、生产构建、图表审计、壳层交互审计、布局审计、部署预检和交付截图资产审计：

```powershell
.\scripts\quality-gate.ps1
```

如果只需要快速检查部署资料、报告和截图资产：

```powershell
.\scripts\quality-gate.ps1 -SkipBackendTests -SkipFrontendTests -SkipBuild -SkipLayoutAudit
```

质量闸门的布局审计会临时启动干净的本地后端和前端端口，跑完后自动关闭由它启动的进程，并恢复 `frontend/public/runtime-config.js`。

```powershell
cd backend
$env:FLASK_APP="run.py"
python -m flask status
python -m flask audit-enterprise-data --strict
python -m pytest
```

```powershell
cd frontend
npm test -- --watch=false
npm run build
npm run audit:shell
```

部署前本地检查：

```powershell
$env:NEXUS_API_BASE_URL="https://your-api-host.example.com/api/v1"
$env:FRONTEND_ORIGIN="https://your-vercel-domain.vercel.app"
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
$env:CORS_ORIGINS=$env:FRONTEND_ORIGIN
$env:AUTH_COOKIE_SECURE="true"
$env:AUTH_COOKIE_SAMESITE="None"
$env:SECRET_KEY="replace-with-at-least-32-random-characters"
$env:CLOUDINARY_URL="cloudinary://api_key:api_secret@cloud_name"
.\scripts\preflight.ps1 -SkipApiProbe
```

浏览器验收使用 Playwright 截图检查首页、登录、注册、Dock、AI、物料、采购、报表、规则、集成、数据质量、质量检验、预算成本、产能计划、设备维护、移动扫码终端、个人页、任务异常中心、设置页成熟度控制台和移动端布局，重点检查无控制台错误、无 4xx/5xx、无横向溢出、无空按钮、图标居中、文字不重叠。总览作战台升级专项审核见 `output/playwright/overview-command-upgrade-1780992882786/report.json`；任务队列专项审核见 `output/playwright/task-queue-review-1780941937011/report.json`；集成治理专项审核见 `output/playwright/integration-governance-review-1780942978805/report.json`；数据质量治理专项审核见 `output/playwright/data-quality-governance-1780969703241/report.json`；质量检验治理专项审核见 `output/playwright/quality-inspection-governance-1780989292960/report.json`；采购协同控制台专项审核见 `output/playwright/procurement-control-upgrade-1780996622570/report.json`；规则治理专项审核见 `output/playwright/rules-governance-1780973553475/report.json`，决策表可见性截图见 `output/playwright/rules-decision-table-1780973745905/report.json`；预算成本治理专项审核见 `output/playwright/budget-governance-1780976362599/report.json`，Toast 二次复审见 `output/playwright/webpage-review-1780976875726/report.json`；产能计划治理专项审核见 `output/playwright/capacity-governance-1780979251443/report.json`；设备可靠性治理专项审核见 `output/playwright/maintenance-reliability-1780984911955/report.json`；移动扫码终端治理专项审核见 `output/playwright/mobile-terminal-governance-1780982319037/report.json`；部署就绪与 ERP 成熟度专项审核见 `output/playwright/deployment-readiness-audit-1781498047746/report.json`；最新全站布局审计见 `output/playwright/layout-audit-1781497856364/report.json`；壳层交互审计见 `output/playwright/shell-interaction-1781497836740/report.json`；关键页面网页复审见 `output/playwright/web-review-1780997929715/report.json`。

完整交付质量闸门可一键执行：

```powershell
.\scripts\quality-gate.ps1
```

该脚本会串联 DOCX 报告生成、企业数据审计、后端测试、前端测试、生产构建、前后端 API 契约审计、图表审计、壳层交互审计、布局审计、部署就绪与 ERP 成熟度专项审计、部署预检和交付资产审计。浏览器审计临时写入本地 API 地址后会自动恢复 `frontend/public/runtime-config.js` 为空 fallback。

前后端 API 契约审计可单独执行：

```powershell
python scripts\audit-api-contracts.py
```

该脚本从 Flask 运行时 `url_map` 和后端资源配置读取权威接口，再扫描 Angular `ApiService`、详情页动作和文件下载 URL，防止页面调用已经不存在或未接入权限/资源层的接口。当前审计结果为 168/168 个前端 endpoint 匹配 114 个后端运行时路由和 31 个资源配置。

交付资产审计可单独执行：

```powershell
python scripts\audit-delivery-assets.py
```

该脚本会校验 `docs/images/final/` 截图尺寸、Markdown 图片引用、ER 图、DOCX 报告新旧、前端真实图片登记、`legacy/monolith-flask/` 对照快照和活跃项目中的死链接/待完善文案风险。

清理本地运行产物：

```powershell
.\scripts\clean-workspace.ps1 -StopDevServers
```

该脚本会清理缓存、截图输出、日志、SQLite WAL/SHM 和 Python 缓存，不删除源码、主数据库、依赖锁文件、部署配置、上传目录和头像目录。需要同时移除本地依赖时追加 `-RemoveDependencies`；需要清理本地上传附件时追加 `-PurgeUploads`；需要连头像一起清理时再追加 `-PurgeAvatars`。

删除依赖后，`.\scripts\dev.ps1`、`.\scripts\preflight.ps1` 和 `.\scripts\deploy-supabase-vercel.ps1` 都会在需要时自动恢复依赖；需要只检查部署配置、不安装且允许依赖缺失时，预检可追加 `-NoInstall -AllowMissingDependencies -SkipBuild -SkipBackendTests`。

## 部署方向

完整清单见 `docs/deployment-supabase-vercel.md` 和 `docs/api-token-deployment-guide.md`。最终交付报告见 `docs/final-delivery-report.md`，完成度审计见 `docs/final-completion-audit.md`，截图审核报告见 `docs/final-screenshot-report.md`，视频讲稿见 `docs/final-video-script.md`，项目规范见 `docs/project-standards.md`。仓库已移除旧托管平台配置；`legacy/monolith-flask/` 保留为旧版报告对照快照，部署前预检会检查活跃项目是否重新引入旧平台文件或旧域名。

### Vercel 前端

Vercel Project Root 选择 `frontend/`：

```text
Framework Preset: Angular
Build Command: npm run build
Output Directory: dist/frontend/browser
```

生产 API 地址通过 Vercel 环境变量 `NEXUS_API_BASE_URL` 注入。`npm run build` 会执行 `frontend/scripts/write-runtime-config.mjs`，生成 `frontend/public/runtime-config.js`：

```env
NEXUS_API_BASE_URL=https://your-api-host.example.com/api/v1
```

### Flask API + Supabase PostgreSQL

后端可作为独立 Flask API 部署。Vercel 入口为 `backend/server.py`，配置为 `backend/vercel.json`；也可使用 `backend/Procfile` 部署到支持 Gunicorn 的 Python 平台。数据库使用 Supabase PostgreSQL。推荐使用 Supabase Pooler 连接串，并设置：

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
CORS_ORIGINS=https://your-vercel-domain.vercel.app
FRONTEND_ORIGIN=https://your-vercel-domain.vercel.app
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=None
SECRET_KEY=replace-with-at-least-32-random-characters
CACHE_TYPE=RedisCache
REDIS_URL=redis://cache.example.com:6379/0
CACHE_REDIS_URL=redis://cache.example.com:6379/0
```

跨域 Cookie 必须使用 HTTPS、`Secure=true`、`SameSite=None`。生产登录限流必须配置 Redis/Upstash 共享缓存，避免 Serverless 多实例下只在单实例内存中计数。本地开发可使用 `backend/storage/uploads/`，但 Vercel/Serverless 的本地磁盘是临时目录，生产头像和附件长期保存必须配置 `CLOUDINARY_URL`，或后续接入 Supabase Storage 适配器。

一键部署：

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

## 清理规则

不要提交：

```text
node_modules/
venv/
__pycache__/
dist/
.angular/cache/
output/
frontend/output/
.playwright-cli/
backend/storage/uploads/*
!backend/storage/uploads/avatars/.gitkeep
data_export/
*.db-wal
*.db-shm
```

保留但不运行：

```text
legacy/monolith-flask/
```

本地运行数据库不提交：

```text
backend/instance/nexus_prime.db
```
