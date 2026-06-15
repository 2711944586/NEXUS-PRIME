import { DataRecord } from './models';

export type ResourceFieldType = 'text' | 'number' | 'date' | 'textarea' | 'select' | 'lookup' | 'boolean';
export type ResourceActionTone = 'default' | 'success' | 'warning' | 'danger' | 'info';

export interface ResourceLookupConfig {
  path: string;
  params?: Record<string, string | number | boolean>;
}

export interface ResourceFieldConfig {
  key: string;
  label: string;
  type?: ResourceFieldType;
  placeholder?: string;
  options?: Array<{ label: string; value: string | boolean | number }>;
  lookup?: ResourceLookupConfig;
  defaultValue?: string | boolean | number;
  min?: number;
  step?: number;
  required?: boolean;
}

export interface ResourceWorkflowAction {
  label: string;
  icon: string;
  description: string;
  endpoint?: string;
  method?: 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  path?: string;
  requiresRecord?: boolean;
  tone?: ResourceActionTone;
  body?: (record: DataRecord | null) => Record<string, unknown>;
}

export interface ResourceWorkflowConfig {
  key: string;
  title: string;
  eyebrow: string;
  resource?: string;
  detailBase?: string;
  routePrefixes: string[];
  searchPlaceholder: string;
  createEndpoint?: string;
  updateEndpoint?: string;
  deleteEndpoint?: string;
  createFields: ResourceFieldConfig[];
  editFields: ResourceFieldConfig[];
  columns: ResourceFieldConfig[];
  workflowSteps: Array<{ label: string; detail: string; path?: string; tone?: ResourceActionTone }>;
  actions: ResourceWorkflowAction[];
  toCreatePayload?: (form: Record<string, unknown>) => Record<string, unknown>;
  toUpdatePayload?: (form: Record<string, unknown>) => Record<string, unknown>;
  exportable?: boolean;
  canDelete?: boolean;
  readonlyReason?: string;
  emptyText?: string;
}

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '待处理', value: 'pending' },
  { label: '已发布', value: 'published' },
  { label: '已完成', value: 'done' }
];

const notificationTypeOptions = [
  { label: '信息', value: 'info' },
  { label: '提醒', value: 'warning' },
  { label: '告警', value: 'alert' },
  { label: '完成', value: 'success' }
];

const partnerTypeOptions = [
  { label: '客户', value: 'customer' },
  { label: '供应商', value: 'supplier' }
];

const yesNoOptions = [
  { label: '是', value: true },
  { label: '否', value: false }
];

const orderStatusOptions = [
  { label: '待付款', value: 'pending' },
  { label: '已付款', value: 'paid' }
];

const stocktakeTypeOptions = [
  { label: '全盘', value: 'full' },
  { label: '循环盘点', value: 'cycle' },
  { label: '抽盘', value: 'partial' }
];

const productCreateFields: ResourceFieldConfig[] = [
  { key: 'sku', label: 'SKU', required: true, placeholder: 'MFG-SKU-001' },
  { key: 'name', label: '物料名称', required: true },
  { key: 'price', label: '标准售价', type: 'number' },
  { key: 'cost', label: '标准成本', type: 'number' },
  { key: 'min_stock', label: '安全库存', type: 'number' },
  { key: 'max_stock', label: '目标库存', type: 'number' },
  { key: 'supplier_id', label: '默认供应商', type: 'lookup', lookup: { path: 'lookups/partners', params: { type: 'supplier' } }, placeholder: '可选供应商' },
  { key: 'description', label: '说明', type: 'textarea' }
];

const partnerFields: ResourceFieldConfig[] = [
  { key: 'name', label: '名称', required: true },
  { key: 'type', label: '类型', type: 'select', options: partnerTypeOptions },
  { key: 'contact_person', label: '联系人' },
  { key: 'phone', label: '电话' },
  { key: 'email', label: '邮箱' },
  { key: 'address', label: '地址', type: 'textarea' },
  { key: 'credit_score', label: '信用评分', type: 'number' }
];

