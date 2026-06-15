# NEXUS Prime 架构维护审阅

## 1. 当前架构定位

NEXUS Prime 已从旧单体形态整理为前后端分离架构：

```text
frontend/  Angular SPA，负责登录、工作台、图表、页面交互和 Vercel 前端发布
backend/   Flask REST API，负责认证、权限、业务流程、数据库、AI 调用、文件与头像
scripts/   本地开发、清理、质量闸门、预检、Supabase/Vercel 一键部署
docs/      部署说明、接口清单、项目规范、最终汇报和截图
```

浏览器只知道 `NEXUS_API_BASE_URL`，所有数据库连接、AI Key、文件存储密钥、Cookie 策略都留在后端。生产数据库目标是 Supabase PostgreSQL，前端和后端分别创建独立 Vercel 项目。

`legacy/monolith-flask/` 作为旧版 Flask/Jinja2 单体快照保留，用于对照说明从 Railway 单体页面升级到前后端分离架构；它不参与新版运行、构建、部署或活跃 API 扫描。

## 2. 前端维护边界

核心入口：

```text
frontend/src/app/app.routes.ts             路由表
frontend/src/app/shell/app-shell.component.ts  应用壳层、顶部栏、Dock、搜索、更多菜单
frontend/src/app/core/navigation.ts        Dock、更多模块、导航分组、可见入口顺序
frontend/src/app/core/visual-assets.ts     真实图片资源登记
frontend/src/app/core/theme.service.ts     主题、密度、Dock 标签、图表动效偏好
frontend/src/app/pages/page-utils.ts       页面通用格式化和图表辅助
frontend/src/styles.scss                   全局主题、业务页规则与布局稳定层
frontend/src/auth-entry.scss               首页、登录页、注册流程的独立样式层
frontend/src/motion-system.scss            跨页面动效、spotlight 与 reduced-motion
frontend/src/experience-polish.scss        移动端动作按钮、工作卡和最终质感收口层
```

Dock 桌面/移动可见项和排序 helper 已集中在 `core/navigation.ts`，壳组件只消费配置。纵览页使用 `core/visual-assets.ts` 读取真实图片，避免页面模板散落路径。

2026-06-06 维护重点：

- 首页、登录页、注册流程改为独立 `auth-entry.scss` 维护，避免继续扩大 `styles.scss` 的历史覆盖链。
- 首页使用简约首屏和本地真实现场图；登录页保留左右信息结构；注册流程改为单卡居中，隐藏左侧说明面板，验证码、许可确认和提交按钮完整可见。
- 首页右侧图片墙增加最终稳定层，`.entry-operations-card.entry-minimal-panel` 与 `.entry-photo-mosaic` 在 `styles.scss` 文件尾部收束尺寸，避免历史样式或热更新顺序把图片撑成整页。
- 图标按钮、Dock、抽屉图标、头像入口使用统一居中约束。
- 文件中心移动端类型筛选改为两列网格，消除横向溢出。
- AI 分析、报表工作室、文件中心、个人工作台的图表和分页尺寸统一兜底。
- AI 分析台进一步补强结构化摘要、行动队列、服务设置、诊断卡片、消息流和长配置项的换行规则；概览、指标、内容中心、个人页的共享 KPI/图表头卡片统一纵向节奏，消除标签与数值重叠。
- `frontend/scripts/layout-audit.mjs` 新增可见文本几何重叠检测，修正 `viewport` 字段覆盖问题，并排除隐藏 Dock tooltip，避免误报不可见浮层。
- 更多模块抽屉打开时隐藏顶部栏，避免右侧窗口和顶部栏视觉叠压。
- 开发 CORS 默认覆盖 4200-4230 与 4300-4310，方便用备用端口做 Playwright 视觉审查；生产仍必须通过 `CORS_ORIGINS` 精确设置。
- 企业演示数据库已在 2026-06-15 审计到用户 15001、商品 57608、销售订单 100803、文件 7200，并通过业务闭环审计。

## 3. 纵览页结构

