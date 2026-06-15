# API 接口、Token 获取与 Supabase + Vercel 部署手册

本手册覆盖 NEXUS Prime 当前前后端分离架构的部署步骤、第三方 Token 获取入口、本系统 API 认证方式和完整接口清单。所有业务接口默认以前缀 `/api/v1` 开头。

正式部署或最终交付前，建议先运行：

```powershell
.\scripts\quality-gate.ps1
```

该闸门会把最终 DOCX 报告、截图资产、企业数据、前后端测试、生产构建、布局审计和部署预检串成一条流水线，避免 Token 已配置完成后才发现报告或页面资产不同步。

## 1. 基础地址

| 环境 | 地址 |
| --- | --- |
| 本地前端 | `http://127.0.0.1:4200` |
| 本地后端 API | `http://127.0.0.1:5000/api/v1` |
| 生产前端 | `https://<frontend-project>.vercel.app` |
| 生产后端 API | `https://<backend-project>.vercel.app/api/v1` |
| 后端根健康页 | `https://<backend-project>.vercel.app/` |

后端统一返回：

```json
{
  "data": {},
  "message": "操作结果",
  "error": null
}
```

通用分页字段：

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 100,
    "pages": 10,
    "has_next": true,
    "has_prev": false
  }
}
```

## 2. Token 与密钥获取网址

| 用途 | 获取网址 | 项目变量 | 说明 |
| --- | --- | --- | --- |
| Vercel CLI/API Token | https://vercel.com/account/settings/tokens | `VERCEL_TOKEN` | 用于脚本无交互部署前端和后端。手动 `vercel login` 后可不填。 |
| Vercel 项目控制台 | https://vercel.com/dashboard | 无固定变量 | 创建 `frontend` 与 `backend` 两个独立项目。 |
| Supabase 项目列表 | https://supabase.com/dashboard/projects | 无固定变量 | 新建 PostgreSQL 项目。 |
| Supabase 数据库连接串 | `https://supabase.com/dashboard/project/<project-ref>/settings/database` | `DATABASE_URL` | 复制 Pooler 连接串，保留 `sslmode=require`。 |
| Supabase API Key | `https://supabase.com/dashboard/project/<project-ref>/settings/api` | 暂不必填 | 当前后端直连 PostgreSQL，不需要前端直连 Supabase。后续接 Storage 时再使用。 |
| Supabase API Key 新入口 | `https://supabase.com/dashboard/project/<project-ref>/settings/api-keys` | 暂不必填 | 部分 Supabase 项目控制台使用该入口。 |
| Supabase 连接串文档 | https://supabase.com/docs/reference/postgres/connection-strings | 无 | 核对 direct、session pooler、transaction pooler。 |
| Supabase SSL 文档 | https://supabase.com/docs/guides/platform/ssl-enforcement | 无 | 生产连接必须使用 SSL。 |
| DeepSeek API Key | https://platform.deepseek.com/api_keys | `DEEPSEEK_API_KEY` | AI 经营分析外部模型凭证。 |
| DeepSeek API 文档 | https://api-docs.deepseek.com/ | `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com`，模型默认 `deepseek-chat`。 |
| Cloudinary 控制台 | https://console.cloudinary.com/ | `CLOUDINARY_URL` 或拆分变量 | Vercel/Serverless 生产头像和文件长期保存必填。进入 Settings / API Keys 获取。 |
| Cloudinary API Keys 入口 | https://console.cloudinary.com/settings/api-keys | `CLOUDINARY_CLOUD_NAME`、`CLOUDINARY_API_KEY`、`CLOUDINARY_API_SECRET` | 如该直达入口跳转异常，从控制台首页进入 Settings。 |
| Sentry Auth Token | https://sentry.io/settings/account/api/auth-tokens/ | 可选 | 仅在需要读取 Sentry API 时使用。 |
| Sentry DSN | https://sentry.io/settings/projects/ | `SENTRY_DSN` | 可选错误监控。进入具体项目的 Client Keys/DSN。 |
| GitHub Token | https://github.com/settings/tokens | 可选 | Vercel 绑定 GitHub 通常走 OAuth，不需要手动 PAT。 |
| GitHub Token 文档 | https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens | 可选 | 仅在自动化访问私有仓库时使用。 |

### 2.1 一键复制用入口与变量

下面内容可直接复制到部署检查表；尖括号内内容需要替换，所有 secret 只进入后端 Vercel 项目或本地脚本环境变量。

```text
Vercel Token:
https://vercel.com/account/settings/tokens
变量: VERCEL_TOKEN
用途: scripts/deploy-supabase-vercel.ps1 非交互部署
```

```text
Supabase Database URL:
https://supabase.com/dashboard/project/<project-ref>/settings/database
变量: DATABASE_URL
示例: postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
用途: 后端连接生产 PostgreSQL
```

```text
Supabase API Keys:
https://supabase.com/dashboard/project/<project-ref>/settings/api-keys
变量: 后续接 Supabase Storage 或 Edge API 时再配置
边界: 当前前端不直连 Supabase，不需要把 Supabase key 放进 frontend
```

```text
Cloudinary API Keys:
https://console.cloudinary.com/settings/api-keys
变量: CLOUDINARY_URL
示例: cloudinary://api_key:api_secret@cloud_name
用途: Vercel/Serverless 生产头像和附件持久化
```

