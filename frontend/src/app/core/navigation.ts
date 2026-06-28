import { DockGroup, DockItem } from './models';

export interface DockGroupMeta {
  key: DockItem['dockGroup'];
  label: string;
  tone: string;
  summary: string;
}

export interface NavigationBreadcrumb {
  key: string;
  label: string;
  path?: string;
}

export interface NavigationState {
  url: string;
  activeItem: DockItem;
  activeGroup: DockGroupMeta;
  siblings: DockItem[];
  breadcrumbs: NavigationBreadcrumb[];
  inPrimaryDock: boolean;
}

export const DESKTOP_DOCK_KEYS = [
  'overview',
  'materials',
  'flow',
  'procurement',
  'quality-inspection',
  'fulfillment',
  'receivables',
  'reports'
] as const;

export const COMPACT_DOCK_KEYS = [
  'overview',
  'materials',
  'flow',
  'procurement',
  'quality-inspection',
  'fulfillment',
  'receivables',
  'reports'
] as const;

export const MOBILE_DOCK_KEYS = [
  'overview',
  'materials',
  'flow',
  'procurement',
  'quality-inspection',
  'fulfillment',
  'receivables',
  'reports'
] as const;

export const DOCK_GROUP_ORDER: DockItem['dockGroup'][] = [
  'operations',
  'warehouse',
  'supply',
  'fulfillment',
  'finance',
  'insight',
  'collaboration',
  'security',
  'personal'
];

