# Supabase + Vercel 部署前置清单

本项目采用前后端分离部署：`frontend/` 是 Vercel 上的 Angular SPA，`backend/` 是独立 Flask API，生产数据库使用 Supabase PostgreSQL。仓库已移除旧托管平台配置和运行缓存；`legacy/monolith-flask/` 保留为旧版 Flask/Jinja2 单体快照，用于报告对照，不参与新版运行、构建或部署。本地上传目录只保留 `.gitkeep`，真实上传文件不进入版本库，`scripts/preflight.ps1` 会阻止旧平台配置回流。

详细 API、Token 获取入口和接口清单见 `docs/api-token-deployment-guide.md`。

官方核对入口：

- Vercel 环境变量：https://vercel.com/docs/environment-variables
- Vercel CLI env：https://vercel.com/docs/cli/env
- Vercel 敏感环境变量：https://vercel.com/docs/environment-variables/sensitive-environment-variables
- Supabase 数据库连接串：https://supabase.com/docs/reference/postgres/connection-strings
- Supabase SSL Enforcement：https://supabase.com/docs/guides/platform/ssl-enforcement

2026-06-06 已再次核对官方资料：Vercel CLI 支持 `vercel env add ... --sensitive`，Supabase transaction pooler 适合 Serverless/短生命周期函数并使用 `6543`，Supabase API Key 位于 Dashboard 的 `Settings -> API Keys`，生产 PostgreSQL 连接保留 SSL。

## 0.1 架构维护边界

部署前需要确认本地代码仍保持以下边界：

```text
frontend/src/app/core/navigation.ts     导航、Dock、更多菜单、可见入口顺序
frontend/src/app/core/visual-assets.ts  前端真实图片资源登记
frontend/src/app/pages/page-utils.ts    页面通用格式化与图表工具
frontend/src/styles.scss                全局主题与业务页面布局稳定层
frontend/src/auth-entry.scss            首页、登录、注册独立样式层
backend/app/api/                        REST API 路由
backend/app/services/                   业务服务、AI、报表、库存、采购、销售、财务
backend/migrations/                     Supabase PostgreSQL schema 迁移
scripts/preflight.ps1                   部署前配置、资源、构建与测试检查
scripts/quality-gate.ps1                报告、数据、测试、构建、API 契约、布局、部署预检和交付资产总闸门
scripts/audit-api-contracts.py          Angular 调用与 Flask 运行时路由/资源配置契约审计
scripts/audit-delivery-assets.py        截图、ER 图、Markdown 图片和前端真实图片资源审计
```

浏览器端只允许读取 `NEXUS_API_BASE_URL`。`DATABASE_URL`、`SECRET_KEY`、Supabase secret key、DeepSeek API Key、Cloudinary secret 等服务端密钥只能放在后端项目环境变量中。

更多架构维护说明见 `docs/architecture-maintenance-review.md`，项目规范见 `docs/project-standards.md`。

## 0. 纯净仓库边界

当前活跃目录：

```text
backend/       Flask REST API、模型、迁移、测试、Vercel 后端配置
frontend/      Angular SPA、运行时 API 配置、Vercel 前端配置
scripts/       本地启动、清理、预检、一键部署脚本
docs/          最终报告、部署文档、接口文档、截图与讲稿
legacy/        旧版 Flask/Jinja2 单体快照，仅用于升级对照
```

已清理或禁止提交：

```text
data_export/
output/
frontend/output/
.playwright-cli/
frontend/.angular/
frontend/dist/
backend/.pytest_cache/
__pycache__/
backend/storage/uploads/*
backend/storage/uploads/files/*
backend/storage/uploads/avatars/*
backend/storage/uploads/library/*
backend/instance/*.db-wal
backend/instance/*.db-shm
*.log
.env
.vscode/
```

`legacy/monolith-flask/` 可以提交并应当保留；它不进入 Vercel 项目 Root，也不会被 `scripts/preflight.ps1` 当作活跃项目扫描对象。

本地清理命令：

```powershell
.\scripts\clean-workspace.ps1 -StopDevServers
```

需要同时移除本地依赖时再运行：

```powershell
.\scripts\clean-workspace.ps1 -StopDevServers -RemoveDependencies
```

`-RemoveDependencies` 会删除 `venv/` 和 `frontend/node_modules/`，之后需要重新执行 `.\scripts\dev.ps1 -Install`。

