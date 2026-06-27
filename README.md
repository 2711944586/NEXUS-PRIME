# NEXUS Prime 制造业 ERP 管理信息系统

学生：庄颂  
学号：20241334  
当前交付日期：2026-06-28

NEXUS Prime 是一个前后端分离的制造业 ERP/仓配经营管理系统。前端使用 Angular 21 Standalone Components、PrimeNG 21、ECharts 和 RxJS，后端使用 Flask REST API、SQLAlchemy、Flask-Migrate 和 pytest。系统围绕库存、采购、销售履约、仓配调度、应收回款、盘点、质量、产能、设备、合同、售后、规则、集成、报表、文件、通知、AI 经营分析、权限和审计建立闭环。

当前版本不是旧版页面拼接。`legacy/monolith-flask/` 只保留为 Flask/Jinja2 单体对照快照，不参与新版运行、构建或部署。活跃系统边界为 `backend/`、`frontend/`、`scripts/` 和 `docs/`。

![运营控制塔](docs/images/final/final-light-overview.png)

2026-06-28 补充升级：登录后页面已按 ERP 业务流做减法重构。应用壳层只保留顶栏、核心 Dock、当前页面和更多模块面板；总览页重写为轻量 ERP 控制塔，使用真实现场图片、4 个核心 KPI、6 步闭环、经营趋势和当班待办。详细记录见 `docs/production-upgrade-report-2026-06-28.md`。

## 架构总览

```text
Angular 21 SPA
  Standalone Components / Router / Guard / Interceptor / PrimeNG / ECharts
          |
          | HTTP JSON + HttpOnly Cookie + CSRF
          v
Flask REST API /api/v1
  Auth / Bounded Context APIs / Application Services / Reports / AI / Audit
          |
          v
SQLAlchemy + Alembic
  Local SQLite for demo, PostgreSQL/Supabase-ready for production
```

后端采取“微服务就绪的模块化单体”路线：库存、采购、销售、财务、流程、内容、报表、AI、通知、身份等能力域按 bounded context 组织，保持 `/api/v1` 稳定合同。当前交付不假装已经拆成真实分布式微服务，而是把服务边界、资源注册、测试、OpenAPI/契约审计和部署配置整理到可继续拆分的状态。

核心 ER 图：

![ER 图](docs/images/final/er-diagram.svg)

## 项目结构

```text
nexus_prime/
├── backend/
│   ├── app/api/          # /api/v1 REST API、认证、聚合接口、业务动作
│   ├── app/domains/      # 微服务就绪能力域与资源注册
│   ├── app/models/       # SQLAlchemy 模型
│   ├── app/services/     # 应用服务、报表、AI、库存、工作流等
│   ├── migrations/       # Alembic 迁移
│   ├── tests/            # 207 个后端测试
│   ├── run.py            # 本地 Flask 入口
│   └── server.py         # 部署入口
├── frontend/
│   ├── src/app/core/     # API、认证、主题、模型、导航、可视资产
│   ├── src/app/pages/    # 业务页面与详情页
│   ├── src/app/shell/    # 顶栏、Dock、模块面板
│   ├── src/styles/       # 企业升级层、主题 token、页面修复层
│   └── scripts/          # Playwright 审计与截图采集
├── docs/
│   ├── er.mmd
│   ├── er.dot
│   ├── final-delivery-report.md
│   ├── final-screenshot-report.md
│   ├── final-video-script.md
│   └── images/final/
├── scripts/              # 启动、质量闸门、预检、部署、报告生成
└── legacy/monolith-flask/ # 旧版对照，不参与新版运行
```

## 功能范围