`frontend/src/app/pages/command-center.page.ts` 现在按业务优先级组织：

```text
顶部经营入口        业务叙事、现场图片、顶部交互图表、关键 KPI
业务处理账本        物料、采购、履约、应收
核心经营图表        流向、风险、仓库、健康、压力、节奏切换
流程闭环            低库存 -> 补货 -> 采购 -> 收货 -> 发货 -> 回款 -> 归档
流向与风险          现场流向网络、优先处理墙
快捷系统            指标、任务、AI 分析
补充图表与 Playbook  出入库账本、仓库热力、行动路径
```

样式稳定层集中命中 `.command-overview-refined` 与末尾全局兜底层。全局兜底层只处理居中、溢出、图标对齐、分页、图表最小尺寸和移动端网格，不承接业务逻辑。真实图片来自 `frontend/public/images/`，部署前由 `scripts/preflight.ps1` 检查文件存在。

## 4. 后端维护边界

核心入口：

```text
backend/run.py                         Flask app 入口
backend/server.py                      Vercel 后端入口
backend/app/api/                       REST API 路由
backend/app/services/                  业务服务、AI、报表、库存、采购、销售、财务
backend/app/models/                    SQLAlchemy 模型
backend/migrations/                    Alembic 迁移
backend/scripts/sync_sqlite_to_postgres.py  本地 SQLite 到 Supabase 同步
backend/tests/                         API 与业务测试
```

后端必须保持 `/api/v1` 前缀和 `{ data, message, error }` 响应结构。写接口必须经过登录、权限和 CSRF。AI 外部模型调用在后端完成，前端只通过 `/api/v1/ai/*` 读写设置和触发分析。

2026-06-07 维护重点：

