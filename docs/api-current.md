# NEXUS Prime API Current Baseline

Generated for `NEXUS_PRIME_CODEX_PLAN.md` Phase 0 on 2026-06-20.

Contract audit status: `233/233` frontend endpoint uses matched against `122` runtime routes and `31` resources.

Source command:

```powershell
cd backend
..\venv\Scripts\python.exe - <<PY
from app import create_app
app = create_app('testing')
for rule in sorted(app.url_map.iter_rules(), key=lambda r: (str(r.rule), r.endpoint)):
    methods = ','.join(sorted(m for m in rule.methods if m not in {'HEAD', 'OPTIONS'}))
    print(methods, rule.rule, rule.endpoint)
PY
```

## Runtime Route List

| Methods | Rule | Endpoint |
| --- | --- | --- |
| `GET` | `/` | `root_health` |
| `POST` | `/api/v1/<path:new_path>` | `api.create_new_resource` |
| `GET` | `/api/v1/<path:new_path>` | `api.list_new_resource` |
| `DELETE` | `/api/v1/<path:new_path>/<int:item_id>` | `api.delete_new_resource` |
| `GET` | `/api/v1/<path:new_path>/<int:item_id>` | `api.get_new_resource` |
| `PATCH` | `/api/v1/<path:new_path>/<int:item_id>` | `api.update_new_resource` |
| `PUT` | `/api/v1/<path:new_path>/<int:item_id>` | `api.update_new_resource` |
| `POST` | `/api/v1/<resource>` | `api.create_resource` |
| `GET` | `/api/v1/<resource>` | `api.list_resource` |
| `DELETE` | `/api/v1/<resource>/<int:item_id>` | `api.delete_resource` |
| `GET` | `/api/v1/<resource>/<int:item_id>` | `api.get_resource` |
| `PATCH` | `/api/v1/<resource>/<int:item_id>` | `api.update_resource` |
| `PUT` | `/api/v1/<resource>/<int:item_id>` | `api.update_resource` |
| `POST` | `/api/v1/ai/analyze/inventory` | `api.ai_inventory_analysis` |
| `POST` | `/api/v1/ai/analyze/structured` | `api.ai_structured_analysis` |
| `POST` | `/api/v1/ai/chat` | `api.ai_chat` |
| `POST` | `/api/v1/ai/diagnostics` | `api.ai_diagnostics` |
| `POST` | `/api/v1/ai/sessions` | `api.ai_create_session` |
| `GET` | `/api/v1/ai/sessions` | `api.ai_sessions` |
| `DELETE` | `/api/v1/ai/sessions/<int:session_id>` | `api.ai_delete_session` |
| `GET` | `/api/v1/ai/sessions/<int:session_id>/messages` | `api.ai_session_messages` |
| `GET` | `/api/v1/ai/settings` | `api.ai_settings` |
| `PUT` | `/api/v1/ai/settings` | `api.ai_update_settings` |
| `GET` | `/api/v1/analytics/executive` | `api.executive_analytics` |
| `POST` | `/api/v1/articles/<int:article_id>/comments` | `api.create_article_comment` |
| `GET` | `/api/v1/articles/<int:article_id>/comments` | `api.list_article_comments` |
| `GET` | `/api/v1/auth/captcha` | `api.api_captcha` |
| `POST` | `/api/v1/auth/change-password` | `api.api_change_password` |
| `GET` | `/api/v1/auth/csrf` | `api.api_csrf` |
| `POST` | `/api/v1/auth/login` | `api.api_login` |
| `POST` | `/api/v1/auth/logout` | `api.api_logout` |
| `GET` | `/api/v1/auth/me` | `api.api_me` |
| `POST` | `/api/v1/auth/register` | `api.api_register` |
| `GET` | `/api/v1/auth/register-policy` | `api.api_register_policy` |
| `GET` | `/api/v1/avatars/<path:filename>` | `api.api_avatar_file` |
| `GET` | `/api/v1/avatars/initials/<path:key>` | `api.api_initials_avatar` |
| `POST` | `/api/v1/bulk-actions` | `api.bulk_actions` |
| `GET` | `/api/v1/dashboard/charts` | `api.dashboard_charts` |
| `GET` | `/api/v1/dashboard/summary` | `api.dashboard_summary` |
| `GET` | `/api/v1/erp/control-tower` | `api.erp_control_tower` |
| `GET` | `/api/v1/export/<resource>/<format_type>` | `api.api_export_resource` |
| `GET` | `/api/v1/files/<int:file_id>/download` | `api.api_download_file` |
| `POST` | `/api/v1/files/bulk-delete` | `api.files_bulk_delete` |
| `POST` | `/api/v1/files/upload` | `api.api_upload_file` |
| `GET` | `/api/v1/finance/credits` | `api.finance_credits` |
| `PUT` | `/api/v1/finance/credits/<int:credit_id>` | `api.finance_credit_update` |
| `POST` | `/api/v1/finance/credits/<int:credit_id>/freeze` | `api.finance_credit_freeze` |
| `POST` | `/api/v1/finance/credits/<int:credit_id>/unfreeze` | `api.finance_credit_unfreeze` |
| `POST` | `/api/v1/finance/receivables/<int:receivable_id>/payment` | `api.finance_payment` |
| `POST` | `/api/v1/finance/receivables/<int:receivable_id>/reminder` | `api.finance_receivable_reminder` |
| `GET` | `/api/v1/finance/receivables/aging` | `api.receivables_aging` |
| `GET` | `/api/v1/health` | `api.health` |
| `GET` | `/api/v1/health/live` | `api.health_live` |
| `GET` | `/api/v1/health/ready` | `api.health_ready` |
| `POST` | `/api/v1/inventory/adjust` | `api.adjust_inventory` |
| `GET` | `/api/v1/inventory/health` | `api.inventory_health` |
| `POST` | `/api/v1/inventory/replenishment-suggestions/<int:suggestion_id>/accept` | `api.replenishment_accept` |
| `POST` | `/api/v1/inventory/replenishment-suggestions/generate` | `api.replenishment_generate` |
| `GET` | `/api/v1/lookups/partners` | `api.lookup_partners` |
| `GET` | `/api/v1/lookups/products` | `api.lookup_products` |
| `GET` | `/api/v1/lookups/stock-locations` | `api.lookup_stock_locations` |
| `GET` | `/api/v1/lookups/warehouses` | `api.lookup_warehouses` |
| `GET` | `/api/v1/manufacturing/command-center` | `api.manufacturing_command_center` |
| `GET` | `/api/v1/manufacturing/workflow-board` | `api.manufacturing_workflow_board` |
| `DELETE` | `/api/v1/me/avatar` | `api.api_delete_avatar` |
| `POST` | `/api/v1/me/avatar` | `api.api_upload_avatar` |
| `GET` | `/api/v1/me/preferences` | `api.get_preferences` |
| `PUT` | `/api/v1/me/preferences` | `api.update_preferences` |
| `PUT` | `/api/v1/me/profile` | `api.api_update_profile` |
| `GET` | `/api/v1/meta/navigation` | `api.meta_navigation` |
| `POST` | `/api/v1/notifications/complete` | `api.notifications_complete` |
| `POST` | `/api/v1/notifications/mark-read` | `api.notifications_mark_read` |
| `GET` | `/api/v1/notifications/unread-count` | `api.notifications_unread_count` |
| `GET` | `/api/v1/operations/capacity` | `api.operations_capacity` |
| `POST` | `/api/v1/operations/capacity-plan` | `api.operations_capacity_plan` |
| `POST` | `/api/v1/operations/capacity/review` | `api.operations_capacity_review` |
| `POST` | `/api/v1/operations/contract-review` | `api.operations_contract_review` |
| `GET` | `/api/v1/operations/costs` | `api.operations_costs` |
| `POST` | `/api/v1/operations/costs/review` | `api.operations_costs_review` |
| `POST` | `/api/v1/operations/customer-followup` | `api.operations_customer_followup` |
| `GET` | `/api/v1/operations/data-quality` | `api.operations_data_quality` |
| `POST` | `/api/v1/operations/data-quality-notice` | `api.operations_data_quality_notice` |
| `POST` | `/api/v1/operations/data-quality/remediation` | `api.operations_data_quality_remediation` |
| `GET` | `/api/v1/operations/deployment-readiness` | `api.operations_deployment_readiness` |
| `POST` | `/api/v1/operations/deployment-readiness/task` | `api.operations_deployment_readiness_task` |
| `POST` | `/api/v1/operations/dispatch-task` | `api.operations_dispatch_task` |
| `GET` | `/api/v1/operations/exceptions` | `api.operations_exceptions` |
| `GET` | `/api/v1/operations/integrations` | `api.operations_integrations` |
| `POST` | `/api/v1/operations/integrations/resync` | `api.operations_integrations_resync` |
| `GET` | `/api/v1/operations/maintenance` | `api.operations_maintenance` |
| `POST` | `/api/v1/operations/maintenance-workorder` | `api.operations_maintenance_workorder` |
| `GET` | `/api/v1/operations/mobile-terminal` | `api.operations_mobile_terminal` |
| `POST` | `/api/v1/operations/mobile-terminal/task` | `api.operations_mobile_terminal_task` |
| `GET` | `/api/v1/operations/procurement-control` | `api.operations_procurement_control_payload` |
| `POST` | `/api/v1/operations/procurement-control/task` | `api.operations_procurement_control_task` |
| `POST` | `/api/v1/operations/quality-inspection` | `api.operations_quality_inspection` |
| `GET` | `/api/v1/operations/quality-inspection` | `api.operations_quality_inspection_payload` |
| `GET` | `/api/v1/operations/rules` | `api.operations_rules` |
| `POST` | `/api/v1/operations/rules/review` | `api.operations_rules_review` |
| `POST` | `/api/v1/operations/service-workorder` | `api.operations_service_workorder` |
| `GET` | `/api/v1/operations/supplier-collaboration` | `api.operations_supplier_collaboration_payload` |
| `POST` | `/api/v1/operations/supplier-collaboration/task` | `api.operations_supplier_collaboration_task` |
| `GET` | `/api/v1/operations/task-queue` | `api.operations_task_queue` |
| `GET` | `/api/v1/operations/todo` | `api.operations_todo` |
| `GET` | `/api/v1/overview/charts` | `api.overview_charts` |
| `GET` | `/api/v1/overview/command-center` | `api.overview_command_center` |
| `GET` | `/api/v1/overview/control-tower` | `api.overview_control_tower` |
| `GET` | `/api/v1/overview/summary` | `api.overview_summary` |
| `GET` | `/api/v1/overview/workflow-board` | `api.overview_workflow_board` |
| `POST` | `/api/v1/procurement/orders/<int:po_id>/approve` | `api.procurement_approve` |
| `POST` | `/api/v1/procurement/orders/<int:po_id>/receive` | `api.procurement_receive` |
| `POST` | `/api/v1/procurement/orders/<int:po_id>/reject` | `api.procurement_reject` |
| `POST` | `/api/v1/procurement/orders/<int:po_id>/submit` | `api.procurement_submit` |
| `GET` | `/api/v1/procurement/summary` | `api.procurement_summary` |
| `POST` | `/api/v1/purchase-orders/<int:po_id>/approve` | `api.approve_purchase_order` |
| `POST` | `/api/v1/purchase-orders/<int:po_id>/receive` | `api.receive_purchase_order` |
| `POST` | `/api/v1/purchase-orders/<int:po_id>/reject` | `api.reject_purchase_order` |
| `POST` | `/api/v1/purchase-orders/<int:po_id>/submit` | `api.submit_purchase_order` |
| `POST` | `/api/v1/receivables/<int:receivable_id>/payment` | `api.api_record_payment` |
| `POST` | `/api/v1/replenishment-suggestions/<int:suggestion_id>/accept` | `api.api_accept_replenishment` |
| `POST` | `/api/v1/replenishment-suggestions/<int:suggestion_id>/generate` | `api.api_generate_single_replenishment` |
| `POST` | `/api/v1/replenishment-suggestions/generate` | `api.api_generate_replenishment` |
| `POST` | `/api/v1/reports/generate/<report_type>` | `api.api_report_generate` |
| `GET` | `/api/v1/reports/types` | `api.api_report_types` |
| `POST` | `/api/v1/sales/orders` | `api.create_sales_order` |
| `POST` | `/api/v1/sales/orders/<int:order_id>/transition` | `api.sales_order_transition` |
| `GET` | `/api/v1/search` | `api.global_search` |
| `POST` | `/api/v1/statements/generate` | `api.api_generate_statement` |
| `POST` | `/api/v1/stock-alerts/check` | `api.api_check_alerts` |
| `POST` | `/api/v1/stocktake-items/<int:item_id>/count` | `api.api_count_stocktake_item` |
| `POST` | `/api/v1/stocktakes/<int:take_id>/complete` | `api.api_complete_stocktake` |
| `POST` | `/api/v1/stocktakes/<int:take_id>/count` | `api.stocktake_count_input` |
| `POST` | `/api/v1/stocktakes/<int:take_id>/start` | `api.api_start_stocktake` |
| `GET` | `/api/v1/stocktakes/<int:take_id>/variance` | `api.stocktake_variance` |
| `POST` | `/api/v1/stocktakes/create` | `api.api_create_stocktake` |
| `GET` | `/health/live` | `health_live` |
| `GET` | `/health/ready` | `health_ready` |

