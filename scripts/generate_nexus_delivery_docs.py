import json
import shutil
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MANIFEST = DOCS / "images" / "final" / "pages" / "manifest.json"

FRONTEND_URL = "https://constantine-d3gjhwmtz0336c36a-1448158108.tcloudbaseapp.com/nexus-prime-fulldata-06292135-44aed6a/"
API_BASE = "https://nexus-api-fulldata-06292135-44aed6a-276095-6-1448158108.sh.run.tcloudbase.com/api/v1"
DB_ASSET_URL = "https://constantine-d3gjhwmtz0336c36a-1448158108.tcloudbaseapp.com/nexus-data/nexus_prime_full_06292108.db.gz"

DATA_COUNTS = [
    ("auth_users", "用户账号", "15001"),
    ("biz_products", "物料商品", "57609"),
    ("biz_partners", "客户供应商伙伴", "25200"),
    ("trade_orders", "销售订单", "100803"),
    ("trade_order_items", "销售明细", "201603"),
    ("purchase_orders", "采购订单", "46803"),
    ("purchase_order_items", "采购明细", "93603"),
    ("finance_receivables", "应收账款", "80640"),
    ("finance_payments", "收款记录", "70560"),
    ("stock_quantities", "库存数量", "111360"),
    ("stock_logs", "库存日志", "111360"),
    ("sys_notifications", "系统通知", "32431"),
    ("sys_audit_logs", "审计日志", "7694"),
    ("cms_articles", "公告知识文章", "16200"),
    ("generated_reports", "生成报表", "16200"),
]

PAGE_ORDER = [
    "/app/overview",
    "/app/metrics",
    "/app/tasks",
    "/app/inventory/products",
    "/app/inventory/stock",
    "/app/inventory/replenishment",
    "/app/sales/orders",
    "/app/procurement/orders",
    "/app/suppliers/performance",
    "/app/dispatch",
    "/app/data-quality",
    "/app/quality",
    "/app/customers",
    "/app/capacity",
    "/app/maintenance",
    "/app/contracts",
    "/app/service",
    "/app/rules",
    "/app/integrations",
    "/app/budget",
    "/app/mobile-terminal",
    "/app/finance/receivables",
    "/app/finance/credits",
    "/app/stocktakes",
    "/app/reports",
    "/app/files",
    "/app/content/articles",
    "/app/system/users",
    "/app/system/audit",
    "/app/notifications",
    "/app/ai",
    "/app/profile",
    "/app/settings",
]

PAGE_DETAILS = {
    "/app/overview": {
        "purpose": "作为登录后的总览页，把库存、采购、销售、应收、异常任务和经营风险合并为一个运营控制塔。",
        "functions": ["查看经营控制分和核心 KPI", "进入库存、采购、销售、财务等业务闭环", "查看当班待办、风险提示和趋势图"],
        "data": "制造指挥中心、待办任务、异常队列、库存和财务摘要。",
        "apis": "manufacturing/command-center, operations/todo, operations/exceptions",
    },
    "/app/metrics": {
        "purpose": "经营指标中心用于展示业务健康度、营收趋势、库存效率和现金流风险。",
        "functions": ["查看核心经营指标", "对比多维度图表", "识别异常指标并进入相关业务页"],
        "data": "经营指标、库存水位、销售和财务汇总。",
        "apis": "analytics/executive",
    },
    "/app/tasks": {
        "purpose": "任务异常中心把超期、堵点、审批、库存和质量异常集中到统一队列。",
        "functions": ["查看异常任务", "按状态和优先级识别风险", "从异常跳转到具体业务对象"],
        "data": "待办、异常、流程任务和通知。",
        "apis": "operations/todo, operations/exceptions, notifications",
    },
    "/app/inventory/products": {
        "purpose": "物料库存图谱管理产品主数据、分类、供应商和库存关联。",
        "functions": ["查看物料清单", "搜索筛选商品", "维护物料属性并查看库存摘要"],
        "data": "商品、分类、供应商、标签和库存数量。",
        "apis": "products, categories, partners, inventory",
    },
    "/app/inventory/stock": {
        "purpose": "仓配流向图展示仓库、库存数量、调拨流向和库存动作。",
        "functions": ["查看仓库和库存流向", "查看库存明细和分页", "执行库存调整和仓配调度"],
        "data": "仓库、库存数量、库存日志、库存移动和预警。",
        "apis": "stocks, warehouses, inventory/adjust",
    },
    "/app/inventory/replenishment": {
        "purpose": "采购补货建议把低库存商品、建议数量、供应商和采购转化关系放在同一页。",
        "functions": ["生成补货建议", "接受或忽略建议", "跟踪建议到采购订单的转化"],
        "data": "补货建议、商品、仓库、供应商和采购单。",
        "apis": "inventory/replenishment-suggestions",
    },
    "/app/sales/orders": {
        "purpose": "销售履约中心管理客户订单、发货状态、销售人员和应收联动。",
        "functions": ["创建和查看销售订单", "推进订单状态", "查看客户和商品明细"],
        "data": "销售订单、订单明细、客户、销售员、应收。",
        "apis": "sales/orders, sales/orders/:id/transition",
    },
    "/app/procurement/orders": {
        "purpose": "采购协同控制台覆盖采购创建、提交、审批、收货和供应商承诺。",
        "functions": ["查看采购订单", "提交审批和批准", "登记收货并跟踪采购进度"],
        "data": "采购订单、采购明细、供应商、仓库和补货建议。",
        "apis": "procurement/orders, operations/procurement-control",
    },
    "/app/suppliers/performance": {
        "purpose": "供应商协同网络评估供应商交付、质量、信用和待办采购风险。",
        "functions": ["查看供应商绩效", "识别延期和质量风险", "联动采购订单和补货任务"],
        "data": "供应商绩效、伙伴档案、采购订单和质量指标。",
        "apis": "suppliers-performance, partners",
    },
    "/app/dispatch": {
        "purpose": "仓配调度中心聚焦仓库负载、出入库节奏和调度任务。",
        "functions": ["查看仓配任务", "识别拥堵仓库", "跟踪执行队列和调度建议"],
        "data": "仓库、库存流水、任务队列和异常提示。",
        "apis": "operations/dispatch, stocks, stock-logs",
    },
    "/app/data-quality": {
        "purpose": "数据质量中心用于检查主数据完整性、重复记录和业务字段异常。",
        "functions": ["查看数据质量评分", "定位缺失字段", "跟踪修复任务"],
        "data": "商品、伙伴、订单、库存和审计检查结果。",
        "apis": "operations/data-quality",
    },
    "/app/quality": {
        "purpose": "质量检验中心管理检验批、质量问题、处置动作和质量趋势。",
        "functions": ["查看检验任务", "记录质量处置", "识别供应商和产品质量风险"],
        "data": "质量任务、采购、供应商、商品和异常记录。",
        "apis": "operations/quality-inspection",
    },
    "/app/customers": {
        "purpose": "客户经营中心把客户档案、交易贡献、风险和服务动作合并展示。",
        "functions": ["查看客户清单", "识别高价值和高风险客户", "进入订单、应收和信用动作"],
        "data": "客户伙伴、订单、应收、信用和服务记录。",
        "apis": "partners, sales/orders, finance/credits",
    },
    "/app/capacity": {
        "purpose": "产能计划中心用于查看产能负载、瓶颈工序、齐套风险和排产建议。",
        "functions": ["查看产能负载", "发起产能复核", "识别齐套和设备瓶颈"],
        "data": "产能计划、设备、采购、库存和任务队列。",
        "apis": "operations/capacity, operations/capacity/review",
    },
    "/app/maintenance": {
        "purpose": "设备维护中心用于管理设备状态、预防维护、故障工单和可靠性指标。",
        "functions": ["查看设备健康", "创建维护工单", "跟踪维修队列和停机影响"],
        "data": "设备、维护工单、产能和质量异常。",
        "apis": "operations/maintenance, operations/maintenance-workorder",
    },
    "/app/contracts": {
        "purpose": "合同回款中心连接合同、订单、应收和回款风险。",
        "functions": ["查看合同和回款节点", "识别逾期风险", "联动财务收款和客户信用"],
        "data": "合同、销售订单、应收账款、收款记录和客户。",
        "apis": "contracts, finance/receivables",
    },
    "/app/service": {
        "purpose": "售后服务中心管理客户服务、问题处理和履约后的反馈闭环。",
        "functions": ["查看服务工单", "识别客户反馈风险", "联动客户、订单和质量页面"],
        "data": "客户、订单、售后工单、质量问题和通知。",
        "apis": "operations/service, partners",
    },
    "/app/rules": {
        "purpose": "规则引擎中心展示预警、审批、补货和报表规则的运行状态。",
        "functions": ["查看规则命中", "管理规则状态", "追踪规则带来的任务和通知"],
        "data": "规则、通知、报表订阅、补货建议和审计记录。",
        "apis": "rules, notifications, report-subscriptions",
    },
    "/app/integrations": {
        "purpose": "集成监控中心用于查看外部系统、任务队列和数据同步状态。",
        "functions": ["查看集成健康", "识别失败同步", "跟踪后台任务和领域事件"],
        "data": "后台任务、领域事件、集成状态和错误摘要。",
        "apis": "integrations, background-jobs, domain-events",
    },
    "/app/budget": {
        "purpose": "预算成本中心管理采购成本、库存成本、预算偏差和复核动作。",
        "functions": ["查看预算执行", "识别成本偏差", "发起预算复核"],
        "data": "采购、库存、财务、预算指标和异常任务。",
        "apis": "operations/costs, operations/costs/review",
    },
    "/app/mobile-terminal": {
        "purpose": "移动扫码终端模拟仓库现场扫码、拣货、上架、盘点和执行记录。",
        "functions": ["查看扫码任务", "创建现场任务", "跟踪执行状态和移动端适配"],
        "data": "移动任务、库存、仓库、盘点和通知。",
        "apis": "operations/mobile-terminal, operations/mobile-terminal/task",
    },
    "/app/finance/receivables": {
        "purpose": "账龄风险墙用于查看应收账款、逾期天数、账龄分布和催收动作。",
        "functions": ["查看应收列表", "登记收款", "分析账龄风险和客户风险"],
        "data": "应收、收款、客户、销售订单和账龄统计。",
        "apis": "finance/receivables, finance/receivables/aging",
    },
    "/app/finance/credits": {
        "purpose": "客户信用中心管理信用额度、可用额度、冻结状态和客户风险。",
        "functions": ["查看客户信用", "冻结或释放信用", "联动订单和应收风险"],
        "data": "客户信用、客户、订单和应收。",
        "apis": "finance/credits, finance/credits/:id/freeze",
    },
    "/app/stocktakes": {
        "purpose": "库存盘点中心管理盘点单、盘点明细、差异和库存修正。",
        "functions": ["创建盘点", "启动和完成盘点", "录入差异并查看调整影响"],
        "data": "盘点单、盘点明细、仓库、商品和库存日志。",
        "apis": "stocktakes, stocktakes/create, stocktakes/:id/complete",
    },
    "/app/reports": {
        "purpose": "报表工作室用于生成、查看、订阅和下载经营报表。",
        "functions": ["生成报表", "查看报表状态", "管理报表订阅和历史"],
        "data": "生成报表、报表订阅、经营指标和用户。",
        "apis": "reports/generate, generated-reports, report-subscriptions",
    },
    "/app/files": {
        "purpose": "文件资料库管理业务附件、知识资料、下载和上传。",
        "functions": ["上传文件", "下载附件", "按业务对象查看文件归档"],
        "data": "附件、文章、上传人和业务引用。",
        "apis": "files/upload, files/:id/download, attachments",
    },
    "/app/content/articles": {
        "purpose": "公告与知识库发布企业公告、知识文章、评论和附件。",
        "functions": ["查看文章", "维护公告", "评论和引用附件"],
        "data": "文章、评论、附件、作者和审计记录。",
        "apis": "articles, article-comments, attachments",
    },
    "/app/system/users": {
        "purpose": "系统安全中心管理账号、角色、部门、权限和账号状态。",
        "functions": ["查看用户列表", "调整角色和账号状态", "检查权限边界"],
        "data": "用户、角色、权限、部门和审计。",
        "apis": "users, roles, permissions, departments",
    },
    "/app/system/audit": {
        "purpose": "审计日志页面集中展示登录、写入、审批、删除和系统动作留痕。",
        "functions": ["查看审计日志", "按用户和动作追踪", "支撑问题回溯和课程验收"],
        "data": "审计日志、用户、模块、动作和请求上下文。",
        "apis": "audit-logs",
    },
    "/app/notifications": {
        "purpose": "任务通知中心用于查看未读、已读、异常和业务提醒。",
        "functions": ["查看通知", "标记已读", "从通知进入业务对象"],
        "data": "系统通知、库存预警、任务事件和用户。",
        "apis": "notifications, notifications/mark-read",
    },
    "/app/ai": {
        "purpose": "经营分析台提供 AI 对话、结构化诊断、经营建议和动作草稿。",
        "functions": ["发起经营问答", "生成结构化分析", "查看 AI 会话和动作草稿"],
        "data": "AI 会话、消息、经营指标、文档分块和动作草稿。",
        "apis": "ai/chat, ai/analyze/structured, ai/diagnostics",
    },
    "/app/profile": {
        "purpose": "个人中心管理身份资料、头像、偏好、工作负载和最近业务入口。",
        "functions": ["更新个人资料", "上传或恢复头像", "查看个人待办和偏好"],
        "data": "当前用户、头像、偏好、通知和待办。",
        "apis": "me/profile, me/avatar, me/preferences, operations/todo",
    },
    "/app/settings": {
        "purpose": "控制中心管理主题、密度、部署状态、AI 配置提示和系统能力概览。",
        "functions": ["查看运行配置", "调整主题偏好", "检查部署就绪和系统能力"],
        "data": "个人偏好、健康检查、AI 状态和系统配置摘要。",
        "apis": "me/preferences, health, observability/metrics",
    },
}


