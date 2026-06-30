# NEXUS Prime 交付包

更新时间：2026-06-30

## 线上地址

- 前端演示地址：`https://constantine-d3gjhwmtz0336c36a-1448158108.tcloudbaseapp.com/nexus-prime-fulldata-06292135-44aed6a/`
- 后端 API Base：`https://nexus-api-fulldata-06292135-44aed6a-276095-6-1448158108.sh.run.tcloudbase.com/api/v1`
- 管理员账号：`admin@nexus.com / admin123`
- 普通账号：`user00001@nexus.com / password123`

## 交付文件

- `nexus-prime-system-report.pdf`：完整系统报告，包含部署地址、ER 图、页面截图、功能说明、架构设计、代码讲解和部署流程。
- `nexus-prime-video-walkthrough.mp4`：讲解视频成片。
- `docs/nexus-prime-system-report.md`：可维护的报告源文件。
- `docs/nexus-prime-video-script.md`：可直接朗读的视频讲稿。

## 云端数据验证

当前 CloudRun 后端已接入完整 SQLite 演示库。`/health/deployment-data` 最新验证：

| 数据项 | 数量 |
| --- | ---: |
| 用户账号 `auth_users` | 15001 |
| 商品主数据 `biz_products` | 57609 |
| 客户/供应商 `biz_partners` | 25200 |
| 销售订单 `trade_orders` | 100803 |
| 采购订单 `purchase_orders` | 46803 |
| 应收账款 `finance_receivables` | 80640 |
| 库存数量 `stock_quantities` | 111360 |
| 系统通知 `sys_notifications` | 32431 |
| 生成报表 `generated_reports` | 16200 |

登录探针已通过：管理员存在、密码正确、权限序列化正常、令牌可创建。

## 本轮修复

- 修复腾讯云静态前端和 CloudRun API 跨域部署时，前端登录成功后仍被守卫踢回登录页的问题。
- 修复后端经 CloudBase 网关生成头像 URL 时可能输出 `http://` 的混合内容警告。
- 增加 CloudRun SQLite 引导脚本，启动时下载、解压并校验完整演示库，避免空库上线。
- 增加部署诊断端点，便于确认云端数据量和登录探针。
- 整理腾讯云 CloudBase 自动部署脚本，支持唯一前端路径、运行时 API 地址和静态资源路径修正。

## 验证命令

```powershell
.\venv\Scripts\python.exe -m pytest backend/tests/test_config.py backend/tests/test_api.py backend/tests/test_storage_service.py
cd frontend
npm test -- --watch=false --include src/app/core/auth.service.spec.ts
$env:NEXUS_API_BASE_URL='https://nexus-api-fulldata-06292135-44aed6a-276095-6-1448158108.sh.run.tcloudbase.com/api/v1'
npm run build -- --base-href /nexus-prime-release-06301105/ --deploy-url /nexus-prime-release-06301105/
```

验证结果：

- 后端：`64 passed`
- 前端认证：`3 passed`
- 前端生产构建：通过，仅保留一个未使用图标导入警告 `LucideMonitor`
- 浏览器链路：修复后的前端在腾讯云静态域名上下文中登录到 `/app/overview`，10 个云端 API 请求全部 HTTP 200

## 重新部署命令

当前本机缺少 CloudBase CLI 登录态，实际上传被 CLI 阻止。完成以下任一认证后即可复跑：

```powershell
npx --yes --package @cloudbase/cli@3.5.8 tcb login
```

或设置：

```powershell
$env:CLOUDBASE_API_KEY='...'
# 或
$env:TENCENTCLOUD_SECRET_ID='...'
$env:TENCENTCLOUD_SECRET_KEY='...'
```

前端重新部署命令：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\tencent-cloudbase-auto-deploy.ps1 `
  -Suffix release-06301105 `
  -ApiBaseUrl "https://nexus-api-fulldata-06292135-44aed6a-276095-6-1448158108.sh.run.tcloudbase.com/api/v1" `
  -SkipBackend `
  -SkipRoutes
```

后端当前已验证可用，除非需要发布后端补丁，否则不必重建 CloudRun。若要完整发布，先确认 `.env.tencent-cloudbase` 中的 `NEXUS_DB_BOOTSTRAP_URL`、`DATABASE_URL`、`SECRET_KEY`、`CORS_ORIGINS` 已正确设置，再去掉 `-SkipBackend`。