| 能力域 | 页面/路径 | 当前能力 |
| --- | --- | --- |
| 运营控制塔 | `/app/overview` | KPI、风险队列、工作流、现场事件、服务边界、经营图表 |
| 经营指标 | `/app/metrics` | 执行指标、趋势、异常归因 |
| 任务异常 | `/app/tasks` | 通知、预警、部署任务、业务异常统一派发 |
| 物料库存 | `/app/inventory/products` | SKU、分类、供应商、库存关联、详情 |
| 仓配流向 | `/app/inventory/stock` | 仓库网络、库存流水、调度任务、移动端执行快线 |
| 补货建议 | `/app/inventory/replenishment` | 低水位、建议采购、处理闭环 |
| 销售履约 | `/app/sales/orders` | 客户订单、发货调度、应收联动 |
| 采购协同 | `/app/procurement/orders` | 审批、到货、供应商确认、采购任务 |
| 供应商绩效 | `/app/suppliers/performance` | 准入、SLA、CAPA、集中度、协同队列 |
| 仓配调度 | `/app/dispatch` | 调拨、优先级、补货/盘点/报表快捷动作 |
| 数据质量 | `/app/data-quality` | 质量评分、失败规则、整改队列、血缘 |
| 质量检验 | `/app/quality` | 检验批、缺陷、供应商质量、CAPA |
| 客户经营 | `/app/customers` | 客户档案、信用、应收和履约视图 |
| 产能计划 | `/app/capacity` | 需求、供给、齐套、释放能力、瓶颈队列 |
| 设备维护 | `/app/maintenance` | 资产、工单、MRO、停机窗口 |
| 合同回款 | `/app/contracts` | 合同、应收、信用、动作队列 |
| 售后服务 | `/app/service` | 服务工单、客户响应、闭环 |
| 规则引擎 | `/app/rules` | 决策表、命中行、复核队列 |
| 集成监控 | `/app/integrations` | 服务目录、SLO、错误预算、依赖 |
| 预算成本 | `/app/budget` | 预算、实际、承诺、差异复核 |
| 移动终端 | `/app/mobile-terminal` | 收货、盘点、发货、异常扫码队列 |
| 应收账龄 | `/app/finance/receivables` | 账龄、收款、催收、冻结联动 |
| 客户信用 | `/app/finance/credits` | 授信、冻结、风险分层 |
| 库存盘点 | `/app/stocktakes` | 计划、扫码、差异、审核 |
| 报表工作室 | `/app/reports` | 模板、生成队列、归档、图表 |
| 文件资料 | `/app/files` | 上传、下载、详情、关联对象 |
| 公告知识库 | `/app/content/articles` | 文章、评论、附件 |
| 系统用户 | `/app/system/users` | 用户、角色、权限、部门 |
| 审计日志 | `/app/system/audit` | 登录、审批、上传、任务、报表审计 |
| 通知中心 | `/app/notifications` | 任务通知、跳转、完成处理 |
| AI 经营分析 | `/app/ai` | 结构化分析、会话、诊断、草稿动作 |
| 个人中心 | `/app/profile` | 资料、偏好、头像、个人活动 |
| 控制中心 | `/app/settings` | 主题、密度、部署就绪、ERP 成熟度 |

所有页面的桌面/移动截图索引见 `docs/images/final/pages/manifest.json`，稳定交付截图见 `docs/images/final/`。

## 数据规模

当前本地演示库通过 `flask status` 验证：

| 数据 | 数量 |
| --- | ---: |
| 用户 | 15001 |
| 商品 | 57608 |
| 销售订单 | 100803 |
| 库存流水 | 111360 |
| 采购单 | 46803 |
| 应收账款 | 80640 |
| 收款记录 | 70560 |
| 盘点单 | 2400 |
| 通知 | 32424 |
| 报表 | 16200 |
| 文章 | 16200 |
| 文件 | 7200 |
| 审计日志 | 6004 |

默认本地演示账号：

```text
admin@nexus.com / admin123
user00001@nexus.com / password123
```

生产或远程演示必须使用自定义密码和真实环境变量，不提交 `.env`、SQLite 数据库、上传运行目录或密钥。

## 本地运行

推荐一键启动：

```powershell
.\scripts\dev.ps1
```

或双击根目录 `start-dev.bat`。一键启动会先停止同工作区内残留的开发进程、清理本地缓存，再自动检查依赖、选择可用端口、写入 `frontend/public/runtime-config.js`、启动 Flask API 和 Angular SPA，并在就绪后打开浏览器。

