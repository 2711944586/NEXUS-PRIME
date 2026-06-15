import { DockGroup, ManufacturingCommandCenter, ServiceHealth } from '../core/models';
import { VisualAsset } from '../core/visual-assets';
import { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';

export type WorkflowSignal = {
  label: string;
  value: string;
  caption: string;
  path: string;
  tone: 'default' | 'success' | 'warning' | 'danger' | 'info';
};

export type ShiftHandoffAction = {
  label: string;
  metric: string;
  owner: string;
  due: string;
  evidence: string;
  path: string;
  priority: 'P0' | 'P1' | 'P2';
  tone: 'default' | 'success' | 'warning' | 'danger' | 'info';
};

export type WorkflowEvidenceTile = {
  photo: VisualAsset;
  stage: WorkflowStage;
};

export const EMPTY_COMMAND_CENTER: ManufacturingCommandCenter = {
  kpis: {
    order_amount: 0,
    stock_quantity: 0,
    low_stock_products: 0,
    pending_purchase: 0,
    overdue_amount: 0
  },
  warehouse_heat: [],
  flows: [],
  risks: []
};

export const EMPTY_SERVICE_HEALTH: ServiceHealth = {
  status: 'down',
  service: 'NEXUS API',
  api_base: '/api/v1',
  latency_ms: 0,
  database: { status: 'not_checked' },
  ai: {
    status: 'not_configured',
    local_enabled: false,
    external_configured: false,
    provider: 'openai-compatible',
    base_url: '',
    model: ''
  },
  storage: {
    status: 'local',
    cloud_configured: false,
    cloud_required: false,
    requirement: 'auto',
    folders: {},
    writable: {}
  },
  checks: {
    database: false,
    ai: false,
    storage: true
  }
};

const WORKFLOW_EVIDENCE_PHOTO_INDEXES: Record<string, number[]> = {
  'operations-flow': [25, 26, 27],
  'warehouse-flow': [26, 25, 27],
  'supply-flow': [27, 25, 26],
  'fulfillment-flow': [25, 26, 27],
  'finance-flow': [27, 25, 26],
  'insight-flow': [25, 27, 26]
};

const PAGE_EVIDENCE_PHOTO_INDEXES: Record<string, number[]> = {
  'operations-flow': [0, 2, 4, 11],
  'warehouse-flow': [1, 7, 9, 21],
  'supply-flow': [6, 14, 10, 2],
  'fulfillment-flow': [8, 12, 19, 16],
  'finance-flow': [3, 16, 20, 11],
  'insight-flow': [17, 18, 13, 4]
};

export function normalizeServiceHealth(value: Partial<ServiceHealth> | null | undefined): ServiceHealth {
  return {
    ...EMPTY_SERVICE_HEALTH,
    ...(value ?? {}),
    database: {
      ...EMPTY_SERVICE_HEALTH.database,
      ...(value?.database ?? {})
    },
    ai: {
      ...EMPTY_SERVICE_HEALTH.ai,
      ...(value?.ai ?? {})
    },
    storage: {
      ...EMPTY_SERVICE_HEALTH.storage,
      ...(value?.storage ?? {}),
      folders: {
        ...EMPTY_SERVICE_HEALTH.storage.folders,
        ...(value?.storage?.folders ?? {})
      },
      writable: {
        ...EMPTY_SERVICE_HEALTH.storage.writable,
        ...(value?.storage?.writable ?? {})
      }
    },
    checks: {
      ...EMPTY_SERVICE_HEALTH.checks,
      ...(value?.checks ?? {})
    }
  };
}

export function compactMoney(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(value || 0);
}

export function compactNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(value || 0);
}

export function userInitials(user: { full_name?: string | null; username?: string | null; email?: string | null }): string {
  const name = (user.full_name || user.username || user.email || 'NX').trim();
  return name.replace(/\s+/g, '').slice(0, 2).toUpperCase();
}

export function riskPath(risk: ManufacturingCommandCenter['risks'][number]): string {
  if (risk.type.includes('应收')) {
    return '/app/finance/receivables';
  }
  if (risk.type.includes('采购')) {
    return '/app/procurement/orders';
  }
  return '/app/inventory/replenishment';
}