export const DOCK_ITEMS: DockItem[] = [
  {
    key: 'overview',
    label: '制造运营驾驶舱',
    shortLabel: '运营',
    path: '/app/overview',
    icon: 'gauge',
    group: '运营',
    dockGroup: 'operations',
    accent: '#62d8cb',
    quickActions: [
      { label: '补货建议', path: '/app/inventory/replenishment' },
      { label: '采购审批', path: '/app/procurement/orders' }
    ]
  },
  {
    key: 'materials',
    label: '物料与成品中心',
    shortLabel: '物料',
    path: '/app/inventory/products',
    activePaths: ['/app/inventory/products'],
    icon: 'boxes',
    group: '仓配',
    dockGroup: 'warehouse',
    accent: '#9aa8ff',
    quickActions: [
      { label: '查看水位', path: '/app/inventory/products' },
      { label: '仓配流向', path: '/app/inventory/stock' }
    ]
  },
  {
    key: 'flow',
    label: '仓配流向图',
    shortLabel: '流向',
    path: '/app/inventory/stock',
    activePaths: ['/app/inventory/stock'],
    icon: 'network',
    group: '仓配',
    dockGroup: 'warehouse',
    accent: '#67d19b',
    quickActions: [
      { label: '库存调整', path: '/app/inventory/stock' },
      { label: '低库存', path: '/app/inventory/replenishment' }
    ]
  },
  {
    key: 'procurement',
    label: '采购补货中心',
    shortLabel: '采购',
    path: '/app/procurement/orders',
    activePaths: ['/app/procurement/orders', '/app/inventory/replenishment'],
    icon: 'shopping-cart',
    group: '供应',
    dockGroup: 'supply',
    accent: '#f0b76a',
    quickActions: [
      { label: '补货建议', path: '/app/inventory/replenishment' },
      { label: '收货进度', path: '/app/procurement/orders' }
    ]
  },
  {
    key: 'fulfillment',
    label: '销售履约中心',
    shortLabel: '履约',
    path: '/app/sales/orders',
    activePaths: ['/app/sales'],
    icon: 'send',
    group: '履约',
    dockGroup: 'fulfillment',
    accent: '#62d8cb',
    quickActions: [
      { label: '履约队列', path: '/app/sales/orders' },
      { label: '应收风控', path: '/app/finance/receivables' }
    ]
  },
  {
    key: 'stocktake',
    label: '库存盘点中心',
    shortLabel: '盘点',
    path: '/app/stocktakes',
    activePaths: ['/app/stocktakes'],
    icon: 'scan-line',
    group: '履约',
    dockGroup: 'fulfillment',
    accent: '#8fd3ff',
    quickActions: [
      { label: '扫码录入', path: '/app/stocktakes' },
      { label: '审计日志', path: '/app/system/audit' }
    ]
  },
  {
    key: 'receivables',
    label: '应收风控中心',
    shortLabel: '应收',
    path: '/app/finance/receivables',
    activePaths: ['/app/finance/receivables', '/app/finance/credits'],
    icon: 'shield-alert',
    group: '财务',
    dockGroup: 'finance',
    accent: '#ff8fa3',
    quickActions: [
      { label: '收款', path: '/app/finance/receivables' },
      { label: '信用额度', path: '/app/finance/credits' }
    ]
  },
  {
    key: 'reports',
    label: '报表工作室',
    shortLabel: '报表',
    path: '/app/reports',
    activePaths: ['/app/reports'],
    icon: 'bar-chart-3',
    group: '分析',
    dockGroup: 'insight',
    accent: '#c5a8ff',
    quickActions: [
      { label: '经营日报', path: '/app/reports' },
      { label: '导出文件', path: '/app/files' }
    ]
  },
  {
    key: 'ai',
    label: '经营分析台',
    shortLabel: '分析',
    path: '/app/ai',
    icon: 'sparkles',
    group: '分析',
    dockGroup: 'insight',
    accent: '#c5a8ff',
    quickActions: [
      { label: '风险诊断', path: '/app/ai' },
      { label: '经营报表', path: '/app/reports' }
    ]
  },
  {
    key: 'notifications',
    label: '通知中心',
    shortLabel: '通知',
    path: '/app/notifications',
    icon: 'bell',
    group: '协作',
    dockGroup: 'collaboration',
    accent: '#62d8cb',
    quickActions: [
      { label: '全部通知', path: '/app/notifications' },
      { label: '审计日志', path: '/app/system/audit' }
    ]
  },
  {
    key: 'files',
    label: '文件与内容中心',
    shortLabel: '文件',
    path: '/app/files',
    activePaths: ['/app/files', '/app/content/articles'],
    icon: 'folder-open',
    group: '协作',
    dockGroup: 'collaboration',
    accent: '#ffd166',
    quickActions: [
      { label: '文件上传', path: '/app/files' },
      { label: '公告知识', path: '/app/content/articles' }
    ]
  },
  {
    key: 'security',
    label: '系统安全中心',
    shortLabel: '安全',
    path: '/app/system/users',
    activePaths: ['/app/system/users', '/app/system/audit'],
    icon: 'lock-keyhole',
    group: '安全',
    dockGroup: 'security',
    accent: '#8da2ff',
    quickActions: [
      { label: '用户权限', path: '/app/system/users' },
      { label: '审计日志', path: '/app/system/audit' }
    ]
  },
  {
    key: 'settings',
    label: '全局设置中心',
    shortLabel: '设置',
    path: '/app/settings',
    icon: 'settings-2',
    group: '个人',
    dockGroup: 'personal',
    accent: '#0f8f86',
    quickActions: [
      { label: 'AI 服务设置', path: '/app/ai' },
      { label: '个人偏好', path: '/app/profile' }
    ]
  }
];