```text
DeepSeek API Key:
https://platform.deepseek.com/api_keys
变量: DEEPSEEK_API_KEY
Base URL: https://api.deepseek.com
模型: deepseek-chat
用途: 后端真实调用 OpenAI-compatible Chat Completions
```

```text
前端 API 地址:
https://vercel.com/docs/environment-variables
变量: NEXUS_API_BASE_URL
示例: https://<backend-project>.vercel.app/api/v1
边界: 前端只放公开 API 地址，不放 DATABASE_URL、SECRET_KEY、AI Key、Cloudinary secret
```

常用命令模板：

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

```powershell
vercel env add DATABASE_URL production --sensitive
vercel env add SECRET_KEY production --sensitive
vercel env add CLOUDINARY_URL production --sensitive
vercel env add DEEPSEEK_API_KEY production --sensitive
vercel env add NEXUS_API_BASE_URL production
```

官方依据：

- Vercel 环境变量用于在构建和函数运行时改变行为；敏感环境变量在创建后不可读，适合保存 Token、数据库连接串和服务端密钥。
- Vercel CLI 支持 `vercel env add <NAME> production --sensitive`，一键部署脚本对 `DATABASE_URL`、`SECRET_KEY`、`DEEPSEEK_API_KEY`、`CLOUDINARY_URL` 等变量按敏感变量写入。
- Supabase API Keys 位于项目 Dashboard 的 `Settings -> API Keys`；当前项目后端直连 PostgreSQL，浏览器端不需要 Supabase key。
- Supabase 官方连接建议中，Serverless 或短生命周期函数使用 transaction pooler，常见端口为 `6543`；生产连接必须启用 SSL，当前脚本要求 `sslmode=require`。

`SECRET_KEY` 不是外部平台 Token，应在本机生成并只放入后端环境变量：

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

## 3. 部署前准备

### 3.0 架构与资源边界

当前项目按前后端分离维护：

```text
frontend/  Angular SPA、页面交互、主题、真实图片资源、Vercel 前端项目
backend/   Flask REST API、认证权限、业务流程、数据库、AI 调用、文件与头像
scripts/   本地开发、清理、质量闸门、预检、Supabase/Vercel 一键部署
docs/      部署文档、接口清单、架构审阅、截图与交付说明
```

部署前确认：

- `frontend/src/app/core/navigation.ts` 统一维护 Dock、更多菜单、桌面/移动可见入口。
- `frontend/src/app/core/visual-assets.ts` 统一登记真实图片资源。
- `frontend/public/images/` 保留页面使用的制造、仓配、工业现场图片。
- `frontend/src/styles.scss` 保留业务页面布局稳定层，只处理居中、溢出、图标对齐、分页、图表最小尺寸和移动端网格。
- `frontend/src/auth-entry.scss` 独立维护首页、登录页和注册流程，避免认证入口继续被全局业务样式覆盖。
- `backend/.env.example` 已包含 `FLASK_CONFIG=production` 与 `NEXUS_RUNTIME_DIR=/tmp/nexus-prime`。
- 浏览器端只配置 `NEXUS_API_BASE_URL`，不得放入数据库、AI Key、Supabase secret key 或后端密钥。

架构审阅见 `docs/architecture-maintenance-review.md`，项目规范见 `docs/project-standards.md`。

### 3.1 安装本地工具

1. 安装 Git、Git LFS、Node.js LTS、Python 3.11+。
2. 在仓库根目录拉取 LFS 数据：

```powershell
git lfs install
git lfs pull
```

3. 安装依赖并启动本地开发环境：

```powershell
.\scripts\dev.ps1 -Install
```

如果只需要从纯净仓库恢复依赖，不启动服务：

```powershell
.\scripts\install-dependencies.ps1
```

4. 本地演示账号：

```text
admin@nexus.com / admin123
user00001@nexus.com / password123
```

远程 `-SeedRemoteWhenEmpty` 必须使用 `NEXUS_DEMO_ADMIN_PASSWORD` 和 `NEXUS_DEMO_USER_PASSWORD` 自定义密码，脚本会拒绝本地默认密码。

### 3.2 创建 Supabase 数据库

1. 打开 https://supabase.com/dashboard/projects。
2. 创建新项目并记录 `<project-ref>`、数据库密码和区域。
3. 打开 `Project Settings -> Database`，复制 PostgreSQL connection string。
4. Vercel/Serverless 场景优先使用 Pooler 连接串。
5. 确保连接串形态类似：