如果仓库处于纯净交付状态，下面三个脚本会自动恢复缺失依赖：

```powershell
.\scripts\dev.ps1
.\scripts\preflight.ps1 -SkipApiProbe
.\scripts\deploy-supabase-vercel.ps1 <参数见第 4 节>
```

运行生产预检前，需要按第 3.2 节设置 `DATABASE_URL`、Cookie 变量、`SECRET_KEY` 和 `CLOUDINARY_URL`。

完整交付或正式部署前推荐先运行总质量闸门：

```powershell
.\scripts\quality-gate.ps1
```

如果只是复核部署资料、最终报告、截图和资源引用，可运行快速模式：

```powershell
.\scripts\quality-gate.ps1 -SkipBackendTests -SkipFrontendTests -SkipBuild -SkipLayoutAudit
```

也可以单独执行依赖准备：

```powershell
.\scripts\install-dependencies.ps1
```

## 1. Vercel 前端项目

在 Vercel 新建项目时选择：

```text
Project Root: frontend
Framework Preset: Angular
Build Command: npm run build
Output Directory: dist/frontend/browser
```

前端只需要一个生产环境变量：

```env
NEXUS_API_BASE_URL=https://your-api-host.example.com/api/v1
```

不要把后端密钥、Supabase 数据库连接串、DeepSeek API Key 放进 Vercel 前端项目。`frontend/vercel.json` 只负责 Angular 构建、SPA 路由回退和静态响应头；密钥通过 Vercel Dashboard 的 Environment Variables 配置。

前端环境变量矩阵：

| 名称 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `NEXUS_API_BASE_URL` | 是 | `https://nexus-prime-api.vercel.app/api/v1` | 必须 HTTPS，必须以 `/api/v1` 结尾。 |

前端部署注意：

- Vercel 前端项目只配置 `NEXUS_API_BASE_URL`。
- 生产构建前 `frontend/scripts/write-runtime-config.mjs` 会生成 `public/runtime-config.js`。
- `runtime-config.js` 必须 no-store，避免 API 地址缓存到旧后端。
- 命令行部署时，`scripts/deploy-supabase-vercel.ps1` 会同时写入 Vercel build env 与 runtime env。

## 2. Flask API 项目

后端部署到独立 Python/Flask 托管环境，入口在 `backend/`。Vercel 入口为 `backend/server.py`，配置文件为 `backend/vercel.json`：

```text
Start Command: gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --timeout 120
Health Check: /api/v1/health
```

必须配置：

```env
FLASK_ENV=production
SECRET_KEY=replace-with-at-least-32-random-characters
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
CORS_ORIGINS=https://your-vercel-domain.vercel.app
FRONTEND_ORIGIN=https://your-vercel-domain.vercel.app
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=None
NEXUS_RUNTIME_DIR=/tmp/nexus-prime
UPLOAD_FOLDER=/tmp/nexus-prime/storage/uploads
UPLOAD_FILES_FOLDER=/tmp/nexus-prime/storage/uploads/files
UPLOAD_AVATARS_FOLDER=/tmp/nexus-prime/storage/uploads/avatars
UPLOAD_LIBRARY_FOLDER=/tmp/nexus-prime/storage/uploads/library
USE_CLOUD_STORAGE=auto
REQUIRE_CLOUD_STORAGE_FOR_UPLOADS=auto
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
```

可选配置：

