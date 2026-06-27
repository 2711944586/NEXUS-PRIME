# NEXUS Prime 操作指南

## 1. 本地启动

推荐使用根目录脚本：

```powershell
.\scripts\dev.ps1
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

访问地址：

```text
前端: http://127.0.0.1:4200
API: http://127.0.0.1:5001/api/v1
```

## 2. 登录

本地演示账号：

```text
管理员: admin@nexus.com / admin123
普通用户: user00001@nexus.com / password123
```

生产部署必须通过环境变量替换默认密码，不要在公网保留演示密码。

## 3. 日常业务流程

### 运营控制塔

路径：`/app/overview`

用途：

- 查看经营控制分。
- 查看低库存、待审批采购、逾期应收、库存水位。
- 进入库存、采购、应收、报表等核心模块。

### 库存补货

路径：`/app/inventory/replenishment`

流程：

1. 查看低库存建议。
2. 选择建议转采购。
3. 进入采购中心审批。
4. 收货后回写库存。

### 采购协同

路径：`/app/procurement/orders`

流程：

1. 查看待审批采购单。
2. 审批下一张或推进收货。
3. 跟踪供应商、到货窗口和预算暴露。
4. 完成后进入供应商绩效和报表归档。

### 销售履约

路径：`/app/sales/orders`

流程：

1. 查看待付款、待发货、已发货、已完成阶段。
2. 推进下一张订单。
3. 发货后联动库存出库和应收。
4. 完成后进入报表。

### 应收风控

路径：`/app/finance/receivables`

流程：

1. 查看账龄、未收金额和客户信用。
2. 记录收款或催款。
3. 回款后释放信用额度。
4. 风险动作写入审计。

### 报表归档

路径：`/app/reports`

流程：

1. 选择经营日报、库存风险、财务风险等模板。
2. 生成报表。
3. 进入文件中心下载或归档。
4. 相关通知推送到通知中心。

## 4. 更多模块

顶部 Dock 只保留核心路径。其它页面从“更多模块”进入：

- 经营指标：`/app/metrics`
- 任务异常：`/app/tasks`
- 仓配流向：`/app/inventory/stock`
- 盘点中心：`/app/stocktakes`
- 质量检验：`/app/quality`
- 产能计划：`/app/capacity`
- 设备维护：`/app/maintenance`
- 合同回款：`/app/contracts`
- 售后服务：`/app/service`
- 规则引擎：`/app/rules`
- 集成监控：`/app/integrations`
- 预算成本：`/app/budget`
- 移动扫码：`/app/mobile-terminal`
- 文件中心：`/app/files`
- 公告知识：`/app/content/articles`
- 系统用户：`/app/system/users`
- 审计日志：`/app/system/audit`
- AI 分析：`/app/ai`

## 5. 验收命令

前端：

```powershell
cd frontend
npm run build
npm run audit:theme-contrast
npm run audit:layout
npm run audit:api-contract
npm run audit:workflow-links
npm run audit:completeness
npm run audit:visual-assets
npm run audit:shell
npm run audit:charts
npm run audit:topbar
npm run audit:more-menus
npm run audit:deployment-readiness
npm run api:check
npm run capture:final-screenshots
```

后端：

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask db upgrade
..\venv\Scripts\python.exe -m flask status
```

## 6. 常见问题

### 前端打不开 API

检查 `frontend/public/runtime-config.js` 是否指向：

```text
http://127.0.0.1:5001/api/v1
```

可重新生成：

```powershell
cd frontend
$env:NEXUS_LOCAL_API_BASE_URL='http://127.0.0.1:5001/api/v1'
node scripts/write-runtime-config.mjs --local
```

### 登录失败

确认后端已启动，并且浏览器能访问：

```text
http://127.0.0.1:5001/api/v1/health
```

### 数据为空

执行：

```powershell
cd backend
$env:FLASK_APP='run.py'
..\venv\Scripts\python.exe -m flask db upgrade
..\venv\Scripts\python.exe -m flask status
```

如果是全新库，再运行项目的种子或重置脚本。