```text
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

### 3.3 创建两个 Vercel 项目

后端项目：

```text
Project Root: backend
Framework: Other / Python
入口: backend/server.py
健康检查: /api/v1/health
```

前端项目：

```text
Project Root: frontend
Framework Preset: Angular
Build Command: npm run build
Output Directory: dist/frontend/browser
```

两个项目必须分开，前端只存前端环境变量，后端只存数据库、Cookie、AI、上传等服务端密钥。

## 4. 环境变量

### 4.1 后端 Vercel 项目

必填：

```env
FLASK_ENV=production
FLASK_CONFIG=production
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=<至少32位强随机字符串>
CORS_ORIGINS=https://<frontend-project>.vercel.app
FRONTEND_ORIGIN=https://<frontend-project>.vercel.app
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=None
LOGIN_RATE_LIMIT_ATTEMPTS=8
LOGIN_RATE_LIMIT_WINDOW_SECONDS=600
NEXUS_RUNTIME_DIR=/tmp/nexus-prime
AI_LOCAL_ANALYSIS=true
AI_REQUEST_TIMEOUT_SECONDS=20
AI_CONNECT_TIMEOUT_SECONDS=5
```

生产上传必填：

```env
USE_CLOUD_STORAGE=auto
REQUIRE_CLOUD_STORAGE_FOR_UPLOADS=auto
UPLOAD_FOLDER=/tmp/nexus-prime/storage/uploads
UPLOAD_FILES_FOLDER=/tmp/nexus-prime/storage/uploads/files
UPLOAD_AVATARS_FOLDER=/tmp/nexus-prime/storage/uploads/avatars
UPLOAD_LIBRARY_FOLDER=/tmp/nexus-prime/storage/uploads/library
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
```

Vercel/Serverless 后端没有长期本地磁盘，头像和文件上传必须配置 `CLOUDINARY_URL`。未配置时上传接口会返回 `persistent_storage_required`，避免刷新后文件丢失。独立长驻主机可使用本地三目录：附件 `UPLOAD_FILES_FOLDER`、头像 `UPLOAD_AVATARS_FOLDER`、资料库 `UPLOAD_LIBRARY_FOLDER`。

可选：

```env
DEEPSEEK_API_KEY=<DeepSeek API Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
AI_REQUEST_TIMEOUT_SECONDS=20
AI_CONNECT_TIMEOUT_SECONDS=5
SENTRY_DSN=<Sentry DSN>
```

生产后端会在启动时强校验关键变量：必须设置 `SECRET_KEY`、`DATABASE_URL`、`CORS_ORIGINS`；正式环境默认拒绝 SQLite，数据库应使用 PostgreSQL/Supabase。只有本地演练生产配置时，才可显式设置 `ALLOW_PRODUCTION_SQLITE=true`。

### 4.2 前端 Vercel 项目

只需要：

```env
NEXUS_API_BASE_URL=https://<backend-project>.vercel.app/api/v1
```

不要把 `DATABASE_URL`、`SECRET_KEY`、`DEEPSEEK_API_KEY`、`CLOUDINARY_API_SECRET`、Supabase `service_role` 放入前端项目。

## 5. 本地预检

在仓库根目录执行：

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

真实 API 已部署后，去掉 `-SkipApiProbe`，脚本会访问：

```text
https://<backend-project>.vercel.app/api/v1/health
```

## 6. 一键部署

建议按“先质量闸门、后 Token 配置、再部署”的顺序推进：先确认 `docs/final-delivery-report.docx`、`docs/images/final/`、ER 图、真实图片登记、测试和部署预检一致，再把 `VERCEL_TOKEN`、`DATABASE_URL`、`SECRET_KEY`、`CLOUDINARY_URL`、`DEEPSEEK_API_KEY` 写入对应项目或终端环境。

先设置可选 Token：

```powershell
$env:VERCEL_TOKEN="<从 https://vercel.com/account/settings/tokens 获取>"
$env:DEEPSEEK_API_KEY="<从 https://platform.deepseek.com/api_keys 获取，可选>"
$env:SECRET_KEY="<至少32位强随机字符串>"
$env:CLOUDINARY_URL="<从 Cloudinary 控制台复制的 cloudinary://api_key:api_secret@cloud_name>"
$env:NEXUS_DEMO_ADMIN_PASSWORD="<远程演示管理员密码>"
$env:NEXUS_DEMO_USER_PASSWORD="<远程演示普通用户密码>"
```

执行完整部署：

```powershell
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

只演练流程、不真正发布：

```powershell
.\scripts\deploy-supabase-vercel.ps1 `
  -DatabaseUrl "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" `
  -BackendProjectName "nexus-prime-api" `
  -FrontendProjectName "nexus-prime-web" `
  -SecretKey $env:SECRET_KEY `
  -CloudinaryUrl $env:CLOUDINARY_URL `
  -SkipMigrations `
  -SkipDataVerify `
  -SkipBackendDeploy `
  -SkipFrontendDeploy `
  -SkipApiProbe
```

脚本执行顺序：

1. 自动恢复缺失的 `venv/` 与 `frontend/node_modules/`。
2. 校验 Node、npm、npx、Python venv、Vercel CLI 输入。
3. 运行 `scripts/preflight.ps1`。
4. 执行 `flask db upgrade` 升级 Supabase schema。
5. 可选同步 `backend/instance/nexus_prime.db` 到 Supabase。
6. 配置后端 Vercel 环境变量并部署后端。
7. 配置前端 Vercel 环境变量并部署前端。
8. 请求 `/api/v1/health` 做上线探测。

## 7. 本系统 API 认证方式

### 7.1 Cookie + CSRF

正常前端使用 HttpOnly Cookie，不需要手工保存访问 Token。登录后后端设置：

| 名称 | 类型 | 用途 |
| --- | --- | --- |
| `nexus_access_token` | HttpOnly Cookie | 登录态 JWT，浏览器脚本不可读取 |
| `nexus_csrf_token` | 普通 Cookie | 写请求 CSRF 校验 |
| `X-CSRF-Token` | Header | `POST/PUT/PATCH/DELETE` 必须携带 |

公开接口不需要登录。登录后接口需要 Cookie。写接口在 Cookie 模式下必须带 `X-CSRF-Token`。

### 7.2 Bearer Token

`POST /auth/login` 响应体里也会返回 `data.token`。脚本或外部系统可以使用：

```http
Authorization: Bearer <data.token>
```

使用 Bearer Token 时，后端不要求 CSRF Header。生产前端仍建议使用 Cookie + CSRF。

