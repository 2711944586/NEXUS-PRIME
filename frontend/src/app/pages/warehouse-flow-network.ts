import type { DataRecord, ManufacturingCommandCenter } from '../core/models';

export type WarehouseNetworkNodeKind = 'supplier' | 'plant' | 'regional' | 'customer' | 'transfer';
export type WarehouseNetworkTone = 'success' | 'warning' | 'danger' | 'info';

export interface WarehouseNetworkNode {
  id: string;
  label: string;
  kicker: string;
  metric: string;
  detail: string;
  path: string;
  kind: WarehouseNetworkNodeKind;
  tone: WarehouseNetworkTone;
  x: number;
  y: number;
  stockQuantity: number;
  slotCount: number;
  lowStockCount: number;
}

export interface WarehouseNetworkLink {
  id: string;
  source: string;
  target: string;
  label: string;
  value: number;
  tone: WarehouseNetworkTone;
  width: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  midX: number;
  midY: number;
}

export interface WarehouseNetworkModel {
  nodes: WarehouseNetworkNode[];
  links: WarehouseNetworkLink[];
  summary: {
    totalThroughput: number;
    warehouseCount: number;
    lowStockCount: number;
    slotCount: number;
  };
}

type FlowItem = ManufacturingCommandCenter['flows'][number];
type WarehouseHeatItem = ManufacturingCommandCenter['warehouse_heat'][number];

const LOW_STOCK_THRESHOLD = 40;

export function buildWarehouseNetwork(command: ManufacturingCommandCenter, stock: DataRecord[]): WarehouseNetworkModel {
  const warehouses = command.warehouse_heat ?? [];
  const warehouseByName = new Map(warehouses.map(item => [item.name, item]));
  const lowStockByWarehouse = countLowStockByWarehouse(stock);
  const flows = normalizeFlows(command, warehouses);
  const names = uniqueNames([
    ...flows.flatMap(flow => [flow.from, flow.to]),
    ...warehouses.slice(0, 4).map(item => item.name)
  ]).slice(0, 8);
  const nodes = names.map((name, index) => buildNode(name, index, warehouseByName, lowStockByWarehouse));
  const nodeByLabel = new Map(nodes.map(node => [node.label, node]));
  const maxFlow = Math.max(...flows.map(flow => safeNumber(flow.value)), 1);
  const links = flows
    .map((flow, index) => buildLink(flow, index, nodeByLabel, maxFlow))
    .filter((link): link is WarehouseNetworkLink => Boolean(link));

  return {
    nodes,
    links,
    summary: {
      totalThroughput: flows.reduce((sum, flow) => sum + safeNumber(flow.value), 0),
      warehouseCount: warehouses.length,
      lowStockCount: Array.from(lowStockByWarehouse.values()).reduce((sum, count) => sum + count, 0),
      slotCount: warehouses.reduce((sum, warehouse) => sum + safeNumber(warehouse.slot_count), 0)
    }
  };
}

function normalizeFlows(command: ManufacturingCommandCenter, warehouses: WarehouseHeatItem[]): FlowItem[] {
  const valid = (command.flows ?? []).filter(flow => flow.from && flow.to);
  if (valid.length) {
    return valid.slice(0, 5);
  }

  const primary = warehouses[0]?.name ?? '工厂仓';
  const secondary = warehouses[1]?.name ?? '区域仓';
  const stockQuantity = safeNumber(command.kpis.stock_quantity);
  const lowStock = safeNumber(command.kpis.low_stock_products);

  return [
    { from: '供应商', to: primary, value: Math.max(1, lowStock) },
    { from: primary, to: secondary, value: Math.max(1, Math.round(stockQuantity / 100)) },
    { from: secondary, to: '客户发货', value: Math.max(1, Math.round(safeNumber(command.kpis.order_amount) / 10000)) }
  ];
}