const notificationFields: ResourceFieldConfig[] = [
  { key: 'title', label: '标题', required: true },
  { key: 'content', label: '内容', type: 'textarea' },
  { key: 'type', label: '类型', type: 'select', options: notificationTypeOptions },
  { key: 'category', label: '分类' },
  { key: 'related_type', label: '关联类型' },
  { key: 'related_id', label: '关联 ID', type: 'number' }
];

const articleFields: ResourceFieldConfig[] = [
  { key: 'title', label: '标题', required: true },
  { key: 'category', label: '分类' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
  { key: 'content', label: '正文', type: 'textarea' }
];

const salesOrderCreateFields: ResourceFieldConfig[] = [
  { key: 'customer_id', label: '客户', type: 'lookup', lookup: { path: 'lookups/partners', params: { type: 'customer' } }, required: true, placeholder: '选择客户' },
  { key: 'product_id', label: '产品', type: 'lookup', lookup: { path: 'lookups/products' }, required: true, placeholder: '选择产品' },
  { key: 'quantity', label: '数量', type: 'number', required: true, defaultValue: 1, min: 1, step: 1 },
  { key: 'status', label: '初始阶段', type: 'select', options: orderStatusOptions, defaultValue: 'pending' }
];

const purchaseOrderCreateFields: ResourceFieldConfig[] = [
  { key: 'supplier_id', label: '供应商', type: 'lookup', lookup: { path: 'lookups/partners', params: { type: 'supplier' } }, required: true, placeholder: '选择供应商' },
  { key: 'warehouse_id', label: '收货仓库', type: 'lookup', lookup: { path: 'lookups/warehouses' }, required: true, placeholder: '选择仓库' },
  { key: 'product_id', label: '采购产品', type: 'lookup', lookup: { path: 'lookups/products' }, required: true, placeholder: '选择产品' },
  { key: 'quantity', label: '采购数量', type: 'number', required: true, defaultValue: 1, min: 1, step: 1 },
  { key: 'unit_price', label: '采购单价', type: 'number', required: true, defaultValue: 1, min: 0, step: 0.01 },
  { key: 'expected_date', label: '预计到货', type: 'date' },
  { key: 'remark', label: '备注', type: 'textarea' }
];

const stocktakeCreateFields: ResourceFieldConfig[] = [
  { key: 'warehouse_id', label: '盘点仓库', type: 'lookup', lookup: { path: 'lookups/warehouses' }, required: true, placeholder: '选择仓库' },
  { key: 'take_type', label: '盘点类型', type: 'select', options: stocktakeTypeOptions, defaultValue: 'full' },
  { key: 'product_id', label: '抽盘物料', type: 'lookup', lookup: { path: 'lookups/products' }, placeholder: '抽盘时选择' },
  { key: 'planned_date', label: '计划日期', type: 'date' },
  { key: 'remark', label: '备注', type: 'textarea' }
];

function transitionBody(record: DataRecord | null): Record<string, unknown> {
  const status = String(record?.['status'] ?? '');
  return {
    status: status === 'pending' ? 'paid' : status === 'shipped' ? 'done' : 'shipped',
    remark: '模块操作台推进履约阶段'
  };
}

function receiveBody(record: DataRecord | null): Record<string, unknown> {
  const items = Array.isArray(record?.['items']) ? record?.['items'] as DataRecord[] : [];
  return {
    items: items
      .filter(item => Number(item['pending_qty'] ?? 0) > 0)
      .map(item => ({ item_id: item.id, receive_qty: Math.max(1, Number(item['pending_qty'] ?? 1)) }))
  };
}

function paymentBody(record: DataRecord | null): Record<string, unknown> {
  const total = Number(record?.['total_amount'] ?? 0);
  const paid = Number(record?.['paid_amount'] ?? 0);
  const unpaid = Number(record?.['unpaid_amount'] ?? Math.max(1, total - paid));
  return {
    amount: Math.max(1, unpaid),
    payment_method: 'bank',
    reference_no: `PAY-${Date.now()}`,
    remark: '模块操作台记录银行回款'
  };
}

function positiveNumber(value: unknown, fallback = 1): number {
  const next = Number(value ?? fallback);
  return Number.isFinite(next) && next > 0 ? next : fallback;
}

function optionalNumber(value: unknown): number | undefined {
  const next = Number(value ?? 0);
  return Number.isFinite(next) && next > 0 ? next : undefined;
}

function salesOrderCreateBody(form: Record<string, unknown>): Record<string, unknown> {
  return {
    customer_id: Number(form['customer_id']),
    status: form['status'] || 'pending',
    items: [{
      product_id: Number(form['product_id']),
      quantity: positiveNumber(form['quantity'])
    }]
  };
}

function purchaseOrderCreateBody(form: Record<string, unknown>): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    supplier_id: Number(form['supplier_id']),
    warehouse_id: Number(form['warehouse_id']),
    items: [{
      product_id: Number(form['product_id']),
      quantity: positiveNumber(form['quantity']),
      unit_price: positiveNumber(form['unit_price'])
    }]
  };
  if (form['expected_date']) {
    payload['expected_date'] = form['expected_date'];
  }
  if (form['remark']) {
    payload['remark'] = form['remark'];
  }
  return payload;
}