ENTRY_SCREENSHOTS = [
    ("首页入口", "images/final/entry-dark.png", "首页保持原样，仅在报告中使用暗色主题截图。它承担品牌入口、产品气质和进入登录流程的第一视觉锚点。"),
    ("登录页", "images/final/login-dark.png", "登录页保持原样，仅在报告中使用暗色主题截图。它承担账号密码登录、注册切换、会话建立和 CSRF 初始化。"),
    ("注册页", "images/final/register-dark.png", "注册页保持原样，仅在报告中使用暗色主题截图。它承担普通用户准入、资料填写、协议确认和验证码校验。"),
    ("注册协议页", "images/final/register-policy-dark.png", "注册协议页保持原样，仅在报告中使用暗色主题截图。它承担注册规则、隐私说明和用户准入边界说明。"),
]

ER_DIAGRAMS = [
    {
        "file": "er-identity-master.png",
        "title": "身份权限与主数据 ER",
        "description": "该图覆盖账号、角色、权限、部门、客户供应商、物料分类、物料标签和商品主数据。身份权限决定谁能进入系统、能执行哪些动作；主数据则是采购、库存、销售、财务等后续交易的共同事实源。",
        "dot": r"""
digraph er_identity_master {
  graph [rankdir=LR, bgcolor="white", pad="0.32", nodesep="0.55", ranksep="0.9", splines=ortho, fontname="Microsoft YaHei", label="身份权限与主数据", labelloc=t, fontsize=22];
  node [shape=record, style="rounded,filled", fillcolor="#f8fafc", color="#91a4b7", fontname="Microsoft YaHei", fontsize=10, margin="0.08,0.05"];
  edge [color="#52697d", arrowsize=0.7, fontname="Microsoft YaHei", fontsize=8];
  auth_users [label="{auth_users|PK id\lFK role_id\lFK department_id\lusername / email\lis_active\l}"];
  auth_roles [label="{auth_roles|PK id\lname / description\l}"];
  auth_permissions [label="{auth_permissions|PK id\lcode / name\lresource / action\l}"];
  roles_permissions [label="{roles_permissions|FK role_id\lFK permission_id\l}"];
  auth_departments [label="{auth_departments|PK id\lFK parent_id\lname\l}"];
  biz_partners [label="{biz_partners|PK id\lpartner_type\lname\lcontact / risk_level\lcredit_score\l}"];
  biz_categories [label="{biz_categories|PK id\lname\l}"];
  biz_tags [label="{biz_tags|PK id\lname\l}"];
  biz_products [label="{biz_products|PK id\lFK category_id\lFK supplier_id\lsku / name\lprice / cost\lmin_stock / max_stock\l}"];
  biz_product_tags [label="{biz_product_tags|FK product_id\lFK tag_id\l}"];
  auth_roles -> auth_users [label="1:N"];
  auth_departments -> auth_users [label="1:N"];
  auth_departments -> auth_departments [label="parent"];
  auth_roles -> roles_permissions [label="1:N"];
  auth_permissions -> roles_permissions [label="1:N"];
  biz_categories -> biz_products [label="classifies"];
  biz_partners -> biz_products [label="default supplier"];
  biz_products -> biz_product_tags [label="tagged"];
  biz_tags -> biz_product_tags [label="labels"];
}
""",
    },
    {
        "file": "er-inventory-procurement.png",
        "title": "库存仓配与采购补货 ER",
        "description": "该图覆盖仓库、库存数量、库存余额、库存流水、库存预警、补货建议、采购订单、采购明细、供应商报价和供应商绩效。它解释了从低库存识别到补货建议、采购审批、收货入库、供应商评分的闭环。",
        "dot": r"""
digraph er_inventory_procurement {
  graph [rankdir=LR, bgcolor="white", pad="0.32", nodesep="0.55", ranksep="0.85", splines=ortho, fontname="Microsoft YaHei", label="库存仓配与采购补货", labelloc=t, fontsize=22];
  node [shape=record, style="rounded,filled", fillcolor="#f8fafc", color="#91a4b7", fontname="Microsoft YaHei", fontsize=10, margin="0.08,0.05"];
  edge [color="#52697d", arrowsize=0.7, fontname="Microsoft YaHei", fontsize=8];
  biz_products [label="{biz_products|PK id\lsku / name\lmin_stock / max_stock\l}"];
  biz_partners [label="{biz_partners|PK id\lpartner_type=supplier\lname\lrisk_level\l}"];
  auth_users [label="{auth_users|PK id\loperator / approver\l}"];
  stock_warehouses [label="{stock_warehouses|PK id\lcode / name\lregion\l}"];
  stock_quantities [label="{stock_quantities|PK id\lFK product_id\lFK warehouse_id\lquantity / shelf\l}"];
  stock_balances [label="{stock_balances|PK id\lFK product_id\lFK warehouse_id\lavailable / reserved\l}"];
  stock_movements [label="{stock_movements|PK id\lFK product_id\lFK warehouse_id\lFK created_by\lmovement_type / qty\l}"];
  stock_logs [label="{stock_logs|PK id\lFK product_id\lFK warehouse_id\lFK operator_id\laction / qty\l}"];
  stock_alerts [label="{stock_alerts|PK id\lFK product_id\lFK warehouse_id\lFK resolved_by\llevel / status\l}"];
  stock_replenishment_suggestions [label="{stock_replenishment_suggestions|PK id\lFK product_id\lFK warehouse_id\lFK supplier_id\lFK purchase_order_id\lstatus / suggested_qty\l}"];
  purchase_orders [label="{purchase_orders|PK id\lFK supplier_id\lFK warehouse_id\lFK submitted_by\lFK approved_by\lstatus / amount\l}"];
  purchase_order_items [label="{purchase_order_items|PK id\lFK order_id\lFK product_id\lquantity / unit_price\l}"];
  purchase_price_history [label="{purchase_price_history|PK id\lFK product_id\lFK supplier_id\lprice\l}"];
  supplier_performance [label="{supplier_performance|PK id\lFK supplier_id\lon_time_rate\lquality_score\l}"];
  biz_products -> stock_quantities [label="stocked"];
  stock_warehouses -> stock_quantities [label="holds"];
  biz_products -> stock_balances [label="balances"];
  stock_warehouses -> stock_balances [label="balances"];
  biz_products -> stock_movements [label="moves"];
  stock_warehouses -> stock_movements [label="moves"];
  auth_users -> stock_movements [label="creates"];
  biz_products -> stock_logs [label="logs"];
  stock_warehouses -> stock_logs [label="logs"];
  auth_users -> stock_logs [label="operates"];
  biz_products -> stock_alerts [label="alerts"];
  stock_warehouses -> stock_alerts [label="alerts"];
  auth_users -> stock_alerts [label="resolves"];
  stock_alerts -> stock_replenishment_suggestions [label="drives"];
  biz_products -> stock_replenishment_suggestions [label="replenishes"];
  stock_warehouses -> stock_replenishment_suggestions [label="requests"];
  biz_partners -> stock_replenishment_suggestions [label="fulfills"];
  stock_replenishment_suggestions -> purchase_orders [label="converts"];
  biz_partners -> purchase_orders [label="supplier"];
  stock_warehouses -> purchase_orders [label="receives"];
  auth_users -> purchase_orders [label="submit/approve"];
  purchase_orders -> purchase_order_items [label="1:N"];
  biz_products -> purchase_order_items [label="purchased"];
  biz_products -> purchase_price_history [label="priced"];
  biz_partners -> purchase_price_history [label="quoted"];
  biz_partners -> supplier_performance [label="1:1 score"];
}
""",
    },
    {
        "file": "er-sales-finance-stocktake.png",
        "title": "销售履约、财务应收与盘点 ER",
        "description": "该图覆盖销售订单、销售明细、客户信用、应收、收款、对账单、盘点单、盘点明细和盘点历史。它解释了销售发货后如何形成应收，收款如何核销账龄，盘点差异如何回写库存并进入审计。",
        "dot": r"""
digraph er_sales_finance_stocktake {
  graph [rankdir=LR, bgcolor="white", pad="0.32", nodesep="0.55", ranksep="0.85", splines=ortho, fontname="Microsoft YaHei", label="销售履约、财务应收与盘点", labelloc=t, fontsize=22];
  node [shape=record, style="rounded,filled", fillcolor="#f8fafc", color="#91a4b7", fontname="Microsoft YaHei", fontsize=10, margin="0.08,0.05"];
  edge [color="#52697d", arrowsize=0.7, fontname="Microsoft YaHei", fontsize=8];
  auth_users [label="{auth_users|PK id\lseller / cashier / approver\l}"];
  biz_partners [label="{biz_partners|PK id\lpartner_type=customer\lname\lcredit_score\l}"];
  biz_products [label="{biz_products|PK id\lsku / name\lprice / cost\l}"];
  stock_warehouses [label="{stock_warehouses|PK id\lcode / name\l}"];
  trade_orders [label="{trade_orders|PK id\lFK customer_id\lFK seller_id\lstatus / total_amount\l}"];
  trade_order_items [label="{trade_order_items|PK id\lFK order_id\lFK product_id\lqty / unit_price\l}"];
  finance_customer_credit [label="{finance_customer_credit|PK id\lFK customer_id\lFK frozen_by\lcredit_limit / used\lstatus\l}"];
  finance_receivables [label="{finance_receivables|PK id\lFK order_id\lFK customer_id\lamount / paid\ldue_date / status\l}"];
  finance_payments [label="{finance_payments|PK id\lFK receivable_id\lFK customer_id\lFK operator_id\lamount / method\l}"];
  finance_statements [label="{finance_statements|PK id\lFK customer_id\lFK generated_by\lstatement_amount\l}"];
  stock_takes [label="{stock_takes|PK id\lFK warehouse_id\lFK created_by\lFK approved_by\lstatus / type\l}"];
  stock_take_items [label="{stock_take_items|PK id\lFK take_id\lFK product_id\lFK counted_by\lsystem_qty / counted_qty\l}"];
  stock_take_history [label="{stock_take_history|PK id\lFK take_id\lFK operator_id\laction\l}"];
  biz_partners -> trade_orders [label="customer"];
  auth_users -> trade_orders [label="seller"];
  trade_orders -> trade_order_items [label="1:N"];
  biz_products -> trade_order_items [label="sold"];
  biz_partners -> finance_customer_credit [label="1:1 credit"];
  auth_users -> finance_customer_credit [label="freezes"];
  trade_orders -> finance_receivables [label="bills"];
  biz_partners -> finance_receivables [label="owes"];
  finance_receivables -> finance_payments [label="settled by"];
  biz_partners -> finance_payments [label="pays"];
  auth_users -> finance_payments [label="records"];
  biz_partners -> finance_statements [label="statement"];
  auth_users -> finance_statements [label="generates"];
  stock_warehouses -> stock_takes [label="counted"];
  auth_users -> stock_takes [label="create/approve"];
  stock_takes -> stock_take_items [label="contains"];
  biz_products -> stock_take_items [label="counted"];
  auth_users -> stock_take_items [label="counts"];
  stock_takes -> stock_take_history [label="audits"];
  auth_users -> stock_take_history [label="operates"];
}
""",
    },
    {
        "file": "er-workflow-collaboration-ai.png",
        "title": "工作流、协作、报表与 AI ER",
        "description": "该图覆盖流程定义、流程实例、流程任务、流程日志、通知、公告、评论、附件、报表订阅、生成报表、AI 会话、AI 消息、行动草稿、文档分块、后台任务和领域事件。它解释了系统如何把业务动作变成任务、消息、报表、AI 建议和审计证据。",
        "dot": r"""
digraph er_workflow_collaboration_ai {
  graph [rankdir=LR, bgcolor="white", pad="0.32", nodesep="0.55", ranksep="0.85", splines=ortho, fontname="Microsoft YaHei", label="工作流、协作、报表与 AI", labelloc=t, fontsize=22];
  node [shape=record, style="rounded,filled", fillcolor="#f8fafc", color="#91a4b7", fontname="Microsoft YaHei", fontsize=10, margin="0.08,0.05"];
  edge [color="#52697d", arrowsize=0.7, fontname="Microsoft YaHei", fontsize=8];
  auth_users [label="{auth_users|PK id\lactor / owner\l}"];
  workflow_definitions [label="{workflow_definitions|PK id\lcode / version\lsteps_json\l}"];
  workflow_instances [label="{workflow_instances|PK id\lFK definition_id\lFK applicant_id\lbusiness_key / status\l}"];
  workflow_tasks [label="{workflow_tasks|PK id\lFK instance_id\lFK assignee_id\lFK action_by\lstatus / due_at\l}"];
  workflow_logs [label="{workflow_logs|PK id\lFK instance_id\lFK task_id\lFK actor_id\laction / comment\l}"];
  sys_notifications [label="{sys_notifications|PK id\lFK user_id\ltype / category\lrelated_type / status\l}"];
  sys_audit_logs [label="{sys_audit_logs|PK id\lFK user_id\laction / resource\lip / detail\l}"];
  cms_articles [label="{cms_articles|PK id\lFK author_id\ltitle / status\l}"];
  cms_article_comments [label="{cms_article_comments|PK id\lFK article_id\lFK author_id\lFK parent_id\lcontent\l}"];
  cms_attachments [label="{cms_attachments|PK id\lFK uploader_id\lFK article_id\lfile_name\l}"];
  report_subscriptions [label="{report_subscriptions|PK id\lFK user_id\lreport_type / schedule\l}"];
  generated_reports [label="{generated_reports|PK id\lFK subscription_id\lFK generated_by\lreport_type / status\l}"];
  reporting_daily_metrics [label="{reporting_daily_metrics|PK id\lmetric_date\lmetric_key / value\l}"];
  reporting_projection_states [label="{reporting_projection_states|PK id\lprojection_name\lstatus / watermark\l}"];
  sys_ai_sessions [label="{sys_ai_sessions|PK id\lFK user_id\ltitle\l}"];
  sys_ai_messages [label="{sys_ai_messages|PK id\lFK session_id\lrole / content\l}"];
  ai_action_drafts [label="{ai_action_drafts|PK id\lFK created_by\lFK confirmed_by\lFK rejected_by\lstatus / payload\l}"];
  document_chunks [label="{document_chunks|PK id\lsource_type / source_id\lcontent / embedding_ref\l}"];
  background_jobs [label="{background_jobs|PK id\lFK created_by\ljob_type / status\l}"];
  domain_events [label="{domain_events|PK id\laggregate_type / aggregate_id\levent_type / payload\l}"];
  workflow_definitions -> workflow_instances [label="instantiates"];
  auth_users -> workflow_instances [label="applicant"];
  workflow_instances -> workflow_tasks [label="creates"];
  auth_users -> workflow_tasks [label="assignee/action"];
  workflow_instances -> workflow_logs [label="records"];
  workflow_tasks -> workflow_logs [label="logs"];
  auth_users -> workflow_logs [label="writes"];
  auth_users -> sys_notifications [label="receives"];
  auth_users -> sys_audit_logs [label="triggers"];
  auth_users -> cms_articles [label="authors"];
  cms_articles -> cms_article_comments [label="comments"];
  auth_users -> cms_article_comments [label="comments"];
  cms_article_comments -> cms_article_comments [label="replies"];
  cms_articles -> cms_attachments [label="attaches"];
  auth_users -> cms_attachments [label="uploads"];
  auth_users -> report_subscriptions [label="subscribes"];
  report_subscriptions -> generated_reports [label="schedules"];
  auth_users -> generated_reports [label="generates"];
  auth_users -> sys_ai_sessions [label="owns"];
  sys_ai_sessions -> sys_ai_messages [label="contains"];
  auth_users -> ai_action_drafts [label="creates/confirms/rejects"];
  auth_users -> background_jobs [label="starts"];
  domain_events -> background_jobs [label="can trigger"];
  generated_reports -> cms_attachments [label="archives as"];
}
""",
    },
]