```env
AI_LOCAL_ANALYSIS=true
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

后端环境变量矩阵：

| 名称 | 必填 | 推荐值 | 说明 |
| --- | --- | --- | --- |
| `FLASK_ENV` | 是 | `production` | 生产模式。 |
| `FLASK_CONFIG` | 是 | `production` | 启用生产配置校验。 |
| `DATABASE_URL` | 是 | Supabase Pooler PostgreSQL URL | 必须包含 `sslmode=require`。 |
| `SECRET_KEY` | 是 | 32 位以上强随机字符串 | 用于 JWT 与验证码签名。 |
| `CORS_ORIGINS` | 是 | 前端 Vercel 域名 | 精确域名，不使用 `*`。 |
| `FRONTEND_ORIGIN` | 是 | 前端 Vercel 域名 | 用于跳转和 Cookie 场景。 |
| `AUTH_COOKIE_SECURE` | 是 | `true` | 跨站 Cookie 必须启用。 |
| `AUTH_COOKIE_SAMESITE` | 是 | `None` | 前后端不同域时必须为 `None`。 |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | 建议 | `8` | 同一 IP + 邮箱窗口内登录失败上限，防撞库和枚举。 |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | 建议 | `600` | 登录失败计数窗口秒数。 |
| `CACHE_TYPE` | 是 | `RedisCache` | 生产登录限流使用共享缓存。 |
| `REDIS_URL` / `CACHE_REDIS_URL` | 是 | `redis://...` 或 `rediss://...` | Redis/Upstash 连接串，让限流跨 Vercel 实例生效。 |
| `NEXUS_RUNTIME_DIR` | 是 | `/tmp/nexus-prime` | Serverless 临时运行目录。 |
| `UPLOAD_FILES_FOLDER` | 建议 | `/tmp/nexus-prime/storage/uploads/files` | 本地/长驻主机用户附件目录。 |
| `UPLOAD_AVATARS_FOLDER` | 建议 | `/tmp/nexus-prime/storage/uploads/avatars` | 本地/长驻主机头像目录。 |
| `UPLOAD_LIBRARY_FOLDER` | 建议 | `/tmp/nexus-prime/storage/uploads/library` | 本地/长驻主机系统资料库目录。 |
| `USE_CLOUD_STORAGE` | 是 | `auto` | 生产有 Cloudinary 凭据时启用云存储。 |
| `REQUIRE_CLOUD_STORAGE_FOR_UPLOADS` | 是 | `auto` | Vercel/临时磁盘环境强制头像和附件使用持久化存储。 |
| `CLOUDINARY_URL` | 是 | `cloudinary://...` | Vercel 生产头像和附件长期保存。 |
| `AI_LOCAL_ANALYSIS` | 建议 | `true` | 外部模型不可用时仍可分析。 |
| `DEEPSEEK_API_KEY` | 可选 | `sk-...` | 外部 AI 分析服务。 |
| `DEEPSEEK_BASE_URL` | 可选 | `https://api.deepseek.com` | 可由用户设置覆盖。 |
| `DEEPSEEK_MODEL` | 可选 | `deepseek-chat` | 默认模型。 |

后端部署注意：

- Serverless 环境必须设置 `NEXUS_RUNTIME_DIR=/tmp/nexus-prime`，本地目录仅用于临时处理和健康检查；长期保存依赖 Cloudinary 或后续 Supabase Storage。
- 独立长驻主机可以使用本地三目录存储，但必须把 `UPLOAD_FILES_FOLDER`、`UPLOAD_AVATARS_FOLDER`、`UPLOAD_LIBRARY_FOLDER` 指向持久卷。
- Vercel 环境变量中 `DATABASE_URL`、`SECRET_KEY`、`DEEPSEEK_API_KEY`、`CLOUDINARY_URL` 应标记为 sensitive。
- Vercel 环境变量中 `REDIS_URL` 或 `CACHE_REDIS_URL` 也应标记为 sensitive；未配置共享缓存时生产后端会拒绝启动，避免登录限流只在单实例内存中生效。
- 如果没有配置 `CLOUDINARY_URL`，Vercel/Serverless 环境下头像和文件上传会返回 `persistent_storage_required`，避免“上传成功但刷新后丢失”。本地或长驻主机上传会分别进入 `files/`、`avatars/`、`library/` 专用目录。
- 后端 `vercel.json` 排除 `instance/`、`storage/`、`logs/`、`tests/` 和运行产物，避免把本地数据库或上传文件打包进函数。
- Flask API 的 Vercel 入口是 `backend/server.py`，本地和其他 Python host 入口仍是 `backend/run.py`。

## 3. Supabase 数据库

在 Supabase Dashboard 的 Connect 面板复制 PostgreSQL 连接串。独立长驻后端可使用 direct connection；如果托管环境只有 IPv4，使用 Supavisor session pooler；如果后端是 serverless/短生命周期环境，使用 transaction pooler。生产连接串统一保留 `sslmode=require`。

连接模式建议：

| 场景 | 推荐连接 |
| --- | --- |
| 迁移、备份、GUI、长期管理任务 | Direct connection，支持 IPv6 或已开 IPv4 add-on 时使用。 |
| 长驻后端且网络仅 IPv4 | Supavisor session pooler，常见端口 `5432`。 |
| Vercel Serverless、短生命周期 API、edge-like 运行时 | Supavisor transaction pooler，常见端口 `6543`。 |