### 7.3 PowerShell 调用示例

```powershell
$base = "http://127.0.0.1:5000/api/v1"
$demoAdminPassword = $env:NEXUS_DEMO_ADMIN_PASSWORD
if (-not $demoAdminPassword) { $demoAdminPassword = "admin123" } # 仅本地演示默认值
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

$csrf = (Invoke-RestMethod "$base/auth/csrf" -WebSession $session).data.csrf_token

$login = Invoke-RestMethod "$base/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -WebSession $session `
  -Body (@{ email="admin@nexus.com"; password=$demoAdminPassword } | ConvertTo-Json)

$csrf = $login.data.csrf_token

Invoke-RestMethod "$base/products?page=1&page_size=10&q=轴承" -WebSession $session

Invoke-RestMethod "$base/me/preferences" `
  -Method Put `
  -ContentType "application/json" `
  -WebSession $session `
  -Headers @{ "X-CSRF-Token" = $csrf } `
  -Body (@{ theme="light-luxury"; density="comfortable" } | ConvertTo-Json)
```

### 7.4 注册调用流程

1. `GET /auth/register-policy` 获取许可版本、必选勾选项和可展开的《服务许可》《隐私说明》《数据使用范围》。
2. `GET /auth/captcha` 获取验证码图片、`captcha_token`、`terms_version`。
3. `POST /auth/register` 提交注册信息。

注册请求体示例：

```json
{
  "username": "demo-user",
  "email": "demo@example.com",
  "password": "replace-with-demo-password",
  "full_name": "演示用户",
  "phone": "13800000000",
  "position": "业务协同成员",
  "accepted_terms": true,
  "accepted_privacy": true,
  "accepted_data_scope": true,
  "terms_version": "2026.06",
  "captcha_token": "<GET /auth/captcha 返回>",
  "captcha_answer": "<用户识别结果>"
}
```

### 7.5 AI 设置调用流程

1. `GET /ai/settings` 读取当前分析模式、Base URL、模型和凭证配置状态。
2. `PUT /ai/settings` 保存 `analysis_mode`、`ai_api_base`、`ai_model`、`ai_api_key`。
3. `POST /ai/diagnostics` 检查本地分析引擎和外部模型连通性。
4. `POST /ai/chat` 发起经营分析。`hybrid` 模式会优先外部模型，失败时回退本地经营分析。

浏览器端只提交配置到后端，不保存数据库连接串、Supabase secret、Vercel Token 或 Cloudinary secret。

## 8. 权限说明

| 权限点 | 含义 |
| --- | --- |
| `admin` | 系统管理 |
| `masterdata.write` | 主数据维护 |
| `inventory.adjust` | 库存调整 |
| `purchase.write` | 采购创建 |
| `purchase.approve` | 采购审批 |
| `purchase.receive` | 采购收货 |
| `sales.write` | 销售履约 |
| `finance.payment` | 收款处理 |
| `finance.credit.write` | 信用管理 |
| `stocktake.write` | 盘点管理 |
| `reports.generate` | 报表生成 |
| `files.manage` | 文件管理 |
| `content.write` | 内容管理 |

管理员账号具备全部权限。普通账号默认只能访问非管理员资源，写入动作由角色权限控制。

## 9. 完整 API 接口清单

除 `GET /` 外，以下路径均相对于 `/api/v1`。

### 9.1 根与健康检查

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/` | 后端根健康页 | 否 |
| GET | `/health` | API 健康检查 | 否 |

### 9.2 认证、注册、个人资料

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/auth/csrf` | 获取 CSRF Token | 否 |
| GET | `/auth/captcha` | 获取注册验证码 | 否 |
| GET | `/auth/register-policy` | 获取注册许可策略 | 否 |
| POST | `/auth/register` | 注册账号并建立会话 | 否 |
| POST | `/auth/login` | 登录并设置 Cookie | 否 |
| POST | `/auth/logout` | 退出登录并清除 Cookie | 是 |
| GET | `/auth/me` | 当前用户信息并刷新 Cookie | 是 |
| POST | `/auth/change-password` | 修改密码 | 是 |
| PUT | `/me/profile` | 更新个人资料 | 是 |
| POST | `/me/avatar` | 上传头像，multipart `file` | 是 |
| DELETE | `/me/avatar` | 删除头像并恢复默认 | 是 |
| GET | `/avatars/<filename>` | 读取本地头像 | 否 |
| GET | `/avatars/initials/<key>` | 生成默认首字母头像 | 否 |
| GET | `/me/preferences` | 获取用户偏好 | 是 |
| PUT | `/me/preferences` | 保存主题、布局、图表、Dock 等偏好 | 是 |

### 9.3 总览、图表、导航、搜索

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/dashboard/summary` | 仪表盘汇总 | 是 |
| GET | `/dashboard/charts` | 仪表盘图表数据 | 是 |
| GET | `/overview/summary` | 新版总览汇总 | 是 |
| GET | `/overview/charts` | 新版总览图表数据 | 是 |
| GET | `/analytics/executive` | 经营分析指标 | 是 |
| GET | `/manufacturing/command-center` | 制造仓配指挥数据 | 是 |
| GET | `/meta/navigation` | 导航元数据与资源数量 | 是 |
| GET | `/search?q=<keyword>` | 全局搜索 | 是 |

### 9.4 通用 CRUD 资源接口

通用查询参数：

| 参数 | 说明 |
| --- | --- |
| `page` | 页码，默认 `1` |
| `page_size` / `per_page` | 每页条数，最大 `100` |
| `q` | 模糊搜索 |
| `sort` | 排序字段 |
| `order` | `asc` 或 `desc` |
| 其他字段 | 若模型存在同名字段，会按等值过滤 |

通用方法：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/<resource>` | 资源列表 |
| GET | `/<resource>/<id>` | 资源详情 |
| POST | `/<resource>` | 创建资源 |
| PUT/PATCH | `/<resource>/<id>` | 更新资源 |
| DELETE | `/<resource>/<id>` | 软删除资源 |