CODE_REFERENCE_BLOCKS = [
    ("前端 API 总线", "frontend/src/app/core/api.service.ts", "统一封装 HttpClient、withCredentials、查询参数和 envelope 解包。页面组件不再散落拼接 URL，也不直接处理后端统一响应结构，从而降低每个业务页重复错误处理的概率。"),
    ("认证与会话恢复", "frontend/src/app/core/auth.service.ts, auth.guard.ts, auth.interceptor.ts", "登录结果写入 sessionStorage 和 CSRF 缓存，真正的会话凭据保留在 HttpOnly Cookie 中；刷新页面时 authGuard 会先检查 Cookie hint，再通过 /auth/me 恢复用户，避免误把可恢复会话踢回登录页。"),
    ("主题与偏好", "frontend/src/app/core/theme.service.ts", "主题源被收敛为 dark-cockpit 与 light-luxury 两个实际展示状态，写入 localStorage 与用户偏好；切换后同时更新 html class、data-theme 和 nexus-theme-change 事件，图表与组件可以同步刷新。"),
    ("导航壳层", "frontend/src/app/shell/app-shell.component.ts", "登录后页面统一进入 App Shell。它管理 Dock、顶部栏、搜索防抖、通知轮询、服务健康、路由 loading 和页面滚动复位，避免各页面自己实现一套壳层逻辑。"),
    ("左侧 Dock", "frontend/src/app/shell/app-dock.component.ts, frontend/src/app/core/navigation.ts", "Dock 数据来自统一导航模型，按运营、仓配、供应、履约、财务、分析、协作、安全、个人分组。按钮不再做拉长动画，采用稳定图标、短标签、当前态和文字浮窗。"),
    ("顶部导航", "frontend/src/app/shell/app-topbar.component.ts", "顶部栏合并品牌、面包屑、搜索、服务健康、快捷创建、AI、设置、主题、通知、头像与退出，避免页面上出现多套跳转规则并行。"),
    ("模块操作台", "frontend/src/app/shell/resource-workbench.component.ts, frontend/src/app/core/resource-workflow.ts", "对可 CRUD 的模块提供统一搜索、分页、详情、创建、编辑、删除、导出和领域动作配置。页面上方负责看业务态势，下方负责实际数据操作。"),
    ("后端认证权限", "backend/app/api/auth_routes.py, backend/app/platform/auth/decorators.py, backend/app/platform/policy/policy_engine.py", "后端集中处理登录、注册、CSRF、JWT、权限装饰器、管理员覆盖、资源权限、对象授权和字段过滤，前端展示权限不是最终安全边界。"),
    ("通用 CRUD", "backend/app/api/generic_crud_routes.py, backend/app/platform/crud/*", "资源注册表统一接入列表、详情、搜索、创建、更新、删除、分页和审计。新增资源时优先注册资源配置，而不是复制一组相似接口。"),
    ("完整库启动", "backend/scripts/bootstrap_sqlite.py", "CloudRun 启动时读取 backend/.env，下载完整 SQLite 压缩库，解压到 /tmp/nexus-prime，执行写锁测试、pragma quick_check 和最小数据量断言，防止空库误上线。"),
    ("腾讯云发布脚本", "deploy/tencent-cloudbase-auto-deploy.ps1", "脚本负责准备后端 CloudRun 源码、写入生产环境变量、构建前端、上传静态托管路径，并支持完整库引导参数与唯一版本后缀。"),
]