如果使用 transaction pooler，后端数据库驱动不得依赖 prepared statements。当前项目通过 SQLAlchemy 常规查询访问，部署前仍需执行 `flask db upgrade` 和业务数据审计。

初始化或升级数据库：

```powershell
cd backend
$env:FLASK_APP="run.py"
python -m flask db upgrade
python -m flask status
python -m flask audit-enterprise-data --strict
```

如需重建数据，先确认目标库可被清空，再运行：

```powershell
cd backend
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
python reset_db.py --i-understand-destroy-data --allow-remote --expected-host "aws-0-<region>.pooler.supabase.com"
python -m flask seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334
```

远程数据库默认禁止 reset。`reset_db.py` 必须同时传入显式销毁确认、远程允许标志和预期 host，且交互输入 `RESET NEXUS DATA` 后才会执行。

同步本地企业数据到 Supabase：

```powershell
cd backend
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
..\venv\Scripts\python.exe scripts\sync_sqlite_to_postgres.py `
  --source ".\instance\nexus_prime.db" `
  --target $env:DATABASE_URL `
  --require-supabase
```

如果目标库允许清空，追加 `--reset-target`。生产数据库已有真实业务数据时禁止使用 `--reset-target`。

## 4. 一键部署脚本

仓库根目录提供一键部署脚本 `scripts/deploy-supabase-vercel.ps1`。脚本会按顺序执行：

1. 自动恢复 `venv/` 与 `frontend/node_modules/`
2. 本地预检
3. Supabase schema 升级
4. SQLite -> Supabase 数据同步
5. 后端 Vercel 发布
6. 前端 Vercel 发布

示例命令：

```powershell
.\scripts\deploy-supabase-vercel.ps1 `
  -DatabaseUrl "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" `
  -BackendProjectName "nexus-prime-api" `
  -FrontendProjectName "nexus-prime-web" `
  -SeedRemoteWhenEmpty `
  -DemoAdminPassword "replace-with-demo-admin-password" `
  -DemoUserPassword "replace-with-demo-user-password" `
  -SecretKey "replace-with-at-least-32-random-characters" `
  -CloudinaryUrl "cloudinary://api_key:api_secret@cloud_name"
```

带 Token 的无交互部署：

```powershell
$env:VERCEL_TOKEN="<Vercel Token>"
$env:SECRET_KEY="<至少32位强随机字符串>"
$env:DEEPSEEK_API_KEY="<可选 DeepSeek Key>"
$env:CLOUDINARY_URL="cloudinary://api_key:api_secret@cloud_name"
$env:NEXUS_DEMO_ADMIN_PASSWORD="<远程演示管理员密码>"
$env:NEXUS_DEMO_USER_PASSWORD="<远程演示普通用户密码>"

.\scripts\deploy-supabase-vercel.ps1 `
  -DatabaseUrl "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" `
  -BackendProjectName "nexus-prime-api" `
  -FrontendProjectName "nexus-prime-web" `
  -ApiBaseUrl "https://nexus-prime-api.vercel.app/api/v1" `
  -FrontendOrigin "https://nexus-prime-web.vercel.app" `
  -SeedRemoteWhenEmpty `
  -SecretKey $env:SECRET_KEY `
  -CloudinaryUrl $env:CLOUDINARY_URL
