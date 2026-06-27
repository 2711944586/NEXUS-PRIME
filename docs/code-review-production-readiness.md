# Code Review 与生产就绪检查

日期：2026-06-28  
范围：登录后 shell、总览页、导航、样式层、文档和部署准备。

## 1. 主要发现与处理

### 问题 1：登录后 shell 过重

严重度：高

现象：

- 所有登录后路由都被强制插入 workflow strip、execution ledger、page evidence、resource workbench 和 context panel。
- 业务页本身还要展示自己的列表、图表、动作队列，导致页面显得杂乱。

修复：

- 修改 `frontend/src/app/shell/app-shell.component.ts`。
- shell 只保留顶栏、Dock、当前路由和更多模块面板。
- 删除模板中的重复全局业务组件渲染。

### 问题 2：总览页模板过长且重复

严重度：高

现象：

- `command-center.page.ts` 原模板超过 1000 行。
- 健康度、图表、流程、风险墙、控制塔和作战流重复出现。
- 页面像演示拼贴，无法在第一屏说明下一步动作。

修复：

- 重写 `frontend/src/app/pages/command-center.page.ts`。
- 保留后端聚合接口和真实业务数据。
- 页面结构压缩为：现场 hero、4 个 KPI、6 步流程、经营图表、当班待办、模块边界、真实图片证据。

### 问题 3：核心导航入口过多

严重度：中

现象：

- 首屏导航过多，用户无法判断主要路径。

修复：

- 修改 `frontend/src/app/core/navigation.ts`。
- 核心 Dock 保留：运营、物料、采购、履约、应收、报表。
- 其它模块放入更多模块面板。

### 问题 4：真实图片资源没有系统性复用

严重度：中

现象：

- 项目已有大量真实工业、仓库、财务、质量、服务图片，但后续页面没有统一视觉语言。

修复：

- 新增 `frontend/src/styles/_erp-simplified-workspace.scss`。
- 给采购、仓配、履约、质量、售后、预算、个人、设置等 hero 绑定真实图片背景。
- 总览页证据图使用现有真实工作流资产。

### 问题 5：文档没有记录本轮 ERP skill 与减法依据

严重度：中

修复：

- 新增 `docs/production-upgrade-report-2026-06-28.md`。
- 新增 `docs/operator-guide.md`。
- 新增本 code review 文档。
- 更新大陆部署文档，补充免费云平台入口。

### 问题 6：桌面总览页主按钮文本溢出

严重度：中

现象：

- `npm run audit:layout` 发现桌面 `/app/overview` 的“处理低库存”按钮存在 nowrap 溢出。

修复：

- 修改 `frontend/src/styles/_erp-simplified-workspace.scss`。
- 总览 hero 动作按钮改为 `repeat(auto-fit, minmax(118px, 1fr))`，并允许按钮文本正常换行。

### 问题 7：移动端物料页 hero 被旧高度裁切

严重度：高

现象：

- 移动端 `/app/inventory/products` 的分类图谱被旧规则限制为 `max-height: 172px` 并裁切，隐藏行仍参与文本坐标计算，造成视觉审计重叠。

修复：

- 在最后加载的 `_erp-simplified-workspace.scss` 中对 `header.material-atlas-hero` 加强覆盖。
- 小屏改为“标题 -> 分类图谱 -> 低水位摘要”三段布局，解除 `overflow:hidden`，保持完整业务信息可见。

### 问题 8：总览页移动端证据图 lazy 加载不稳定

严重度：中

现象：

- `npm run audit:visual-assets` 发现移动端 `/app/overview` 有 3 张真实证据图在审计时尚未 decode，被误判为 broken image。

修复：

- 修改 `frontend/src/app/pages/command-center.page.ts`。
- 总览证据图从 `loading="lazy"` 改为 `loading="eager"`，确保演示和审计首轮访问时稳定显示。

### 问题 9：工作流链接审计未等待异步列表渲染

严重度：中

现象：

- 采购、销售和集成页的首条记录链接在 reload 后 250ms 内尚未渲染，审计报 `target_not_found_after_reload`。
- 链接本身不是死链，属于审计脚本等待策略过短。

修复：

- 修改 `frontend/scripts/workflow-link-audit.mjs`。
- 点击前等待目标 href 出现在可见 DOM 中，再执行真实点击和路径校验。

## 2. 验证

已运行：

| 命令 | 结果 |
| --- | --- |
| `npm run audit:layout` | 通过，66 个页面检查 |
| `npm run audit:workflow-links` | 通过 |
| `npm run audit:completeness` | 通过 |
| `npm run audit:visual-assets` | 通过，37 张本地 JPG、25 个唯一使用来源 |
| `npm run audit:theme-contrast` | 通过 |
| `npm run audit:shell` | 通过 |
| `npm run audit:charts` | 通过，37 个页面文件 |
| `npm run audit:api-contract` | 通过，16 个资源、155 条后端路由 |
| `npm run audit:topbar` | 通过 |
| `npm run audit:more-menus` | 通过 |
| `npm run audit:supplier` | 通过 |
| `npm run audit:deployment-readiness` | 通过 |
| `npm run api:check` | 通过 |
| `npm run build` | 通过，产物在 `frontend/dist/frontend` |
| `..\venv\Scripts\python.exe -m pytest` | 207 passed |
| `npm run capture:final-screenshots` | 完成，`docs/images/final/pages/manifest.json` 66 条索引 |

## 3. 仍需关注

- 当前“微服务”是可拆分边界，不是已经多进程、多仓库、多数据库的分布式微服务。
- 当前多租户隔离在文档和架构层已规划，生产多租户上线前仍需逐表补 `tenant_id` 或采用独立 schema/数据库方案。
- 免费云平台只适合课程演示、MVP 或低流量试用，生产环境必须配置备案、HTTPS、日志、备份、监控和告警。

## 4. 建议发布前检查清单

- `npm run build`
- `npm run audit:api-contract`
- `npm run audit:layout`
- `npm run audit:completeness`
- `..\venv\Scripts\python.exe -m pytest`
- `flask db upgrade`
- `flask status`
- 检查 `.env.mainland` 不含默认密钥。
- 检查 `CORS_ORIGINS` 只包含生产前端域名。
- 检查前端 `NEXUS_API_BASE_URL` 指向生产 API。
- 检查数据库备份和迁移回滚说明。
