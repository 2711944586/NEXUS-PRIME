# 中国大陆前后端分离部署准备

本文档面向阿里云、腾讯云、华为云、火山引擎、私有云或单机 Docker Compose 交付。当前代码保持 `frontend/` Angular SPA 与 `backend/` Flask REST API 分离，浏览器只读取 `NEXUS_API_BASE_URL`，数据库、AI、对象存储和 Cookie 密钥全部留在后端。

## 新增部署资产

| 文件 | 用途 |
| --- | --- |
| `Dockerfile.frontend.prod` | 构建 Angular 静态资源，并用 Nginx 服务前端。容器启动时重写 `runtime-config.js`，同一镜像可用于多环境。 |
| `Dockerfile.backend.prod` | 生产 Flask/Gunicorn 镜像，默认 `FLASK_CONFIG=production`，暴露 `/health/ready` 健康检查。 |
| `deploy/nginx/frontend.conf` | SPA fallback、静态资源缓存、`runtime-config.js` no-store 和基础安全头。 |
| `docker-compose.mainland.yml` | 单机或预生产演练的前端、后端、worker、beat、PostgreSQL、Redis 编排样例。 |
| `.env.mainland.example` | 大陆部署环境变量模板，复制为 `.env.mainland` 后替换真实域名和密钥。 |

## 推荐拓扑

```text
用户浏览器
  -> CDN / WAF / HTTPS 证书
  -> frontend Nginx 静态站点
  -> https://api.example.cn/api/v1
  -> backend Gunicorn API
  -> PostgreSQL / Redis / Celery worker / 对象存储
```

正式域名建议至少拆为：

| 类型 | 示例 | 说明 |
| --- | --- | --- |
| 前端 | `https://erp.example.cn` | CDN 或静态站点入口，必须备案并启用 HTTPS。 |
| API | `https://api.example.cn/api/v1` | 后端网关入口，加入 `CORS_ORIGINS`。 |
| CDN | `https://cdn.example.cn` | 图片、附件或对象存储外链域名。 |

## 免费/低成本云平台入口

以下链接可直接复制到浏览器打开。免费额度会随平台政策变化，创建资源前必须在控制台再次确认“免费、试用、资源点、到期时间、是否自动转付费”。本文按 2026-06-28 可查到的官方信息整理，优先引用官方页面。

官方核验摘要：

- 腾讯云 CloudBase 官方价格文档写明：自 2026-01-16 起，每个云开发账号可创建一个免费体验版环境，免费环境提供 3000 点/月资源点，但存在续费、发布后到期和功能限制。
- 阿里云函数计算官方文档写明：首次登录函数计算控制台的用户可获得连续 3 个周期的免费试用包，超出额度按量付费。
- Sealos 官方页面强调一键部署数据库、中间件、应用、对象存储和静态托管，适合本项目容器化形态；免费/赠送额度以登录控制台后的实时活动为准。
- 华为云 RDS 免费数据库页面提供“领取免费云数据库/免费体验中心”入口，但名额、实名条件、数据库类型和到期规则需要下单前再次确认。

### 方案 A：腾讯云 CloudBase，适合课程演示和轻量 API

CloudBase 官方价格文档说明，自 2026-01-16 起，每个云开发账号可创建一个免费体验版环境，免费环境提供 3000 点/月资源点；CloudBase 云函数支持 HTTP 云函数和 Python，适合把轻量 API 做成云函数或容器服务。

```text
CloudBase 控制台:
https://console.cloud.tencent.com/tcb

CloudBase 免费环境/价格文档:
https://cloud.tencent.com/document/product/876/75213
https://cloud.tencent.com/document/product/876/127357

CloudBase 云函数说明:
https://docs.cloudbase.net/cloud-function/introduce
```

建议用途：

- 前端：CloudBase 静态网站托管。
- 后端：课程演示可迁移为 CloudBase HTTP 云函数；如果保留完整 Flask/Gunicorn，优先使用容器化平台。
- 数据库：CloudBase 数据库适合轻量演示；如果坚持 PostgreSQL，使用 Sealos、华为云 RDS 试用或自建容器数据库。

### 方案 B：Sealos，适合一站式容器、PostgreSQL 和前后端分离

Sealos 官方页面说明支持一键部署数据库、AI 应用与企业级服务。它更贴近当前项目的 Docker 化形态。是否有新用户赠送额度或免费活动，以登录控制台后的实时活动为准，不建议在生产预算里假设永久免费。

```text
Sealos 国内入口:
https://sealos.run/

Sealos 国际入口:
https://sealos.io/

Sealos 应用部署入口:
https://fastdeploy.cloud.sealos.io/
```

建议用途：

- 前端：Nginx 容器部署 `Dockerfile.frontend.prod`。
- 后端：Gunicorn 容器部署 `Dockerfile.backend.prod`。
- 数据库：Sealos PostgreSQL。
- Redis：Sealos Redis 或内置应用市场。

### 方案 C：阿里云函数计算 FC，适合 Serverless 试用

阿里云函数计算是全托管 Serverless 计算服务，官方提供新用户免费试用额度说明。当前 Flask 项目可以通过自定义容器函数部署，但生产数据库仍建议使用 RDS/PostgreSQL 或外部托管数据库。

