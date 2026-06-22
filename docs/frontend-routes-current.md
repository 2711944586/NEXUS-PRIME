# NEXUS Prime Frontend Routes Current Baseline

Generated for `NEXUS_PRIME_CODEX_PLAN.md` Phase 0 on 2026-06-20.

Source: `frontend/src/app/app.routes.ts`

| Path | Type | Target | Guard | Detail |
| --- | --- | --- | --- | --- |
| `/` | route | `./pages/entry.page::EntryPage` | `guestGuard` |  |
| `/auth/login` | route | `./pages/login.page::LoginPage` | `guestGuard` |  |
| `/auth/register-policy` | route | `./pages/register-policy.page::RegisterPolicyPage` | `guestGuard` |  |
| `/login` | redirect | `/auth/login` |  |  |
| `/app` | route | `./shell/app-shell.component::AppShellComponent` | `authGuard` |  |
| `/app` | redirect | `/app/overview` |  |  |
| `/app/overview` | route | `./pages/command-center.page::CommandCenterPage` |  |  |
| `/app/metrics` | route | `./pages/executive-metrics.page::ExecutiveMetricsPage` |  |  |
| `/app/tasks` | route | `./pages/operations-tasks.page::OperationsTasksPage` |  |  |
| `/app/inventory/products` | route | `./pages/materials.page::MaterialsPage` |  |  |
| `/app/inventory/products/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `products` |
| `/app/inventory/stock` | route | `./pages/warehouse-flow.page::WarehouseFlowPage` |  |  |
| `/app/inventory/stock/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `stock` |
| `/app/inventory/replenishment` | route | `./pages/replenishment.page::ReplenishmentPage` |  |  |
| `/app/inventory/replenishment/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `replenishment` |
| `/app/sales/orders` | route | `./pages/fulfillment.page::FulfillmentPage` |  |  |
| `/app/sales/orders/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `salesOrders` |
| `/app/sales/kanban` | redirect | `/app/sales/orders` |  |  |
| `/app/procurement/orders` | route | `./pages/procurement.page::ProcurementPage` |  |  |
| `/app/procurement/orders/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `purchaseOrders` |
| `/app/suppliers/performance` | route | `./pages/supplier-performance.page::SupplierPerformancePage` |  |  |
| `/app/dispatch` | route | `./pages/dispatch-center.page::DispatchCenterPage` |  |  |
| `/app/data-quality` | route | `./pages/data-quality.page::DataQualityPage` |  |  |
| `/app/quality` | route | `./pages/quality-inspection.page::QualityInspectionPage` |  |  |
| `/app/customers` | route | `./pages/customer-operations.page::CustomerOperationsPage` |  |  |
| `/app/customers/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `customers` |
| `/app/capacity` | route | `./pages/capacity-planning.page::CapacityPlanningPage` |  |  |
| `/app/maintenance` | route | `./pages/maintenance.page::MaintenancePage` |  |  |
| `/app/contracts` | route | `./pages/contract-collection.page::ContractCollectionPage` |  |  |
| `/app/service` | route | `./pages/service-workorders.page::ServiceWorkordersPage` |  |  |
| `/app/rules` | route | `./pages/rules-engine.page::RulesEnginePage` |  |  |
| `/app/integrations` | route | `./pages/integration-monitor.page::IntegrationMonitorPage` |  |  |
| `/app/budget` | route | `./pages/budget-cost.page::BudgetCostPage` |  |  |
| `/app/mobile-terminal` | route | `./pages/mobile-terminal.page::MobileTerminalPage` |  |  |
| `/app/finance/receivables` | route | `./pages/receivables.page::ReceivablesPage` |  |  |
| `/app/finance/receivables/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `receivables` |
| `/app/finance/credits` | route | `./pages/credit.page::CreditPage` |  |  |
| `/app/finance/credits/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `credits` |
| `/app/stocktakes` | route | `./pages/stocktake.page::StocktakePage` |  |  |
| `/app/stocktakes/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `stocktakes` |
| `/app/reports` | route | `./pages/reports.page::ReportsPage` |  |  |
| `/app/reports/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `reports` |
| `/app/files` | route | `./pages/files.page::FilesPage` |  |  |
| `/app/files/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `files` |
| `/app/content/articles` | route | `./pages/content.page::ContentPage` |  |  |
| `/app/content/articles/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `articles` |
| `/app/system/users` | route | `./pages/security.page::SecurityPage` |  |  |
| `/app/system/users/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `users` |
| `/app/system/audit` | route | `./pages/audit.page::AuditPage` |  |  |
| `/app/system/audit/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `auditLogs` |
| `/app/notifications` | route | `./pages/notifications.page::NotificationsPage` |  |  |
| `/app/notifications/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `notifications` |
| `/app/ai` | route | `./pages/ai.page::AiPage` |  |  |
| `/app/ai/:id` | route | `./pages/record-detail.page::RecordDetailPage` |  | `aiSessions` |
| `/app/profile` | route | `./pages/profile.page::ProfilePage` |  |  |
| `/app/settings` | route | `./pages/settings.page::SettingsPage` |  |  |
| `/dashboard` | redirect | `/app/overview` |  |  |
| `/inventory` | redirect | `/app/inventory/products` |  |  |
| `/sales` | redirect | `/app/sales/orders` |  |  |
| `/purchase` | redirect | `/app/procurement/orders` |  |  |
| `/finance` | redirect | `/app/finance/receivables` |  |  |
| `/stocktake` | redirect | `/app/stocktakes` |  |  |
| `/reports` | redirect | `/app/reports` |  |  |
| `/files` | redirect | `/app/files` |  |  |
| `/system` | redirect | `/app/system/users` |  |  |
| `/**` | redirect | `/` |  |  |