export const MORE_DOCK_ITEMS: DockItem[] = [
  {
    key: 'metrics',
    label: '经营指标中心',
    shortLabel: '指标',
    path: '/app/metrics',
    activePaths: ['/app/metrics'],
    icon: 'bar-chart-3',
    group: '运营',
    dockGroup: 'operations',
    accent: '#2ca59d',
    quickActions: [
      { label: '查看效率', path: '/app/metrics' },
      { label: '报表归档', path: '/app/reports' }
    ]
  },
  {
    key: 'tasks',
    label: '任务异常中心',
    shortLabel: '任务',
    path: '/app/tasks',
    activePaths: ['/app/tasks'],
    icon: 'shield-alert',
    group: '运营',
    dockGroup: 'operations',
    accent: '#d99135',
    quickActions: [
      { label: '异常泳道', path: '/app/tasks' },
      { label: '通知中心', path: '/app/notifications' }
    ]
  },
  {
    key: 'customers',
    label: '客户经营中心',
    shortLabel: '客户',
    path: '/app/customers',
    activePaths: ['/app/customers'],
    icon: 'user-round',
    group: '履约',
    dockGroup: 'fulfillment',
    accent: '#5fa8ff',
    quickActions: [
      { label: '客户画像', path: '/app/customers' },
      { label: '应收风控', path: '/app/finance/receivables' }
    ]
  },
  {
    key: 'capacity',
    label: '产能计划中心',
    shortLabel: '计划',
    path: '/app/capacity',
    activePaths: ['/app/capacity'],
    icon: 'bar-chart-3',
    group: '运营',
    dockGroup: 'operations',
    accent: '#67d19b',
    quickActions: [
      { label: '产能负载', path: '/app/capacity' },
      { label: '采购补货', path: '/app/procurement/orders' }
    ]
  },
  {
    key: 'maintenance',
    label: '设备维护中心',
    shortLabel: '设备',
    path: '/app/maintenance',
    activePaths: ['/app/maintenance'],
    icon: 'scan-line',
    group: '运营',
    dockGroup: 'operations',
    accent: '#f0b76a',
    quickActions: [
      { label: '维护工单', path: '/app/maintenance' },
      { label: '文件归档', path: '/app/files' }
    ]
  },
  {
    key: 'supplier-performance',
    label: '供应商绩效中心',
    shortLabel: '供应',
    path: '/app/suppliers/performance',
    icon: 'shopping-cart',
    group: '供应',
    dockGroup: 'supply',
    accent: '#f0b76a',
    quickActions: [
      { label: '供应商评分', path: '/app/suppliers/performance' },
      { label: '采购审批', path: '/app/procurement/orders' }
    ]
  },
  {
    key: 'dispatch',
    label: '仓配调度中心',
    shortLabel: '调度',
    path: '/app/dispatch',
    icon: 'network',
    group: '仓配',
    dockGroup: 'warehouse',
    accent: '#67d19b',
    quickActions: [
      { label: '生成调度任务', path: '/app/dispatch' },
      { label: '仓配流向', path: '/app/inventory/stock' }
    ]
  },
  {
    key: 'data-quality',
    label: '数据质量中心',
    shortLabel: '质量',
    path: '/app/data-quality',
    icon: 'shield-alert',
    group: '分析',
    dockGroup: 'insight',
    accent: '#8fd3ff',
    quickActions: [
      { label: '质量体检', path: '/app/data-quality' },
      { label: '审计日志', path: '/app/system/audit' }
    ]
  },
  {
    key: 'quality-inspection',
    label: '质量检验中心',
    shortLabel: '质检',
    path: '/app/quality',
    icon: 'shield-alert',
    group: '供应',
    dockGroup: 'supply',
    accent: '#55c7a6',
    quickActions: [
      { label: '来料检验', path: '/app/quality' },
      { label: '供应商表现', path: '/app/suppliers/performance' }
    ]
  },
  {
    key: 'contracts',
    label: '合同回款中心',
    shortLabel: '合同',
    path: '/app/contracts',
    icon: 'circle-dollar-sign',
    group: '财务',
    dockGroup: 'finance',
    accent: '#ff8fa3',
    quickActions: [
      { label: '回款窗口', path: '/app/contracts' },
      { label: '应收风控', path: '/app/finance/receivables' }
    ]
  },
  {
    key: 'service',
    label: '售后服务中心',
    shortLabel: '服务',
    path: '/app/service',
    icon: 'sparkles',
    group: '协作',
    dockGroup: 'collaboration',
    accent: '#8fd3ff',
    quickActions: [
      { label: '服务工单', path: '/app/service' },
      { label: '客户经营', path: '/app/customers' }
    ]
  },
  {
    key: 'rules',
    label: '规则引擎中心',
    shortLabel: '规则',
    path: '/app/rules',
    icon: 'shield-alert',
    group: '分析',
    dockGroup: 'insight',
    accent: '#8fd3ff',
    quickActions: [
      { label: '规则复核', path: '/app/rules' },
      { label: '审计回放', path: '/app/system/audit' }
    ]
  },
  {
    key: 'integrations',
    label: '集成监控中心',
    shortLabel: '集成',
    path: '/app/integrations',
    icon: 'network',
    group: '安全',
    dockGroup: 'security',
    accent: '#8da2ff',
    quickActions: [
      { label: '接口状态', path: '/app/integrations' },
      { label: '数据质量', path: '/app/data-quality' }
    ]
  },
  {
    key: 'budget',
    label: '预算成本中心',
    shortLabel: '成本',
    path: '/app/budget',
    icon: 'circle-dollar-sign',
    group: '财务',
    dockGroup: 'finance',
    accent: '#ff8fa3',
    quickActions: [
      { label: '成本复核', path: '/app/budget' },
      { label: '报表归档', path: '/app/reports' }
    ]
  },
  {
    key: 'mobile-terminal',
    label: '移动扫码终端',
    shortLabel: '扫码',
    path: '/app/mobile-terminal',
    icon: 'scan-line',
    group: '仓配',
    dockGroup: 'warehouse',
    accent: '#67d19b',
    quickActions: [
      { label: '扫码任务', path: '/app/mobile-terminal' },
      { label: '盘点中心', path: '/app/stocktakes' }
    ]
  },
  {
    key: 'profile',
    label: '个人工作台',
    shortLabel: '我的',
    path: '/app/profile',
    icon: 'user-round',
    group: '个人',
    dockGroup: 'personal',
    accent: '#9aa8ff',
    quickActions: [{ label: '偏好设置', path: '/app/profile' }]
  },
  {
    key: 'credits',
    label: '信用额度中心',
    shortLabel: '信用',
    path: '/app/finance/credits',
    activePaths: ['/app/finance/credits'],
    icon: 'circle-dollar-sign',
    group: '财务',
    dockGroup: 'finance',
    accent: '#e05d78',
    quickActions: [
      { label: '额度复核', path: '/app/finance/credits' },
      { label: '应收风控', path: '/app/finance/receivables' }
    ]
  },
  {
    key: 'content',
    label: '公告知识中心',
    shortLabel: '公告',
    path: '/app/content/articles',
    activePaths: ['/app/content/articles'],
    icon: 'folder-open',
    group: '协作',
    dockGroup: 'collaboration',
    accent: '#d99f2b',
    quickActions: [
      { label: '公告知识', path: '/app/content/articles' },
      { label: '文件资料', path: '/app/files' }
    ]
  },
  {
    key: 'audit',
    label: '审计日志中心',
    shortLabel: '审计',
    path: '/app/system/audit',
    activePaths: ['/app/system/audit'],
    icon: 'lock-keyhole',
    group: '安全',
    dockGroup: 'security',
    accent: '#6f86ff',
    quickActions: [
      { label: '审计日志', path: '/app/system/audit' },
      { label: '用户权限', path: '/app/system/users' }
    ]
  }
];