export function calculateShellHealth(commandData: ManufacturingCommandCenter): number {
  const kpis = commandData.kpis;
  const pressure = Math.min(38, kpis.low_stock_products * 2 + kpis.pending_purchase * 2 + Math.round(kpis.overdue_amount / 110000));
  return Math.max(60, 98 - pressure);
}

export function serviceHealthLabel(health: ServiceHealth): string {
  if (health.status === 'ok') {
    return '服务正常';
  }
  if (health.status === 'degraded') {
    return '服务关注';
  }
  return '服务异常';
}

export function serviceHealthLatencyLabel(health: ServiceHealth): string {
  const apiLatency = health.latency_ms ? `${health.latency_ms}ms` : '检测中';
  const dbLatency = health.database?.latency_ms !== undefined ? `DB ${health.database.latency_ms}ms` : 'DB -';
  return `${apiLatency} / ${dbLatency}`;
}

export function serviceHealthTooltip(health: ServiceHealth): string {
  const ai = health.ai.external_configured ? `${health.ai.model || '外部模型'} 已配置` : health.ai.local_enabled ? '本地分析可用' : 'AI 未配置';
  const storage = health.storage.status === 'cloud' ? '云存储' : health.storage.status === 'missing_cloud' ? '缺少云存储' : '本地存储';
  return `API ${health.status} · 数据库 ${health.database.status} · ${ai} · ${storage}`;
}

export function buildWorkflowSignals(commandData: ManufacturingCommandCenter, workflow: WorkflowBlueprint): WorkflowSignal[] {
  const kpis = commandData.kpis;
  const flows = commandData.flows;
  const fulfillmentCount = flows[flows.length - 1]?.value ?? 0;
  const lowStockTone = kpis.low_stock_products > 0 ? 'warning' : 'success';
  const purchaseTone = kpis.pending_purchase > 0 ? 'warning' : 'success';
  const receivableTone = kpis.overdue_amount > 0 ? 'danger' : 'success';
  const compactOverdue = compactMoney(kpis.overdue_amount);
  const compactStock = compactNumber(kpis.stock_quantity);

  switch (workflow.key) {
    case 'warehouse-flow':
      return [
        { label: '库存水位', value: compactStock, caption: '复核库位与低库存', path: '/app/inventory/products', tone: lowStockTone },
        { label: '低库存', value: `${kpis.low_stock_products} 项`, caption: '生成补货建议', path: '/app/inventory/replenishment', tone: lowStockTone },
        { label: '现场盘点', value: '扫码', caption: '盘点差异入审计', path: '/app/stocktakes', tone: 'info' }
      ];
    case 'supply-flow':
      return [
        { label: '补货建议', value: `${kpis.low_stock_products} 项`, caption: '低库存转采购', path: '/app/inventory/replenishment', tone: lowStockTone },
        { label: '待审批', value: `${kpis.pending_purchase} 单`, caption: '审批后进入收货', path: '/app/procurement/orders', tone: purchaseTone },
        { label: '供应商', value: '评分', caption: '到货结果回写绩效', path: '/app/suppliers/performance', tone: 'success' }
      ];
    case 'fulfillment-flow':
      return [
        { label: '履约单', value: `${fulfillmentCount} 单`, caption: '发货和签收推进', path: '/app/sales/orders', tone: fulfillmentCount > 0 ? 'warning' : 'success' },
        { label: '应收风险', value: compactOverdue, caption: '发货后回款跟进', path: '/app/finance/receivables', tone: receivableTone },
        { label: '客户服务', value: '回访', caption: '售后工单和资料归档', path: '/app/service', tone: 'info' }
      ];
    case 'finance-flow':
      return [
        { label: '未收压力', value: compactOverdue, caption: '催款与收款回写', path: '/app/finance/receivables', tone: receivableTone },
        { label: '信用控制', value: '额度', caption: '冻结和释放客户额度', path: '/app/finance/credits', tone: receivableTone },
        { label: '经营报表', value: '归档', caption: '输出现金与账龄报告', path: '/app/reports', tone: 'success' }
      ];
    case 'insight-flow':
      return [
        { label: '风险队列', value: `${commandData.risks.length} 条`, caption: '分析建议转动作', path: '/app/ai', tone: commandData.risks.length ? 'warning' : 'success' },
        { label: '数据质量', value: '体检', caption: '接口与主数据复核', path: '/app/data-quality', tone: 'info' },
        { label: '审计追溯', value: '日志', caption: '文件、规则和动作留痕', path: '/app/system/audit', tone: 'success' }
      ];
    default:
      return [
        { label: '低库存', value: `${kpis.low_stock_products} 项`, caption: '进入补货队列', path: '/app/inventory/replenishment', tone: lowStockTone },
        { label: '采购审批', value: `${kpis.pending_purchase} 单`, caption: '推进收货入库', path: '/app/procurement/orders', tone: purchaseTone },
        { label: '逾期应收', value: compactOverdue, caption: '回款释放信用', path: '/app/finance/receivables', tone: receivableTone }
      ];
  }
}

