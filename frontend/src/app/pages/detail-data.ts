import { DetailPageConfig } from '../core/models';

export type DetailKey =
  | 'products'
  | 'stock'
  | 'replenishment'
  | 'purchaseOrders'
  | 'salesOrders'
  | 'receivables'
  | 'credits'
  | 'stocktakes'
  | 'reports'
  | 'files'
  | 'articles'
  | 'users'
  | 'auditLogs'
  | 'notifications'
  | 'customers'
  | 'aiSessions';

export const DETAIL_CONFIGS: Record<DetailKey, DetailPageConfig> = {
  products: {
    key: 'products',
    title: '物料详情',
    eyebrow: '物料详情',
    resource: 'products',
    backPath: '/app/inventory/products',
    titleFields: ['name', 'sku'],
    subtitleFields: ['category_name', 'supplier_name'],
    heroMetricFields: ['total_stock', 'min_stock', 'price'],
    fields: [
      { key: 'sku', label: 'SKU' },
      { key: 'name', label: '物料名称' },
      { key: 'category_name', label: '分类' },
      { key: 'supplier_name', label: '首选供应商' },
      { key: 'total_stock', label: '总库存', type: 'number' },
      { key: 'min_stock', label: '安全库存', type: 'number' },
      { key: 'price', label: '标准售价', type: 'money' }
    ],
    timeline: [
      { code: '01', title: '主数据已归档', time: '08:20', tone: 'success' },
      { code: '02', title: '库存水位进入监控', time: '09:10', tone: 'info' },
      { code: '03', title: '低水位将自动进入补货建议', time: '实时', tone: 'warning' }
    ],
    related: [
      { label: '补货中心', value: '安全库存不足时自动生成建议', meta: '/app/inventory/replenishment', tone: 'warning' },
      { label: '仓配流向', value: '按仓库、库区、库位定位库存', meta: '/app/inventory/stock', tone: 'info' }
    ],
    actions: [
      { label: '生成补货建议', icon: 'pi-bolt', kind: 'generate-replenishment', endpoint: 'replenishment-suggestions/generate', method: 'POST', confirm: '根据当前库存水位重新生成补货建议？' }
    ]
  },
  stock: {
    key: 'stock',
    title: '库存库位详情',
    eyebrow: '库存库位',
    resource: 'stock',
    backPath: '/app/inventory/stock',
    titleFields: ['product_name', 'product_sku'],
    subtitleFields: ['warehouse_name', 'shelf_location'],
    heroMetricFields: ['quantity', 'updated_at', 'warehouse_name'],
    fields: [
      { key: 'product_sku', label: 'SKU' },
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'shelf_location', label: '库位' },
      { key: 'quantity', label: '可用库存', type: 'number' }
    ],
    timeline: [
      { code: '01', title: '采购收货增加库存', time: '09:32', tone: 'success' },
      { code: '02', title: '调拨任务占用库存', time: '10:18', tone: 'info' },
      { code: '03', title: '盘点差异进入确认', time: '待办', tone: 'warning' }
    ],
    related: [
      { label: '库位热区', value: '华东工厂仓 A区-03-02', meta: '现场扫码定位', tone: 'info' },
      { label: '库存流水', value: '采购入库、销售出库、调拨统一追踪', meta: '审计可追溯', tone: 'success' }
    ],
    actions: [
      { label: '刷新库存', icon: 'pi-refresh', kind: 'refresh' }
    ]
  },
  replenishment: {
    key: 'replenishment',
    title: '补货建议详情',
    eyebrow: '补货建议',
    resource: 'replenishment-suggestions',
    backPath: '/app/inventory/replenishment',
    titleFields: ['product_name', 'product_id'],
    subtitleFields: ['warehouse_name', 'status'],
    heroMetricFields: ['current_qty', 'suggested_qty', 'status'],
    fields: [
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'current_qty', label: '当前库存', type: 'number' },
      { key: 'suggested_qty', label: '建议补货', type: 'number' },
      { key: 'status', label: '状态', type: 'status' }
    ],
    timeline: [
      { code: '01', title: '库存低于安全线', time: '09:12', tone: 'danger' },
      { code: '02', title: '建议量按安全库存和交期计算', time: '09:16', tone: 'info' },
      { code: '03', title: '接受后创建采购单', time: '下一步', tone: 'success' }
    ],
    related: [
      { label: '触发原因', value: '当前库存低于安全库存', meta: '低库存链路', tone: 'warning' },
      { label: '采购单', value: '接受后生成 PO 草稿', meta: '/app/procurement/orders', tone: 'success' }
    ],
    actions: [
      { label: '接受并转采购', icon: 'pi-shopping-cart', kind: 'accept-replenishment', endpoint: 'replenishment-suggestions/:id/accept', method: 'POST', confirm: '接受该补货建议并创建采购单？' },
      { label: '重新生成建议', icon: 'pi-bolt', kind: 'generate-replenishment', endpoint: 'replenishment-suggestions/generate', method: 'POST', confirm: '重新扫描低库存并生成建议？' }
    ]
  },
  purchaseOrders: {
    key: 'purchaseOrders',
    title: '采购单详情',
    eyebrow: '采购详情',
    resource: 'purchase-orders',
    backPath: '/app/procurement/orders',
    titleFields: ['po_no', 'supplier_name'],
    subtitleFields: ['warehouse_name', 'status'],
    heroMetricFields: ['total_amount', 'receive_progress', 'status'],
    fields: [
      { key: 'po_no', label: '采购单' },
      { key: 'supplier_name', label: '供应商' },
      { key: 'warehouse_name', label: '收货仓' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'receive_progress', label: '收货进度', type: 'percent' },
      { key: 'total_amount', label: '金额', type: 'money' },
      { key: 'expected_date', label: '预计到货', type: 'date' }
    ],
    timeline: [
      { code: '01', title: '补货建议转采购草稿', time: '09:26', tone: 'info' },
      { code: '02', title: '提交审批并记录权限校验', time: '当前', tone: 'warning' },
      { code: '03', title: '收货后更新库存水位', time: 'ETA', tone: 'success' }
    ],
    related: [
      { label: '供应商绩效', value: '准点率、质检通过率、历史采购金额', meta: '影响补货优先级', tone: 'info' },
      { label: '库存入库', value: '收货动作写入库存流水', meta: '/app/inventory/stock', tone: 'success' }
    ],
    actions: [
      { label: '提交审批', icon: 'pi-send', kind: 'submit-purchase', endpoint: 'procurement/orders/:id/submit', method: 'POST', confirm: '提交该采购单进入审批？' },
      { label: '审批通过', icon: 'pi-check', kind: 'approve-purchase', endpoint: 'procurement/orders/:id/approve', method: 'POST', confirm: '审批通过该采购单？' },
      { label: '按待收数量收货', icon: 'pi-inbox', kind: 'receive-purchase', endpoint: 'procurement/orders/:id/receive', method: 'POST', confirm: '按待收数量执行收货入库？' }
    ]
  },
  salesOrders: {
    key: 'salesOrders',
    title: '销售履约详情',
    eyebrow: '销售履约',
    resource: 'orders',
    backPath: '/app/sales/orders',
    titleFields: ['order_no', 'customer_name'],
    subtitleFields: ['status', 'created_at'],
    heroMetricFields: ['total_amount', 'status', 'created_at'],
    fields: [
      { key: 'order_no', label: '订单号' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '阶段', type: 'status' },
      { key: 'total_amount', label: '金额', type: 'money' },
      { key: 'created_at', label: '创建时间', type: 'date' }
    ],
    timeline: [
      { code: '01', title: '客户信用校验通过', time: '10:03', tone: 'success' },
      { code: '02', title: '仓库锁定库存并安排出库', time: '10:15', tone: 'info' },
      { code: '03', title: '发货后生成应收', time: '下一步', tone: 'warning' }
    ],
    related: [
      { label: '客户应收', value: '发货后推送到应收风控', meta: '/app/finance/receivables', tone: 'warning' },
      { label: '库存扣减', value: '出库扣减并生成流水', meta: '/app/inventory/stock', tone: 'info' }
    ],
    actions: [
      { label: '推进到发货', icon: 'pi-send', kind: 'ship-order', endpoint: 'sales/orders/:id/transition', method: 'POST', confirm: '将订单推进到已发货阶段？' }
    ]
  },
  receivables: {
    key: 'receivables',
    title: '应收详情',
    eyebrow: '应收详情',
    resource: 'receivables',
    backPath: '/app/finance/receivables',
    titleFields: ['receivable_no', 'customer_name'],
    subtitleFields: ['status', 'due_date'],
    heroMetricFields: ['total_amount', 'paid_amount', 'unpaid_amount'],
    fields: [
      { key: 'receivable_no', label: '应收单' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'total_amount', label: '应收金额', type: 'money' },
      { key: 'paid_amount', label: '已收', type: 'money' },
      { key: 'unpaid_amount', label: '未收', type: 'money' },
      { key: 'due_date', label: '到期日', type: 'date' },
      { key: 'overdue_days', label: '逾期天数', type: 'number' }
    ],
    timeline: [
      { code: '01', title: '销售发货生成应收', time: '自动', tone: 'info' },
      { code: '02', title: '账龄超过阈值进入风险队列', time: '当前', tone: 'warning' },
      { code: '03', title: '收款后释放信用占用', time: '下一步', tone: 'success' }
    ],
    related: [
      { label: '信用管理', value: '逾期影响客户可用额度', meta: '/app/finance/credits', tone: 'warning' },
      { label: '催款通知', value: '可生成催款提醒并留痕', meta: '/app/notifications', tone: 'info' }
    ],
    actions: [
      { label: '记录收款', icon: 'pi-wallet', kind: 'record-payment', endpoint: 'receivables/:id/payment', method: 'POST', confirm: '按未收金额记录银行回款？' },
      { label: '发送催款', icon: 'pi-bell', kind: 'send-reminder', endpoint: 'finance/receivables/:id/reminder', method: 'POST', confirm: '发送催款提醒？' }
    ]
  },
  credits: {
    key: 'credits',
    title: '客户信用详情',
    eyebrow: '信用详情',
    resource: 'credits',
    backPath: '/app/finance/credits',
    titleFields: ['customer_name', 'customer_id'],
    subtitleFields: ['is_frozen', 'usage_rate'],
    heroMetricFields: ['credit_limit', 'used_credit', 'available_credit'],
    fields: [
      { key: 'customer_name', label: '客户' },
      { key: 'credit_limit', label: '信用额度', type: 'money' },
      { key: 'used_credit', label: '已用额度', type: 'money' },
      { key: 'available_credit', label: '可用额度', type: 'money' },
      { key: 'usage_rate', label: '占用率', type: 'percent' },
      { key: 'is_frozen', label: '是否冻结', type: 'status' },
      { key: 'frozen_reason', label: '冻结原因' }
    ],
    timeline: [
      { code: '01', title: '销售订单占用信用额度', time: '实时', tone: 'info' },
      { code: '02', title: '逾期应收提升风险等级', time: '当前', tone: 'warning' },
      { code: '03', title: '冻结或解冻写入审计', time: '动作后', tone: 'success' }
    ],
    related: [
      { label: '销售履约', value: '冻结客户会阻断信用销售', meta: '/app/sales/orders', tone: 'danger' },
      { label: '应收风控', value: '收款后降低额度占用', meta: '/app/finance/receivables', tone: 'success' }
    ],
    actions: [
      { label: '冻结客户', icon: 'pi-ban', kind: 'freeze-credit', endpoint: 'finance/credits/:id/freeze', method: 'POST', confirm: '冻结该客户信用？' },
      { label: '解冻客户', icon: 'pi-unlock', kind: 'unfreeze-credit', endpoint: 'finance/credits/:id/unfreeze', method: 'POST', confirm: '解除该客户信用冻结？' }
    ]
  },
  stocktakes: {
    key: 'stocktakes',
    title: '盘点详情',
    eyebrow: '盘点详情',
    resource: 'stocktakes',
    backPath: '/app/stocktakes',
    titleFields: ['take_no', 'warehouse_name'],
    subtitleFields: ['status', 'take_type'],
    heroMetricFields: ['progress', 'total_variance_qty', 'total_variance_value'],
    fields: [
      { key: 'take_no', label: '盘点单' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'take_type', label: '类型' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'planned_date', label: '计划日期', type: 'date' },
      { key: 'progress', label: '进度', type: 'percent' },
      { key: 'total_variance_qty', label: '差异数量', type: 'number' }
    ],
    timeline: [
      { code: '01', title: '创建盘点计划', time: '计划', tone: 'info' },
      { code: '02', title: '扫码录入现场数量', time: '盘点中', tone: 'warning' },
      { code: '03', title: '完成后自动调整并审计', time: '完成', tone: 'success' }
    ],
    related: [
      { label: '扫码终端', value: '库位、批次、实盘数量', meta: '现场交互', tone: 'info' },
      { label: '库存调整', value: '差异确认后写入库存流水', meta: '/app/inventory/stock', tone: 'success' }
    ],
    actions: [
      { label: '开始盘点', icon: 'pi-play', kind: 'start-stocktake', endpoint: 'stocktakes/:id/start', method: 'POST', confirm: '开始该盘点任务？' },
      { label: '录入扫码', icon: 'pi-qrcode', kind: 'count-stocktake', endpoint: 'stocktakes/:id/count', method: 'POST', confirm: '写入当前待盘物料的扫码数量？' },
      { label: '完成盘点', icon: 'pi-check', kind: 'complete-stocktake', endpoint: 'stocktakes/:id/complete', method: 'POST', confirm: '完成盘点并自动调整库存？' }
    ]
  },
  reports: {
    key: 'reports',
    title: '报表详情',
    eyebrow: '报表详情',
    resource: 'generated-reports',
    backPath: '/app/reports',
    titleFields: ['report_name', 'report_type'],
    subtitleFields: ['generated_at', 'file_path'],
    heroMetricFields: ['report_type', 'generated_at', 'file_path'],
    fields: [
      { key: 'report_name', label: '报表名称' },
      { key: 'report_type', label: '报表类型' },
      { key: 'generated_at', label: '生成时间', type: 'date' },
      { key: 'file_path', label: '导出文件' }
    ],
    timeline: [
      { code: '01', title: '模板参数就绪', time: '08:40', tone: 'info' },
      { code: '02', title: '图表与业务队列生成', time: '08:44', tone: 'success' },
      { code: '03', title: '导出后归档到文件中心', time: '08:45', tone: 'success' }
    ],
    related: [
      { label: '文件中心', value: '报表导出件可下载', meta: '/app/files', tone: 'success' },
      { label: '通知中心', value: '生成完成推送管理层', meta: '/app/notifications', tone: 'info' }
    ],
    actions: [
      { label: '重新生成库存汇总', icon: 'pi-chart-line', kind: 'generate-report', endpoint: 'reports/generate/inventory_summary', method: 'POST', confirm: '重新生成库存水位汇总？' }
    ]
  },
  files: {
    key: 'files',
    title: '文件详情',
    eyebrow: '文件详情',
    resource: 'files',
    backPath: '/app/files',
    titleFields: ['filename', 'title'],
    subtitleFields: ['mimetype', 'created_at'],
    heroMetricFields: ['size', 'mimetype', 'created_at'],
    fields: [
      { key: 'filename', label: '文件名' },
      { key: 'mimetype', label: '文件类型' },
      { key: 'size', label: '大小', type: 'number' },
      { key: 'created_at', label: '上传时间', type: 'date' },
      { key: 'download_url', label: '下载地址' }
    ],
    timeline: [
      { code: '01', title: '上传时完成内容类型校验', time: '上传', tone: 'success' },
      { code: '02', title: '分类归档到内容中心', time: '当前', tone: 'info' },
      { code: '03', title: '下载行为进入审计', time: '访问时', tone: 'warning' }
    ],
    related: [
      { label: '公告知识', value: '文件可作为 SOP 附件', meta: '/app/content/articles', tone: 'info' },
      { label: '审计日志', value: '下载、预览均留痕', meta: '/app/system/audit', tone: 'success' }
    ],
    actions: [
      { label: '下载文件', icon: 'pi-download', kind: 'download-file', endpoint: 'files/:id/download', method: 'GET', confirm: '下载该文件并记录审计？' }
    ]
  },
  articles: {
    key: 'articles',
    title: '内容详情',
    eyebrow: '内容详情',
    resource: 'articles',
    backPath: '/app/content/articles',
    titleFields: ['title', 'category'],
    subtitleFields: ['status', 'created_at'],
    heroMetricFields: ['category', 'status', 'created_at'],
    fields: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'created_at', label: '发布时间', type: 'date' }
    ],
    timeline: [
      { code: '01', title: '草稿编写', time: '创建', tone: 'info' },
      { code: '02', title: '附件与流程校验', time: '发布前', tone: 'warning' },
      { code: '03', title: '发布后通知相关角色', time: '发布', tone: 'success' }
    ],
    related: [
      { label: '文件附件', value: 'SOP、库位图、供应商报告', meta: '/app/files', tone: 'info' },
      { label: '通知中心', value: '发布后推送到任务队列', meta: '/app/notifications', tone: 'success' }
    ],
    actions: [
      { label: '刷新内容', icon: 'pi-refresh', kind: 'refresh' }
    ]
  },
  users: {
    key: 'users',
    title: '用户权限详情',
    eyebrow: '用户权限',
    resource: 'users',
    backPath: '/app/system/users',
    titleFields: ['username', 'email'],
    subtitleFields: ['role_name', 'department_name_display'],
    heroMetricFields: ['is_admin_effective', 'role_name', 'department_name_display'],
    fields: [
      { key: 'username', label: '用户名' },
      { key: 'email', label: '邮箱' },
      { key: 'role_name', label: '角色' },
      { key: 'department_name_display', label: '部门' },
      { key: 'is_admin_effective', label: '管理员', type: 'status' }
    ],
    timeline: [
      { code: '01', title: '登录会话使用 HttpOnly Cookie', time: '登录', tone: 'success' },
      { code: '02', title: '写操作经过 CSRF 与权限矩阵校验', time: '动作时', tone: 'info' },
      { code: '03', title: '关键动作写入审计', time: '持续', tone: 'success' }
    ],
    related: [
      { label: '权限矩阵', value: '库存、采购、财务、报表拆分授权', meta: '安全中心', tone: 'success' },
      { label: '审计日志', value: '登录、审批、文件下载可追踪', meta: '/app/system/audit', tone: 'info' }
    ],
    actions: [
      { label: '刷新权限', icon: 'pi-refresh', kind: 'refresh' }
    ]
  },
  auditLogs: {
    key: 'auditLogs',
    title: '审计详情',
    eyebrow: '审计详情',
    resource: 'audit-logs',
    backPath: '/app/system/audit',
    titleFields: ['action', 'module'],
    subtitleFields: ['username', 'created_at'],
    heroMetricFields: ['module', 'action', 'created_at'],
    fields: [
      { key: 'module', label: '模块' },
      { key: 'action', label: '动作' },
      { key: 'username', label: '操作者' },
      { key: 'created_at', label: '时间', type: 'date' },
      { key: 'details', label: '详情' }
    ],
    timeline: [
      { code: '01', title: '请求进入领域动作', time: '触发', tone: 'info' },
      { code: '02', title: '权限与边界校验通过', time: '执行', tone: 'success' },
      { code: '03', title: '审计记录落库', time: '完成', tone: 'success' }
    ],
    related: [
      { label: '安全中心', value: '按模块回看关键动作', meta: '/app/system/users', tone: 'info' }
    ],
    actions: [
      { label: '刷新审计', icon: 'pi-refresh', kind: 'refresh' }
    ]
  },
  notifications: {
    key: 'notifications',
    title: '通知详情',
    eyebrow: '通知详情',
    resource: 'notifications',
    backPath: '/app/notifications',
    titleFields: ['title', 'category'],
    subtitleFields: ['is_read', 'created_at'],
    heroMetricFields: ['category', 'is_read', 'created_at'],
    fields: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'content', label: '内容' },
      { key: 'is_read', label: '已读', type: 'status' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    timeline: [
      { code: '01', title: '业务事件触发通知', time: '实时', tone: 'info' },
      { code: '02', title: '通知进入个人任务队列', time: '当前', tone: 'warning' },
      { code: '03', title: '处理后回写业务状态', time: '完成', tone: 'success' }
    ],
    related: [
      { label: '业务源', value: '低库存、采购审批、应收催款、报表生成', meta: '运营闭环', tone: 'info' }
    ],
    actions: [
      { label: '标记已读', icon: 'pi-check', kind: 'mark-read', endpoint: 'notifications/:id', method: 'PATCH', confirm: '将该通知标记为已读？' }
    ]
  },
  customers: {
    key: 'customers',
    title: '客户经营详情',
    eyebrow: '客户经营',
    resource: 'partners',
    backPath: '/app/customers',
    titleFields: ['name', 'contact_person'],
    subtitleFields: ['address', 'credit_score'],
    heroMetricFields: ['credit_score', 'phone', 'email'],
    fields: [
      { key: 'name', label: '客户名称' },
      { key: 'contact_person', label: '联系人' },
      { key: 'phone', label: '电话' },
      { key: 'email', label: '邮箱' },
      { key: 'address', label: '地址' },
      { key: 'credit_score', label: '信用评分', type: 'number' }
    ],
    timeline: [
      { code: '01', title: '客户资料进入主数据', time: '创建', tone: 'success' },
      { code: '02', title: '销售履约形成订单与应收', time: '持续', tone: 'info' },
      { code: '03', title: '风险客户进入跟进任务', time: '当前', tone: 'warning' }
    ],
    related: [
      { label: '销售履约', value: '客户订单、发货、应收联动', meta: '/app/sales/orders', tone: 'info' },
      { label: '应收风控', value: '账龄与信用占用', meta: '/app/finance/receivables', tone: 'warning' }
    ],
    actions: [
      { label: '创建跟进任务', icon: 'pi-bell', kind: 'customer-followup', endpoint: 'operations/customer-followup', method: 'POST', confirm: '为该客户创建经营跟进任务？' },
      { label: '生成客户报表', icon: 'pi-chart-line', kind: 'generate-customer-report', endpoint: 'reports/generate/customer_operations', method: 'POST', confirm: '生成客户经营报表？' }
    ]
  },
  aiSessions: {
    key: 'aiSessions',
    title: '经营分析详情',
    eyebrow: '经营分析',
    resource: 'ai-sessions',
    backPath: '/app/ai',
    titleFields: ['title', 'id'],
    subtitleFields: ['created_at', 'is_archived'],
    heroMetricFields: ['created_at', 'is_archived', 'id'],
    fields: [
      { key: 'title', label: '会话标题' },
      { key: 'created_at', label: '创建时间', type: 'date' },
      { key: 'is_archived', label: '归档', type: 'status' }
    ],
    timeline: [
      { code: '01', title: '读取库存、采购、应收上下文', time: '输入', tone: 'info' },
      { code: '02', title: '生成异常摘要与行动建议', time: '分析', tone: 'warning' },
      { code: '03', title: '转化为补货、催款或报表动作', time: '输出', tone: 'success' }
    ],
    related: [
      { label: '低库存分析', value: '可转补货建议', meta: '/app/inventory/replenishment', tone: 'warning' },
      { label: '催款草案', value: '可转通知或应收动作', meta: '/app/finance/receivables', tone: 'info' }
    ],
    actions: [
      { label: '刷新分析', icon: 'pi-refresh', kind: 'refresh' }
    ]
  }
};

export const PAGE_DETAIL_PATH: Record<string, string> = {
  materials: '/app/inventory/products',
  flow: '/app/inventory/stock',
  replenishment: '/app/inventory/replenishment',
  fulfillment: '/app/sales/orders',
  procurement: '/app/procurement/orders',
  receivables: '/app/finance/receivables',
  credit: '/app/finance/credits',
  stocktake: '/app/stocktakes',
  reports: '/app/reports',
  files: '/app/files',
  content: '/app/content/articles',
  security: '/app/system/users',
  audit: '/app/system/audit',
  notifications: '/app/notifications',
  ai: '/app/ai'
};