- 前端新增 `frontend/src/app/core/api-url.ts`，统一处理运行时 API 地址、`/api/v1` 前缀和文件下载 URL，避免页面级硬编码后端域名。
- 生产后端启动时强校验 `SECRET_KEY`、`DATABASE_URL`、`CORS_ORIGINS` 和跨站 Cookie 策略；默认拒绝 SQLite，防止误把本地演示数据库当生产数据库。
- AI 外部模型调用改为可配置短超时，默认 `AI_REQUEST_TIMEOUT_SECONDS=20`、`AI_CONNECT_TIMEOUT_SECONDS=5`；健康检查会暴露当前超时配置，便于上线排障。
- 增加配置测试，覆盖生产数据库保护和 AI 超时边界。
- 上传存储已拆成三类专用位置：用户附件进入 `UPLOAD_FILES_FOLDER`，头像进入 `UPLOAD_AVATARS_FOLDER`，种子资料库和系统资料进入 `UPLOAD_LIBRARY_FOLDER`。`GET /api/v1/health` 会返回 `storage.folders` 和 `storage.writable`，接口测试覆盖新路径、旧根目录附件和资料库附件下载兼容。
- 上传类型策略已抽到 `backend/upload_policy.py`，API 上传、头像和 `save_file()` 共享扩展名、MIME、危险类型、文件头和 Office Zip 结构校验，避免入口策略分叉和普通 zip 伪装成文档。
- `scripts/deploy-supabase-vercel.ps1` 的命令输出新增脱敏层，`VERCEL_TOKEN`、`DATABASE_URL`、Cloudinary secret、AI Key 和远程演示密码不会在脚本日志中明文出现。
- 前端 `AuthService` 不再把用户资料写入 `localStorage`，只保留会话级缓存并在启动时清理旧版本遗留资料。
- 登录接口增加同 IP + 邮箱维度失败限流，未知邮箱也计入窗口并写入审计；生产环境要求 Redis/Upstash 共享缓存，避免 Serverless 多实例削弱限流。
- 登录/注册响应体不再返回可读 JWT，前端只依赖 HttpOnly Cookie、CSRF Cookie 和会话级用户摘要；全局搜索、运营待办和运营异常按用户边界过滤附件和通知。
- `seed-enterprise` 会在本地资料库目录生成可下载的 PDF、XLSX、DOCX、CSV 业务资料文件，文件中心不再只有数据库记录。
- 总览页现场图扩展到质检、维护、合同回款、接口监控、数据质量、服务工单、成本计划和移动扫码；移动端保留横向现场图片区，不再直接隐藏真实图片。
- 新增 `scripts/quality-gate.ps1`，将最终报告 DOCX 生成、企业数据审计、后端测试、前端测试、生产构建、前后端 API 契约审计、图表审计、布局审计、部署预检和交付资产审计串联为可重复执行的交付流水线。
- 新增 `scripts/audit-api-contracts.py`，从 Flask 运行时 `url_map`、后端资源配置和 Angular `ApiService` 调用中生成契约校验，防止页面调用漂移到不存在的后端接口。
- 新增 `scripts/audit-delivery-assets.py`，检查最终截图、ER 图、Markdown 图片引用、DOCX 报告同步、前端真实图片登记、旧版快照保留和活跃项目死链接风险。
- 集成监控页的 Runbook 标题、状态和标签已收敛为计算属性，模板层不再重复做可空链判断；生产构建的 Angular 21 模板诊断警告已清零。
- 新增 `frontend/src/motion-system.scss`，把路由入场、Hero 揭示、卡片 spotlight、按钮按压、Dock 弹性、图表唤醒和 reduced-motion 统一到独立动效层。该层位于 `styles.scss` 与 `auth-entry.scss` 之后加载，用作最终质感层，而不是继续扩大历史大样式文件。
- `AppShellComponent` 增加 requestAnimationFrame 节流的 pointer spotlight 坐标写入，只对业务工作台内的卡片、Dock、上下文卡、记录行和操作入口生效；监听器和动画帧会在销毁时清理，避免路由切换后残留。
- 2026-06-15 复核时将 spotlight 从文档描述补齐为壳层实际能力，并把 `npm run audit:shell` 纳入 `scripts/quality-gate.ps1`；该审计会在桌面和移动端移动鼠标，确认 `.spotlight-active` 以及 `--spotlight-x/y` 已写入。
- 本轮查询 curated skills 后确认没有新的前端/动画专项 skill；采用已安装的 `frontend-design`、`frontend-ui-engineering`、`redesign-existing-projects`、`gpt-taste` 和 `playwright`。未引入 GSAP，是为了控制 ERP 管理台包体、避免部署复杂度增加，并保持布局审计稳定。
- 新增 `frontend/src/experience-polish.scss`，把真实截图复核后发现的移动端动作按钮、采购审批工作卡和管线按钮高光集中到最终精修层。该层只做视觉和触控体验收口，不放页面数据、权限或业务判断。
- 新增 `backend/app/services/rules_service.py`，把库存补货、采购审批、应收信用、报表归档和关键写入审计规则从页面本地数组迁移到后端服务层，返回 DMN 风格决策表、风险队列、负责人、SLA、Runbook、服务边界和监控指标；`/operations/rules/review` 将复核项写入通知和审计。

## 5. 可升级性规则

