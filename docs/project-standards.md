# NEXUS Prime 项目规范

## 1. 路径规范

- 后端运行代码只放在 `backend/`。
- 前端运行代码只放在 `frontend/`。
- 文档、截图和讲稿放在 `docs/`。
- 自动化脚本放在 `scripts/`。
- 历史代码、临时导出和运行缓存不得回流到活跃项目边界。
- 运行时图片资源放在 `frontend/public/images/`，页面只引用集中登记的资源，不在模板里散落外链。
- 本地运行产物、构建产物、截图输出、本地上传运行文件、数据库 WAL/SHM、依赖目录不得作为功能代码提交；`uploads/files`、`uploads/avatars`、`uploads/library` 三类上传目录只保留 `.gitkeep`。
- 最终交付截图统一放在 `docs/images/final/`，报告引用必须能被 `scripts/audit-delivery-assets.py` 解析。
- 最终完成度审计统一写入 `docs/final-completion-audit.md`，必须按目标要求列出证据、验证命令和审计结论。
- 最终截图审核结论统一写入 `docs/final-screenshot-report.md`，必须包含桌面/移动覆盖、关键截图、验收结果和复现命令。
- 前端设计研究、skills 使用和本轮工作流升级记录统一写入 `docs/frontend-upgrade-research-notes.md`。
- Markdown 最终报告更新后必须重新生成 `docs/final-delivery-report.docx`，不得让 DOCX 版本滞后于 Markdown。

## 2. 架构边界

- `frontend/` 只负责浏览器端页面、主题、交互、运行时 API 地址配置和 Vercel SPA 发布。
- `backend/` 只负责 Flask REST API、认证授权、业务流程、数据库模型、迁移、审计、文件/头像存储和后端发布。
- `frontend/src/app/core/navigation.ts` 是导航、Dock 可见入口、更多菜单入口和导航分组的唯一配置源。
- `frontend/src/app/core/visual-assets.ts` 是前端真实图片资源的登记入口。
- `frontend/src/app/pages/page-utils.ts` 放页面通用格式化、图表图例和列表辅助方法；页面内不要重复写同类格式化逻辑。
- `frontend/src/styles.scss` 底部的页面稳定层只做布局兜底和跨页面修复；首页、登录、注册统一维护在 `frontend/src/auth-entry.scss`；跨页面动效进入 `frontend/src/motion-system.scss`；真实截图后发现的触控按钮、工作卡和状态胶囊精修进入 `frontend/src/experience-polish.scss`；每日制造经营作战流进入 `frontend/src/workflow-board.scss`；部署就绪、ERP 成熟度和服务拓扑验收进入 `frontend/src/deployment-readiness.scss`。新增页面优先写清晰局部类，避免继续扩大无差别全局覆盖。
- 后端 API 必须保持 `/api/v1` 契约，前端不得绕过后端直连 Supabase 数据库或后端密钥。

## 3. 前端规范

- 新页面必须使用 Angular standalone component。
- 新页面必须在 `frontend/src/app/app.routes.ts` 注册路由。
- 可导航页面必须在 `frontend/src/app/core/navigation.ts` 注册 Dock 或更多菜单入口。
- 列表页面必须具备搜索、分页、跳转和详情页入口。
- 创建、修改、详情类流程优先使用独立页面，不使用拥挤弹窗承载复杂业务。
- 图标按钮必须使用 PrimeIcons 或 Lucide，内容居中并带明确可访问标签。
- 页面主体不得被 Dock、Drawer、顶部栏遮挡。
- 图表容器必须有稳定高度，移动端不得出现横向溢出。
- 图表头、KPI 卡、状态卡、用户身份区、AI 消息流和设置表单必须具备稳定纵向间距、最小宽度兜底和长文本换行，不允许标签与数值互相覆盖。
- 首页、总览、登录/注册、报表、AI 分析、文件中心等关键页面必须包含真实图片或真实业务数据支撑的图表，不使用空洞装饰块冒充内容。
- 图表必须具备 tooltip、稳定 legend 和响应式容器；图表模式切换按钮使用可点击控件，不使用静态说明文字替代交互。
- 主题切换、密度、Dock 标签、图表动效等偏好由 `ThemeService` 管理，页面不得各自写一套主题状态。
- 跨页面动效必须使用 transform、opacity、filter、box-shadow 等低重排属性，并保留 `prefers-reduced-motion` 兜底；不得为了单页效果重复注册全局 pointermove 监听器。
- `experience-polish.scss` 只做最终体验收口，选择器必须有页面或模块父类约束，不得承接数据逻辑、权限逻辑或临时调试样式。
- 页面新增图片时，先放入 `frontend/public/images/`，再在 `visual-assets.ts` 登记，最后由组件引用。
- 纵览页的结构顺序固定为：顶部经营入口、业务账本、每日制造经营作战流、核心交互图表、流程闭环、流向/风险、快捷系统、补充图表、行动 playbook。