UPGRADE_FOCUS = [
    ("导航逻辑统一", "原来左侧 Dock、省略号、页面顶部卡片和页面内部跳转并行存在，用户会被迫在多套规则之间猜测入口。本轮把 `/app/**` 全部纳入 `navigation.ts` 和 App Shell，Dock 是一级业务流程，顶部栏是当前位置、搜索和全局动作，模块操作台是当前资源的增删查改。"),
    ("Dock 交互收敛", "Dock 删除按钮拉长动画，不再让按钮 hover 后挤占空间；所有入口按业务域分组展示，一行一个稳定按钮，图标、短标签、当前态和浮窗名称共同表达含义。这样既保留文字说明，也避免动画导致布局跳动。"),
    ("顶部栏合并", "顶部栏从零散按钮升级为统一控制面。搜索栏负责跨物料、订单、客户、报表的命令搜索；头像区域只承担个人工作台和退出；主题切换只保留深色和亮色两个可理解状态；服务健康、通知和快捷创建都放在同一层级。"),
    ("页面结构统一", "每个业务页面都遵循“真实图/关键图表在上，交互报表在中，表格、表单、分页和 CRUD 在下”的布局。运营页的设计理念被推广到库存、采购、销售、财务、AI、个人页和设置页，减少孤立方框和未利用空白。"),
    ("空间利用优化", "大面积空白区域不再放无意义卡片，而是放交互报表、执行队列、图表说明、分页表格和当前模块操作台。每页控制长度，信息分层清晰，避免上下页显示不全和底部操作台被挤出视口。"),
    ("数据与部署兜底", "云端不再使用小型演示库，而是上传本地完整库。启动脚本会验证用户数和销售订单数，避免迁移空库后前端看起来正常但数据缺失。报告也把云端数据量列出，便于验收。"),
]

DOMAIN_NARRATIVES = {
    "operations": "运营域强调经营指标、任务异常、产能和设备状态，目标是把管理者每天先看的信息放在同一层。页面不再用零散跳转块，而是以态势图、风险队列和执行列表组织。",
    "warehouse": "仓配域围绕物料、库存、仓库、库位、扫码和盘点。上方看库存真实场景和流向，中间看交互报表，下方用统一操作台处理库存变动、分页和记录检查。",
    "supply": "供应域连接补货建议、采购订单、供应商绩效和质量检验。核心逻辑是从低库存到采购、从采购到收货、从收货结果到供应商评分。",
    "fulfillment": "履约域连接客户、销售订单、仓配调度和售后服务。页面重点不是孤立订单表，而是展示客户价值、履约阶段、发货动作和服务闭环。",
    "finance": "财务域覆盖应收、信用、合同和预算成本。它用账龄、额度、回款和成本偏差表达经营风险，让财务动作能回到订单、客户和合同。",
    "insight": "分析域覆盖报表、规则、数据质量、集成和 AI。它把系统状态、数据可信度和经营建议放到一套分析流程里。",
    "collaboration": "协作域覆盖通知、文件、公告和服务工单。它让业务结果能形成消息、资料、知识和后续动作，而不是停留在单页操作。",
    "security": "安全域覆盖用户、权限、审计和集成边界。核心是让谁做了什么、能做什么、何时做的都有清晰证据。",
    "personal": "个人域覆盖个人资料、头像、偏好、默认工作台和控制中心。它把用户自己的工作环境整理为可维护的独立区域。",
}

PAGE_CODE_AREAS = {
    "/app/overview": "AppShell + command-center.page.ts + operations APIs",
    "/app/metrics": "executive-metrics.page.ts + analytics/executive",
    "/app/tasks": "operations-tasks.page.ts + operations/todo + notifications",
    "/app/inventory/products": "ResourceWorkbench + products 资源配置 + materials.page.ts",
    "/app/inventory/stock": "ResourceWorkbench + inventory/adjust + warehouse-flow.page.ts",
    "/app/inventory/replenishment": "ResourceWorkbench + replenishment-suggestions + replenishment.page.ts",
    "/app/sales/orders": "ResourceWorkbench + sales/orders transition + fulfillment.page.ts",
    "/app/procurement/orders": "ResourceWorkbench + procurement workflow + procurement.page.ts",
    "/app/suppliers/performance": "supplier-performance.page.ts + supplier_performance 模型",
    "/app/dispatch": "dispatch-center.page.ts + operations/dispatch",
    "/app/data-quality": "data-quality.page.ts + data quality jobs",
    "/app/quality": "quality-inspection.page.ts + operations/quality-inspection",
    "/app/customers": "ResourceWorkbench + partners 资源配置 + customer-operations.page.ts",
    "/app/capacity": "capacity-planning.page.ts + operations/capacity",
    "/app/maintenance": "maintenance.page.ts + operations/maintenance",
    "/app/contracts": "contract-collection.page.ts + finance/receivables",
    "/app/service": "service-workorders.page.ts + operations/service",
    "/app/rules": "rules-engine.page.ts + rules/notifications/report-subscriptions",
    "/app/integrations": "integration-monitor.page.ts + background_jobs + domain_events",
    "/app/budget": "budget-cost.page.ts + operations/costs",
    "/app/mobile-terminal": "mobile-terminal.page.ts + operations/mobile-terminal",
    "/app/finance/receivables": "ResourceWorkbench + receivables + payment action",
    "/app/finance/credits": "ResourceWorkbench + credits + freeze/unfreeze action",
    "/app/stocktakes": "ResourceWorkbench + stocktakes + stocktake actions",
    "/app/reports": "ResourceWorkbench + generated-reports + reports/generate",
    "/app/files": "ResourceWorkbench + files/download/upload",
    "/app/content/articles": "ResourceWorkbench + articles/comments/attachments",
    "/app/system/users": "ResourceWorkbench + users/roles/permissions",
    "/app/system/audit": "ResourceWorkbench + audit-logs",
    "/app/notifications": "ResourceWorkbench + notifications/mark-read",
    "/app/ai": "ResourceWorkbench + ai/chat + ai/analyze/structured",
    "/app/profile": "profile.page.ts + me/profile + me/preferences",
    "/app/settings": "settings.page.ts + health + preferences + theme",
}

def tex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def route_slug(route: str) -> str:
    return route.strip("/").replace("app/", "").replace("/", "-")


def load_pages():
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    desktop = {
        item["route"]: item
        for item in items
        if item["viewport"] == "desktop" and item["theme"] == "light-luxury" and item["route"].startswith("/app/")
    }
    mobile = {
        item["route"]: item
        for item in items
        if item["viewport"] == "mobile" and item["theme"] == "light-luxury" and item["route"].startswith("/app/")
    }
    pages = []
    pages_dir = MANIFEST.parent
    for idx, route in enumerate(PAGE_ORDER, start=1):
        item = desktop[route].copy()
        slug = route_slug(route)
        dark_file = f"pages/desktop-dark-cockpit-{slug}.png"
        light_file = item["file"]
        use_dark = idx % 2 == 1 and (pages_dir / f"desktop-dark-cockpit-{slug}.png").exists()
        item["desktop_file"] = dark_file if use_dark else light_file
        item["desktop_theme"] = "dark-cockpit" if use_dark else "light-luxury"
        item["desktop_theme_label"] = "深色驾驶舱" if use_dark else "亮色系统"
        item["mobile_file"] = mobile.get(route, {}).get("file", "")
        item["code_area"] = PAGE_CODE_AREAS.get(route, "Angular page component + Flask API resource")
        item["domain_note"] = DOMAIN_NARRATIVES.get(navigation_group_for_route(route), "该页面纳入统一业务工作台，按统一导航、图表和操作台规则组织。")
        pages.append(item)
    return pages


def navigation_group_for_route(route: str) -> str:
    if route in {"/app/overview", "/app/metrics", "/app/tasks", "/app/capacity", "/app/maintenance"}:
        return "operations"
    if route in {"/app/inventory/products", "/app/inventory/stock", "/app/dispatch", "/app/mobile-terminal", "/app/stocktakes"}:
        return "warehouse"
    if route in {"/app/inventory/replenishment", "/app/procurement/orders", "/app/suppliers/performance", "/app/quality"}:
        return "supply"
    if route in {"/app/sales/orders", "/app/customers", "/app/service"}:
        return "fulfillment"
    if route in {"/app/finance/receivables", "/app/finance/credits", "/app/contracts", "/app/budget"}:
        return "finance"
    if route in {"/app/reports", "/app/ai", "/app/rules", "/app/integrations", "/app/data-quality"}:
        return "insight"
    if route in {"/app/files", "/app/content/articles", "/app/notifications"}:
        return "collaboration"
    if route in {"/app/system/users", "/app/system/audit"}:
        return "security"
    return "personal"


def generate_er_diagrams() -> None:
    final_dir = DOCS / "images" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    dot = shutil.which("dot") or r"C:\Program Files\Graphviz\bin\dot.exe"
    if not Path(dot).exists() and shutil.which("dot") is None:
        print("Graphviz dot not found; ER domain diagrams will be skipped")
        return
    for diagram in ER_DIAGRAMS:
        dot_path = final_dir / diagram["file"].replace(".png", ".dot")
        png_path = final_dir / diagram["file"]
        dot_path.write_text(textwrap.dedent(diagram["dot"]).strip() + "\n", encoding="utf-8")
        subprocess.run([dot, "-Tpng", str(dot_path), "-o", str(png_path)], check=True)


def md_entry_section() -> list[str]:
    lines = [
        "## 5. 公共入口页面（暗色主题截图，源码未改）",
        "",
        "首页、登录页、注册页和注册协议页严格保持原样。本报告只在截图阶段设置暗色主题偏好，用来满足入口流程统一暗色展示要求；这不是源码改动。",
        "",
    ]
    for title, image, description in ENTRY_SCREENSHOTS:
        lines += [f"### {title}", "", f"![{title}]({image})", "", description, ""]
    return lines