## Generic CRUD Resource Registry

| Resource | Model | Permission |
| --- | --- | --- |
| `ai-messages` | `AiChatMessage` |  |
| `ai-sessions` | `AiChatSession` |  |
| `article-comments` | `ArticleComment` |  |
| `articles` | `Article` | `content.write` |
| `audit-logs` | `AuditLog` | `admin_only` |
| `categories` | `Category` | `masterdata.write` |
| `credits` | `CustomerCredit` | `finance.credit.write` |
| `departments` | `Department` | `admin_only` |
| `files` | `Attachment` |  |
| `generated-reports` | `GeneratedReport` |  |
| `inventory-logs` | `InventoryLog` |  |
| `notifications` | `Notification` |  |
| `order-items` | `OrderItem` | `sales.write` |
| `orders` | `Order` | `sales.write` |
| `partners` | `Partner` | `masterdata.write` |
| `payments` | `PaymentRecord` | `finance.payment` |
| `products` | `Product` | `masterdata.write` |
| `purchase-order-items` | `PurchaseOrderItem` | `purchase.write` |
| `purchase-orders` | `PurchaseOrder` | `purchase.write` |
| `receivables` | `Receivable` | `finance.payment` |
| `replenishment-suggestions` | `ReplenishmentSuggestion` | `purchase.write` |
| `report-subscriptions` | `ReportSubscription` |  |
| `roles` | `Role` | `admin_only` |
| `statements` | `AccountStatement` | `reports.generate` |
| `stock` | `Stock` | `inventory.adjust` |
| `stock-alerts` | `StockAlert` | `inventory.adjust` |
| `stocktake-items` | `StockTakeItem` | `stocktake.write` |
| `stocktakes` | `StockTake` | `stocktake.write` |
| `supplier-performance` | `SupplierPerformance` |  |
| `users` | `User` | `admin_only` |
| `warehouses` | `Warehouse` | `inventory.adjust` |

Aliases:

| Alias | Resource |
| --- | --- |
| `reports` | `generated-reports` |