可用资源：

| Resource | 说明 | 写入权限 |
| --- | --- | --- |
| `users` | 用户 | 管理员 |
| `roles` | 角色 | 管理员 |
| `departments` | 部门 | 管理员 |
| `categories` | 分类 | `masterdata.write` |
| `partners` | 客户/供应商伙伴 | `masterdata.write` |
| `products` | 物料与成品 | `masterdata.write` |
| `warehouses` | 仓库 | `inventory.adjust` |
| `stock` | 库存 | `inventory.adjust` |
| `inventory-logs` | 库存流水 | 登录 |
| `orders` | 销售订单 | `sales.write` |
| `order-items` | 销售订单明细 | `sales.write` |
| `purchase-orders` | 采购单 | `purchase.write` |
| `purchase-order-items` | 采购明细 | `purchase.write` |
| `supplier-performance` | 供应商绩效 | 登录 |
| `receivables` | 应收 | `finance.payment` |
| `payments` | 收款记录 | `finance.payment` |
| `statements` | 对账单 | `reports.generate` |
| `credits` | 客户信用 | `finance.credit.write` |
| `stocktakes` | 盘点单 | `stocktake.write` |
| `stocktake-items` | 盘点明细 | `stocktake.write` |
| `notifications` | 通知 | 本人/管理员 |
| `stock-alerts` | 库存预警 | `inventory.adjust` |
| `replenishment-suggestions` | 补货建议 | `purchase.write` |
| `report-subscriptions` | 报表订阅 | 本人/管理员 |
| `generated-reports` | 已生成报表 | 本人/管理员 |
| `reports` | `generated-reports` 别名 | 本人/管理员 |
| `articles` | 公告文章 | `content.write` |
| `article-comments` | 文章评论 | 本人/管理员 |
| `files` | 文件记录 | 本人/管理员 |
| `audit-logs` | 审计日志 | 管理员 |
| `ai-sessions` | AI 分析会话 | 本人/管理员 |
| `ai-messages` | AI 消息 | 本人/管理员 |

新版路径别名：

| 新路径 | 映射资源 |
| --- | --- |
| `/inventory/products` | `products` |
| `/inventory/stock` | `stock` |
| `/inventory/replenishment-suggestions` | `replenishment-suggestions` |
| `/sales/orders` | `orders` |
| `/procurement/orders` | `purchase-orders` |
| `/finance/receivables` | `receivables` |
| `/stocktakes` | `stocktakes` |
| `/notifications` | `notifications` |
| `/reports` | `generated-reports` |
| `/content/articles` | `articles` |
| `/files` | `files` |
| `/ai/sessions` | `ai-sessions` |
| `/system/users` | `users` |
| `/system/audit` | `audit-logs` |

这些别名同样支持：

| 方法 | 路径 |
| --- | --- |
| GET/POST | `/<path:new_path>` |
| GET/PUT/PATCH/DELETE | `/<path:new_path>/<id>` |

### 9.5 库存、补货、仓配

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/inventory/health` | 库存健康度 | 登录 |
| POST | `/inventory/adjust` | 库存调整 | `inventory.adjust` |
| POST | `/stock-alerts/check` | 生成/检查库存预警 | `inventory.adjust` |
| POST | `/replenishment-suggestions/generate` | 生成补货建议 | `purchase.write` |
| POST | `/replenishment-suggestions/<id>/accept` | 补货建议转采购 | `purchase.write` |
| POST | `/inventory/replenishment-suggestions/generate` | 新路径：生成补货建议 | `purchase.write` |
| POST | `/inventory/replenishment-suggestions/<id>/accept` | 新路径：补货建议转采购 | `purchase.write` |

### 9.6 采购、销售、应收、信用

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/procurement/summary` | 采购汇总 | 登录 |
| POST | `/purchase-orders/<id>/submit` | 提交采购单 | `purchase.write` |
| POST | `/purchase-orders/<id>/approve` | 审批采购单 | `purchase.approve` |
| POST | `/purchase-orders/<id>/reject` | 驳回采购单 | `purchase.approve` |
| POST | `/purchase-orders/<id>/receive` | 采购收货 | `purchase.receive` |
| POST | `/procurement/orders/<id>/submit` | 新路径：提交采购单 | `purchase.write` |
| POST | `/procurement/orders/<id>/approve` | 新路径：审批采购单 | `purchase.approve` |
| POST | `/procurement/orders/<id>/reject` | 新路径：驳回采购单 | `purchase.approve` |
| POST | `/procurement/orders/<id>/receive` | 新路径：采购收货 | `purchase.receive` |
| POST | `/sales/orders` | 创建销售订单 | `sales.write` |
| POST | `/sales/orders/<id>/transition` | 销售订单状态流转 | `sales.write` |
| GET | `/finance/receivables/aging` | 应收账龄分析 | 登录 |
| POST | `/receivables/<id>/payment` | 记录收款 | `finance.payment` |
| POST | `/finance/receivables/<id>/payment` | 新路径：记录收款 | `finance.payment` |
| POST | `/finance/receivables/<id>/reminder` | 创建催款提醒 | `finance.payment` |
| GET | `/finance/credits` | 客户信用列表 | 登录 |
| PUT | `/finance/credits/<id>` | 调整信用额度/预警线 | `finance.credit.write` |
| POST | `/finance/credits/<id>/freeze` | 冻结客户信用 | `finance.credit.write` |
| POST | `/finance/credits/<id>/unfreeze` | 解冻客户信用 | `finance.credit.write` |
| POST | `/statements/generate` | 生成对账单 | `reports.generate` |