## 4. 后端规范

- API 统一使用 `/api/v1` 前缀。
- 响应结构统一为 `{ data, message, error }`。
- 跨模块经营聚合接口优先放在 `/manufacturing/*`，例如 `/manufacturing/command-center` 和 `/manufacturing/workflow-board`；前端不得在组件里重复拼接跨模块数据库逻辑。
- `/manufacturing/workflow-board` 必须同时返回 `stages`、`handoffs`、`bottlenecks`、`action_queue`、`service_boundaries` 和 `deployment_checks`，确保总览页不是静态展示，而是可执行、可拆分、可部署前检查的班次控制台。
- `/operations/task-queue` 必须聚合通知、部署预检、库存预警和采购审批等当班任务，返回可追溯的 `source_path` 与 `action_kind`；排序必须保证 P0 优先，并让同优先级的可执行动作进入前屏，不得只返回普通跳转列表。
- `/operations/integrations` 必须返回服务目录、契约、依赖、SLO、观测信号覆盖、错误预算和治理队列；集成治理项必须能通过 `/operations/integrations/resync` 创建通知任务并写入审计，不得只做静态监控。
- `/operations/data-quality` 必须由后端服务层聚合主数据、仓配、采购、履约和财务质量维度，返回评分、失败测试、整改队列、负责人、SLA、Runbook 和血缘链路；前端页面不得再通过多个资源列表临时拼接权威质量分。
- `/operations/data-quality/remediation` 必须把治理项写入通知与审计，并通过 `related_type='quality'` 映射回 `/app/data-quality`；任务内容不得包含数据库连接、Token、AI Key、Cloudinary secret 或其他生产密钥。
- `/operations/rules` 必须由后端服务层聚合库存、采购、应收、报表和审计规则，返回规则健康、DMN 风格决策表、hit policy、输入/输出列、命中行、风险队列、负责人、SLA、Runbook 和服务边界；前端不得只用本地静态规则列表冒充规则引擎。
- `/operations/rules/review` 必须把规则复核项写入通知与审计，并通过 `related_type='rules'` 映射回 `/app/rules`；任务内容不得包含数据库连接、Token、AI Key、Cloudinary secret 或其他生产密钥。
- `/operations/deployment-readiness` 必须只返回配置状态、证据、修复动作、能力域地图、微服务拓扑、成熟度维度和交付资产证据，不得返回真实 `DATABASE_URL`、`SECRET_KEY`、AI Key、Cloudinary secret 或 Vercel Token。前端设置页只能展示边界、检查项、服务快照、成熟度、拓扑、证据和 runbook。
- `/operations/deployment-readiness/task` 只能把检查项 key、label、scope、status、evidence 和 action 写入通知与审计，不得接收、存储或返回真实 secret 值；attention/blocked 项才应提供创建任务入口。
- 写操作必须校验登录、CSRF 和业务权限。
- 关键业务动作必须写入审计日志。
- 通知类任务如果提供“处理完成”入口，必须调用 `/notifications/complete` 或等价后端接口回写 `is_read/read_at`，并在审计日志记录来源页面和处理说明；不得只做前端本地隐藏。
- 列表接口必须支持 `page`、`page_size`、`q`、`sort` 和 `order`。
- 生产密钥只能读取环境变量。
- 上传存储不得依赖 Vercel 本地持久磁盘。
- 前端运行时只接收 `NEXUS_API_BASE_URL`，不接收 `DATABASE_URL`、`SECRET_KEY`、AI API Key、Cloudinary secret 或 Supabase secret key。
- AI 外部服务只在后端配置和调用；用户保存的 API Key/Base URL/Model 通过后端接口读写并做脱敏返回。
- 生产部署必须设置 `FLASK_CONFIG=production` 和 `NEXUS_RUNTIME_DIR=/tmp/nexus-prime`。

## 5. 部署规范

