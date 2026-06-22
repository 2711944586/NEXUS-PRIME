import { describe, expect, it } from 'vitest';

import type { DataRecord, ManufacturingCommandCenter } from '../core/models';
import { buildWarehouseNetwork } from './warehouse-flow-network';

const COMMAND: ManufacturingCommandCenter = {
  kpis: {
    order_amount: 126000,
    stock_quantity: 880,
    low_stock_products: 3,
    pending_purchase: 2,
    overdue_amount: 0
  },
  warehouse_heat: [
    { name: '华东工厂仓', stock_quantity: 520, slot_count: 18 },
    { name: '长三角区域仓', stock_quantity: 260, slot_count: 12 }
  ],
  flows: [
    { from: '供应商集群', to: '华东工厂仓', value: 16 },
    { from: '华东工厂仓', to: '长三角区域仓', value: 9 },
    { from: '长三角区域仓', to: '客户发货', value: 7 }
  ],
  risks: []
};

const STOCK: DataRecord[] = [
  { id: 1, product_name: 'MRO 备件包', warehouse_name: '长三角区域仓', quantity: 24 },
  { id: 2, product_name: '编码器线束', warehouse_name: '华东工厂仓', quantity: 88 },
  { id: 3, product_name: '伺服电机组件', warehouse_name: '长三角区域仓', quantity: 12 }
];

describe('warehouse flow network', () => {
  it('builds positioned nodes and links from command-center flows', () => {
    const network = buildWarehouseNetwork(COMMAND, STOCK);

    expect(network.nodes.map(node => node.label)).toEqual([
      '供应商集群',
      '华东工厂仓',
      '长三角区域仓',
      '客户发货'
    ]);
    expect(network.links).toHaveLength(3);
    expect(network.links[0]).toMatchObject({
      label: '供应商集群 → 华东工厂仓',
      value: 16
    });
    expect(network.nodes.every(node => node.x >= 0 && node.x <= 100 && node.y >= 0 && node.y <= 100)).toBe(true);
  });

  it('marks warehouses with low stock pressure and summarizes the network', () => {
    const network = buildWarehouseNetwork(COMMAND, STOCK);
    const regional = network.nodes.find(node => node.label === '长三角区域仓');

    expect(regional?.tone).toBe('warning');
    expect(regional?.lowStockCount).toBe(2);
    expect(network.summary).toMatchObject({
      totalThroughput: 32,
      warehouseCount: 2,
      lowStockCount: 2,
      slotCount: 30
    });
  });

  it('falls back to a usable network when backend flow rows are empty', () => {
    const network = buildWarehouseNetwork({ ...COMMAND, flows: [] }, STOCK);

    expect(network.links.length).toBeGreaterThanOrEqual(3);
    expect(network.nodes.some(node => node.kind === 'supplier')).toBe(true);
    expect(network.nodes.some(node => node.kind === 'customer')).toBe(true);
    expect(network.summary.totalThroughput).toBeGreaterThan(0);
  });
});
