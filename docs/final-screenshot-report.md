# NEXUS Prime 最终截图审核报告

日期：2026-06-28
截图方式：Playwright 登录真实系统后采集
前端地址：`http://127.0.0.1:4200`
API 地址：`http://127.0.0.1:5001/api/v1`

## 1. 结论

本次截图覆盖登录前入口、登录/注册、关键业务页、模块 Dock、详情页、ER 图，以及 33 条业务路由的桌面和移动端页面截图。所有截图均来自真实浏览器访问，不是静态摆图。

| 项目 | 结果 |
| --- | --- |
| 桌面视口 | 1440 x 950 |
| 移动视口 | 390 x 844 |
| 覆盖业务路由 | 33 |
| 全页面截图 | 66 张，见 `docs/images/final/pages/manifest.json` |
| 页面截图文件 | 102 张 PNG，位于 `docs/images/final/pages/` |
| 本地真实图片资产 | 37 张 JPG |
| 页面实际使用图片来源 | 25 个唯一来源 |
| 亮色主题对比 | 通过，最低对比度不低于审计阈值 |
| 暗色主题对比 | 通过 |
| 横向溢出 | 0 |
| 死链 | 0 |
| 未完成文案 | 0 |
| 控制台错误 | 0 |

## 2. 最新审计证据

| 审计 | 输出 |
| --- | --- |
| 布局审计 | `output/playwright/layout-audit-1782581461815/report.json` |
| 工作流链接审计 | `output/playwright/workflow-link-audit-1782581643833/report.json` |
| 完整度审计 | `output/playwright/completeness-audit-1782581707771/report.json` |
| 真实图片审计 | `output/playwright/visual-assets-audit-1782581940592/report.json` |
| 主题对比审计 | `output/playwright/theme-contrast-audit-1782582039323/report.json` |
| Shell 交互审计 | `output/playwright/shell-interaction-1782582085025/report.json` |
| 图表审计 | `output/playwright/chart-audit-1782582111122/report.json` |
| API 合同审计 | `output/playwright/api-contract-audit-1782582119272/report.json` |
| 顶部栏审计 | `output/playwright/topbar-operations-audit-1782582129058/report.json` |
| 更多菜单审计 | `output/playwright/more-menu-audit-1782582228527/report.json` |
| 供应商专项审计 | `output/playwright/supplier-collaboration-1782582291918/report.json` |
| 部署准备审计 | `output/playwright/deployment-readiness-audit-1782582343660/report.json` |
| 最终截图目录 | `docs/images/final/` |
| 全页面截图索引 | `docs/images/final/pages/manifest.json` |

## 3. 关键截图

### 入口页

![入口页](images/final/entry.png)

### 登录页

![登录页](images/final/login.png)

### 注册页

![注册页](images/final/register.png)

### 亮色运营控制塔

![亮色运营控制塔](images/final/final-light-overview.png)

### 暗色运营控制塔

![暗色运营控制塔](images/final/final-dark-overview.png)

### 暗色采购协同

![暗色采购协同](images/final/final-dark-procurement.png)

### 暗色销售履约

![暗色销售履约](images/final/final-dark-fulfillment.png)

### 亮色应收风控

![亮色应收风控](images/final/final-light-receivables.png)

### 报表工作室

![报表工作室](images/final/reports.png)

### 文件详情

![文件详情](images/final/file-detail.png)

### Dock 模块面板

![Dock 模块面板](images/final/dock.png)

### 移动扫码终端

![移动扫码终端](images/final/mobile.png)

### ER 图

![ER 图](images/final/er-diagram.svg)

## 4. 所有页面截图索引