```text
阿里云函数计算产品页:
https://www.aliyun.com/product/fc

函数计算免费试用额度说明:
https://help.aliyun.com/zh/functioncompute/fc/product-overview/trial-quota-1

自定义容器函数文档:
https://help.aliyun.com/zh/functioncompute/fc-2-0/user-guide/create-a-custom-container-function

阿里云免费试用/解决方案入口:
https://www.aliyun.com/solution/free
```

建议用途：

- 前端：OSS 静态网站 + CDN，或继续使用任意静态托管。
- 后端：FC 自定义容器运行 Flask。
- 数据库：阿里云 RDS PostgreSQL/MySQL 试用或自建演示库。

### 方案 D：华为云 RDS 试用，适合数据库免费试用

华为云官方有 RDS MySQL 免费数据库页面，也有 RDS for PostgreSQL 规格/使用入口。若前后端部署在其它平台，也可以单独用华为云 RDS 作为数据库试用。

```text
华为云 RDS MySQL 免费数据库:
https://www.huaweicloud.com/special/rds-free-xsms.html

华为云 RDS MySQL 入门:
https://www.huaweicloud.com/product/mysql/getting-started.html

华为云 RDS PostgreSQL:
https://www.huaweicloud.com/special/pro-pg-instance-free.html
```

建议用途：

- 数据库：PostgreSQL/MySQL 托管试用。
- 后端：云容器、云耀云服务器或其它容器服务。
- 前端：OBS 静态托管或 CDN。

### 推荐免费/低成本演示组合

优先级：

1. 腾讯云 CloudBase：最适合免费体验环境演示，前端静态托管和轻量 API 成本最低。
2. 阿里云 FC：适合把后端做成 Serverless 自定义容器函数，首次用户可用官方试用额度。
3. 华为云 RDS 试用 + 任意静态托管：适合只需要免费/试用数据库托管的场景。
4. Sealos：最贴近当前 Docker 前后端分离形态，可同时跑前端容器、后端容器、PostgreSQL、Redis；免费额度需以控制台实时活动为准。

## 快速演练

```powershell
Copy-Item .env.mainland.example .env.mainland
# 编辑 .env.mainland，至少替换 SECRET_KEY、POSTGRES_PASSWORD、FRONTEND_ORIGIN、CORS_ORIGINS、NEXUS_API_BASE_URL
docker compose --env-file .env.mainland -f docker-compose.mainland.yml up --build
```

前端本地访问 `http://localhost:8080`，后端健康检查访问 `http://localhost:5000/health/ready`。正式环境中应由 SLB、Ingress 或云网关终止 HTTPS，再转发到容器内 80/5000。

## 环境变量边界

前端容器只允许公开变量：

- `NEXUS_API_BASE_URL`
- `NEXUS_SENTRY_DSN`
- `NEXUS_SENTRY_ENVIRONMENT`
- `NEXUS_SENTRY_RELEASE`
- `NEXUS_SENTRY_TRACES_SAMPLE_RATE`

后端变量必须只配置在后端、worker、beat：

- `DATABASE_URL`
- `SECRET_KEY`
- `REDIS_URL`
- `CACHE_REDIS_URL`
- `CELERY_BROKER_URL`
- `AI_API_KEY`
- `CLOUDINARY_API_SECRET`
- 对象存储 AccessKey / Secret

## 微服务拆分准备

当前建议保持模块化单体运行，先通过边界治理为后续微服务拆分铺路：

| 服务边界 | 当前承载 | 未来拆分信号 |
| --- | --- | --- |
| Identity/Auth | `backend/app/domains/auth` 与 JWT/Cookie 配置 | 多租户、SSO、独立审计或统一用户中心。 |
| Inventory | 库存、补货、盘点相关 API 和 Celery 队列 | 库存写入吞吐独立增长，需独立锁库存。 |
| Procurement/Sales | 采购、销售、履约工作流 | 订单生命周期与库存服务需要事件驱动。 |
| Finance | 应收、信用、预算 | 财务数据权限和审计要求独立升级。 |
| AI/Knowledge | AI 分析、RAG、报告任务 | AI 调用成本、限流和队列需要独立伸缩。 |
| Files/Assets | 上传、头像、资料库 | 对象存储、病毒扫描、CDN 签名下载独立治理。 |

拆分前保持 `/api/v1` 稳定，新增服务应先通过网关聚合和事件队列解耦，不直接让浏览器感知内部服务地址。

## 生产注意事项

- 备案与证书：大陆公网域名需要 ICP 备案；API 和前端都必须启用 HTTPS。
- Cookie：跨子域登录使用 `AUTH_COOKIE_SAMESITE=None` 与 `AUTH_COOKIE_SECURE=true`；同域反代可改为 `Lax`。
- CORS：`CORS_ORIGINS` 精确填写前端 HTTPS 域名，不要保留 localhost。
- 字体与素材：登录后界面不再依赖 Google Fonts；如需 Geist，可自行下载后从自有 CDN 或前端 assets 托管。
- 迁移：Compose 样例在后端启动时执行 `flask db upgrade`；多副本/K8s 应改为一次性 migration job。
- 对象存储：生产上传建议迁移到 OSS/COS/OBS/S3 兼容存储，容器卷只用于临时缓存或单机演练。
- 回滚：前端镜像可通过环境变量切换 API；后端回滚前确认数据库迁移是否可逆。