```

如果只需要部署，不同步现有 SQLite 数据，可去掉 `-SyncDatabase`。如果只演练本地预检和脚本参数，可加 `-SkipMigrations`、`-SkipDataVerify`、`-SkipBackendDeploy`、`-SkipFrontendDeploy`、`-SkipApiProbe`。

`backend/scripts/sync_sqlite_to_postgres.py` 负责把本地 `backend/instance/nexus_prime.db` 同步到 Supabase PostgreSQL。脚本要求目标库已完成 `flask db upgrade`，并会在需要时回填序列。

脚本参数说明：

| 参数 | 用途 |
| --- | --- |
| `-DatabaseUrl` | Supabase PostgreSQL 连接串，必须包含 `sslmode=require`。 |
| `-BackendProjectName` | Vercel 后端 API 项目名。 |
| `-FrontendProjectName` | Vercel 前端 SPA 项目名。 |
| `-ApiBaseUrl` | 前端调用的后端 API 地址，默认按后端项目名推导。 |
| `-FrontendOrigin` | 前端生产域名，默认按前端项目名推导。 |
| `-VercelTeam` | Vercel team scope，可选。 |
| `-VercelToken` | 无交互部署 Token，可从环境变量 `VERCEL_TOKEN` 读取。 |
| `-SecretKey` | 后端生产 SECRET_KEY，可从环境变量读取。 |
| `-DemoAdminPassword` | 远程演示库管理员密码；可从 `NEXUS_DEMO_ADMIN_PASSWORD` 读取，不能使用本地默认值。 |
| `-DemoUserPassword` | 远程演示库普通用户密码；可从 `NEXUS_DEMO_USER_PASSWORD` 读取，不能使用本地默认值。 |
| `-SyncDatabase` | 将本地 SQLite 数据同步到 Supabase。 |
| `-ResetRemoteDatabase` | 同步前清空目标库，仅限确认可重建的远程库。 |
| `-SeedRemoteWhenEmpty` | 远程库为空时生成企业演示数据；脚本会先执行 `backend/scripts/database_state.py --require-empty`，不会 reset 已有数据，并要求自定义演示密码。 |
| `-ResetAndSeedRemote` | 明确清空并重新生成远程演示数据，仅限可丢弃的演练库。 |
| `-Skip*` | 跳过对应预检、迁移、验证、部署或健康探测步骤。 |

## 5. 本地部署预检

在仓库根目录运行：

```powershell
.\scripts\quality-gate.ps1
```

该命令会串联最终 DOCX 报告生成、企业数据审计、后端测试、前端测试、生产构建、图表审计、布局审计、部署预检和交付资产审计。布局审计需要本地前后端服务，脚本会在需要时临时启动并在结束后关闭。

如果只需要检查生产环境变量与部署配置，可单独运行：

```powershell
$env:NEXUS_API_BASE_URL="https://your-api-host.example.com/api/v1"
$env:FRONTEND_ORIGIN="https://your-vercel-domain.vercel.app"
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

真实 API 已上线后，移除 `-SkipApiProbe`，预检会请求 `NEXUS_API_BASE_URL + /health`。

部署前建议优先执行完整质量闸门：

```powershell
.\scripts\quality-gate.ps1
```

该脚本会串联报告生成、企业数据审计、后端测试、前端测试、生产构建、前后端 API 契约审计、图表审计、布局审计、部署就绪与 ERP 成熟度专项审计、部署预检和交付资产审计；布局和成熟度审计临时写入本地 API 地址后会在部署预检前恢复 `frontend/public/runtime-config.js`。2026-06-09 本地完整质量闸门已通过，2026-06-10 已追加成熟度专项审计并纳入质量闸门。

也可以拆分执行以下本地验收：

| 检查项 | 命令 | 通过标准 |
| --- | --- | --- |
| 前端生产构建 | `cd frontend; npm run build` | 生成 `dist/frontend/browser/index.html`，无构建错误。 |
| API 契约审计 | `python scripts\audit-api-contracts.py` | Angular 接口调用全部匹配 Flask 运行时路由、资源配置和路径别名。 |
| 全站布局审计 | `cd frontend; npm run audit:layout` | 66 个桌面/移动页面检查通过，无横向溢出、按钮出界、图表过小、Dock 遮挡。 |
| 图表配置审计 | `cd frontend; npm run audit:charts` | 36 个页面文件通过，图例和图表布局 guard 生效。 |
| 部署就绪与 ERP 成熟度审计 | `cd frontend; npm run audit:deployment-readiness` | ERP 成熟度、能力域、微服务拓扑、交付证据、Token 入口、secret 泄露候选、横向溢出、控制台错误和 HTTP 错误均通过。 |
| 后端接口测试 | `cd backend; ..\venv\Scripts\python.exe -m pytest` | 46 个接口与业务测试全部通过。 |
| 企业数据审计 | `cd backend; $env:FLASK_APP="run.py"; ..\venv\Scripts\python.exe -m flask audit-enterprise-data --strict` | 库存、采购、履约、应收、报表、文件、公告、通知、经营分析、审计数据闭环全部为 OK。 |
| 部署配置预检 | `.\scripts\preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests` | 旧平台配置、Vercel、Supabase、Cookie、环境变量检查全部通过。 |
| 交付资产审计 | `python scripts\audit-delivery-assets.py` | DOCX 报告同步、截图尺寸、Markdown 图片、ER 图、真实图片登记和旧版快照均通过。 |