export const DOCK_GROUP_LABELS: Record<DockItem['dockGroup'], DockGroupMeta> = {
  operations: { key: 'operations', label: '运营', tone: '#62d8cb', summary: '经营指标、异常任务、产能和设备状态' },
  warehouse: { key: 'warehouse', label: '仓配', tone: '#9aa8ff', summary: '物料水位、库存流向、盘点和扫码任务' },
  supply: { key: 'supply', label: '供应', tone: '#f0b76a', summary: '补货、采购、供应商绩效与来料质量' },
  fulfillment: { key: 'fulfillment', label: '履约', tone: '#8fd3ff', summary: '销售订单、客户、发货调度与交付服务' },
  finance: { key: 'finance', label: '财务', tone: '#ff8fa3', summary: '应收、信用、合同回款和预算成本' },
  insight: { key: 'insight', label: '分析', tone: '#c5a8ff', summary: '报表、AI 分析、规则、数据质量和接口监控' },
  collaboration: { key: 'collaboration', label: '协作', tone: '#ffd166', summary: '通知、文件、公告知识和服务工单' },
  security: { key: 'security', label: '安全', tone: '#8da2ff', summary: '用户权限、审计追溯和系统边界' },
  personal: { key: 'personal', label: '个人', tone: '#9aa8ff', summary: '个人工作台和全局偏好设置' }
};