def md_report(pages):
    lines = [
        "# NEXUS Prime 制造业 ERP 全量交付报告",
        "",
        "报告日期：2026-06-29",
        "",
        "## 0. 线上地址和演示账号",
        "",
        f"- 前端可分享地址：`{FRONTEND_URL}`",
        f"- 后端 API Base：`{API_BASE}`",
        f"- 完整数据库压缩资产：`{DB_ASSET_URL}`",
        "- 管理员账号：`admin@nexus.com / admin123`",
        "- 普通演示账号：`user00001@nexus.com / password123`，本地完整库还包含 `user00002` 到 `user15000` 等批量用户。",
        "",
        "本次云端部署已经不再使用小型演示库，而是上传并引导启动本地完整 SQLite 数据库。完整库原始大小约 244MB，压缩后约 46MB，先上传到 CloudBase 静态托管，再由 CloudRun 启动脚本下载、解压、校验并作为运行数据库。",
        "",
        "云端验证结果：管理员和普通用户登录均返回 HTTP 200；完整数据诊断显示用户、商品、伙伴、销售订单、采购订单、库存、应收和报表均为本地完整库规模。",
        "",
        "## 1. 完整数据规模",
        "",
        "| 表 | 含义 | 云端数量 |",
        "| --- | --- | ---: |",
    ]
    for table, label, count in DATA_COUNTS:
        lines.append(f"| `{table}` | {label} | {count} |")

    lines += [
        "",
        "## 2. 架构设计",
        "",
        "系统采用 Angular 21 SPA + Flask REST API + SQLAlchemy/Alembic 的前后端分离架构。首页、登录页和注册页保持原样；登录后的 `/app/**` 业务区统一进入 App Shell，由左侧 Dock、顶部导航、模块面板和页面工作台共同管理。",
        "",
        "后端仍采用模块化单体部署，目的是让课程演示和腾讯云 CloudBase 上线更稳定；代码内部已经按身份、库存、采购、销售、财务、工作流、报表、内容、文件和 AI 划分领域，后续可以把库存、财务、AI、文件拆为独立服务。",
        "",
        "```text",
        "CloudBase Static Hosting",
        "  Angular SPA / runtime-config.js",
        "        | HTTPS + Cookie + CSRF",
        "CloudBase CloudRun",
        "  Flask /api/v1 / Auth / Policy / Audit / Domain Services",
        "        | SQLAlchemy",
        "SQLite full demo DB bootstrapped from CloudBase asset",
        "```",
        "",
        "## 3. ER 图和数据模型",
        "",
        "![完整 ER 图](images/final/er-diagram.png)",
        "",
        "数据库按业务领域拆分为身份权限、主数据、库存仓配、采购、销售履约、财务应收、盘点、工作流、内容文件、报表分析、通知审计、AI 会话和异步事件。关键关系包括：商品和仓库通过库存数量表关联；销售订单形成应收账款；应收账款通过收款记录核销；补货建议可转为采购订单；采购订单和销售订单都关联明细；用户动作写入审计日志。",
        "",
    ]
    for diagram in ER_DIAGRAMS:
        lines += [
            f"### {diagram['title']}",
            "",
            f"![{diagram['title']}](images/final/{diagram['file']})",
            "",
            diagram["description"],
            "",
        ]
    lines += [
        "## 4. 前端升级思路",
        "",
    ]
    for title, body in UPGRADE_FOCUS:
        lines += [f"- **{title}**：{body}"]
    lines += [""] + md_entry_section()
    lines += [
        "## 6. 全部业务页面截图和功能说明（暗色/亮色交替）",
        "",
        "业务页按顺序使用深色驾驶舱与亮色系统交替截图。这样报告既能展示两套主题，也能证明页面结构在不同对比条件下都能保持可读。",
        "",
    ]

    for index, page in enumerate(pages, start=1):
        detail = PAGE_DETAILS[page["route"]]
        lines += [
            f"### {index}. {page['title']}",
            "",
            f"- 路由：`{page['route']}`",
            f"- 桌面截图：`docs/images/final/{page['desktop_file']}`（{page['desktop_theme_label']}）",
            f"- 移动截图：`docs/images/final/{page['mobile_file']}`",
            f"- 页面定位：{detail['purpose']}",
            f"- 主要数据：{detail['data']}",
            f"- 主要接口：`{detail['apis']}`",
            f"- 代码关联：`{page['code_area']}`",
            "",
            f"![{page['title']}](images/final/{page['desktop_file']})",
            "",
            "功能点：",
        ]
        for fn in detail["functions"]:
            lines.append(f"- {fn}")
        lines += [
            "",
            f"升级说明：{page['domain_note']}本页按照“上方真实图和关键图表、中部交互报表、下方表单和分页操作台”的原则组织，避免无意义跳转方框和页面内多套入口竞争。",
            "",
        ]

    lines += [
        "## 7. 核心代码讲解",
        "",
    ]
    for title, files, body in CODE_REFERENCE_BLOCKS:
        lines += [f"- **{title}**：`{files}`。{body}"]
    lines += [
        "",
        "## 8. 部署流程",
        "",
        "1. 本地确认完整库位于 `backend/instance/nexus_prime.db`。",
        "2. 压缩为 `nexus_prime_full_06292108.db.gz`，上传到 CloudBase 静态托管 `nexus-data/` 目录。",
        "3. 后端部署时设置 `DATABASE_URL=sqlite:////tmp/nexus-prime/nexus_prime.db`、`NEXUS_DB_BOOTSTRAP_URL`、`NEXUS_DB_BOOTSTRAP_FORCE=true`、`NEXUS_DB_BOOTSTRAP_MIN_USERS=15000`、`NEXUS_DB_BOOTSTRAP_MIN_ORDERS=100000`。",
        "4. CloudRun 容器启动时先运行 `python scripts/bootstrap_sqlite.py`，确认完整数据后再执行 `flask db upgrade` 和 `gunicorn`。",
        "5. 前端构建时写入 `NEXUS_API_BASE_URL`，部署到 CloudBase 静态托管唯一路径。",
        "6. 用健康检查、登录接口和数据计数确认线上不是空库。",
        "",
        "## 9. 交付结论",
        "",
        "NEXUS Prime 已经完成从旧 Flask 单体页面到前后端分离 ERP 工作台的升级。云端使用完整本地演示数据库，包含 15001 个用户和完整业务数据；报告、ER 图、截图、代码说明、架构说明、升级思路、部署过程和视频讲稿均已补齐。",
        "",
    ]
    return "\n".join(lines)