- 新页面先补路由，再补导航配置，最后补布局审计路径。
- 新图片先进入 `frontend/public/images/`，再进入 `core/visual-assets.ts`。
- 新列表接口必须支持 `page`、`page_size`、`q`、`sort`、`order`。
- 新前端接口调用、详情页动作 endpoint 或文件下载 URL 必须通过 `scripts/audit-api-contracts.py`；通用资源需进入后端资源配置，专用动作需在 Flask 路由中显式存在。
- 新业务动作必须写审计日志，并在前端保留明确反馈。
- 新规则或策略页面必须优先沉淀为后端治理合同，至少包含输入、输出、命中条件、负责人、SLA、Runbook 和任务创建入口；不得只在前端写静态规则说明。
- 新图表必须有稳定高度、tooltip、legend 或可读替代状态。
- 新部署变量必须同时更新 `.env.example`、部署文档和 `preflight.ps1`。
- 新的页面级样式优先写在页面类名作用域内；认证入口继续维护在 `auth-entry.scss`；只有跨页面稳定性问题才进入 `styles.scss` 末尾兜底层，且不得在文件前部重复放置同类兜底。
- 新增跨页面动效必须优先进入 `motion-system.scss`，不得继续分散到页面样式尾部；动效必须使用 transform、opacity、filter、box-shadow 等低重排属性，并保留 `prefers-reduced-motion` 兜底。
- 新增跨页面视觉精修优先进入 `experience-polish.scss`，并用页面级父类约束选择器；它只允许处理触控按钮、工作卡、状态胶囊、hover 高光和最终截图级别的质感问题。
- 需要鼠标位置驱动的 spotlight 或物理反馈必须复用 AppShell 的 `--spotlight-x`、`--spotlight-y` 机制，不得在单个页面重复注册全局 pointermove 监听器。
- 图表头、KPI 卡、状态卡、头像/身份区、AI 消息流和设置表单改动后，必须确认 `npm run audit:layout` 的 `overlapIssues`、`overflowingText`、`badRects` 均为空。
- 外部 AI Key、Supabase secret key、Vercel Token、Cloudinary secret 永远只进入后端或部署脚本环境变量，不进入浏览器端。
- Vercel/Serverless 或 `/tmp` 临时运行目录中，头像和文件上传必须配置 Cloudinary 或后续 Supabase Storage；未配置时接口返回 `persistent_storage_required`，避免临时磁盘造成刷新后丢失。独立长驻主机可使用本地三目录存储，但必须把 `storage/uploads` 纳入持久卷或备份策略。
- 生产登录限流必须使用 `CACHE_TYPE=RedisCache` 和 `REDIS_URL`/`CACHE_REDIS_URL`；只有本地演练可显式设置 `ALLOW_PRODUCTION_SIMPLE_CACHE=true`。
- 生产环境不得使用 SQLite，除非只做本地演练并显式设置 `ALLOW_PRODUCTION_SQLITE=true`；正式部署必须使用 PostgreSQL `DATABASE_URL`。

## 6. 稳定性检查

部署前固定执行：

```powershell
.\scripts\quality-gate.ps1
```

只做报告、截图、ER 图、部署资料和资产引用快速复核时：

```powershell
.\scripts\quality-gate.ps1 -SkipBackendTests -SkipFrontendTests -SkipBuild -SkipLayoutAudit
```

单项排查可继续使用：

```powershell
cd frontend
npm run build
npm run audit:charts
npm run audit:layout
```

```powershell
cd backend
$env:FLASK_APP="run.py"
..\venv\Scripts\python.exe -m pytest
..\venv\Scripts\python.exe -m flask audit-enterprise-data --strict
```

```powershell
$env:NEXUS_API_BASE_URL="https://<backend-project>.vercel.app/api/v1"
$env:FRONTEND_ORIGIN="https://<frontend-project>.vercel.app"
$env:CORS_ORIGINS=$env:FRONTEND_ORIGIN
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
$env:AUTH_COOKIE_SECURE="true"
$env:AUTH_COOKIE_SAMESITE="None"
$env:SECRET_KEY="<至少32位强随机字符串>"
$env:CLOUDINARY_URL="cloudinary://api_key:api_secret@cloud_name"
$env:AI_REQUEST_TIMEOUT_SECONDS="20"
$env:AI_CONNECT_TIMEOUT_SECONDS="5"
.\scripts\preflight.ps1 -SkipApiProbe
```

真实 API 发布后移除 `-SkipApiProbe`。

## 7. 部署准备状态

