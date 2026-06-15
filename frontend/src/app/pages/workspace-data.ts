import { DataRecord } from '../core/models';

export type PageKey =
  | 'materials'
  | 'flow'
  | 'replenishment'
  | 'fulfillment'
  | 'procurement'
  | 'receivables'
  | 'credit'
  | 'stocktake'
  | 'reports'
  | 'files'
  | 'content'
  | 'security'
  | 'audit'
  | 'notifications'
  | 'ai'
  | 'profile';

export interface ColumnConfig {
  key: string;
  label: string;
  type?: 'money' | 'number' | 'status' | 'percent' | 'date';
}

export interface ActionConfig {
  label: string;
  icon: string;
  kind: 'refresh' | 'create' | 'approve' | 'receive' | 'ship' | 'payment' | 'report' | 'upload' | 'freeze' | 'domain';
  severity?: 'primary' | 'secondary' | 'success' | 'info' | 'warn' | 'danger';
}

export interface WorkspaceConfig {
  key: PageKey;
  title: string;
  eyebrow: string;
  description: string;
  endpoint: string;
  searchPlaceholder: string;
  visual: 'materials' | 'flow' | 'timeline' | 'risk' | 'scanner' | 'studio' | 'security';
  visualDensity: 'compact' | 'balanced' | 'immersive';
  heroVariant: 'material-lab' | 'flow-network' | 'approval-lane' | 'fulfillment-lane' | 'risk-studio' | 'report-studio' | 'security-matrix' | 'scanner-floor' | 'knowledge-studio';
  storyBlocks: Array<{ title: string; body: string; metric?: string; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' }>;
  columns: ColumnConfig[];
  actions: ActionConfig[];
  chips: string[];
  seedRows: DataRecord[];
}

export interface WorkspaceBoardLane {
  title: string;
  body: string;
  tone: 'default' | 'success' | 'warning' | 'danger' | 'info';
  items: Array<{ label: string; metric: string; meta: string }>;
}

export function buildBoardLanes(workspace: WorkspaceConfig, rows: DataRecord[]): WorkspaceBoardLane[] {
  const safeRows = rows.length >= 2 ? rows : [...rows, ...workspace.seedRows].slice(0, 2);
  const sampleRows = safeRows.length >= 2 ? safeRows : [
    { id: 1, name: workspace.title, status: 'active' },
    { id: 2, name: workspace.eyebrow, status: 'review' }
  ];
  const titles = boardTitles(workspace);
  return titles.map((lane, index) => ({
    ...lane,
    items: sampleRows.slice(index, index + 2).length >= 2
      ? sampleRows.slice(index, index + 2).map(row => boardItem(row, workspace))
      : sampleRows.slice(0, 2).map(row => boardItem(row, workspace))
  }));
}

function boardTitles(workspace: WorkspaceConfig): Array<Omit<WorkspaceBoardLane, 'items'>> {
  const map: Partial<Record<PageKey, Array<Omit<WorkspaceBoardLane, 'items'>>>> = {
    procurement: [
      { title: '采购审批队列', body: '按金额、供应商表现和收货仓优先级推进审批。', tone: 'warning' },
      { title: '收货进度跟踪', body: '批准后的采购单进入到货、质检和入库确认。', tone: 'info' },
      { title: '供应绩效回写', body: '收货结果会影响供应商准点率和质量评分。', tone: 'success' }
    ],
    receivables: [
      { title: '收款优先队列', body: '按账龄、客户信用和未收金额安排回款动作。', tone: 'warning' },
      { title: '信用占用复核', body: '逾期客户进入额度冻结、解冻和催收协同。', tone: 'danger' },
      { title: '现金流归档', body: '收款后同步应收状态并进入报表复盘。', tone: 'success' }
    ],
    stocktake: [
      { title: '盘点计划', body: '按仓库、库区和物料范围组织盘点任务。', tone: 'info' },
      { title: '扫码录入', body: '现场录入数量后立刻形成差异记录。', tone: 'warning' },
      { title: '差异调整', body: '确认后的差异进入库存调整和审计链路。', tone: 'success' }
    ],
    reports: [
      { title: '模板选择', body: '库存、销售、应收和客户报表按场景生成。', tone: 'info' },
      { title: '图表预览', body: '生成前可预览趋势、结构和风险分布。', tone: 'warning' },
      { title: '文件归档', body: '报表产物进入文件中心并保留下载记录。', tone: 'success' }
    ],
    security: [
      { title: '用户角色', body: '账号、部门、角色和权限边界集中维护。', tone: 'info' },
      { title: '权限矩阵', body: '库存、采购、收款、报表和审计分别授权。', tone: 'warning' },
      { title: '风险审计', body: '关键写入与越权请求进入审计追踪。', tone: 'success' }
    ]
  };
  return map[workspace.key] ?? [
    { title: `${workspace.eyebrow}总览`, body: workspace.storyBlocks[0]?.body || workspace.description, tone: workspace.storyBlocks[0]?.tone || 'info' },
    { title: `${workspace.eyebrow}处理`, body: workspace.storyBlocks[1]?.body || '按优先级推进当前业务对象。', tone: workspace.storyBlocks[1]?.tone || 'warning' },
    { title: `${workspace.eyebrow}复盘`, body: workspace.storyBlocks[2]?.body || '动作完成后进入报表、通知和审计链路。', tone: workspace.storyBlocks[2]?.tone || 'success' }
  ];
}

function boardItem(row: DataRecord, workspace: WorkspaceConfig): { label: string; metric: string; meta: string } {
  const labelKeys = ['name', 'product_name', 'order_no', 'po_no', 'receivable_no', 'report_name', 'title', 'filename', 'username'];
  const metricKeys = ['status', 'total_amount', 'quantity', 'current_qty', 'suggested_qty', 'amount', 'size', 'created_at'];
  const label = firstRecordText(row, labelKeys) || `${workspace.title} #${row.id ?? '-'}`;
  const metric = firstRecordText(row, metricKeys) || workspace.chips[0] || workspace.eyebrow;
  const meta = firstRecordText(row, ['supplier_name', 'customer_name', 'warehouse_name', 'category', 'role_name']) || workspace.eyebrow;
  return { label, metric, meta };
}

function firstRecordText(row: DataRecord, keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== '') {
      return String(value);
    }
  }
  return '';
}