2026-06-06 额外页面验收：

- 文件中心移动端类型筛选已改为两列网格，布局审计不再出现横向溢出。
- 登录页和注册页在桌面、移动端均保持居中和可滚动，不再出现顶部裁切。
- 浅色模式登录文字、输入框、卡片背景对比已调整。
- 图标按钮、Dock、抽屉、头像入口已统一居中。
- 更多模块抽屉打开时隐藏顶部栏，避免右侧弹窗显示不全和叠压。
- 首页右侧真实图片墙固定为首屏面板，不再撑高页面；入口页在 4200 与 4300 两个本地审查端口均完成截图复核。
- 本地开发 CORS 默认覆盖 4200-4230 与 4300-4310，生产仍由 `CORS_ORIGINS` 精确配置。
- 企业演示数据库可通过 `seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 重建；本轮 `flask status` 显示用户 15001、商品 57608、销售订单 100803、文件 7200，运行数据库不提交。


2026-06-06 认证入口复核：

- 入场页使用本地制造、仓储、车间真实图组成首屏，不再依赖外链图。
- 登录页桌面端左右两列居中，浅色模式文字和输入框对比通过截图复核。
- 注册流程改为单卡居中，验证码、许可确认、注册按钮和返回登录入口完整可见。
- 认证入口样式独立到 `frontend/src/auth-entry.scss`，并在 `angular.json` 中排在 `styles.scss` 后面；入口最终兜底层位于 `frontend/src/styles.scss` 文件尾部，避免旧全局样式覆盖。

`preflight.ps1` 还会检查：

- `core/navigation.ts` 中 Dock 桌面/移动可见入口是否集中维护。
- `core/visual-assets.ts` 是否登记纵览页真实图片。
- `frontend/public/images/plant-floor.jpg`、`warehouse-aisles.jpg`、`industrial-manufacturing.jpg` 是否存在。
- `backend/.env.example` 是否包含 `FLASK_CONFIG`、`NEXUS_RUNTIME_DIR` 等生产变量。
- `frontend/public/runtime-config.js` 不得硬编码本地 API 或旧托管平台地址。
- 首页、登录页、注册流程的兜底放在 `frontend/src/auth-entry.scss`，业务页面布局兜底放在 `frontend/src/styles.scss`。
- 本地大规模演示库可通过 `flask seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 重建；远程默认使用 `-SeedRemoteWhenEmpty` 和自定义演示密码，只有可丢弃演练库才允许 `-ResetRemoteDatabase` 或 `-ResetAndSeedRemote`。

`preflight.ps1` 默认会补齐缺失依赖。只想验证当前机器状态、不自动安装时：

```powershell
.\scripts\preflight.ps1 -SkipApiProbe -NoInstall
```

纯净交付状态下，如果已经主动删除 `venv/` 与 `frontend/node_modules/`，可只检查部署配置：

```powershell
.\scripts\preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests -NoInstall -AllowMissingDependencies
```

## 6. 发布后验收

后端健康检查：

```powershell
Invoke-RestMethod "https://nexus-prime-api.vercel.app/api/v1/health"
Invoke-RestMethod "https://nexus-prime-api.vercel.app/"
```

登录和 CSRF 检查：

```powershell
$base = "https://nexus-prime-api.vercel.app/api/v1"
$demoAdminPassword = $env:NEXUS_DEMO_ADMIN_PASSWORD
if (-not $demoAdminPassword) { throw "请先设置 NEXUS_DEMO_ADMIN_PASSWORD 为远程演示管理员密码" }
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$csrf = (Invoke-RestMethod "$base/auth/csrf" -WebSession $session).data.csrf_token
$login = Invoke-RestMethod "$base/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -WebSession $session `
  -Body (@{ email="admin@nexus.com"; password=$demoAdminPassword } | ConvertTo-Json)