function stocktakeCreateBody(form: Record<string, unknown>): Record<string, unknown> {
  const productId = optionalNumber(form['product_id']);
  const payload: Record<string, unknown> = {
    warehouse_id: Number(form['warehouse_id']),
    take_type: form['take_type'] || 'full',
    product_ids: productId ? [productId] : []
  };
  if (form['planned_date']) {
    payload['planned_date'] = form['planned_date'];
  }
  if (form['remark']) {
    payload['remark'] = form['remark'];
  }
  return payload;
}

export const RESOURCE_WORKFLOW_CONFIGS: ResourceWorkflowConfig[] = [
  {
    key: 'materials',
    title: '物料与成品中心',
    eyebrow: '主数据 / 库存水位',
    resource: 'products',
    detailBase: '/app/inventory/products',
    routePrefixes: ['/app/inventory/products', '/app/maintenance'],
    searchPlaceholder: '搜索 SKU、物料、供应商',
    createFields: productCreateFields,
    editFields: productCreateFields.filter(field => field.key !== 'sku'),
    columns: [
      { key: 'sku', label: 'SKU' },
      { key: 'name', label: '物料' },
      { key: 'total_stock', label: '库存', type: 'number' },
      { key: 'min_stock', label: '安全线', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看水位', detail: '复核总库存、安全线、供应商和库位覆盖。', path: '/app/inventory/products', tone: 'info' },
      { label: '编辑主数据', detail: '维护价格、成本、库存阈值和说明。', tone: 'warning' },
      { label: '生成补货', detail: '低水位物料进入补货建议和采购审批。', path: '/app/inventory/replenishment', tone: 'success' }
    ],
    actions: [
      { label: '生成补货', icon: 'pi-bolt', description: '扫描低库存并刷新补货建议。', endpoint: 'inventory/replenishment-suggestions/generate', method: 'POST', tone: 'success' },
      { label: '盘点复核', icon: 'pi-qrcode', description: '跳转库存盘点中心核对差异。', path: '/app/stocktakes', tone: 'info' }
    ],
    exportable: true
  },
  {
    key: 'warehouse-flow',
    title: '仓配流向图',
    eyebrow: '仓库 / 库位 / 调拨',
    resource: 'stock',
    detailBase: '/app/inventory/stock',
    routePrefixes: ['/app/inventory/stock', '/app/dispatch', '/app/mobile-terminal'],
    searchPlaceholder: '搜索物料、仓库、库位',
    createFields: [],
    editFields: [{ key: 'shelf_location', label: '库位' }],
    columns: [
      { key: 'product_sku', label: 'SKU' },
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'quantity', label: '库存', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看库位', detail: '定位仓库、库区、库位和当前数量。', tone: 'info' },
      { label: '更新库位', detail: '库存数量通过收货、发货、盘点等领域动作写入。', tone: 'warning' },
      { label: '创建调度', detail: '异常库存进入仓配调度和移动扫码任务。', path: '/app/dispatch', tone: 'success' }
    ],
    actions: [
      { label: '创建调度任务', icon: 'pi-send', description: '把当前仓配问题写入通知中心。', endpoint: 'operations/dispatch-task', method: 'POST', tone: 'info' },
      { label: '生成流向报表', icon: 'pi-chart-line', description: '生成库存变动报表并归档。', endpoint: 'reports/generate/inventory_movement', method: 'POST', tone: 'success' }
    ],
    exportable: true,
    readonlyReason: '库存数量由收货、出库、盘点和调拨动作维护。'
  },
  {
    key: 'replenishment',
    title: '采购补货建议',
    eyebrow: '低库存 / 转采购',
    resource: 'replenishment-suggestions',
    detailBase: '/app/inventory/replenishment',
    routePrefixes: ['/app/inventory/replenishment'],
    searchPlaceholder: '搜索物料、仓库、状态',
    createFields: [],
    editFields: [],
    columns: [
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'current_qty', label: '现存', type: 'number' },
      { key: 'suggested_qty', label: '建议', type: 'number' }
    ],
    workflowSteps: [
      { label: '生成建议', detail: '根据安全库存和现存量刷新建议。', tone: 'info' },
      { label: '查看原因', detail: '复核物料、仓库、供应商和建议量。', tone: 'warning' },
      { label: '接受转采购', detail: '生成采购草稿并进入审批/收货。', path: '/app/procurement/orders', tone: 'success' }
    ],
    actions: [
      { label: '重新生成', icon: 'pi-bolt', description: '重新扫描低库存并生成建议。', endpoint: 'inventory/replenishment-suggestions/generate', method: 'POST', tone: 'info' },
      { label: '接受建议', icon: 'pi-shopping-cart', description: '把选中建议转成采购单。', endpoint: 'inventory/replenishment-suggestions/:id/accept', method: 'POST', requiresRecord: true, tone: 'success' }
    ],
    exportable: true,
    readonlyReason: '补货建议由库存预警引擎生成，通过接受动作转采购。'
  },
  {
    key: 'procurement',
    title: '采购补货中心',
    eyebrow: '采购 / 审批 / 收货',
    resource: 'purchase-orders',
    createEndpoint: 'purchase-orders',
    detailBase: '/app/procurement/orders',
    routePrefixes: ['/app/procurement/orders', '/app/suppliers/performance', '/app/quality'],
    searchPlaceholder: '搜索采购单、供应商、状态',
    createFields: purchaseOrderCreateFields,
    editFields: [
      { key: 'expected_date', label: '预计到货', type: 'date' },
      { key: 'remark', label: '备注', type: 'textarea' }
    ],
    columns: [
      { key: 'po_no', label: '采购单' },
      { key: 'supplier_name', label: '供应商' },
      { key: 'status', label: '状态' },
      { key: 'total_amount', label: '金额', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看采购单', detail: '复核供应商、仓库、金额和明细。', tone: 'info' },
      { label: '审批推进', detail: '草稿提交审批，待审批通过后进入收货。', tone: 'warning' },
      { label: '收货入库', detail: '收货后更新库存、供应商表现和审计记录。', tone: 'success' }
    ],
    actions: [
      { label: '提交审批', icon: 'pi-send', description: '把草稿采购单提交审批。', endpoint: 'procurement/orders/:id/submit', method: 'POST', requiresRecord: true, tone: 'info' },
      { label: '审批通过', icon: 'pi-check', description: '通过当前采购单审批。', endpoint: 'procurement/orders/:id/approve', method: 'POST', requiresRecord: true, tone: 'success' },
      { label: '收货入库', icon: 'pi-inbox', description: '按待收数量执行收货。', endpoint: 'procurement/orders/:id/receive', method: 'POST', requiresRecord: true, body: receiveBody, tone: 'warning' }
    ],
    toCreatePayload: purchaseOrderCreateBody,
    exportable: true,
    readonlyReason: '采购金额、审批和收货数量由采购领域动作维护，操作台可创建带一条明细的采购草稿。'
  },
  {
    key: 'fulfillment',
    title: '销售履约中心',
    eyebrow: '订单 / 发货 / 应收',
    resource: 'orders',
    createEndpoint: 'sales/orders',
    detailBase: '/app/sales/orders',
    routePrefixes: ['/app/sales/orders', '/app/capacity', '/app/service'],
    searchPlaceholder: '搜索订单、客户、状态',
    createFields: salesOrderCreateFields,
    editFields: [],
    columns: [
      { key: 'order_no', label: '订单' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '阶段' },
      { key: 'total_amount', label: '金额', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看订单', detail: '确认客户、明细、金额与当前阶段。', tone: 'info' },
      { label: '推进履约', detail: '按状态推进付款、发货和完成。', tone: 'warning' },
      { label: '进入应收', detail: '发货后联动应收、信用和报表归档。', path: '/app/finance/receivables', tone: 'success' }
    ],
    actions: [
      { label: '推进阶段', icon: 'pi-send', description: '将订单推进到下一履约阶段。', endpoint: 'sales/orders/:id/transition', method: 'POST', requiresRecord: true, body: transitionBody, tone: 'success' },
      { label: '客户跟进', icon: 'pi-bell', description: '为客户创建履约跟进任务。', endpoint: 'operations/customer-followup', method: 'POST', requiresRecord: true, body: record => ({ customer_id: record?.['customer_id'], title: `客户经营跟进 - ${record?.['customer_name'] ?? '客户'}` }), tone: 'info' }
    ],
    toCreatePayload: salesOrderCreateBody,
    exportable: true,
    readonlyReason: '订单金额、发货和应收由履约领域动作维护，操作台可创建带一条明细的销售订单。'
  },
  {
    key: 'customers',
    title: '客户经营中心',
    eyebrow: '客户 / 信用 / 跟进',
    resource: 'partners',
    detailBase: '/app/customers',
    routePrefixes: ['/app/customers'],
    searchPlaceholder: '搜索客户、联系人、电话',
    createFields: partnerFields,
    editFields: partnerFields.filter(field => field.key !== 'type'),
    columns: [
      { key: 'name', label: '客户' },
      { key: 'contact_person', label: '联系人' },
      { key: 'phone', label: '电话' },
      { key: 'credit_score', label: '信用', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看客户', detail: '查看联系人、电话、信用评分和地址。', tone: 'info' },
      { label: '编辑资料', detail: '更新客户联系人、信用评分和地址。', tone: 'warning' },
      { label: '创建跟进', detail: '把重点客户写入任务/通知队列。', tone: 'success' }
    ],
    actions: [
      { label: '创建跟进任务', icon: 'pi-bell', description: '创建客户经营跟进任务。', endpoint: 'operations/customer-followup', method: 'POST', requiresRecord: true, body: record => ({ customer_id: record?.id, title: `客户经营跟进 - ${record?.['name'] ?? '重点客户'}` }), tone: 'info' }
    ],
    exportable: true
  },
  {
    key: 'receivables',
    title: '应收风控中心',
    eyebrow: '应收 / 收款 / 催款',
    resource: 'receivables',
    detailBase: '/app/finance/receivables',
    routePrefixes: ['/app/finance/receivables', '/app/contracts', '/app/budget'],
    searchPlaceholder: '搜索应收单、客户、状态',
    createFields: [],
    editFields: [
      { key: 'due_date', label: '到期日', type: 'date' },
      { key: 'remark', label: '备注', type: 'textarea' }
    ],
    columns: [
      { key: 'receivable_no', label: '应收单' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '状态' },
      { key: 'unpaid_amount', label: '未收', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看账龄', detail: '确认客户、金额、已收和逾期天数。', tone: 'info' },
      { label: '记录收款', detail: '回款后更新应收并释放信用占用。', tone: 'success' },
      { label: '催款/冻结', detail: '高风险客户进入催款和信用控制。', path: '/app/finance/credits', tone: 'warning' }
    ],
    actions: [
      { label: '记录收款', icon: 'pi-wallet', description: '按未收金额记录银行回款。', endpoint: 'finance/receivables/:id/payment', method: 'POST', requiresRecord: true, body: paymentBody, tone: 'success' },
      { label: '发送催款', icon: 'pi-bell', description: '创建催款提醒并写审计。', endpoint: 'finance/receivables/:id/reminder', method: 'POST', requiresRecord: true, tone: 'warning' }
    ],
    exportable: true,
    readonlyReason: '应收生成来自销售发货，金额和状态通过收款等领域动作维护。'
  },
  {
    key: 'credits',
    title: '客户信用管理',
    eyebrow: '额度 / 占用 / 冻结',
    resource: 'credits',
    detailBase: '/app/finance/credits',
    routePrefixes: ['/app/finance/credits'],
    searchPlaceholder: '搜索客户信用',
    createFields: [],
    editFields: [
      { key: 'credit_limit', label: '信用额度', type: 'number' },
      { key: 'warning_threshold', label: '预警阈值', type: 'number' }
    ],
    columns: [
      { key: 'customer_name', label: '客户' },
      { key: 'credit_limit', label: '额度', type: 'number' },
      { key: 'used_credit', label: '已用', type: 'number' },
      { key: 'usage_rate', label: '占用率', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看额度', detail: '查看信用额度、已用、可用和占用率。', tone: 'info' },
      { label: '编辑阈值', detail: '维护信用额度和预警阈值。', tone: 'warning' },
      { label: '冻结/解冻', detail: '风险客户进入冻结或解冻审计。', tone: 'success' }
    ],
    actions: [
      { label: '冻结客户', icon: 'pi-ban', description: '冻结当前客户信用。', endpoint: 'finance/credits/:id/freeze', method: 'POST', requiresRecord: true, body: () => ({ reason: '模块操作台风险控制' }), tone: 'danger' },
      { label: '解冻客户', icon: 'pi-unlock', description: '解除当前客户信用冻结。', endpoint: 'finance/credits/:id/unfreeze', method: 'POST', requiresRecord: true, tone: 'success' }
    ],
    exportable: true,
    canDelete: false
  },
  {
    key: 'stocktakes',
    title: '库存盘点中心',
    eyebrow: '盘点 / 扫码 / 调整',
    resource: 'stocktakes',
    createEndpoint: 'stocktakes/create',
    detailBase: '/app/stocktakes',
    routePrefixes: ['/app/stocktakes'],
    searchPlaceholder: '搜索盘点单、仓库、状态',
    createFields: stocktakeCreateFields,
    editFields: [
      { key: 'planned_date', label: '计划日期', type: 'date' },
      { key: 'remark', label: '备注', type: 'textarea' }
    ],
    columns: [
      { key: 'take_no', label: '盘点单' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'status', label: '状态' },
      { key: 'progress', label: '进度', type: 'number' }
    ],
    workflowSteps: [
      { label: '查看计划', detail: '查看仓库、盘点类型、状态和计划日期。', tone: 'info' },
      { label: '扫码录入', detail: '盘点中录入实际数量并形成差异。', tone: 'warning' },
      { label: '完成调整', detail: '完成后生成库存调整和审计记录。', tone: 'success' }
    ],
    actions: [
      { label: '开始盘点', icon: 'pi-play', description: '启动选中盘点任务。', endpoint: 'stocktakes/:id/start', method: 'POST', requiresRecord: true, tone: 'info' },
      { label: '完成盘点', icon: 'pi-check', description: '完成盘点并自动调整。', endpoint: 'stocktakes/:id/complete', method: 'POST', requiresRecord: true, body: () => ({ auto_adjust: true }), tone: 'success' }
    ],
    toCreatePayload: stocktakeCreateBody,
    exportable: true,
    readonlyReason: '盘点数量和差异调整由扫码录入/完成动作维护，操作台可创建盘点计划。'
  },
  {
    key: 'reports',
    title: '报表工作室',
    eyebrow: '报表 / 生成 / 归档',
    resource: 'generated-reports',
    detailBase: '/app/reports',
    routePrefixes: ['/app/reports', '/app/metrics'],
    searchPlaceholder: '搜索报表名称、类型',
    createFields: [],
    editFields: [],
    columns: [
      { key: 'report_name', label: '报表' },
      { key: 'report_type', label: '类型' },
      { key: 'generated_at', label: '时间', type: 'date' }
    ],
    workflowSteps: [
      { label: '选择模板', detail: '选择库存、应收、供应商或经营日报模板。', tone: 'info' },
      { label: '生成预览', detail: '生成图表、数据和导出文件。', tone: 'warning' },
      { label: '文件归档', detail: '产物进入文件中心并推送通知。', path: '/app/files', tone: 'success' }
    ],
    actions: [
      { label: '生成库存报表', icon: 'pi-chart-line', description: '生成库存水位汇总。', endpoint: 'reports/generate/inventory_summary', method: 'POST', tone: 'success' },
      { label: '查看文件库', icon: 'pi-folder-open', description: '打开报表归档文件。', path: '/app/files', tone: 'info' }
    ],
    exportable: true,
    canDelete: false,
    readonlyReason: '报表由模板生成，不建议直接编辑生成记录。'
  },
  {
    key: 'files',
    title: '文件与内容中心',
    eyebrow: '文件 / 附件 / 下载',
    resource: 'files',
    detailBase: '/app/files',
    routePrefixes: ['/app/files'],
    searchPlaceholder: '搜索文件名、类型',
    createFields: [],
    editFields: [],
    columns: [
      { key: 'filename', label: '文件' },
      { key: 'mimetype', label: '类型' },
      { key: 'size', label: '大小', type: 'number' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    workflowSteps: [
      { label: '上传校验', detail: '通过类型和大小策略校验后保存。', tone: 'info' },
      { label: '查看下载', detail: '详情页提供下载并写入审计。', tone: 'success' },
      { label: '关联内容', detail: 'SOP、公告和报表可引用文件。', path: '/app/content/articles', tone: 'warning' }
    ],
    actions: [
      { label: '公告知识', icon: 'pi-book', description: '跳转公告与知识中心。', path: '/app/content/articles', tone: 'info' }
    ],
    exportable: true,
    readonlyReason: '文件通过上传接口创建，下载和删除会进入审计。'
  },
  {
    key: 'content',
    title: '公告与知识中心',
    eyebrow: '公告 / SOP / 协同',
    resource: 'articles',
    detailBase: '/app/content/articles',
    routePrefixes: ['/app/content/articles'],
    searchPlaceholder: '搜索标题、分类、正文',
    createFields: articleFields,
    editFields: articleFields,
    columns: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'status', label: '状态' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    workflowSteps: [
      { label: '编写草稿', detail: '维护标题、分类和正文。', tone: 'info' },
      { label: '发布触达', detail: '发布后通知相关岗位。', tone: 'success' },
      { label: '讨论留痕', detail: '评论、附件和下载进入审计。', tone: 'warning' }
    ],
    actions: [
      { label: '发布', icon: 'pi-megaphone', description: '把选中文章标记为已发布。', endpoint: 'articles/:id', method: 'PATCH', requiresRecord: true, body: () => ({ status: 'published' }), tone: 'success' }
    ],
    exportable: true
  },
  {
    key: 'notifications',
    title: '通知中心',
    eyebrow: '通知 / 任务 / 来源',
    resource: 'notifications',
    detailBase: '/app/notifications',
    routePrefixes: ['/app/overview', '/app/notifications', '/app/tasks', '/app/data-quality', '/app/rules', '/app/integrations', '/app/profile', '/app/settings'],
    searchPlaceholder: '搜索通知、任务、来源',
    createFields: notificationFields,
    editFields: [...notificationFields, { key: 'is_read', label: '已读', type: 'select', options: yesNoOptions }],
    columns: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'type', label: '类型' },
      { key: 'is_read', label: '已读' }
    ],
    workflowSteps: [
      { label: '查看通知', detail: '确认来源、内容、业务对象和优先级。', tone: 'info' },
      { label: '编辑任务', detail: '补充标题、类型、分类和关联对象。', tone: 'warning' },
      { label: '处理完成', detail: '标记已读并回到来源业务页。', tone: 'success' }
    ],
    actions: [
      { label: '标记已读', icon: 'pi-check', description: '把选中通知标记为已读。', endpoint: 'notifications/:id', method: 'PATCH', requiresRecord: true, body: () => ({ is_read: true }), tone: 'success' }
    ],
    exportable: true
  },
  {
    key: 'security',
    title: '系统安全中心',
    eyebrow: '用户 / 权限 / 审计',
    resource: 'users',
    detailBase: '/app/system/users',
    routePrefixes: ['/app/system/users'],
    searchPlaceholder: '搜索用户、邮箱、姓名',
    createFields: [
      { key: 'username', label: '用户名', required: true },
      { key: 'email', label: '邮箱', required: true },
      { key: 'password', label: '初始密码', required: true },
      { key: 'full_name', label: '姓名' },
      { key: 'phone', label: '电话' },
      { key: 'position', label: '职位' },
      { key: 'is_active_user', label: '启用账号', type: 'select', options: yesNoOptions, defaultValue: true }
    ],
    editFields: [
      { key: 'username', label: '用户名' },
      { key: 'email', label: '邮箱' },
      { key: 'full_name', label: '姓名' },
      { key: 'phone', label: '电话' },
      { key: 'position', label: '职位' },
      { key: 'bio', label: '说明', type: 'textarea' }
    ],
    columns: [
      { key: 'username', label: '用户' },
      { key: 'email', label: '邮箱' },
      { key: 'role_name', label: '角色' },
      { key: 'is_admin_effective', label: '管理员' }
    ],
    workflowSteps: [
      { label: '查看用户', detail: '确认身份、角色、部门和管理员状态。', tone: 'info' },
      { label: '维护资料', detail: '更新姓名、电话、职位和说明。', tone: 'warning' },
      { label: '审计追踪', detail: '关键权限动作进入审计日志。', path: '/app/system/audit', tone: 'success' }
    ],
    actions: [
      { label: '查看审计', icon: 'pi-history', description: '打开安全审计日志。', path: '/app/system/audit', tone: 'info' }
    ],
    exportable: true
  },
  {
    key: 'audit',
    title: '审计日志',
    eyebrow: '追踪 / 回放 / 合规',
    resource: 'audit-logs',
    detailBase: '/app/system/audit',
    routePrefixes: ['/app/system/audit'],
    searchPlaceholder: '搜索模块、动作、详情',
    createFields: [],
    editFields: [],
    columns: [
      { key: 'module', label: '模块' },
      { key: 'action', label: '动作' },
      { key: 'username', label: '操作者' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    workflowSteps: [
      { label: '查看事件', detail: '确认模块、动作、操作者和时间。', tone: 'info' },
      { label: '回看对象', detail: '根据详情字段回到业务来源。', tone: 'warning' },
      { label: '保留证据', detail: '审计日志只读保留，支持导出。', tone: 'success' }
    ],
    actions: [
      { label: '安全中心', icon: 'pi-lock', description: '返回用户权限中心。', path: '/app/system/users', tone: 'info' }
    ],
    exportable: true,
    canDelete: false,
    readonlyReason: '审计日志为合规证据，只允许查看和导出。'
  },
  {
    key: 'ai',
    title: '经营分析台',
    eyebrow: '分析 / 会话 / 行动草案',
    resource: 'ai-sessions',
    detailBase: '/app/ai',
    routePrefixes: ['/app/ai'],
    searchPlaceholder: '搜索分析会话',
    createFields: [{ key: 'title', label: '会话标题', required: true }],
    editFields: [
      { key: 'title', label: '会话标题' },
      { key: 'is_archived', label: '归档', type: 'select', options: yesNoOptions }
    ],
    columns: [
      { key: 'title', label: '会话' },
      { key: 'message_count', label: '消息', type: 'number' },
      { key: 'created_at', label: '创建时间', type: 'date' }
    ],
    workflowSteps: [
      { label: '查看会话', detail: '查看分析主题、消息数和创建时间。', tone: 'info' },
      { label: '编辑标题', detail: '整理分析会话名称和归档状态。', tone: 'warning' },
      { label: '转行动', detail: '把分析建议转补货、催款、任务或报表。', path: '/app/tasks', tone: 'success' }
    ],
    actions: [
      { label: '结构化分析', icon: 'pi-sparkles', description: '生成结构化经营分析。', endpoint: 'ai/analyze/structured', method: 'POST', tone: 'info' }
    ],
    exportable: false
  }
];

export function resourceConfigForUrl(url: string): ResourceWorkflowConfig | null {
  const clean = url.split('?')[0].split('#')[0];
  return [...RESOURCE_WORKFLOW_CONFIGS]
    .sort((a, b) => longestPrefix(b, clean) - longestPrefix(a, clean))
    .find(config => longestPrefix(config, clean) > 0) ?? null;
}

function longestPrefix(config: ResourceWorkflowConfig, url: string): number {
  return Math.max(...config.routePrefixes.map(prefix => (url === prefix || url.startsWith(`${prefix}/`) ? prefix.length : 0)));
}