常用参数：

```powershell
.\scripts\dev.ps1 -CheckOnly
.\scripts\dev.ps1 -Install
.\scripts\dev.ps1 -Seed
.\scripts\dev.ps1 -NoOpen
.\scripts\dev.ps1 -ResetWorkspace
```

手动启动后端：

```powershell
cd backend
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask run --host 127.0.0.1 --port 5001
```

手动启动前端：

```powershell
cd frontend
$env:NEXUS_LOCAL_API_BASE_URL='http://127.0.0.1:5001/api/v1'
node scripts/write-runtime-config.mjs --local
npm start -- --host 127.0.0.1
```

访问：

```text
前端: http://127.0.0.1:4200
后端: http://127.0.0.1:5001/api/v1
```

## 验证命令

前端：

```powershell
cd frontend
$env:NEXUS_LOCAL_API_BASE_URL='http://127.0.0.1:5001/api/v1'
node scripts/write-runtime-config.mjs --local
$env:NEXUS_AUDIT_BASE_URL='http://127.0.0.1:4200'
$env:NEXUS_AUDIT_API_BASE_URL='http://127.0.0.1:5001/api/v1'
npm run audit:theme-contrast
npm run audit:layout
npm run audit:api-contract
npm run audit:workflow-links
npm run audit:completeness
npm run audit:shell
npm run build
```

后端：

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask db upgrade
..\venv\Scripts\python.exe -m flask status
```

截图：

```powershell
cd frontend
$env:NEXUS_LOCAL_API_BASE_URL='http://127.0.0.1:5001/api/v1'
node scripts/write-runtime-config.mjs --local
$env:NEXUS_AUDIT_BASE_URL='http://127.0.0.1:4200'
npm run capture:final-screenshots
```

## 本轮验收结果

| 检查 | 结果 |
| --- | --- |
| `npm run audit:theme-contrast` | 通过，亮/暗主题桌面和移动无低对比、无不可见文字、无横向溢出 |
| `npm run audit:layout` | 通过，66 个页面检查无布局失败 |
| `npm run audit:api-contract` | 通过，16 个资源、155 条后端路由无合同缺口 |
| `npm run audit:workflow-links` | 通过，桌面/移动工作流入口无死链、可点击 |
| `npm run audit:completeness` | 通过，33 条路由桌面/移动完整度失败数 0 |
| `npm run audit:shell` | 通过，顶栏/ Dock 模块面板、Escape、跳转和 spotlight 坐标正常 |
| `npm run build` | 通过，Angular 生产构建成功 |
| `pytest` | 通过，207 passed |
| `flask db upgrade` | 通过，迁移检查无待执行失败 |

## 文档交付

| 文档 | 说明 |
| --- | --- |
| `docs/final-delivery-report.md` | 最终交付报告 |
| `docs/project_report.md` | 课程汇报报告 |
| `docs/final-screenshot-report.md` | 全页面截图和审计证据 |
| `docs/final-video-script.md` | 讲解视频稿 |
| `docs/production-upgrade-report-2026-06-28.md` | 登录后页面减法重构与生产就绪升级报告 |
| `docs/operator-guide.md` | 操作指南 |
| `docs/code-review-production-readiness.md` | Code review 与生产就绪检查 |
| `docs/er.mmd` | Mermaid ER 源文件 |
| `docs/images/final/er-diagram.svg` | ER 图 |
| `docs/images/final/pages/manifest.json` | 66 张页面截图索引 |

## 部署方向

当前架构支持前端静态部署、后端独立 API 部署、数据库迁移到 PostgreSQL/Supabase。部署前应配置：

- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `NEXUS_DEMO_ADMIN_PASSWORD`
- `NEXUS_DEMO_USER_PASSWORD`
- 可选：Cloudinary/Supabase Storage、Redis/Upstash、AI 服务 Key

`Dockerfile.frontend.prod`、`Dockerfile.backend.prod`、`docker-compose.mainland.yml` 和 `deploy/` 目录提供大陆网络环境下的容器化部署参考。