### 9.7 盘点

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/stocktakes/create` | 创建盘点单 | `stocktake.write` |
| POST | `/stocktakes/<id>/start` | 开始盘点 | `stocktake.write` |
| POST | `/stocktakes/<id>/count` | 批量录入盘点数量 | `stocktake.write` |
| POST | `/stocktake-items/<id>/count` | 录入单个盘点明细数量 | `stocktake.write` |
| POST | `/stocktakes/<id>/complete` | 完成盘点 | `stocktake.write` |
| GET | `/stocktakes/<id>/variance` | 盘点差异汇总 | 登录 |

### 9.8 报表、导出、文件、内容

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/reports/types` | 报表类型 | 登录 |
| POST | `/reports/generate/<report_type>` | 生成报表 | `reports.generate` |
| GET | `/export/<resource>/<format_type>` | 导出资源，支持 `csv/excel/pdf` | 资源读取权限 |
| POST | `/files/upload` | 上传文件，multipart `file` | 登录 |
| GET | `/files/<id>/download` | 下载文件 | 本人/管理员 |
| POST | `/files/bulk-delete` | 批量删除文件 | `files.manage` |
| GET | `/articles/<id>/comments` | 文章评论列表 | 登录 |
| POST | `/articles/<id>/comments` | 新增文章评论 | 登录 |

### 9.9 通知、查询、批量动作、字典

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/notifications/mark-read` | 批量标记通知已读 | 本人/管理员 |
| POST | `/bulk-actions` | 批量业务动作 | 依动作而定 |
| GET | `/lookups/products` | 商品下拉搜索 | 登录 |
| GET | `/lookups/partners` | 客户/供应商下拉搜索 | 登录 |
| GET | `/lookups/warehouses` | 仓库下拉搜索 | 登录 |
| GET | `/lookups/stock-locations` | 库存库位下拉搜索 | 登录 |

`POST /bulk-actions` 当前支持：

| Action | 说明 | 权限 |
| --- | --- | --- |
| `products.delete` | 批量删除商品 | `masterdata.write` |
| `orders.update_status` | 批量更新订单状态 | `sales.write` |
| `purchase_orders.approve` | 批量审批采购 | `purchase.approve` |
| `notifications.mark_read` | 批量已读 | 本人/管理员 |
| `files.delete` | 批量删除文件 | `files.manage` |
| `operations.dispatch_task` | 创建仓配调度任务 | 登录 |
| `operations.data_quality_notice` | 创建数据质量通知 | 登录 |
| `operations.customer_followup` | 创建客户跟进任务 | 登录 |
| `operations.capacity_plan` | 创建产能计划任务 | 登录 |
| `operations.maintenance_workorder` | 创建设备维护工单 | 登录 |

### 9.10 AI 经营分析

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/ai/sessions` | 分析会话列表 | 本人 |
| POST | `/ai/sessions` | 创建分析会话 | 本人 |
| GET | `/ai/sessions/<id>/messages` | 会话消息列表 | 本人 |
| POST | `/ai/chat` | 发送经营分析消息 | 本人 |
| POST | `/ai/analyze/inventory` | 库存风险分析 | 本人 |
| POST | `/ai/analyze/structured` | 结构化经营分析 | 本人 |
| GET | `/ai/settings` | 读取 AI 设置 | 本人 |
| PUT | `/ai/settings` | 保存 API Key、Base URL、模型、分析模式 | 本人 |
| POST | `/ai/diagnostics` | 外部模型连通性诊断 | 本人 |

AI 设置请求体示例：

```json
{
  "analysis_mode": "hybrid",
  "ai_api_base": "https://api.deepseek.com",
  "ai_model": "deepseek-chat",
  "ai_api_key": "sk-..."
}
```

`analysis_mode` 可选：

| 值 | 说明 |
| --- | --- |
| `local` | 只使用本地经营分析 |
| `hybrid` | 优先外部模型，失败时回退本地分析 |
| `external` | 只使用外部模型 |

补充说明：

- `GET /ai/settings` 会返回当前模式、外部 Base URL、模型名、是否已配置用户凭证。
- `POST /ai/diagnostics` 会检测本地引擎和外部推理服务的连通性。
- `POST /ai/chat` 在 `hybrid` 模式下会先尝试外部推理，失败时回退本地经营引擎并保留可追踪来源；`external` 模式下外部服务不可用会返回 `502 ai_provider_unavailable`。
- 外部模型调用默认连接超时 5 秒、请求总超时 20 秒，可用 `AI_CONNECT_TIMEOUT_SECONDS` 和 `AI_REQUEST_TIMEOUT_SECONDS` 调整，范围会被限制在 3 到 60 秒之间。