def tex_report(pages):
    header = r"""\documentclass[UTF8,zihao=-4]{ctexart}
\usepackage[a4paper,margin=1.85cm,headheight=26pt]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{tabularx}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{array}
\usepackage{float}
\usepackage{caption}
\usepackage{multicol}
\graphicspath{{docs/}}
\definecolor{nexusInk}{HTML}{172033}
\definecolor{nexusMuted}{HTML}{64748B}
\definecolor{nexusTeal}{HTML}{0F766E}
\definecolor{nexusGold}{HTML}{9A6A18}
\definecolor{nexusLine}{HTML}{CBD5E1}
\definecolor{nexusPanel}{HTML}{F7F9FB}
\hypersetup{colorlinks=true,linkcolor=nexusTeal,urlcolor=nexusTeal}
\pagestyle{fancy}
\fancyhf{}
\lhead{\textcolor{nexusMuted}{NEXUS Prime 制造业 ERP}}
\rhead{\textcolor{nexusMuted}{全量交付报告}}
\cfoot{\textcolor{nexusMuted}{\thepage}}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{nexusLine}\leaders\hrule height \headrulewidth\hfill}}
\titleformat{\section}{\Large\bfseries\color{nexusInk}}{\thesection}{0.7em}{}[\vspace{0.15em}{\color{nexusTeal}\titlerule[0.8pt]}]
\titleformat{\subsection}{\large\bfseries\color{nexusInk}}{\thesubsection}{0.7em}{}
\setlist[itemize]{leftmargin=2em,itemsep=0.18em,topsep=0.25em}
\renewcommand{\arraystretch}{1.2}
\emergencystretch=5em
\sloppy
\newcommand{\code}[1]{{\small\url{#1}}}
\newcommand{\tightpara}[1]{{\small #1\par}}
\begin{document}
"""
    parts = [header]
    parts.append(r"""\begin{titlepage}
  \centering
  \vspace*{1.1cm}
  {\Huge\bfseries\color{nexusInk} NEXUS Prime\par}
  \vspace{0.3cm}
  {\Large\bfseries\color{nexusTeal} 制造业经营管理 ERP 全量交付报告\par}
  \vspace{0.45cm}
  {\large Angular 21 + Flask REST API + SQLAlchemy + Tencent CloudBase\par}
  \vfill
  \begin{tabularx}{0.96\textwidth}{>{\bfseries}lX}
    前端地址 & \code{""" + FRONTEND_URL + r"""} \\
    后端 API & \code{""" + API_BASE + r"""} \\
    完整数据资产 & \code{""" + DB_ASSET_URL + r"""} \\
    演示账号 & \code{admin@nexus.com / admin123}; \code{user00001@nexus.com / password123} \\
    报告日期 & 2026-06-29 \\
  \end{tabularx}
  \vfill
  \includegraphics[width=0.92\textwidth,height=0.46\textheight,keepaspectratio]{images/final/pages/desktop-dark-cockpit-overview.png}
  \vfill
\end{titlepage}
\tableofcontents
\clearpage
""")

    parts.append(r"""\section{线上部署和完整数据}
\begin{longtable}{p{0.24\textwidth}p{0.66\textwidth}}
\toprule
项目 & 结果 \\
\midrule
\endhead
前端可分享地址 & \code{""" + FRONTEND_URL + r"""} \\
后端 API Base & \code{""" + API_BASE + r"""} \\
CloudBase 环境 & \code{constantine-d3gjhwmtz0336c36a} \\
后端服务 & \code{nexus-api-fulldata-06292135-44aed6a} \\
完整库资产 & \code{""" + DB_ASSET_URL + r"""} \\
管理员登录 & \code{admin@nexus.com / admin123}, HTTP 200 \\
普通用户登录 & \code{user00001@nexus.com / password123}, HTTP 200 \\
\bottomrule
\end{longtable}

本次上线已经使用完整本地演示数据库，不再使用小型演示库。完整 SQLite 原始文件约 244MB，压缩后约 46MB。部署过程先把压缩库上传到 CloudBase 静态托管，再由 CloudRun 启动脚本下载、解压、写锁验证、quick check 校验和最小数据量断言，最后再启动 Flask API。

\begingroup
\small
\renewcommand{\arraystretch}{1.08}
\begin{tabularx}{\textwidth}{p{0.34\textwidth}r p{0.34\textwidth}r}
\toprule
表和含义 & 云端数量 & 表和含义 & 云端数量 \\
\midrule
""")
    for index in range(0, len(DATA_COUNTS), 2):
        left_table, left_label, left_count = DATA_COUNTS[index]
        left_cell = f"\\code{{{left_table}}}\\newline {{\\footnotesize {tex_escape(left_label)}}}"
        if index + 1 < len(DATA_COUNTS):
            right_table, right_label, right_count = DATA_COUNTS[index + 1]
            right_cell = f"\\code{{{right_table}}}\\newline {{\\footnotesize {tex_escape(right_label)}}}"
            parts.append(f"{left_cell} & {left_count} & {right_cell} & {right_count} \\\\\n")
        else:
            parts.append(f"{left_cell} & {left_count} & & \\\\\n")
    parts.append(r"""\bottomrule
\end{tabularx}
\endgroup

\vspace{0.5em}
\begin{tabularx}{\textwidth}{>{\bfseries}p{0.18\textwidth}X}
\toprule
验证维度 & 证据 \\
\midrule
服务健康 & \code{/api/v1/health/ready} 返回 HTTP 200，说明 CloudRun 服务和运行数据库可访问。 \\
登录链路 & 管理员和普通用户账号均已登录成功，说明 Cookie、CSRF、跨域和用户恢复链路可用。 \\
完整数据 & 诊断接口返回 15001 个用户、100803 张销售订单和完整库存、采购、财务、报表数据，证明线上不是空库。 \\
启动保护 & \code{bootstrap_sqlite.py} 下载压缩库后执行写锁测试、\code{pragma quick_check} 和最小数据量断言，避免空库误上线。 \\
前端配置 & 前端构建写入线上 API Base，CloudBase 静态托管页面直接请求 CloudRun API，不再依赖本地地址。 \\
分享交付 & 前端地址、后端 API、完整数据库资产和演示账号都放在报告首页，方便评审直接访问。 \\
\bottomrule
\end{tabularx}
\vspace{0.65em}
\begin{tabularx}{\textwidth}{>{\bfseries}p{0.18\textwidth}X}
\toprule
验收结论 & 说明 \\
\midrule
数据完整 & 用户、商品、伙伴、销售、采购、库存、财务、通知、审计、文章和报表都达到完整库规模。 \\
链路闭合 & 首页进入登录，登录后进入 \code{/app/**}，再由 Dock、顶部栏和资源操作台管理全部业务入口。 \\
可演示性 & 管理员账号用于系统、权限、审计和全局数据演示；普通账号用于常规业务角色演示。 \\
可追溯性 & 后端权限、审计日志、资源注册表和部署诊断共同支撑课程验收时的问题回溯。 \\
不改入口 & 首页、登录页、注册页只在报告里使用暗色截图，源码保持原样，避免入口视觉被额外改动影响验收。 \\
\bottomrule
\end{tabularx}

这一页的结论是：云端不是“能跑起来”的空壳，而是带着完整本地数据、完整认证链路和完整业务入口一起上线。对于评审来说，先看这页就能确认三个最关键的东西：系统可访问、数据完整、入口未被改坏。
\vspace{0.35em}
\clearpage
""")

    parts.append(r"""\section{架构设计和升级思路}
系统采用 Angular 21 SPA + Flask REST API + SQLAlchemy/Alembic 的前后端分离架构。首页、登录页和注册页保持原样，登录后的 \code{/app/**} 业务区统一进入 App Shell。

\begin{verbatim}
CloudBase Static Hosting
  Angular SPA / runtime-config.js
        | HTTPS + HttpOnly Cookie + CSRF
CloudBase CloudRun
  Flask /api/v1 / Auth / Policy / Audit / Domain Services
        | SQLAlchemy
SQLite full demo DB bootstrapped from CloudBase asset
\end{verbatim}

升级重点是把零散页面整理为一套 ERP 工作台。Dock 不再拉长，顶部栏统一搜索、面包屑、状态、主题、通知和头像。页面结构统一为上方真实图和关键图表，中部交互报表，下方表格、表单、增删查改和分页。大量无意义小方框被改成摘要、图表、表格和执行队列。

\begingroup
\small
\renewcommand{\arraystretch}{1.06}
\begin{tabularx}{\textwidth}{p{0.2\textwidth}X}
\toprule
升级重点 & 说明 \\
\midrule
""")
    for title, body in UPGRADE_FOCUS:
        parts.append(f"{tex_escape(title)} & {tex_escape(body)} \\\\\n")
    parts.append(r"""\bottomrule
\end{tabularx}
\endgroup

\vspace{0.55em}
这些升级共同解决三个问题：第一，路由入口只服从 Dock、顶部搜索和当前资源操作台三层结构；第二，页面视觉不再用大量孤立方框堆叠，而是把真实图、图表、表格和表单放到稳定位置；第三，数据和权限由后端兜底，前端负责把业务动作讲清楚，避免页面看起来能跳、实际上没有业务闭环。
\clearpage

\section{代码结构总览}
下面按运行链路说明关键代码。这里不是简单列文件名，而是说明为什么这些文件能支撑本次导航、主题、页面布局、资源操作台和云端完整数据上线。

\begin{longtable}{p{0.2\textwidth}p{0.28\textwidth}p{0.44\textwidth}}
\toprule
主题 & 文件 & 设计说明 \\
\midrule
\endhead
""")
    for title, files, body in CODE_REFERENCE_BLOCKS:
        parts.append(f"{tex_escape(title)} & \\code{{{tex_escape(files)}}} & {tex_escape(body)} \\\\\n")
    parts.append(r"""\bottomrule
\end{longtable}
\clearpage

\section{组件职责矩阵}
这一页把运行链路拆成组件职责。它对应用户最关心的“为什么页面不会再乱跳”：入口保护、API、Shell、Dock、顶栏、资源操作台、后端授权和完整库启动各自只负责一层，页面组件不再重复实现导航和 CRUD 规则。

\begin{tabularx}{\textwidth}{p{0.2\textwidth}p{0.3\textwidth}X}
\toprule
层级 & 文件或组件 & 职责 \\
\midrule
运行配置 & \code{runtime-config.js} & 前端读取线上 API Base，不把敏感变量放到浏览器。 \\
认证守卫 & \code{auth.guard.ts} & 保护登录后路由，刷新时恢复 Cookie 会话。 \\
API 服务 & \code{api.service.ts} & 统一 withCredentials、路径、envelope 解包和错误处理。 \\
App Shell & \code{app-shell.component.ts} & 登录后壳层、搜索、通知、模块状态和页面容器。 \\
Dock & \code{app-dock.component.ts} & 统一核心流程入口，删除按钮拉长动画。 \\
顶栏 & \code{app-topbar.component.ts} & 搜索、主题、通知、头像和面包屑。 \\
后端认证 & \code{auth_routes.py}, \code{decorators.py} & 登录、CSRF、JWT、权限装饰器。 \\
策略引擎 & \code{policy_engine.py} & 管理员、权限、对象和字段级授权。 \\
完整库启动 & \code{bootstrap_sqlite.py} & 下载、解压、写锁、quick check 和数据量断言。 \\
\bottomrule
\end{tabularx}

\vspace{0.7em}
\begin{tabularx}{\textwidth}{>{\bfseries}p{0.2\textwidth}X}
\toprule
约束 & 落地方式 \\
\midrule
入口不改 & 首页、登录页、注册页源码保持不变，报告只使用暗色截图说明入口流程。 \\
跳转归一 & \code{navigation.ts} 作为 Dock、面包屑、当前模块和跳转关系的唯一业务地图。 \\
操作归一 & \code{resource-workbench.component.ts} 统一承载搜索、分页、表单、删除、导出和领域动作。 \\
视觉归一 & 页面上方展示真实图与关键图表，中部放交互报表，下方放 CRUD 操作台。 \\
数据兜底 & \code{bootstrap_sqlite.py} 校验完整数据规模，防止空库或裁剪库误上线。 \\
\bottomrule
\end{tabularx}
\clearpage
""")

    parts.append(r"""\section{完整 ER 图和数据模型}
\begin{figure}[H]
  \centering
  \includegraphics[width=\textwidth,height=0.72\textheight,keepaspectratio]{images/final/er-diagram.png}
  \caption{完整 ER 图}
\end{figure}
数据库按领域划分为身份权限、主数据、库存仓配、采购、销售履约、财务应收、盘点、工作流、内容文件、报表分析、通知审计、AI 会话和异步事件。关键关系包括：商品和仓库通过库存数量表关联；销售订单形成应收账款；应收账款通过收款记录核销；补货建议可转采购单；采购单、销售单和盘点单都有关联明细；用户动作进入审计日志。

\begin{tabularx}{\textwidth}{>{\bfseries}p{0.2\textwidth}X}
\toprule
领域 & ER 覆盖说明 \\
\midrule
身份权限 & 用户、角色、权限和部门决定谁能进入系统、看到哪些模块、执行哪些动作。 \\
主数据 & 商品、分类、标签、客户和供应商是采购、库存、销售、财务共同引用的事实源。 \\
库存采购 & 仓库、库存数量、库存流水、预警、补货建议和采购订单形成补货闭环。 \\
销售财务 & 客户、销售订单、订单明细、应收、收款、信用和合同形成履约回款闭环。 \\
工作流协作 & 流程实例、任务、日志、通知、文章、附件和报表把业务结果沉淀为协作证据。 \\
AI 分析 & AI 会话、消息、文档分块和行动草稿支撑经营问答、结构化诊断和后续执行。 \\
\bottomrule
\end{tabularx}
\clearpage
""")
    for diagram in ER_DIAGRAMS:
        parts.append(f"\\section{{{tex_escape(diagram['title'])}}}\n")
        parts.append("\\begin{figure}[H]\n  \\centering\n")
        parts.append(f"  \\includegraphics[width=\\textwidth,height=0.66\\textheight,keepaspectratio]{{images/final/{diagram['file']}}}\n")
        parts.append(f"  \\caption{{{tex_escape(diagram['title'])}}}\n\\end{{figure}}\n")
        parts.append(f"{tex_escape(diagram['description'])}\n\n")
        parts.append("这张分域图用于弥补全局 ER 图信息密度过高的问题。全局图负责展示系统全貌，分域图负责在课程讲解时逐个解释表、外键和业务闭环。\n\\clearpage\n")

    parts.append(r"""\section{公共入口页面}
本轮严格遵守约束：首页、登录页、注册页和注册协议页不修改。报告只展示它们在系统流程中的位置，并使用暗色主题截图作为交付材料。
""")
    for title, image, description in ENTRY_SCREENSHOTS:
        parts.append("\\begin{figure}[H]\n  \\centering\n")
        parts.append(f"  \\includegraphics[width=\\textwidth,height=0.205\\textheight,keepaspectratio]{{{image}}}\n")
        parts.append(f"  \\caption{{{tex_escape(title)}，暗色主题截图，源码未修改}}\n\\end{{figure}}\n")
        parts.append(f"\\tightpara{{{tex_escape(description)}}}\n")
    parts.append(r"""
\clearpage
""")

    parts.append(r"""\section{全部业务页面截图和功能说明}
以下章节从登录后运营首页开始，逐页说明所有业务页面。业务页按顺序使用深色驾驶舱和亮色系统交替截图，既展示主题能力，也展示统一布局在不同背景下的稳定性。每个页面都列出路由、截图、定位、主要功能、数据来源、接口范围、代码关联和升级效果。
""")
    parts.append(r"""\begin{longtable}{p{0.06\textwidth}p{0.2\textwidth}p{0.31\textwidth}p{0.14\textwidth}p{0.19\textwidth}}
\toprule
序号 & 页面 & 路由 & 主题 & 业务域 \\
\midrule
\endhead
""")
    for idx, page in enumerate(pages, start=1):
        detail = PAGE_DETAILS[page["route"]]
        parts.append(
            f"{idx} & {tex_escape(page['title'])} & \\code{{{page['route']}}} & "
            f"{tex_escape(page['desktop_theme_label'])} & {tex_escape(detail['data'].split('、')[0])} \\\\\n"
        )
    parts.append(r"""\bottomrule
\end{longtable}

上表先给出完整页面地图，后续每页再展开截图、功能、数据、接口和代码关联。这样报告从入口、ER、架构到所有业务页面是一条连续链路，而不是零散截图集合。
""")
    for idx, page in enumerate(pages, start=1):
        detail = PAGE_DETAILS[page["route"]]
        parts.append("\\clearpage\n")
        parts.append(f"\\subsection{{{idx}. {tex_escape(page['title'])}}}\n")
        parts.append("\\begin{figure}[H]\n  \\centering\n")
        parts.append(f"  \\includegraphics[width=\\textwidth,height=0.38\\textheight,keepaspectratio]{{images/final/{page['desktop_file']}}}\n")
        parts.append(f"  \\caption{{{tex_escape(page['title'])}桌面截图，{tex_escape(page['desktop_theme_label'])}}}\n\\end{{figure}}\n")
        parts.append("\\begin{tabularx}{\\textwidth}{>{\\bfseries}p{0.16\\textwidth}X>{\\bfseries}p{0.16\\textwidth}X}\n\\toprule\n")
        parts.append(f"路由 & \\code{{{page['route']}}} & 展示主题 & {tex_escape(page['desktop_theme_label'])} \\\\\n")
        parts.append(f"主要数据 & {tex_escape(detail['data'])} & 主要接口 & \\code{{{detail['apis']}}} \\\\\n")
        parts.append(f"代码关联 & \\multicolumn{{3}}{{p{{0.7\\textwidth}}}}{{\\small {tex_escape(page['code_area'])}}} \\\\\n")
        parts.append("\\bottomrule\n\\end{tabularx}\n\\vspace{0.5em}\n")
        parts.append(f"\\tightpara{{\\textbf{{页面定位：}}{tex_escape(detail['purpose'])}}}\n")
        parts.append(f"\\tightpara{{\\textbf{{升级效果：}}{tex_escape(page['domain_note'])}本页按照“真实图和关键图表在上、交互报表在中、表单和分页操作台在下”的规则整理，减少无意义跳转方框，让业务动作和数据对象保持同一条线。}}\n")
        parts.append("\\begin{multicols}{2}\n\\textbf{主要功能}\n\\begin{itemize}\n")
        for fn in detail["functions"]:
            parts.append(f"  \\item {tex_escape(fn)}\n")
        parts.append("\\end{itemize}\n\\columnbreak\n\\textbf{验收关注}\n\\begin{itemize}\n")
        parts.append("  \\item 上方区域优先展示真实图、态势图和关键指标，不再堆叠重复入口。\n")
        parts.append("  \\item 下方操作台承担搜索、分页、创建、编辑、删除、导出和领域动作。\n")
        parts.append("  \\item 页面跳转由 Dock、顶部搜索和资源操作台统一管理，避免随机跳转。\n")
        parts.append("\\end{itemize}\n\\end{multicols}\n")

    parts.append(r"""\clearpage
\section{核心代码详解}
\subsection{前端 API 和会话}
\code{frontend/src/app/core/api.service.ts} 统一封装 \code{HttpClient}。所有请求带 \code{withCredentials: true}，浏览器自动携带 HttpOnly Cookie，页面只关心业务数据。返回值通过 envelope 解包，减少重复样板代码。查询参数统一过滤空值，列表页、搜索页和资源操作台不用重复判断 \code{undefined}、\code{null} 和空字符串。

\code{frontend/src/app/core/auth.service.ts} 保存当前用户和权限摘要，登录后写入 CSRF token，刷新后通过 \code{auth.guard.ts} 保护 \code{/app/**}。如果 Cookie 仍有效，会调用 \code{/auth/me} 恢复会话；没有登录态才跳回登录页。\code{auth.interceptor.ts} 对写操作附加 \code{X-CSRF-Token}，并把 401、403、500 等错误统一转成页面消息。

\subsection{Shell、Dock 和顶部导航}
\code{app-shell.component.ts} 承担登录后壳层职责，包括搜索防抖、通知轮询、服务健康、模块状态、路由 loading、页面滚动复位和页面容器。\code{navigation.ts} 把所有 \code{/app/**} 路由映射到统一 Dock 分组、当前项、兄弟项和面包屑。\code{app-dock.component.ts} 是左侧核心流程入口，按钮不再拉长，只保留稳定图标、当前状态、短标签和文字浮窗。\code{app-topbar.component.ts} 合并搜索、面包屑、服务状态、快捷创建、AI、主题按钮、通知、头像和退出。

\subsection{资源操作台}
\code{resource-workflow.ts} 把物料、仓配、补货、采购、销售、客户、应收、信用、盘点、报表、文件、内容、通知、用户、审计和 AI 会话配置为资源工作流。每个资源定义字段、列、搜索、创建端点、更新端点、领域动作和导出能力。\code{resource-workbench.component.ts} 根据当前 URL 自动选择配置，统一渲染搜索、分页、记录列表、详情检查、创建表单、编辑表单、删除确认和动作执行。这是下半部分 CRUD 排版统一的关键。

\subsection{后端认证、策略和 CRUD}
\code{backend/app/api/auth_routes.py} 负责登录、注册、退出、CSRF、当前用户和修改密码。\code{backend/app/platform/auth/decorators.py} 提供 \code{jwt_required}、\code{csrf_required} 和 \code{permission_required}。\code{backend/app/platform/policy/policy_engine.py} 集中处理管理员、权限集合、资源权限、对象授权和字段过滤。\code{generic_crud_routes.py} 通过资源注册表复用分页、搜索、创建、更新、删除、权限和审计逻辑。这样前端资源操作台能够通过统一 API 访问不同业务对象。

\subsection{完整数据库启动}
\code{backend/scripts/bootstrap_sqlite.py} 是本次完整数据上线的关键。它会读取 \code{backend/.env}，下载 \code{.db.gz} 文件，解压到 \code{/tmp/nexus-prime/nexus_prime.db}，执行写锁测试、\code{pragma quick_check}，并确认用户数和销售订单数达到阈值。这样可以防止空库误上线。脚本还会在已有数据库足够大且未强制刷新时复用现有文件，避免每次启动都重复下载 46MB 压缩库。

\subsection{代码链路验收点}
\begin{longtable}{p{0.24\textwidth}p{0.66\textwidth}}
\toprule
链路 & 验收重点 \\
\midrule
\endhead
入口保护 & 首页、登录页、注册页不改源码，只通过主题偏好截图；登录后才进入 \code{/app/**}。 \\
会话恢复 & Cookie 存在时 \code{authGuard} 调用 \code{/auth/me} 恢复用户，避免刷新后误跳登录。 \\
全局请求 & \code{ApiService} 和 interceptor 统一凭据、CSRF、错误提示和 envelope 解包。 \\
导航归一 & \code{navigation.ts} 是 Dock、面包屑、当前模块和跳转规则的唯一业务地图。 \\
主题切换 & \code{ThemeService} 只暴露深色与亮色两个实际状态，并广播图表刷新事件。 \\
资源操作 & \code{ResourceWorkbench} 统一搜索、分页、表单、动作、导出和审计提示。 \\
后端边界 & 权限装饰器和策略引擎作为最终授权边界，前端只负责体验和引导。 \\
云端数据 & \code{bootstrap_sqlite.py} 使用 quick check 与最小数据量断言防止空库上线。 \\
\bottomrule
\end{longtable}
\clearpage
\section{腾讯云部署流程}
\begin{enumerate}
  \item 本地完整库位于 \code{backend/instance/nexus_prime.db}，大小约 244MB。
  \item 压缩为 \code{nexus_prime_full_06292108.db.gz}，上传到 CloudBase 静态托管 \code{nexus-data/}。
  \item 后端环境设置 \code{DATABASE_URL=sqlite:////tmp/nexus-prime/nexus_prime.db}，并设置 \code{NEXUS_DB_BOOTSTRAP_URL}。
  \item 设置 \code{NEXUS_DB_BOOTSTRAP_FORCE=true}、\code{NEXUS_DB_BOOTSTRAP_MIN_USERS=15000}、\code{NEXUS_DB_BOOTSTRAP_MIN_ORDERS=100000}。
  \item CloudRun 启动命令先运行 \code{python scripts/bootstrap_sqlite.py}，再运行 \code{flask db upgrade} 和 \code{gunicorn}。
  \item 前端构建时写入 \code{NEXUS_API_BASE_URL}，部署到 CloudBase 静态托管唯一路径。
  \item 用健康检查、登录接口和数据计数确认线上不是空库。
\end{enumerate}

部署中发现的关键问题是：启动脚本早于 Flask 读取环境变量，因此最初没有拿到完整库 URL，CloudRun 会迁移出一个空库。修复后，bootstrap 脚本主动读取 \code{backend/.env}，并加入最小数据量断言，最终云端完整数据验证通过。

\subsection{上线后的验证证据}
验证分为三类。第一类是健康检查，\code{/api/v1/health/ready} 返回 200，证明后端服务和数据库连接可用。第二类是登录验证，管理员 \code{admin@nexus.com / admin123} 和普通用户 \code{user00001@nexus.com / password123} 均返回 200，证明认证、Cookie、CSRF 和跨域配置可用。第三类是完整数据验证，诊断接口返回 15001 个用户、57609 个商品、100803 张销售订单、46803 张采购订单、111360 条库存数量和 16200 条生成报表，证明云端数据库不是空库或裁剪库。

\subsection{生产化建议}
当前方案适合课程展示和全量演示。继续向生产演进时，建议把 SQLite 迁移到云数据库 PostgreSQL 或 MySQL；把文件中心接入对象存储；将诊断开关关闭或仅限内网；把日志、错误、慢查询和任务失败接入集中观测；并把 CloudRun 镜像、数据库迁移和前端静态版本纳入可回滚发布流程。
\clearpage
\section{交付结论}
本次交付完成了三件核心工作。第一，腾讯云线上环境已经接入完整本地演示库，包含 15001 个用户和完整业务数据。第二，前端业务区完成系统化升级，Dock、顶部导航、页面结构、图表、表格、表单、分页、AI 页面和个人页都进入统一逻辑。第三，报告、ER 图、所有页面截图、代码讲解、架构设计、升级思路、部署说明和视频口播稿已经补齐。

系统当前可用于课程展示、业务流程演示和后续继续升级。若继续向生产级演进，建议将 SQLite 演示库迁移到云数据库 PostgreSQL 或 MySQL，并把文件中心接入对象存储，同时关闭部署诊断开关、接入集中日志和监控。

\begin{longtable}{p{0.24\textwidth}p{0.66\textwidth}}
\toprule
交付物 & 内容 \\
\midrule
\endhead
线上前端 & CloudBase 静态托管完整前端，可直接分享给评审访问。 \\
线上后端 & CloudBase CloudRun 后端 API，健康检查和完整数据诊断均已通过。 \\
完整演示库 & 本地完整 SQLite 压缩后上传，云端启动下载、解压并校验。 \\
入口截图 & 首页、登录、注册、注册协议全部使用暗色主题截图，且源码未改。 \\
业务截图 & 33 个业务页面全部覆盖，并按深色、亮色交替展示。 \\
ER 图 & 1 张全局 ER 图和 4 张分域 ER 图，覆盖身份、库存、采购、销售、财务、工作流、协作、报表和 AI。 \\
代码说明 & API、认证、主题、Shell、Dock、顶部栏、资源操作台、后端权限、通用 CRUD 和启动脚本均已展开说明。 \\
部署说明 & 包含完整库上传、环境变量、CloudRun 启动、前端构建、健康检查、登录验证和生产化建议。 \\
视频稿 & 可按顺序朗读，覆盖地址、数据规模、架构、页面、ER、代码、部署和总结。 \\
\bottomrule
\end{longtable}
\end{document}
""")
    return "".join(parts)