- 前端 Vercel 项目根目录为 `frontend/`。
- 后端 Vercel 项目根目录为 `backend/`。
- Supabase 连接串必须为 PostgreSQL 且包含 `sslmode=require`。
- 跨站 Cookie 必须配置 `AUTH_COOKIE_SECURE=true` 与 `AUTH_COOKIE_SAMESITE=None`。
- 部署前必须设置 `CLOUDINARY_URL` 并运行 `scripts/preflight.ps1`。
- 完整交付前优先运行 `scripts/quality-gate.ps1`，它会串联报告生成、数据审计、后端测试、前端测试、构建、图表审计、壳层交互审计、布局审计、部署预检和交付资产审计。
- 旧托管平台配置不得重新加入项目。
- Vercel 上必须创建两个独立项目：`nexus-prime-web` 一类前端项目和 `nexus-prime-api` 一类后端 API 项目。
- Serverless 或短生命周期后端优先使用 Supabase transaction pooler，连接串端口通常为 `6543`。
- 独立长驻后端可使用 direct connection 或 session pooler；IPv4-only 环境优先使用 pooler。
- 上传存储必须区分用户附件、头像和系统资料库：本地分别使用 `UPLOAD_FILES_FOLDER`、`UPLOAD_AVATARS_FOLDER`、`UPLOAD_LIBRARY_FOLDER`；生产上传文件和头像需要 Cloudinary 或后续 Supabase Storage，不把 Vercel 临时磁盘当持久存储；未配置持久化存储时上传接口应返回 `persistent_storage_required`。
- `scripts/deploy-supabase-vercel.ps1` 是一键部署入口，所有手工部署步骤都应能映射到该脚本参数。
- 演示数据库默认规模为 `--scale 3 --multiplier 300 --seed 20241334`；本地开发脚本、远程部署脚本、README 和报告中的种子命令必须保持一致。

## 6. 测试规范

- 完整交付、答辩截图重做、部署前架构调整后运行 `.\scripts\quality-gate.ps1`。
- 只检查报告、截图、ER 图、真实图片和死链接风险时运行 `python scripts\audit-delivery-assets.py`。
- 修改 `docs/final-delivery-report.md` 后运行 `python scripts\generate_final_report_docx.py`，或直接运行质量闸门自动同步 DOCX。
- 后端提交前运行 `python -m pytest -q`。
- 前端提交前运行 `npm test -- --watch=false` 与 `npm run build`。
- 页面结构变更后运行 `npm run audit:layout`；该审计必须覆盖横向溢出、图表尺寸、Dock 遮挡、ECharts guard 和可见文字几何重叠。
- 顶部栏、Dock、更多模块、壳层搜索、快捷创建或 spotlight 交互变更后运行 `npm run audit:shell`；该审计必须覆盖桌面/移动更多模块、模块跳转、Escape 关闭、无横向溢出、无控制台错误和 `--spotlight-x/y` 坐标写入。
- 图表变更后运行 `npm run audit:charts`。
- 部署前设置 `CLOUDINARY_URL` 后运行 `scripts/preflight.ps1 -SkipApiProbe`；真实后端上线后再移除 `-SkipApiProbe`。
- 纵览页、登录页、AI 分析、报表工作室、文件中心、个人工作台改动后必须通过桌面和移动布局审计。
- 任务异常中心或通知/部署任务闭环改动后，必须用真实浏览器验证创建任务、处理完成、来源跳转、桌面/移动横向溢出、控制台错误和 4xx/5xx 响应。
- 数据质量中心改动后，必须验证 `/operations/data-quality` 在真实本地演示库上可稳定返回，并用真实浏览器验证创建整改任务、任务队列出现质量任务、桌面/移动横向溢出、控制台错误和 4xx/5xx 响应。
- 规则引擎中心改动后，必须验证 `/operations/rules` 返回决策表、风险队列和服务边界，并用真实浏览器验证创建复核任务、任务队列出现规则任务、桌面/移动横向溢出、控制台错误和 4xx/5xx 响应。
- 首页、登录页和注册流程改动后必须重启 Angular dev server 或重新构建，确认 `auth-entry.scss` 已进入最终 `styles.css`；注册模式必须为单卡居中，左侧说明面板不显示。

## 7. 交付资产规范

- `docs/images/final/` 中的截图必须覆盖入场页、登录、注册、总览、Dock、命令菜单、AI、设置、个人、文件、报表、暗色/亮色和移动端关键页面。
- `docs/final-screenshot-report.md` 必须引用最终截图并说明最新布局审计报告路径、截图采集目录、路由覆盖数量和失败项数量。
- `docs/final-completion-audit.md` 必须覆盖前端升级、动画、前后端分离、微服务准备、部署准备、清理、报告、截图、ER 图和质量闸门证据。
- ER 图必须同时保留 `docs/er.mmd`、`docs/images/final/er-diagram.svg` 和 `docs/images/final/er-diagram.png`。
- `frontend/src/app/core/visual-assets.ts` 中登记的每一张图片都必须存在于 `frontend/public/images/`。
- 报告、部署手册、API Token 手册、视频讲稿和 README 中的图片引用不得断链。
- 活跃项目不得出现 `href="#"`、`routerLink="#"`、`javascript:void(0)`、`内容待完善`、`截图占位` 等交付风险内容；表单 `placeholder` 和 CSS `::placeholder` 属于正常输入提示。