### 9.11 运营流程、规则、集成、成本、设备维护、移动终端

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/operations/todo` | 运营待办 | 登录 |
| GET | `/operations/exceptions` | 运营异常 | 登录 |
| GET | `/operations/task-queue` | 任务异常中心当班队列，聚合通知、部署预检、库存预警和采购审批 | 登录 |
| GET | `/operations/deployment-readiness` | 部署就绪分、环境边界、ERP 成熟度、能力域地图、微服务拓扑、交付证据和上线 Runbook | 登录 |
| POST | `/operations/deployment-readiness/task` | 创建部署预检通知任务并写入审计 | 登录 |
| GET | `/operations/rules` | 规则治理工作台：DMN 决策表、风险队列、负责人、SLA、Runbook、服务边界 | 登录 |
| POST | `/operations/rules/review` | 创建规则复核通知任务并写入审计 | 登录 |
| GET | `/operations/integrations` | 集成监控数据 | 登录 |
| POST | `/operations/integrations/resync` | 创建接口重同步任务 | 登录 |
| GET | `/operations/data-quality` | 数据质量治理体检、维度评分、整改队列、Runbook 和血缘链路 | 登录 |
| POST | `/operations/data-quality/remediation` | 创建数据质量整改通知任务并写入审计 | 登录 |
| GET | `/operations/costs` | 预算成本数据 | 登录 |
| POST | `/operations/costs/review` | 创建成本复核任务 | 登录 |
| GET | `/operations/capacity` | 产能计划治理数据：需求、供给、齐套、工作中心、瓶颈队列、服务边界和 Runbook | 登录 |
| POST | `/operations/capacity/review` | 创建产能瓶颈复核任务并写入审计 | 登录 |
| GET | `/operations/maintenance` | 设备可靠性治理工作台：资产线、维护工单、MRO 备件、维修人员、停机窗口、服务边界和 Runbook | 登录 |
| POST | `/operations/maintenance-workorder` | 创建设备维护工单 | 登录 |
| GET | `/operations/mobile-terminal` | 移动扫码终端任务 | 登录 |
| POST | `/operations/mobile-terminal/task` | 创建现场扫码任务 | 登录 |
| GET | `/operations/quality-inspection` | 质量检验治理工作台：检验批、供应商质量、缺陷分类、使用决策、证据、服务边界和 Runbook | 登录 |
| POST | `/operations/quality-inspection` | 创建质量检验任务并写入通知与审计 | 登录 |
| GET | `/operations/procurement-control` | 采购协同控制台：采购泳道、审批队列、到货窗口、供应商风险、补货候选、服务边界和部署检查 | 登录 |
| POST | `/operations/procurement-control/task` | 创建采购协同通知任务并写入审计 | 登录 |
| POST | `/operations/dispatch-task` | 创建仓配调度任务 | 登录 |
| POST | `/operations/data-quality-notice` | 创建数据质量复核任务 | 登录 |
| POST | `/operations/customer-followup` | 创建客户跟进任务 | 登录 |
| POST | `/operations/capacity-plan` | 创建产能计划任务 | 登录 |
| POST | `/operations/contract-review` | 创建合同回款复核任务 | 登录 |
| POST | `/operations/service-workorder` | 创建售后服务工单 | 登录 |

## 10. 仓库纯净化与本地清理

当前活跃项目和保留对照目录：

```text
backend/       Flask REST API、模型、迁移、测试、后端部署配置
frontend/      Angular SPA、主题、页面、前端部署配置
scripts/       本地启动、清理、预检、部署脚本
docs/          交付报告、部署说明、API 清单、ER 图、截图和讲稿
legacy/        旧版 Flask/Jinja2 单体快照，仅用于升级报告对照
```

可保留：

| 路径 | 说明 |
| --- | --- |
| `backend/instance/` | 本地演示数据库运行目录；`nexus_prime.db` 由 seed 命令生成，不提交。 |
| `backend/storage/uploads/.gitkeep`、`backend/storage/uploads/files/.gitkeep`、`backend/storage/uploads/avatars/.gitkeep`、`backend/storage/uploads/library/.gitkeep` | 保留上传目录结构；真实上传文件继续忽略。 |
| `backend/logs/.gitkeep` | 保留日志目录结构。 |
| `frontend/package-lock.json` | 前端依赖锁定文件。 |
| `backend/migrations/` | 数据库迁移。 |
| `docs/images/` | 正式报告截图。 |
| `legacy/monolith-flask/` | 旧版单体快照，保留用于说明如何从 Flask/Jinja2/Railway 升级到前后端分离。 |

禁止提交：

```text
.env
.vscode/
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
node_modules/
venv/
```

清理命令：

```powershell
.\scripts\clean-workspace.ps1 -StopDevServers
```

该命令会停止本地 5000/4200 开发端口并清理缓存、截图输出、日志、SQLite WAL/SHM 与 Python 缓存；默认保留上传目录和头像文件，避免误删本地头像。需要同时删除依赖目录时使用：

```powershell
.\scripts\clean-workspace.ps1 -StopDevServers -RemoveDependencies
```

删除依赖后重新安装：

```powershell
.\scripts\dev.ps1 -Install
```

或只恢复依赖：

```powershell
.\scripts\install-dependencies.ps1
```

`.\scripts\preflight.ps1` 与 `.\scripts\deploy-supabase-vercel.ps1` 也会在缺少依赖时自动恢复。需要只检查、不安装时，预检追加 `-NoInstall`。

纯净交付状态下，只检查部署配置、不恢复依赖：

```powershell
.\scripts\preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests -NoInstall -AllowMissingDependencies
```

## 11. 常用验收命令

后端：

```powershell
cd backend
$env:FLASK_APP="run.py"
python -m flask status
python -m flask audit-enterprise-data --strict
python -m pytest
```

前端：

```powershell
cd frontend
npm test -- --watch=false
npm run build
```

生产健康检查：

```powershell
Invoke-RestMethod "https://<backend-project>.vercel.app/api/v1/health"
Invoke-RestMethod "https://<backend-project>.vercel.app/"
```

## 12. 上线后检查清单

1. 前端能打开 `https://<frontend-project>.vercel.app`。
2. 后端 `GET /api/v1/health` 返回 `status=ok`。
3. `NEXUS_API_BASE_URL` 指向后端 `/api/v1`，不是 localhost。
4. 后端 `CORS_ORIGINS` 精确包含前端域名。
5. 生产 Cookie 为 `Secure=true`、`SameSite=None`。
6. 后端生产日志没有 SQLite 启动错误，`DATABASE_URL` 指向 PostgreSQL/Supabase。
7. 普通用户不能访问 `/system/users`、`/system/audit`。
8. 管理员可以登录、上传头像、下载文件、生成报表。
9. AI 设置页可保存 `api_key`、`base_url`、`model`，`/ai/diagnostics` 能返回诊断结果。
10. 文件和头像上传在生产环境使用 Cloudinary 或后续 Supabase Storage，不依赖 Vercel 临时磁盘。
11. `scripts/preflight.ps1` 通过，不再出现旧托管平台配置。