export function nextWorkflowSteps(workflow: WorkflowBlueprint, activeStage: WorkflowStage): WorkflowStage[] {
  const index = Math.max(0, workflow.stages.findIndex(stage => stage.key === activeStage.key));
  return [...workflow.stages.slice(index + 1), ...workflow.stages.slice(0, index)].slice(0, 3);
}

export function workflowEvidenceTiles(workflow: WorkflowBlueprint, photos: VisualAsset[]): WorkflowEvidenceTile[] {
  return evidenceTiles(workflow, photos, WORKFLOW_EVIDENCE_PHOTO_INDEXES[workflow.key] ?? WORKFLOW_EVIDENCE_PHOTO_INDEXES['operations-flow']);
}

export function pageEvidenceTiles(workflow: WorkflowBlueprint, photos: VisualAsset[]): WorkflowEvidenceTile[] {
  return evidenceTiles(workflow, photos, PAGE_EVIDENCE_PHOTO_INDEXES[workflow.key] ?? PAGE_EVIDENCE_PHOTO_INDEXES['operations-flow']);
}

export function buildShiftHandoffActions(
  workflow: WorkflowBlueprint,
  signals: WorkflowSignal[],
  stages: WorkflowStage[]
): ShiftHandoffAction[] {
  const ownerMap: Record<string, string[]> = {
    'operations-flow': ['运营经理', '仓配主管', '财务BP'],
    'warehouse-flow': ['仓配主管', '补货计划员', '盘点班长'],
    'supply-flow': ['采购经理', '质检主管', '供应商协同'],
    'fulfillment-flow': ['履约调度', '客户经理', '财务BP'],
    'finance-flow': ['应收会计', '信用控制', '经营分析'],
    'insight-flow': ['数据治理', '接口负责人', '系统管理员']
  };
  const dueMap = ['10:30 前', '14:00 前', '17:30 前'];
  const owners = ownerMap[workflow.key] ?? ownerMap['operations-flow'];

  return stages.map((stage, index) => {
    const signal = signals[index] ?? signals[signals.length - 1];
    const priority: ShiftHandoffAction['priority'] =
      stage.tone === 'danger' || signal?.tone === 'danger'
        ? 'P0'
        : stage.tone === 'warning' || signal?.tone === 'warning'
          ? 'P1'
          : 'P2';
    return {
      label: `${stage.label}交接`,
      metric: stage.metric,
      owner: owners[index] ?? owners[0],
      due: dueMap[index] ?? dueMap[dueMap.length - 1],
      evidence: signal ? `${signal.label} ${signal.value}` : `${workflow.title} ${stage.metric}`,
      path: stage.path,
      priority,
      tone: stage.tone
    };
  });
}

export function moduleEntryCount(groups: DockGroup[]): number {
  return groups.reduce((total, group) => total + group.items.length, 0);
}

function evidenceTiles(workflow: WorkflowBlueprint, photos: VisualAsset[], indexes: number[]): WorkflowEvidenceTile[] {
  return indexes.map((photoIndex, index) => ({
    photo: photos[photoIndex] ?? photos[0],
    stage: workflow.stages[index % workflow.stages.length] ?? workflow.stages[0]
  }));
}