def video_script(pages):
    page_names = "、".join(page["title"] for page in pages)
    return f"""# NEXUS Prime 讲解视频连续口播稿

线上演示地址：`{FRONTEND_URL}`

后端 API：`{API_BASE}`

大家好，今天展示的是 NEXUS Prime 制造业经营管理 ERP 系统。这个系统已经部署到腾讯云 CloudBase，前端使用 CloudBase 静态托管，后端使用 CloudBase 云托管。请先把线上演示地址放在浏览器最前面展示，这个地址是 `{FRONTEND_URL}`。演示账号可以使用管理员 `admin@nexus.com / admin123`，也可以使用普通账号 `user00001@nexus.com / password123`。

首先说明最重要的一点，本次云端不是只上传一个小型演示库，而是把本地完整演示数据上传并接入了线上环境。本地完整 SQLite 数据库原始大小约 244MB，压缩后约 46MB，上传到 CloudBase 静态托管的 `nexus-data` 路径。CloudRun 后端启动时会下载这个压缩库，解压到运行目录，然后执行写锁测试、quick check 校验和最小数据量断言。线上已经验证，用户账号有 15001 个，商品有 57609 个，客户和供应商伙伴有 25200 个，销售订单有 100803 张，采购订单有 46803 张，应收账款有 80640 条，库存数量记录有 111360 条，生成报表有 16200 条。这说明云端现在接入的是完整本地数据。

接下来介绍系统定位。NEXUS Prime 面向制造企业的日常经营管理，不只是做几个 CRUD 页面，而是把库存、采购、销售、仓配、应收、质量、产能、设备维护、报表、文件、通知、AI 分析、权限和审计放进同一套工作台。企业经营中的问题往往不是孤立发生的，例如销售订单会影响库存和应收，低库存会触发补货建议，采购收货会影响仓库库存，客户逾期会影响信用额度，盘点差异会反向修正库存。所以这个系统的设计重点是业务闭环，而不是单页堆表格。

架构上，系统已经从旧的 Flask 单体 B/S 页面升级为前后端分离。前端是 Angular 21 SPA，负责路由、页面、组件、图表、主题、Dock 和顶部导航。后端是 Flask REST API，统一提供 `/api/v1` 接口，负责登录、权限、业务服务、文件、报表、AI、审计和数据库访问。数据库通过 SQLAlchemy 模型管理，并使用 Alembic 迁移。登录态使用 HttpOnly Cookie，写操作经过 CSRF 校验，业务接口通过权限装饰器和策略引擎保护。

打开系统后，首页、登录页和注册页保持原样没有修改。登录后的业务区是本轮升级重点。左侧 Dock 不再有按钮拉长动画，图标稳定，配合文字浮窗和当前页状态。顶部栏合并了面包屑、搜索、服务状态、主题切换、通知和头像，避免页面上同时出现好几套跳转规则。每个页面按照统一结构整理：真实图和关键图表放在上面，交互报表放在中间，表格、表单、增删查改和分页放在下面。这样页面不会过长，也不会到处堆无意义方框。

演示时先进入运营控制塔。运营控制塔是登录后的总览页面，负责展示经营控制分、库存风险、采购审批、应收风险、任务异常和业务趋势。它的作用是让管理者一眼看到今天最需要处理的事项，并能从这里进入库存、采购、销售、财务和任务页面。

然后进入经营指标中心。经营指标中心用于查看营收、库存效率、现金流和经营健康度。页面上半部分是关键指标和图表，中间展示趋势和对比，下方提供可追踪的业务列表。这个页面解决的是经营层看数的问题。

任务异常中心用于集中展示异常任务、超期任务、审批任务和高优先级风险。以前任务信息容易散在多个页面，现在统一进入任务异常中心，用户可以按优先级和状态定位问题，再跳转到对应业务对象。

库存模块包括物料库存图谱、仓配流向图和采购补货建议。物料库存图谱管理商品、分类、供应商和库存摘要。仓配流向图展示仓库、库存数量、库存流转和调度动作。采购补货建议根据库存和需求生成建议，用户可以接受建议并转化为采购动作。这个模块体现了从库存监控到采购补货的闭环。

采购协同控制台负责采购订单、提交审批、审批通过、采购收货和供应商承诺。供应商协同网络用于查看供应商绩效、延期风险、质量评分和采购关系。采购不是孤立模块，它会连接库存、预算、质量和供应商风险。

销售履约中心负责客户订单、发货调度、订单状态推进和销售明细。客户经营中心展示客户档案、交易贡献、风险和服务入口。合同回款中心连接合同、销售订单和应收账款。售后服务中心处理客户反馈和服务工单。销售模块最终会与应收、信用和服务闭环连接。

财务模块包括账龄风险墙、客户信用中心和预算成本中心。账龄风险墙展示应收账款、逾期天数、账龄结构和收款动作。客户信用中心管理客户信用额度、可用额度和冻结状态。预算成本中心展示采购成本、库存成本和预算偏差，并支持复核动作。这样财务人员可以从风险、信用和预算三个方向控制经营风险。

生产运营模块包括质量检验中心、产能计划中心、设备维护中心和移动扫码终端。质量检验中心管理检验任务、缺陷和处置动作。产能计划中心展示产能负载、瓶颈和齐套风险。设备维护中心展示设备健康、维护工单和停机影响。移动扫码终端模拟仓库现场扫码、拣货、上架和盘点任务，并适配移动端展示。

协作和系统模块包括报表工作室、文件资料库、公告与知识库、系统安全中心、审计日志、任务通知中心、AI 经营分析台、个人中心和控制中心。报表工作室用于生成和查看经营报表。文件资料库管理附件上传下载。公告与知识库管理文章、评论和资料。系统安全中心管理用户、角色、权限和部门。审计日志记录登录、写入、审批、删除等关键动作。任务通知中心展示未读和业务提醒。AI 经营分析台支持经营问答、结构化诊断和动作草稿。个人中心重新整理了身份资料、头像、偏好、工作负载和最近业务入口。控制中心展示主题、部署状态、AI 状态和系统能力。

本次报告中已经从首页、登录页、注册页和注册协议页开始，逐页放入了截图和功能说明。入口流程全部使用暗色主题截图，且源码没有修改。登录后的业务页面使用深色驾驶舱和亮色系统交替截图，展示两套主题下的实际效果。全部业务页面包括：{page_names}。每个页面都有路由、桌面截图、移动截图索引、页面定位、主要功能、主要数据、主要接口、代码关联和升级说明。

数据库部分请展示 ER 图。报告里既有全局 ER 图，也有身份权限与主数据、库存仓配与采购补货、销售履约与财务盘点、工作流协作报表与 AI 四张分域 ER 图。全局图负责说明系统全貌，分域图负责解释每个业务闭环。关键关系包括：角色分配给用户，部门拥有用户，商品归属分类，商品和仓库通过库存数量关联，采购订单包含采购明细，补货建议可以转采购订单，销售订单包含销售明细，销售订单形成应收账款，应收通过收款记录核销，盘点单包含盘点明细，流程实例产生任务，用户动作写入审计日志，AI 会话可以沉淀行动草稿。

代码部分可以重点讲这些文件。前端 `api.service.ts` 统一封装请求和返回解包，所有请求带 `withCredentials`。`auth.service.ts`、`auth.guard.ts` 和 `auth.interceptor.ts` 负责登录态恢复、CSRF 和未授权处理。`theme.service.ts` 把主题收敛为深色和亮色两个状态，并同步到 html class 和用户偏好。`navigation.ts` 是 Dock 和面包屑的统一来源。`app-shell.component.ts` 管理搜索防抖、通知轮询、服务健康和页面壳层。`app-dock.component.ts` 保留稳定图标、短标签和浮窗文字，删除按钮拉长动画。`app-topbar.component.ts` 合并搜索、服务状态、主题、通知、头像和快捷创建。`resource-workflow.ts` 与 `resource-workbench.component.ts` 负责下半部分的表格、分页、表单和领域动作。后端 `auth_routes.py` 负责登录、注册、CSRF 和当前用户，`policy_engine.py` 负责管理员、权限、资源、对象和字段级授权，`generic_crud_routes.py` 负责通用 CRUD。最后，`bootstrap_sqlite.py` 是完整数据库云端上线的关键，它会下载完整库、校验数据规模，防止空库上线。

部署部分请展示 `deploy/tencent-cloudbase-auto-deploy.ps1`。这份脚本会准备后端 CloudRun 部署包，写入运行环境变量，构建前端静态资源，并上传到 CloudBase 静态托管。上线过程中遇到过两个关键问题。第一个是 CloudBase 路由前缀容易被静态托管兜底拦截，所以最终前端运行时配置直接指向 CloudRun 默认 API 域名。第二个是 bootstrap 脚本最初没有自己读取 `backend/.env`，导致启动时没有拿到完整库 URL，云端迁移出了空库。修复后，bootstrap 主动读取 `.env` 并加入最小数据量断言，最终完整库成功上线。

最后总结，NEXUS Prime 当前已经完成前端业务区的系统升级，也完成腾讯云 CloudBase 的全量数据上线。它现在具备完整演示数据、清晰导航、统一页面结构、业务闭环、完整 ER 图、页面截图、核心代码讲解、部署流程和可直接朗读的视频讲稿。后续如果继续向生产级演进，建议把 SQLite 演示库迁移到云数据库 PostgreSQL 或 MySQL，把文件中心接入对象存储，并关闭部署诊断开关，接入集中日志和监控。
"""


def main():
    generate_er_diagrams()
    pages = load_pages()
    (DOCS / "nexus-prime-system-report.md").write_text(md_report(pages), encoding="utf-8")
    (DOCS / "nexus-prime-system-report.tex").write_text(tex_report(pages), encoding="utf-8")
    (DOCS / "nexus-prime-video-script.md").write_text(video_script(pages), encoding="utf-8")
    print(f"Generated report docs for {len(pages)} business pages")


if __name__ == "__main__":
    main()