## 13. 2026-06-06 本地验收记录

以下命令已在本地通过，可作为部署前参考基线：

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
$env:NEXUS_API_BASE_URL="https://nexus-prime-api.vercel.app/api/v1"
$env:FRONTEND_ORIGIN="https://nexus-prime-web.vercel.app"
$env:CORS_ORIGINS=$env:FRONTEND_ORIGIN
$env:DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"
$env:AUTH_COOKIE_SECURE="true"
$env:AUTH_COOKIE_SAMESITE="None"
$env:SECRET_KEY="local-preflight-secret-key-32-characters"
$env:CLOUDINARY_URL="cloudinary://api_key:api_secret@cloud_name"
.\scripts\preflight.ps1 -SkipApiProbe -SkipBuild -SkipBackendTests
```

本次页面与布局层验收结果：

| 项目 | 结果 |
| --- | --- |
| 布局审计 | 66 个页面检查通过，无文本溢出、无按钮出界、无图表过小、无 Dock 遮挡。 |
| 图表审计 | 36 个页面文件通过。 |
| 数据审计 | 企业数据覆盖与业务闭环均为 OK。 |
| 后端测试 | 46 项测试全部通过，包含采购协同控制台合同、部署就绪成熟度合同与任务创建。 |
| 前端测试 | 5 个测试文件、15 个用例全部通过。 |
| 前端构建 | `npm run build` 生产构建通过，输出目录为 `frontend/dist/frontend/browser`。 |
| 部署就绪与 ERP 成熟度审计 | `npm run audit:deployment-readiness` 通过，ERP 成熟度 91%，secret 泄露候选、横向溢出、控制台错误和 HTTP 错误均为 0。 |
| 部署预检 | Supabase、Vercel、Cookie、环境变量和旧平台残留检查全部通过。 |

2026-06-07 维护补充：

- 前端 API 地址解析已集中到 `frontend/src/app/core/api-url.ts`，文件下载、详情页下载和通用 API 请求共用同一套运行时配置。
- 后端生产配置已增加启动保护：缺少 `DATABASE_URL`、`CORS_ORIGINS`、强 `SECRET_KEY` 或跨站 Cookie 安全配置错误时直接失败；正式生产默认拒绝 SQLite。
- 外部 AI 调用默认连接超时 5 秒、请求超时 20 秒，健康检查会返回当前超时配置。
- 本地回归通过：后端 `pytest -q` 46 项、前端 `npm test -- --watch=false` 6 个文件 19 个用例、前端 `npm run build`。

本轮额外确认：

- `frontend/public/runtime-config.js` 已恢复为空 API 值，生产由 `NEXUS_API_BASE_URL` 注入。
- `backend/instance/nexus_prime.db` 不再作为可提交资产；部署和交付检查改为依赖迁移、seed、同步脚本和 Supabase 状态检查。
- 文件中心移动端类型栏不再横向溢出，布局审计已覆盖。
- 首页、登录页、注册页、AI 分析、报表工作室、文件中心和个人工作台已统一居中、图标对齐和响应式兜底。
- 注册页已重新通过浏览器审查：左侧说明面板在注册模式隐藏，注册卡片单卡居中，横向溢出为 0。
- 上传长期保存链路已重新确认：本地按 `files`、`avatars`、`library` 三类目录隔离，生产 Vercel/Serverless 必须配置 Cloudinary 或后续 Supabase Storage。
- 本地演示数据库可通过 `seed-enterprise --scale 3 --multiplier 300 --reset --seed 20241334` 重建；本轮 `flask status` 显示用户 15001、商品 57608、销售订单 100803、文件 7200，运行数据库不提交。
- 更多模块抽屉、Dock、顶部 AI 入口、全局设置、AI 设置与诊断仍保持独立路由和真实 API 调用边界。