export const WORKSPACES: Record<PageKey, WorkspaceConfig> = {
  materials: {
    key: 'materials',
    title: '物料与成品中心',
    eyebrow: '物料主数据',
    description: '按原材料、半成品、成品和 MRO 备件组织库存水位、供应商与批次库位。',
    endpoint: 'products',
    searchPlaceholder: '搜索伺服电机组件、铝合金外壳、MFG-SKU',
    visual: 'materials',
    visualDensity: 'immersive',
    heroVariant: 'material-lab',
    storyBlocks: [
      { title: '低水位物料', metric: '7 项', body: '安全库存不足会进入补货建议，优先关注 MRO 与核心半成品。', tone: 'warning' },
      { title: '批次可追踪', metric: '128 LOT', body: '批次、库位、供应商表现同时展示，减少只看静态 SKU 的空洞感。', tone: 'info' },
      { title: '供应商优选', metric: '91%', body: '准点率和质检通过率作为补货选择依据。', tone: 'success' }
    ],
    chips: ['原材料', '半成品', '成品', '批次追溯'],
    actions: [
      { label: '新增物料', icon: 'pi-plus', kind: 'create', severity: 'primary' },
      { label: '刷新水位', icon: 'pi-refresh', kind: 'refresh' },
      { label: '生成补货', icon: 'pi-sparkles', kind: 'domain', severity: 'success' }
    ],
    columns: [
      { key: 'sku', label: 'SKU' },
      { key: 'name', label: '物料名称' },
      { key: 'category_name', label: '分类' },
      { key: 'supplier_name', label: '供应商' },
      { key: 'total_stock', label: '总库存', type: 'number' },
      { key: 'min_stock', label: '安全线', type: 'number' },
      { key: 'price', label: '标准售价', type: 'money' }
    ],
    seedRows: [
      { id: 1, sku: 'MFG-SRV-220', name: '伺服电机组件', category_name: '核心半成品', supplier_name: '苏州精驱科技', total_stock: 168, min_stock: 80, price: 1280 },
      { id: 2, sku: 'MFG-ALC-014', name: '铝合金外壳', category_name: '结构原材料', supplier_name: '宁波铝业集团', total_stock: 740, min_stock: 300, price: 186 },
      { id: 3, sku: 'MFG-MRO-09', name: 'MRO 备件包', category_name: '维修耗材', supplier_name: '华东工业品', total_stock: 32, min_stock: 50, price: 420 },
      { id: 4, sku: 'MFG-DRV-332', name: '变频器模块 B型', category_name: '核心半成品', supplier_name: '深圳控制模组', total_stock: 214, min_stock: 90, price: 1760 },
      { id: 5, sku: 'MFG-LIN-118', name: '编码器线束', category_name: '原材料', supplier_name: '无锡工业线束', total_stock: 1180, min_stock: 420, price: 72 },
      { id: 6, sku: 'MFG-JIG-042', name: '装配工装夹具', category_name: '工装夹具', supplier_name: '常州 MRO 备件', total_stock: 44, min_stock: 30, price: 2380 }
    ]
  },
  flow: {
    key: 'flow',
    title: '仓配流向图',
    eyebrow: '仓配网络',
    description: '追踪工厂仓、区域仓、库区、库位与出入库流水，突出仓配流向和现场状态。',
    endpoint: 'stock',
    searchPlaceholder: '搜索华东工厂仓、长三角区域仓、库位',
    visual: 'flow',
    visualDensity: 'immersive',
    heroVariant: 'flow-network',
    storyBlocks: [
      { title: '仓库节点', metric: '4 仓', body: '工厂仓、区域仓、备件仓按流向组织。', tone: 'info' },
      { title: '库位热区', metric: 'A区-03', body: '异常库存定位到具体库区和库位，支撑现场复核。', tone: 'warning' },
      { title: '出入库流水', metric: '10k+', body: '采购入库、销售出库、调拨和盘点调整统一追踪。', tone: 'success' }
    ],
    chips: ['工厂仓', '区域仓', '调拨', '库位热力'],
    actions: [
      { label: '库存调整', icon: 'pi-sliders-h', kind: 'create', severity: 'primary' },
      { label: '刷新流向', icon: 'pi-refresh', kind: 'refresh' },
      { label: '生成调拨', icon: 'pi-directions', kind: 'domain', severity: 'info' }
    ],
    columns: [
      { key: 'product_sku', label: 'SKU' },
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'shelf_location', label: '库位' },
      { key: 'quantity', label: '可用库存', type: 'number' }
    ],
    seedRows: [
      { id: 1, product_sku: 'MFG-SRV-220', product_name: '伺服电机组件', warehouse_name: '华东工厂仓', shelf_location: 'A区-03-02', quantity: 88 },
      { id: 2, product_sku: 'MFG-ALC-014', product_name: '铝合金外壳', warehouse_name: '长三角区域仓', shelf_location: 'C区-07-11', quantity: 420 },
      { id: 3, product_sku: 'MFG-MRO-09', product_name: 'MRO 备件包', warehouse_name: '华南备件仓', shelf_location: 'MRO-02-04', quantity: 32 },
      { id: 4, product_sku: 'MFG-DRV-332', product_name: '变频器模块 B型', warehouse_name: '华东工厂仓', shelf_location: 'B区-06-02', quantity: 176 },
      { id: 5, product_sku: 'MFG-JIG-042', product_name: '装配工装夹具', warehouse_name: '西南备件仓', shelf_location: 'G区-01-06', quantity: 44 }
    ]
  },
  replenishment: {
    key: 'replenishment',
    title: '采购补货中心',
    eyebrow: '补货建议',
    description: '低库存触发补货建议，转采购、审批、收货形成一条可执行闭环。',
    endpoint: 'replenishment-suggestions',
    searchPlaceholder: '搜索补货建议、供应商、物料',
    visual: 'timeline',
    visualDensity: 'balanced',
    heroVariant: 'approval-lane',
    storyBlocks: [
      { title: '建议生成', metric: '160 件', body: '建议量来自安全库存、现存量和交期。', tone: 'warning' },
      { title: '转采购', metric: '自动带入', body: '补货建议可直接生成采购草稿，进入审批流。', tone: 'success' },
      { title: '供应商匹配', metric: '3 家', body: '优先选择准点率更高、质检稳定的供应商。', tone: 'info' }
    ],
    chips: ['低库存', '建议量', '转采购', '供应商表现'],
    actions: [
      { label: '生成建议', icon: 'pi-bolt', kind: 'domain', severity: 'primary' },
      { label: '转采购', icon: 'pi-shopping-cart', kind: 'create', severity: 'success' },
      { label: '刷新', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'product_name', label: '物料' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'current_qty', label: '现存', type: 'number' },
      { key: 'suggested_qty', label: '建议补货', type: 'number' },
      { key: 'status', label: '状态', type: 'status' }
    ],
    seedRows: [
      { id: 1, product_name: 'MRO 备件包', warehouse_name: '华南备件仓', current_qty: 32, suggested_qty: 160, status: 'pending' },
      { id: 2, product_name: '伺服电机组件', warehouse_name: '华东工厂仓', current_qty: 88, suggested_qty: 120, status: 'approved' },
      { id: 3, product_name: '编码器线束', warehouse_name: '长三角区域仓', current_qty: 420, suggested_qty: 680, status: 'pending' },
      { id: 4, product_name: '质量检测治具', warehouse_name: '华东工厂仓', current_qty: 18, suggested_qty: 52, status: 'draft' }
    ]
  },
  fulfillment: {
    key: 'fulfillment',
    title: '销售履约中心',
    eyebrow: '销售履约',
    description: '订单阶段、发货状态、客户应收与履约时间线在一个界面推进。',
    endpoint: 'orders',
    searchPlaceholder: '搜索销售订单、客户、状态',
    visual: 'timeline',
    visualDensity: 'balanced',
    heroVariant: 'fulfillment-lane',
    storyBlocks: [
      { title: '待发货', metric: '18 单', body: '订单阶段与客户交付窗口同屏，优先处理临期订单。', tone: 'warning' },
      { title: '库存锁定', metric: 'A区', body: '发货动作扣减库存，并形成出库流水。', tone: 'info' },
      { title: '应收联动', metric: '自动', body: '发货后自动进入应收风控，支撑回款闭环。', tone: 'success' }
    ],
    chips: ['待付款', '已发货', '客户时间线', '应收联动'],
    actions: [
      { label: '新建订单', icon: 'pi-plus', kind: 'create', severity: 'primary' },
      { label: '发货推进', icon: 'pi-send', kind: 'ship', severity: 'success' },
      { label: '刷新', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'order_no', label: '订单号' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '阶段', type: 'status' },
      { key: 'total_amount', label: '金额', type: 'money' },
      { key: 'created_at', label: '创建时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, order_no: 'SO-20260529-0018', customer_name: '长三角装配中心', status: 'paid', total_amount: 248600, created_at: '2026-05-29' },
      { id: 2, order_no: 'SO-20260529-0027', customer_name: '华南新能源客户群', status: 'shipped', total_amount: 186200, created_at: '2026-05-29' },
      { id: 3, order_no: 'SO-20260530-0031', customer_name: '甬江自动化产线', status: 'pending', total_amount: 96320, created_at: '2026-05-30' },
      { id: 4, order_no: 'SO-20260530-0036', customer_name: '武汉智能装备基地', status: 'done', total_amount: 318900, created_at: '2026-05-30' }
    ]
  },
  procurement: {
    key: 'procurement',
    title: '采购补货中心',
    eyebrow: '采购执行',
    description: '采购草稿、审批、收货进度和供应商履约表现形成真实可操作链路。',
    endpoint: 'purchase-orders',
    searchPlaceholder: '搜索采购单、供应商、状态',
    visual: 'timeline',
    visualDensity: 'balanced',
    heroVariant: 'approval-lane',
    storyBlocks: [
      { title: '待审批', metric: '4 单', body: '金额、供应商、收货仓和补货来源共同影响审批优先级。', tone: 'warning' },
      { title: '收货进度', metric: '64%', body: '部分收货可见，超收会被后端领域动作拒绝。', tone: 'info' },
      { title: '绩效反馈', metric: '91%', body: '收货完成后回写供应商准点和质检表现。', tone: 'success' }
    ],
    chips: ['草稿', '待审批', '已批准', '收货进度'],
    actions: [
      { label: '创建采购', icon: 'pi-plus', kind: 'create', severity: 'primary' },
      { label: '审批', icon: 'pi-check', kind: 'approve', severity: 'success' },
      { label: '收货', icon: 'pi-inbox', kind: 'receive', severity: 'info' }
    ],
    columns: [
      { key: 'po_no', label: '采购单' },
      { key: 'supplier_name', label: '供应商' },
      { key: 'warehouse_name', label: '收货仓' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'receive_progress', label: '收货进度', type: 'percent' },
      { key: 'total_amount', label: '金额', type: 'money' }
    ],
    seedRows: [
      { id: 1, po_no: 'PO-20260529-A118', supplier_name: '苏州精驱科技', warehouse_name: '华东工厂仓', status: 'pending', receive_progress: 0, total_amount: 153600 },
      { id: 2, po_no: 'PO-20260528-C904', supplier_name: '宁波铝业集团', warehouse_name: '长三角区域仓', status: 'partial', receive_progress: 64, total_amount: 89280 },
      { id: 3, po_no: 'PO-20260530-M217', supplier_name: '常州 MRO 备件', warehouse_name: '华南备件仓', status: 'approved', receive_progress: 18, total_amount: 67400 },
      { id: 4, po_no: 'PO-20260530-L331', supplier_name: '无锡工业线束', warehouse_name: '华东工厂仓', status: 'received', receive_progress: 100, total_amount: 126800 }
    ]
  },
  receivables: {
    key: 'receivables',
    title: '应收风控中心',
    eyebrow: '应收风控',
    description: '账龄、客户信用、收款动作、催款和冻结联动展示财务风险。',
    endpoint: 'receivables',
    searchPlaceholder: '搜索应收单、客户、状态',
    visual: 'risk',
    visualDensity: 'balanced',
    heroVariant: 'risk-studio',
    storyBlocks: [
      { title: '逾期风险', metric: '3 客户', body: '账龄、未收金额和客户信用共同决定催款优先级。', tone: 'danger' },
      { title: '信用占用', metric: '84%', body: '应收未回款会占用客户信用额度，影响后续销售。', tone: 'warning' },
      { title: '回款闭环', metric: 'Bank', body: '收款动作校验金额边界并释放信用占用。', tone: 'success' }
    ],
    chips: ['账龄', '收款', '催款', '坏账预警'],
    actions: [
      { label: '记录收款', icon: 'pi-wallet', kind: 'payment', severity: 'primary' },
      { label: '催款', icon: 'pi-bell', kind: 'domain', severity: 'warn' },
      { label: '刷新账龄', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'receivable_no', label: '应收单' },
      { key: 'customer_name', label: '客户' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'total_amount', label: '应收金额', type: 'money' },
      { key: 'paid_amount', label: '已收', type: 'money' },
      { key: 'due_date', label: '到期日', type: 'date' }
    ],
    seedRows: [
      { id: 1, receivable_no: 'AR-202605-017', customer_name: '华南新能源客户群', status: 'overdue', total_amount: 186200, paid_amount: 82000, due_date: '2026-05-12' },
      { id: 2, receivable_no: 'AR-202605-021', customer_name: '长三角装配中心', status: 'pending', total_amount: 248600, paid_amount: 0, due_date: '2026-06-08' },
      { id: 3, receivable_no: 'AR-202605-029', customer_name: '武汉智能装备基地', status: 'partial', total_amount: 318900, paid_amount: 190000, due_date: '2026-06-12' },
      { id: 4, receivable_no: 'AR-202605-033', customer_name: '甬江自动化产线', status: 'paid', total_amount: 96320, paid_amount: 96320, due_date: '2026-06-20' }
    ]
  },
  credit: {
    key: 'credit',
    title: '客户信用管理',
    eyebrow: '信用控制',
    description: '信用额度、占用、冻结原因和风险阈值支撑销售履约决策。',
    endpoint: 'finance/credits',
    searchPlaceholder: '搜索客户信用',
    visual: 'risk',
    visualDensity: 'compact',
    heroVariant: 'risk-studio',
    storyBlocks: [
      { title: '额度占用', metric: '84%', body: '额度、已用、可用和冻结状态直接影响销售履约。', tone: 'warning' },
      { title: '冻结控制', metric: '审计', body: '冻结/解冻写入审计，避免人工口头管控。', tone: 'danger' },
      { title: '收款释放', metric: '实时', body: '回款后额度释放，客户可恢复信用销售。', tone: 'success' }
    ],
    chips: ['额度', '占用率', '冻结', '预警阈值'],
    actions: [
      { label: '冻结客户', icon: 'pi-ban', kind: 'freeze', severity: 'danger' },
      { label: '刷新信用', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'customer_name', label: '客户' },
      { key: 'credit_limit', label: '信用额度', type: 'money' },
      { key: 'used_credit', label: '已用', type: 'money' },
      { key: 'available_credit', label: '可用', type: 'money' },
      { key: 'usage_rate', label: '占用率', type: 'percent' },
      { key: 'is_frozen', label: '冻结', type: 'status' }
    ],
    seedRows: [
      { id: 1, customer_name: '长三角装配中心', credit_limit: 800000, used_credit: 248600, available_credit: 551400, usage_rate: 31, is_frozen: false },
      { id: 2, customer_name: '华南新能源客户群', credit_limit: 500000, used_credit: 418200, available_credit: 81800, usage_rate: 84, is_frozen: false },
      { id: 3, customer_name: '武汉智能装备基地', credit_limit: 650000, used_credit: 318900, available_credit: 331100, usage_rate: 49, is_frozen: false },
      { id: 4, customer_name: '苏南精密制造', credit_limit: 300000, used_credit: 365000, available_credit: -65000, usage_rate: 100, is_frozen: true }
    ]
  },
  stocktake: {
    key: 'stocktake',
    title: '库存盘点中心',
    eyebrow: '库存盘点',
    description: '盘点计划、扫码录入、差异确认和自动调整用接近现场的交互呈现。',
    endpoint: 'stocktakes',
    searchPlaceholder: '搜索盘点单、仓库、状态',
    visual: 'scanner',
    visualDensity: 'immersive',
    heroVariant: 'scanner-floor',
    storyBlocks: [
      { title: '扫码录入', metric: '128', body: '现场终端式录入比表格更适合盘点现场。', tone: 'info' },
      { title: '差异确认', metric: '+4', body: '盘盈盘亏确认后统一生成调整动作。', tone: 'warning' },
      { title: '调整留痕', metric: '审计', body: '盘点完成后自动写库存流水和审计记录。', tone: 'success' }
    ],
    chips: ['计划', '扫码录入', '差异确认', '自动调整'],
    actions: [
      { label: '创建盘点', icon: 'pi-plus', kind: 'create', severity: 'primary' },
      { label: '扫码录入', icon: 'pi-qrcode', kind: 'domain', severity: 'info' },
      { label: '完成盘点', icon: 'pi-check', kind: 'approve', severity: 'success' }
    ],
    columns: [
      { key: 'take_no', label: '盘点单' },
      { key: 'warehouse_name', label: '仓库' },
      { key: 'take_type', label: '类型' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'planned_date', label: '计划日期', type: 'date' }
    ],
    seedRows: [
      { id: 1, take_no: 'ST-20260529-01', warehouse_name: '华东工厂仓', take_type: 'cycle', status: 'counting', planned_date: '2026-05-29' },
      { id: 2, take_no: 'ST-20260530-02', warehouse_name: '长三角区域仓', take_type: 'partial', status: 'planned', planned_date: '2026-05-30' },
      { id: 3, take_no: 'ST-20260530-03', warehouse_name: '华南备件仓', take_type: 'cycle', status: 'done', planned_date: '2026-05-30' },
      { id: 4, take_no: 'ST-20260601-04', warehouse_name: '西南备件仓', take_type: 'full', status: 'draft', planned_date: '2026-06-01' }
    ]
  },
  reports: {
    key: 'reports',
    title: '报表工作室',
    eyebrow: '经营报表',
    description: '模板、生成进度、图表预览与导出集中在一个工作室界面里。',
    endpoint: 'generated-reports',
    searchPlaceholder: '搜索销售日报、库存水位、财务风险',
    visual: 'studio',
    visualDensity: 'immersive',
    heroVariant: 'report-studio',
    storyBlocks: [
      { title: '模板库', metric: '12', body: '经营日报、库存风险、财务风险和供应商表现可统一生成。', tone: 'info' },
      { title: '生成队列', metric: '处理中', body: '报表生成有进度、预览和导出状态。', tone: 'warning' },
      { title: '文件归档', metric: 'PDF/XLSX', body: '生成后进入文件中心，并推送通知。', tone: 'success' }
    ],
    chips: ['模板', '生成队列', '图表预览', '导出'],
    actions: [
      { label: '生成日报', icon: 'pi-chart-line', kind: 'report', severity: 'primary' },
      { label: '刷新队列', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'report_name', label: '报表名称' },
      { key: 'report_type', label: '类型' },
      { key: 'generated_at', label: '生成时间', type: 'date' },
      { key: 'file_path', label: '导出文件' }
    ],
    seedRows: [
      { id: 1, report_name: '库存水位汇总', report_type: 'inventory_summary', generated_at: '2026-05-29 09:20', file_path: 'inventory-summary.pdf' },
      { id: 2, report_name: '低库存与补货建议', report_type: 'inventory_risk', generated_at: '2026-05-29 10:05', file_path: 'inventory-risk.xlsx' },
      { id: 3, report_name: '应收账龄与信用压力', report_type: 'finance_risk', generated_at: '2026-05-29 16:30', file_path: 'receivable-aging.pdf' },
      { id: 4, report_name: '供应商准点率排行', report_type: 'supplier_score', generated_at: '2026-05-30 08:45', file_path: 'supplier-score.xlsx' }
    ]
  },
  files: {
    key: 'files',
    title: '文件与内容中心',
    eyebrow: '文件归档',
    description: '上传、预览、分类、公告发布和危险文件拦截形成完整内容中心。',
    endpoint: 'files',
    searchPlaceholder: '搜索文件、公告、附件',
    visual: 'studio',
    visualDensity: 'compact',
    heroVariant: 'knowledge-studio',
    storyBlocks: [
      { title: '安全上传', metric: '类型校验', body: '上传动作经过内容类型检查和危险文件拦截。', tone: 'success' },
      { title: '分类预览', metric: '4 类', body: '库位图、供应商报告、SOP、公告附件分层管理。', tone: 'info' },
      { title: '下载审计', metric: '留痕', body: '预览和下载行为会进入审计链路。', tone: 'warning' }
    ],
    chips: ['上传', '预览', '分类', '公告'],
    actions: [
      { label: '上传文件', icon: 'pi-upload', kind: 'upload', severity: 'primary' },
      { label: '发布公告', icon: 'pi-megaphone', kind: 'create', severity: 'info' }
    ],
    columns: [
      { key: 'filename', label: '文件名' },
      { key: 'mimetype', label: '类型' },
      { key: 'size', label: '大小', type: 'number' },
      { key: 'created_at', label: '上传时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, filename: '华东工厂仓库位图.pdf', mimetype: 'application/pdf', size: 184220, created_at: '2026-05-29' },
      { id: 2, filename: '供应商绩效月报.xlsx', mimetype: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', size: 98214, created_at: '2026-05-28' },
      { id: 3, filename: 'MRO 备件安全库存策略.docx', mimetype: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size: 145600, created_at: '2026-05-27' },
      { id: 4, filename: '长三角区域仓调拨 SOP.pdf', mimetype: 'application/pdf', size: 231420, created_at: '2026-05-26' }
    ]
  },
  content: {
    key: 'content',
    title: '公告与知识中心',
    eyebrow: '公告知识',
    description: '仓配制度、盘点公告、供应商协同文档和运营 SOP 统一维护。',
    endpoint: 'articles',
    searchPlaceholder: '搜索公告、SOP、制度',
    visual: 'studio',
    visualDensity: 'compact',
    heroVariant: 'knowledge-studio',
    storyBlocks: [
      { title: 'SOP 发布', metric: '制度', body: '仓配流程、盘点公告、风控规则统一维护。', tone: 'info' },
      { title: '附件联动', metric: '文件', body: '公告与文件中心共享分类、预览和发布反馈。', tone: 'success' },
      { title: '角色触达', metric: '通知', body: '发布后推送给仓库、采购、财务等角色。', tone: 'warning' }
    ],
    chips: ['公告', 'SOP', '制度', '协同'],
    actions: [
      { label: '新建公告', icon: 'pi-plus', kind: 'create', severity: 'primary' },
      { label: '刷新', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'status', label: '状态', type: 'status' },
      { key: 'created_at', label: '发布时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, title: '华东工厂仓月末盘点通知', category: '盘点公告', status: 'published', created_at: '2026-05-29' },
      { id: 2, title: '供应商 ASN 到货协同 SOP', category: '流程制度', status: 'draft', created_at: '2026-05-26' },
      { id: 3, title: 'MRO 备件紧急补货规则', category: '风控规则', status: 'published', created_at: '2026-05-25' },
      { id: 4, title: '客户信用冻结与解冻流程', category: '财务制度', status: 'published', created_at: '2026-05-22' }
    ]
  },
  security: {
    key: 'security',
    title: '系统安全中心',
    eyebrow: '系统安全',
    description: '用户、角色、权限矩阵、审计日志和登录风险统一展示。',
    endpoint: 'users',
    searchPlaceholder: '搜索用户、角色、部门',
    visual: 'security',
    visualDensity: 'balanced',
    heroVariant: 'security-matrix',
    storyBlocks: [
      { title: '权限矩阵', metric: '6 域', body: '库存、采购、收货、财务、报表、审计拆分授权。', tone: 'success' },
      { title: '登录风险', metric: 'Cookie', body: 'HttpOnly Cookie 与 CSRF 保护写请求。', tone: 'info' },
      { title: '审计覆盖', metric: '全链路', body: '审批、收货、收款、下载、用户管理均可追踪。', tone: 'warning' }
    ],
    chips: ['用户', '角色', '权限矩阵', '登录风险'],
    actions: [
      { label: '新增用户', icon: 'pi-user-plus', kind: 'create', severity: 'primary' },
      { label: '刷新审计', icon: 'pi-refresh', kind: 'refresh' }
    ],
    columns: [
      { key: 'username', label: '用户名' },
      { key: 'email', label: '邮箱' },
      { key: 'role_name', label: '角色' },
      { key: 'department_name_display', label: '部门' },
      { key: 'is_admin_effective', label: '管理员', type: 'status' }
    ],
    seedRows: [
      { id: 1, username: 'admin', email: 'admin@nexus.com', role_name: 'Admin', department_name_display: '数字化运营部', is_admin_effective: true },
      { id: 2, username: 'warehouse.lead', email: 'warehouse@nexus.com', role_name: '仓库主管', department_name_display: '华东工厂仓', is_admin_effective: false },
      { id: 3, username: 'procurement.ops', email: 'procurement@nexus.com', role_name: '采购执行', department_name_display: '采购补货部', is_admin_effective: false },
      { id: 4, username: 'finance.risk', email: 'finance@nexus.com', role_name: '应收风控', department_name_display: '应收风控组', is_admin_effective: false }
    ]
  },
  audit: {
    key: 'audit',
    title: '审计日志',
    eyebrow: '审计追踪',
    description: '关键动作、权限拒绝、文件访问和库存变更全部可追踪。',
    endpoint: 'audit-logs',
    searchPlaceholder: '搜索模块、动作、操作者',
    visual: 'security',
    visualDensity: 'compact',
    heroVariant: 'security-matrix',
    storyBlocks: [
      { title: '关键动作', metric: '审计', body: '库存、采购、财务、文件动作统一留痕。', tone: 'success' },
      { title: '权限拒绝', metric: '403', body: '越权尝试以安全错误码呈现。', tone: 'warning' },
      { title: '追踪对象', metric: 'ID', body: '每条日志关联用户、模块、动作和对象。', tone: 'info' }
    ],
    chips: ['登录', '库存', '财务', '文件'],
    actions: [{ label: '刷新审计', icon: 'pi-refresh', kind: 'refresh', severity: 'primary' }],
    columns: [
      { key: 'module', label: '模块' },
      { key: 'action', label: '动作' },
      { key: 'username', label: '操作者' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, module: 'procurement', action: 'approve', username: 'admin', created_at: '2026-05-29 10:33' },
      { id: 2, module: 'finance', action: 'record_payment', username: 'finance.ops', created_at: '2026-05-29 10:41' },
      { id: 3, module: 'inventory', action: 'stock_adjust', username: 'warehouse.lead', created_at: '2026-05-29 11:12' },
      { id: 4, module: 'files', action: 'download', username: 'procurement.ops', created_at: '2026-05-29 14:08' }
    ]
  },
  notifications: {
    key: 'notifications',
    title: '通知中心',
    eyebrow: '任务通知',
    description: '库存预警、审批、应收催款和报表生成状态集中触达。',
    endpoint: 'notifications',
    searchPlaceholder: '搜索通知',
    visual: 'timeline',
    visualDensity: 'compact',
    heroVariant: 'knowledge-studio',
    storyBlocks: [
      { title: '库存预警', metric: '7', body: '低库存自动触达仓库主管。', tone: 'warning' },
      { title: '审批提醒', metric: '4', body: '采购审批任务进入待办队列。', tone: 'info' },
      { title: '报表完成', metric: '日报', body: '生成完成后通知管理层。', tone: 'success' }
    ],
    chips: ['预警', '审批', '催款', '报表'],
    actions: [{ label: '全部已读', icon: 'pi-check', kind: 'domain', severity: 'primary' }],
    columns: [
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'is_read', label: '已读', type: 'status' },
      { key: 'created_at', label: '时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, title: 'MRO 备件包低于安全库存', category: '库存预警', is_read: false, created_at: '2026-05-29' },
      { id: 2, title: '采购单 PO-20260529-A118 待审批', category: '采购审批', is_read: false, created_at: '2026-05-29' },
      { id: 3, title: '华南新能源客户群应收逾期', category: '应收风控', is_read: false, created_at: '2026-05-29' },
      { id: 4, title: '制造仓配经营日报已生成', category: '报表', is_read: true, created_at: '2026-05-30' }
    ]
  },
  ai: {
    key: 'ai',
    title: '经营分析台',
    eyebrow: '经营分析',
    description: '围绕库存风险、补货建议和应收催款生成经营建议。',
    endpoint: 'ai-sessions',
    searchPlaceholder: '搜索会话',
    visual: 'studio',
    visualDensity: 'compact',
    heroVariant: 'knowledge-studio',
    storyBlocks: [
      { title: '异常摘要', metric: '分析', body: '汇总库存、采购、履约和应收异常。', tone: 'info' },
      { title: '行动草案', metric: '下一步', body: '生成补货、催款、审批说明等草案。', tone: 'success' },
      { title: '指标来源', metric: '可追溯', body: '建议引用业务对象和指标来源。', tone: 'warning' }
    ],
    chips: ['库存分析', '补货建议', '异常摘要', '行动草案'],
    actions: [{ label: '新建分析', icon: 'pi-sparkles', kind: 'create', severity: 'primary' }],
    columns: [
      { key: 'title', label: '会话' },
      { key: 'created_at', label: '创建时间', type: 'date' }
    ],
    seedRows: [
      { id: 1, title: '华东工厂仓低库存分析', created_at: '2026-05-29' },
      { id: 2, title: '逾期客户催款话术草案', created_at: '2026-05-28' },
      { id: 3, title: '采购审批停滞原因摘要', created_at: '2026-05-27' },
      { id: 4, title: '供应商准点率异常复盘', created_at: '2026-05-26' }
    ]
  },
  profile: {
    key: 'profile',
    title: '个人工作台',
    eyebrow: '个人工作台',
    description: '保存主题、密度和默认模块，让运营复盘和日常使用保持一致。',
    endpoint: 'me/preferences',
    searchPlaceholder: '搜索偏好',
    visual: 'security',
    visualDensity: 'compact',
    heroVariant: 'security-matrix',
    storyBlocks: [
      { title: '主题偏好', metric: '2 套', body: '深色驾驶舱和轻奢白色系统可切换。', tone: 'info' },
      { title: '默认模块', metric: '总览', body: '进入系统后优先展示运营总览。', tone: 'success' },
      { title: '最近动作', metric: '留痕', body: '保留最近审批、报表和应收动作。', tone: 'warning' }
    ],
    chips: ['主题', '密度', '默认模块'],
    actions: [{ label: '保存偏好', icon: 'pi-save', kind: 'domain', severity: 'primary' }],
    columns: [
      { key: 'name', label: '偏好' },
      { key: 'value', label: '值' }
    ],
    seedRows: [
      { id: 1, name: '主题', value: 'dark-cockpit / light-luxury' },
      { id: 2, name: '默认模块', value: '制造运营驾驶舱' },
      { id: 3, name: '数据密度', value: '紧凑表格 + 右侧洞察' },
      { id: 4, name: '最近动作', value: '审批采购、生成日报、查看应收' }
    ]
  }
};