- 前端 Vercel 项目根目录：`frontend/`
- 后端 Vercel 项目根目录：`backend/`
- 前端生产变量：`NEXUS_API_BASE_URL`
- 后端生产变量：`FLASK_CONFIG`、`DATABASE_URL`、`SECRET_KEY`、`CORS_ORIGINS`、`FRONTEND_ORIGIN`、Cookie 策略、`NEXUS_RUNTIME_DIR`、`UPLOAD_FILES_FOLDER`、`UPLOAD_AVATARS_FOLDER`、`UPLOAD_LIBRARY_FOLDER`、`CLOUDINARY_URL`、`REQUIRE_CLOUD_STORAGE_FOR_UPLOADS`、`AI_REQUEST_TIMEOUT_SECONDS`、`AI_CONNECT_TIMEOUT_SECONDS`
- 数据库目标：Supabase PostgreSQL，连接串保留 `sslmode=require`
- 一键部署入口：`scripts/deploy-supabase-vercel.ps1`
- 远程演示账号密码：通过 `NEXUS_DEMO_ADMIN_PASSWORD` 和 `NEXUS_DEMO_USER_PASSWORD` 注入，远程 seed 拒绝本地默认密码。
- 部署前审计入口：`scripts/preflight.ps1`
- 全流程质量闸门：`scripts/quality-gate.ps1`
- 报告与截图资产审计：`scripts/audit-delivery-assets.py`

## 8. 2026-06-10 验收结果

| 检查项 | 结果 |
| --- | --- |
| 入口页视觉审查 | 4200 显示单屏首屏，图片墙高度 370px，不再撑爆页面。 |
| 截图资产 | `docs/images/final/` 已按最新首页、登录、注册、概览、AI、报表、文件、设置、个人和移动端重新生成。 |
| 注册页复核 | 注册模式为单卡居中，左侧说明面板隐藏，横向溢出为 0。 |
| 存储持久化 | 附件、头像、资料库已拆到专用目录；本地清理默认保留目录结构，Serverless 未配置 Cloudinary 时上传返回 `persistent_storage_required`。 |
| 数据扩容 | `seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 可重建大规模演示库；本次 `flask status` 显示用户 15001、商品 57608、销售订单 100803、文件 7200。 |
| 企业数据审计 | `flask audit-enterprise-data --strict` 通过，业务闭环数据 OK。 |
| 后端健康检查 | `GET /api/v1/health` 返回 `status=ok`。 |
| 后端测试 | `pytest -q` 46 项通过。 |
| 前端测试 | `npm test -- --watch=false` 5 个测试文件、15 个用例通过。 |
| 前端构建 | `npm run build` 生产构建通过，Angular 21 模板诊断警告已清零；动效系统接入后初始包体仍低于生产预算。 |
| API 契约审计 | `scripts/audit-api-contracts.py` 通过，168 个前端接口使用全部匹配后端 114 个运行时路由和 31 个资源配置。 |
| 图表审计 | `npm run audit:charts` 36 个页面文件通过，最新报告落在 `output/playwright/chart-audit-*/report.json`。 |
| 布局审计 | `scripts/quality-gate.ps1` 启动本地前后端后运行布局审计，66 个桌面/移动页面检查通过，最新报告落在 `output/playwright/layout-audit-1781497856364/report.json`。 |
| 部署就绪与 ERP 成熟度审计 | `npm run audit:deployment-readiness` 通过，最新报告落在 `output/playwright/deployment-readiness-audit-1781498047746/report.json`；设置页成熟度控制台覆盖 6 个成熟度维度、4 个能力域、8 个拓扑节点和 8 个交付证据卡。 |
| AI 排版复核 | `/app/ai` 桌面和移动均无横向溢出、无文字几何重叠、无图表尺寸异常。 |
| 同类排版复核 | `/app/overview`、`/app/metrics`、`/app/content/articles`、`/app/profile` 的标签/数值重叠已清零。 |
| 部署预检 | `preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests` 通过。 |
| 壳层交互审计 | 2026-06-15 `npm run audit:shell` 通过，桌面/移动更多模块、模块跳转、Escape 关闭、控制台错误、4xx/5xx、横向溢出和 spotlight 坐标写入均通过；报告落在 `output/playwright/shell-interaction-1781497836740/report.json`。 |
| 完整质量闸门 | `scripts/quality-gate.ps1` 全量通过；2026-06-15 已把壳层交互审计纳入质量闸门，浏览器审计后会恢复 `frontend/public/runtime-config.js`，再执行部署预检和交付资产审计。 |