export const ALL_DOCK_ITEMS: DockItem[] = [...DOCK_ITEMS, ...MORE_DOCK_ITEMS];

export function groupedDockItems(items: DockItem[] = DOCK_ITEMS): DockGroup[] {
  const itemsByGroup = new Map<DockItem['dockGroup'], DockItem[]>();
  for (const item of items) {
    const groupItems = itemsByGroup.get(item.dockGroup) ?? [];
    groupItems.push(item);
    itemsByGroup.set(item.dockGroup, groupItems);
  }
  return DOCK_GROUP_ORDER
    .filter(key => itemsByGroup.has(key))
    .map(key => {
      const meta = DOCK_GROUP_LABELS[key];
      return { key, label: meta.label, tone: meta.tone, summary: meta.summary, items: itemsByGroup.get(key) ?? [] };
    });
}

export function dockItemsByKeys(keys: readonly string[]): DockItem[] {
  const order = new Map(keys.map((key, index) => [key, index]));
  return ALL_DOCK_ITEMS
    .filter(item => order.has(item.key))
    .sort((a, b) => (order.get(a.key) ?? 0) - (order.get(b.key) ?? 0));
}

export function dockItemForUrl(url: string): DockItem {
  return navigationStateForUrl(url).activeItem;
}

export function dockItemMatchesUrl(item: DockItem, url: string): boolean {
  return matchingScore(item, normalizeNavigationUrl(url)) > 0;
}

export function navigationStateForUrl(url: string): NavigationState {
  const normalizedUrl = normalizeNavigationUrl(url);
  const activeItem = resolveActiveItem(normalizedUrl);
  const activeGroup = DOCK_GROUP_LABELS[activeItem.dockGroup];
  const siblings = ALL_DOCK_ITEMS.filter(item => item.dockGroup === activeItem.dockGroup);
  const inPrimaryDock = DOCK_ITEMS.some(item => item.key === activeItem.key);

  return {
    url: normalizedUrl,
    activeItem,
    activeGroup,
    siblings,
    inPrimaryDock,
    breadcrumbs: [
      { key: 'overview', label: '控制塔', path: '/app/overview' },
      { key: `group:${activeGroup.key}`, label: activeGroup.label, path: siblings[0]?.path },
      { key: `item:${activeItem.key}`, label: activeItem.label, path: activeItem.path }
    ]
  };
}

export function normalizeNavigationUrl(url: string): string {
  const [withoutHash] = url.split('#');
  const [withoutQuery] = withoutHash.split('?');
  const normalized = withoutQuery.replace(/\/+$/, '');
  return normalized || '/app/overview';
}

function resolveActiveItem(url: string): DockItem {
  const ranked = ALL_DOCK_ITEMS
    .map(item => ({ item, score: matchingScore(item, url) }))
    .filter(entry => entry.score > 0)
    .sort((a, b) => b.score - a.score);
  return ranked[0]?.item ?? DOCK_ITEMS[0];
}

function matchingScore(item: DockItem, url: string): number {
  const directScore = pathMatchScore(item.path, url, 20);
  const aliasScore = Math.max(0, ...(item.activePaths ?? []).map(path => pathMatchScore(path, url, 10)));
  return Math.max(directScore, aliasScore);
}

function pathMatchScore(path: string, url: string, weight: number): number {
  if (url === path) {
    return path.length * 10 + weight + 5;
  }
  if (url.startsWith(`${path}/`)) {
    return path.length * 10 + weight;
  }
  return 0;
}