function buildNode(
  label: string,
  index: number,
  warehouseByName: Map<string, WarehouseHeatItem>,
  lowStockByWarehouse: Map<string, number>
): WarehouseNetworkNode {
  const warehouse = warehouseByName.get(label);
  const kind = classifyNode(label, warehouse, index);
  const position = layoutPosition(kind, index);
  const lowStockCount = lowStockByWarehouse.get(label) ?? 0;
  const stockQuantity = safeNumber(warehouse?.stock_quantity);
  const slotCount = safeNumber(warehouse?.slot_count);
  const tone: WarehouseNetworkTone = lowStockCount >= 3 ? 'danger' : lowStockCount > 0 ? 'warning' : kind === 'transfer' ? 'info' : 'success';
  const flowLabel = kind === 'supplier' ? '入厂' : kind === 'customer' ? '发货' : '流转';

  return {
    id: `warehouse-node-${index}`,
    label,
    kicker: nodeKicker(kind, index),
    metric: warehouse ? formatCompact(stockQuantity) : flowLabel,
    detail: warehouse ? `${slotCount} 个库位 · ${lowStockCount} 项低水位` : nodeDetail(kind),
    path: nodePath(kind),
    kind,
    tone,
    x: position.x,
    y: position.y,
    stockQuantity,
    slotCount,
    lowStockCount
  };
}

function buildLink(
  flow: FlowItem,
  index: number,
  nodeByLabel: Map<string, WarehouseNetworkNode>,
  maxFlow: number
): WarehouseNetworkLink | null {
  const source = nodeByLabel.get(flow.from);
  const target = nodeByLabel.get(flow.to);
  if (!source || !target) {
    return null;
  }
  const value = Math.max(1, safeNumber(flow.value));
  const tone: WarehouseNetworkTone = source.tone === 'danger' || target.tone === 'danger'
    ? 'danger'
    : source.tone === 'warning' || target.tone === 'warning'
      ? 'warning'
      : 'success';

  return {
    id: `warehouse-link-${index}`,
    source: source.id,
    target: target.id,
    label: `${source.label} → ${target.label}`,
    value,
    tone,
    width: Number((1.8 + (value / maxFlow) * 4.2).toFixed(2)),
    x1: source.x,
    y1: source.y,
    x2: target.x,
    y2: target.y,
    midX: (source.x + target.x) / 2,
    midY: (source.y + target.y) / 2
  };
}

function countLowStockByWarehouse(stock: DataRecord[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of stock) {
    const warehouse = stringValue(row['warehouse_name']);
    const quantity = safeNumber(row['quantity']);
    if (warehouse && quantity < LOW_STOCK_THRESHOLD) {
      counts.set(warehouse, (counts.get(warehouse) ?? 0) + 1);
    }
  }
  return counts;
}

function classifyNode(label: string, warehouse: WarehouseHeatItem | undefined, index: number): WarehouseNetworkNodeKind {
  if (/供应|supplier/i.test(label)) {
    return 'supplier';
  }
  if (/客户|发货|customer|装配/i.test(label)) {
    return 'customer';
  }
  if (warehouse) {
    return index <= 1 ? 'plant' : 'regional';
  }
  return 'transfer';
}

function layoutPosition(kind: WarehouseNetworkNodeKind, index: number): { x: number; y: number } {
  if (kind === 'supplier') {
    return { x: 10, y: 50 };
  }
  if (kind === 'customer') {
    return { x: 90, y: 50 };
  }
  const positions = [
    { x: 34, y: 28 },
    { x: 62, y: 50 },
    { x: 36, y: 74 },
    { x: 64, y: 24 },
    { x: 50, y: 78 },
    { x: 76, y: 74 }
  ];
  return positions[Math.max(0, index - 1) % positions.length];
}

function nodeKicker(kind: WarehouseNetworkNodeKind, index: number): string {
  const map: Record<WarehouseNetworkNodeKind, string> = {
    supplier: 'SUP',
    plant: 'PLANT',
    regional: 'HUB',
    customer: 'SHIP',
    transfer: `NODE-${index + 1}`
  };
  return map[kind];
}

function nodeDetail(kind: WarehouseNetworkNodeKind): string {
  const map: Record<WarehouseNetworkNodeKind, string> = {
    supplier: '采购到货入口',
    plant: '工厂仓库存水位',
    regional: '区域仓调拨水位',
    customer: '客户履约出口',
    transfer: '跨节点业务流'
  };
  return map[kind];
}

function nodePath(kind: WarehouseNetworkNodeKind): string {
  const map: Record<WarehouseNetworkNodeKind, string> = {
    supplier: '/app/procurement/orders',
    plant: '/app/inventory/stock',
    regional: '/app/inventory/stock',
    customer: '/app/sales/orders',
    transfer: '/app/dispatch'
  };
  return map[kind];
}

function uniqueNames(values: string[]): string[] {
  return values.filter((value, index, list) => Boolean(value) && list.indexOf(value) === index);
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function safeNumber(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(value);
}