Invoke-RestMethod "$base/auth/me" -WebSession $session
```

前端检查：

1. 打开前端 Vercel 域名。
2. 登录管理员账号。
3. 检查 `/app/overview`、`/app/ai`、`/app/files`、`/app/reports`、`/app/settings`。
4. 检查 Network 面板中 API 请求全部指向后端 `/api/v1`，无 `localhost`。
5. 检查 Cookie 包含 `nexus_access_token` 和 `nexus_csrf_token`，生产环境应为 HTTPS。
6. 在经营分析页保存 Base URL、模型和 API Key 后运行诊断；`local` 只使用本地经营数据，`hybrid` 在外部服务异常时回退本地分析，`external` 在外部服务不可用时返回明确的 502 业务错误。
7. 检查 `/app/content/articles` 顶部知识触达图表、分页、搜索、评论和详情跳转；该页应和其他业务页保持一致的图表密度和响应式布局。

## 7. 回滚和故障处理

Vercel 回滚：

1. 打开 https://vercel.com/dashboard。
2. 进入对应前端或后端项目。
3. 进入 Deployments。
4. 选择上一个健康版本。
5. 点击 Promote 或 Redeploy。

数据库回滚：

- 如果刚执行迁移但未写入大量业务数据，优先使用 Supabase Dashboard 的备份/恢复能力。
- 如果只是数据同步错误，先停止前后端写入，再根据最近备份恢复。
- 禁止在生产库直接运行 `reset_db.py`，除非已经确认该库可清空。

常见问题：

| 现象 | 检查项 | 修复 |
| --- | --- | --- |
| 登录后立刻 401 | `SECRET_KEY` 是否变化、Cookie 是否跨域发送 | 后端固定 `SECRET_KEY`，前端使用 HTTPS API。 |
| 写请求 403 CSRF | `nexus_csrf_token` Cookie 与 `X-CSRF-Token` 是否一致 | 刷新页面重新登录，确认前端拦截器生效。 |
| 前端请求 localhost | `NEXUS_API_BASE_URL` 是否配置在前端 Vercel | 重新设置变量并重新部署前端。 |
| 跨域失败 | `CORS_ORIGINS` 是否等于前端域名 | 后端环境变量写入准确域名。 |
| 文件或头像上传后丢失 | 是否使用 Vercel 临时磁盘 | 配置 `CLOUDINARY_URL` 或接入 Supabase Storage。 |
| Supabase 连接失败 | URL 是否 Pooler、是否 SSL | 使用带 `sslmode=require` 的连接串。 |

## 8. 交付前确认

- 设置 `CLOUDINARY_URL`、`CACHE_TYPE=RedisCache` 和 `REDIS_URL`/`CACHE_REDIS_URL` 后，`.\scripts\preflight.ps1 -SkipApiProbe` 通过旧平台残留、Vercel、Supabase、Cookie、共享限流缓存和构建检查。
- `frontend/public/runtime-config.js` 由构建脚本生成，不手写生产 API 地址。
- `CORS_ORIGINS` 精确包含 Vercel 生产域名，不用通配符。
- 跨站 Cookie 使用 HTTPS、`AUTH_COOKIE_SECURE=true`、`AUTH_COOKIE_SAMESITE=None`。
- 文件和头像上传在生产环境使用 Cloudinary 或后续接入 Supabase Storage，本地磁盘不作为持久存储依赖。Vercel/临时磁盘环境未配置持久化存储时，上传接口会返回 `persistent_storage_required`。
- `backend/server.py` 和 `backend/vercel.json` 已准备好独立 Flask 部署。
- `scripts/quality-gate.ps1` 已跑通，确认报告、截图、数据、测试、构建、布局和部署预检一致。
- `scripts/deploy-supabase-vercel.ps1` 可直接用于一键复制式上线。
- `scripts/install-dependencies.ps1` 可从纯净仓库恢复 Python 与 Node 依赖。
- `scripts/clean-workspace.ps1 -StopDevServers` 已清理本地运行产物。
- `.gitignore` 已覆盖缓存、构建产物、本地上传运行文件、导出数据和环境变量，并保留上传目录与头像目录的 `.gitkeep`；`legacy/monolith-flask/` 保留为旧版对照快照。

## 9. 参考资料

- Vercel Flask 部署文档：https://vercel.com/docs/frameworks/backend/flask
- Vercel CLI deploy 文档：https://vercel.com/docs/cli/deploy
- Vercel CLI env 文档：https://vercel.com/docs/cli/env
- Vercel 环境变量文档：https://vercel.com/docs/environment-variables
- Vercel sensitive environment variables：https://vercel.com/docs/environment-variables/sensitive-environment-variables
- Supabase PostgreSQL 连接文档：https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase API Keys 文档：https://supabase.com/docs/guides/api/api-keys
- Supabase SSL 说明：https://supabase.com/docs/guides/platform/ssl-enforcement