| 页面 | 路由 | 桌面截图 | 移动截图 |
| --- | --- | --- | --- |
| 运营控制塔 | `/app/overview` | [desktop](images/final/pages/desktop-light-luxury-overview.png) | [mobile](images/final/pages/mobile-light-luxury-overview.png) |
| 经营指标中心 | `/app/metrics` | [desktop](images/final/pages/desktop-light-luxury-metrics.png) | [mobile](images/final/pages/mobile-light-luxury-metrics.png) |
| 任务异常中心 | `/app/tasks` | [desktop](images/final/pages/desktop-light-luxury-tasks.png) | [mobile](images/final/pages/mobile-light-luxury-tasks.png) |
| 物料库存图谱 | `/app/inventory/products` | [desktop](images/final/pages/desktop-light-luxury-inventory-products.png) | [mobile](images/final/pages/mobile-light-luxury-inventory-products.png) |
| 仓配流向图 | `/app/inventory/stock` | [desktop](images/final/pages/desktop-light-luxury-inventory-stock.png) | [mobile](images/final/pages/mobile-light-luxury-inventory-stock.png) |
| 采购补货建议 | `/app/inventory/replenishment` | [desktop](images/final/pages/desktop-light-luxury-inventory-replenishment.png) | [mobile](images/final/pages/mobile-light-luxury-inventory-replenishment.png) |
| 销售履约 | `/app/sales/orders` | [desktop](images/final/pages/desktop-light-luxury-sales-orders.png) | [mobile](images/final/pages/mobile-light-luxury-sales-orders.png) |
| 采购协同 | `/app/procurement/orders` | [desktop](images/final/pages/desktop-light-luxury-procurement-orders.png) | [mobile](images/final/pages/mobile-light-luxury-procurement-orders.png) |
| 供应商绩效 | `/app/suppliers/performance` | [desktop](images/final/pages/desktop-light-luxury-suppliers-performance.png) | [mobile](images/final/pages/mobile-light-luxury-suppliers-performance.png) |
| 仓配调度中心 | `/app/dispatch` | [desktop](images/final/pages/desktop-light-luxury-dispatch.png) | [mobile](images/final/pages/mobile-light-luxury-dispatch.png) |
| 数据质量中心 | `/app/data-quality` | [desktop](images/final/pages/desktop-light-luxury-data-quality.png) | [mobile](images/final/pages/mobile-light-luxury-data-quality.png) |
| 质量检验中心 | `/app/quality` | [desktop](images/final/pages/desktop-light-luxury-quality.png) | [mobile](images/final/pages/mobile-light-luxury-quality.png) |
| 客户经营中心 | `/app/customers` | [desktop](images/final/pages/desktop-light-luxury-customers.png) | [mobile](images/final/pages/mobile-light-luxury-customers.png) |
| 产能计划中心 | `/app/capacity` | [desktop](images/final/pages/desktop-light-luxury-capacity.png) | [mobile](images/final/pages/mobile-light-luxury-capacity.png) |
| 设备维护中心 | `/app/maintenance` | [desktop](images/final/pages/desktop-light-luxury-maintenance.png) | [mobile](images/final/pages/mobile-light-luxury-maintenance.png) |
| 合同回款中心 | `/app/contracts` | [desktop](images/final/pages/desktop-light-luxury-contracts.png) | [mobile](images/final/pages/mobile-light-luxury-contracts.png) |
| 售后服务中心 | `/app/service` | [desktop](images/final/pages/desktop-light-luxury-service.png) | [mobile](images/final/pages/mobile-light-luxury-service.png) |
| 规则引擎中心 | `/app/rules` | [desktop](images/final/pages/desktop-light-luxury-rules.png) | [mobile](images/final/pages/mobile-light-luxury-rules.png) |
| 集成监控中心 | `/app/integrations` | [desktop](images/final/pages/desktop-light-luxury-integrations.png) | [mobile](images/final/pages/mobile-light-luxury-integrations.png) |
| 预算成本中心 | `/app/budget` | [desktop](images/final/pages/desktop-light-luxury-budget.png) | [mobile](images/final/pages/mobile-light-luxury-budget.png) |
| 移动扫码终端 | `/app/mobile-terminal` | [desktop](images/final/pages/desktop-light-luxury-mobile-terminal.png) | [mobile](images/final/pages/mobile-light-luxury-mobile-terminal.png) |
| 应收账龄 | `/app/finance/receivables` | [desktop](images/final/pages/desktop-light-luxury-finance-receivables.png) | [mobile](images/final/pages/mobile-light-luxury-finance-receivables.png) |
| 客户信用 | `/app/finance/credits` | [desktop](images/final/pages/desktop-light-luxury-finance-credits.png) | [mobile](images/final/pages/mobile-light-luxury-finance-credits.png) |
| 库存盘点中心 | `/app/stocktakes` | [desktop](images/final/pages/desktop-light-luxury-stocktakes.png) | [mobile](images/final/pages/mobile-light-luxury-stocktakes.png) |
| 报表工作室 | `/app/reports` | [desktop](images/final/pages/desktop-light-luxury-reports.png) | [mobile](images/final/pages/mobile-light-luxury-reports.png) |
| 文件资料库 | `/app/files` | [desktop](images/final/pages/desktop-light-luxury-files.png) | [mobile](images/final/pages/mobile-light-luxury-files.png) |
| 公告与知识库 | `/app/content/articles` | [desktop](images/final/pages/desktop-light-luxury-content-articles.png) | [mobile](images/final/pages/mobile-light-luxury-content-articles.png) |
| 系统安全中心 | `/app/system/users` | [desktop](images/final/pages/desktop-light-luxury-system-users.png) | [mobile](images/final/pages/mobile-light-luxury-system-users.png) |
| 审计日志 | `/app/system/audit` | [desktop](images/final/pages/desktop-light-luxury-system-audit.png) | [mobile](images/final/pages/mobile-light-luxury-system-audit.png) |
| 任务通知中心 | `/app/notifications` | [desktop](images/final/pages/desktop-light-luxury-notifications.png) | [mobile](images/final/pages/mobile-light-luxury-notifications.png) |
| AI 经营分析 | `/app/ai` | [desktop](images/final/pages/desktop-light-luxury-ai.png) | [mobile](images/final/pages/mobile-light-luxury-ai.png) |
| 个人中心 | `/app/profile` | [desktop](images/final/pages/desktop-light-luxury-profile.png) | [mobile](images/final/pages/mobile-light-luxury-profile.png) |
| 控制中心 | `/app/settings` | [desktop](images/final/pages/desktop-light-luxury-settings.png) | [mobile](images/final/pages/mobile-light-luxury-settings.png) |

## 5. 复现命令

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
npm run capture:final-screenshots
```
