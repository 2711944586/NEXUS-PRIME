import { OPERATIONS_VISUALS } from './visual-assets';
import type { VisualAsset } from './visual-assets';

export interface WorkflowStage {
  key: string;
  label: string;
  path: string;
  metric: string;
  tone: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export interface WorkflowBlueprint {
  key: string;
  title: string;
  summary: string;
  photo: VisualAsset;
  stages: WorkflowStage[];
}

const OPERATIONS_FLOW: WorkflowBlueprint = {
  key: 'operations-flow',
  title: '制造经营闭环',
  summary: '低库存、采购、收货、履约、回款、报表和审计串成每日作业链。',
  photo: {
    src: OPERATIONS_VISUALS.analyticsMeeting,
    alt: '经营团队围绕数据屏幕复盘',
    label: '控制塔',
    caption: '跨模块经营节奏'
  },
  stages: [
    { key: 'overview', label: '总览', path: '/app/overview', metric: '经营指标', tone: 'info' },
    { key: 'materials', label: '物料', path: '/app/inventory/products', metric: '水位复核', tone: 'warning' },
    { key: 'procurement', label: '采购', path: '/app/procurement/orders', metric: '审批收货', tone: 'warning' },
    { key: 'fulfillment', label: '履约', path: '/app/sales/orders', metric: '发货出库', tone: 'success' },
    { key: 'receivables', label: '回款', path: '/app/finance/receivables', metric: '信用释放', tone: 'danger' },
    { key: 'reports', label: '归档', path: '/app/reports', metric: '经营日报', tone: 'success' }
  ]
};

const WAREHOUSE_FLOW: WorkflowBlueprint = {
  key: 'warehouse-flow',
  title: '仓配现场闭环',
  summary: '库位水位、补货建议、移动扫码、盘点差异和库存流水在同一条线上推进。',
  photo: {
    src: OPERATIONS_VISUALS.warehouseTeam,
    alt: '仓库人员在货架通道协作拣货',
    label: '仓配现场',
    caption: '库位、扫码与库存复核'
  },
  stages: [
    { key: 'materials', label: '物料水位', path: '/app/inventory/products', metric: 'SKU', tone: 'warning' },
    { key: 'flow', label: '仓配流向', path: '/app/inventory/stock', metric: '库位', tone: 'info' },
    { key: 'replenishment', label: '补货建议', path: '/app/inventory/replenishment', metric: '建议量', tone: 'warning' },
    { key: 'mobile', label: '移动扫码', path: '/app/mobile-terminal', metric: '现场任务', tone: 'info' },
    { key: 'stocktake', label: '盘点调整', path: '/app/stocktakes', metric: '差异', tone: 'success' }
  ]
};

const SUPPLY_FLOW: WorkflowBlueprint = {
  key: 'supply-flow',
  title: '采购到货闭环',
  summary: '补货建议生成采购草稿，审批后进入到货、质检、收货和供应商绩效回写。',
  photo: {
    src: OPERATIONS_VISUALS.qualityInspection,
    alt: '质检人员复核工业部件',
    label: '质量现场',
    caption: '采购到货、质检和验收入库'
  },
  stages: [
    { key: 'replenishment', label: '建议', path: '/app/inventory/replenishment', metric: '低库存', tone: 'warning' },
    { key: 'procurement', label: '采购', path: '/app/procurement/orders', metric: '审批', tone: 'warning' },
    { key: 'quality', label: '质检', path: '/app/quality', metric: '来料检验', tone: 'info' },
    { key: 'receive', label: '收货', path: '/app/procurement/orders', metric: '入库', tone: 'success' },
    { key: 'supplier', label: '绩效', path: '/app/suppliers/performance', metric: '评分', tone: 'success' }
  ]
};

const FULFILLMENT_FLOW: WorkflowBlueprint = {
  key: 'fulfillment-flow',
  title: '订单履约闭环',
  summary: '客户订单经过信用校验、库存锁定、发货、签收、应收和客户复盘。',
  photo: {
    src: OPERATIONS_VISUALS.forkliftDock,
    alt: '仓库叉车与发货装卸区',
    label: '履约月台',
    caption: '出库、分拨和客户交付'
  },
  stages: [
    { key: 'customers', label: '客户', path: '/app/customers', metric: '画像', tone: 'info' },
    { key: 'orders', label: '订单', path: '/app/sales/orders', metric: '发货', tone: 'warning' },
    { key: 'dispatch', label: '调度', path: '/app/dispatch', metric: '月台', tone: 'info' },
    { key: 'receivables', label: '应收', path: '/app/finance/receivables', metric: '回款', tone: 'danger' },
    { key: 'service', label: '服务', path: '/app/service', metric: '工单', tone: 'success' }
  ]
};

const FINANCE_FLOW: WorkflowBlueprint = {
  key: 'finance-flow',
  title: '现金与信用闭环',
  summary: '发货后的应收进入账龄墙，回款释放信用额度，异常客户进入催款和合同复核。',
  photo: {
    src: OPERATIONS_VISUALS.financeDashboard,
    alt: '财务报表与回款分析工作台',
    label: '财务现场',
    caption: '应收、信用与现金流'
  },
  stages: [
    { key: 'receivables', label: '应收', path: '/app/finance/receivables', metric: '账龄', tone: 'danger' },
    { key: 'credits', label: '信用', path: '/app/finance/credits', metric: '额度', tone: 'warning' },
    { key: 'contracts', label: '合同', path: '/app/contracts', metric: '回款窗口', tone: 'info' },
    { key: 'budget', label: '成本', path: '/app/budget', metric: '现金缺口', tone: 'warning' },
    { key: 'reports', label: '报表', path: '/app/reports', metric: '归档', tone: 'success' }
  ]
};

const INSIGHT_FLOW: WorkflowBlueprint = {
  key: 'insight-flow',
  title: '分析治理闭环',
  summary: '经营分析、规则、接口、数据质量、文件和审计把问题定位到可执行动作。',
  photo: {
    src: OPERATIONS_VISUALS.integrationMonitor,
    alt: '数据监控屏幕和接口运行图表',
    label: '分析现场',
    caption: '规则、接口、文件和审计复盘'
  },
  stages: [
    { key: 'ai', label: '分析', path: '/app/ai', metric: '建议', tone: 'info' },
    { key: 'rules', label: '规则', path: '/app/rules', metric: '命中', tone: 'warning' },
    { key: 'integrations', label: '集成', path: '/app/integrations', metric: '同步', tone: 'info' },
    { key: 'data', label: '质量', path: '/app/data-quality', metric: '体检', tone: 'warning' },
    { key: 'audit', label: '审计', path: '/app/system/audit', metric: '追溯', tone: 'success' }
  ]
};

export function workflowForUrl(url: string): WorkflowBlueprint {
  if (url.includes('/inventory') || url.includes('/stocktakes') || url.includes('/mobile-terminal')) {
    return WAREHOUSE_FLOW;
  }
  if (url.includes('/procurement') || url.includes('/suppliers') || url.includes('/quality')) {
    return SUPPLY_FLOW;
  }
  if (url.includes('/sales') || url.includes('/customers') || url.includes('/dispatch') || url.includes('/service')) {
    return FULFILLMENT_FLOW;
  }
  if (url.includes('/finance') || url.includes('/contracts') || url.includes('/budget')) {
    return FINANCE_FLOW;
  }
  if (url.includes('/ai') || url.includes('/reports') || url.includes('/rules') || url.includes('/integrations') || url.includes('/data-quality') || url.includes('/files') || url.includes('/content') || url.includes('/system')) {
    return INSIGHT_FLOW;
  }
  return OPERATIONS_FLOW;
}

export function activeWorkflowStage(workflow: WorkflowBlueprint, url: string): WorkflowStage {
  return workflow.stages.find(stage => url === stage.path || url.startsWith(`${stage.path}/`)) ?? workflow.stages[0];
}
