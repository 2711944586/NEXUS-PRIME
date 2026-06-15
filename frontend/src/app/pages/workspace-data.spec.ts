import { describe, expect, it } from 'vitest';

import { DOCK_GROUP_LABELS, DOCK_ITEMS, MORE_DOCK_ITEMS, dockItemForUrl, groupedDockItems } from '../core/navigation';
import { DETAIL_CONFIGS, PAGE_DETAIL_PATH } from './detail-data';
import { buildBoardLanes, WORKSPACES } from './workspace-data';

const BLOCKED_RUNTIME_WORDS = ['演' + '示', '模' + '拟', '兜' + '底', '玩' + '具', 'de' + 'mo'];
const RUNTIME_FORBIDDEN_COPY = new RegExp(BLOCKED_RUNTIME_WORDS.join('|'), 'i');

describe('manufacturing workspace data', () => {
  it('defines independent Prime workspaces with manufacturing language', () => {
    expect(Object.keys(WORKSPACES).length).toBeGreaterThanOrEqual(10);
    expect(WORKSPACES.materials.seedRows.some(row => String(row['name']).includes('伺服'))).toBe(true);
    expect(WORKSPACES.flow.seedRows.some(row => String(row['warehouse_name']).includes('工厂仓'))).toBe(true);
  });

  it('avoids empty actions and id-only operating surfaces', () => {
    for (const workspace of Object.values(WORKSPACES)) {
      expect(workspace.actions.length).toBeGreaterThan(0);
      expect(workspace.actions.every(action => action.label.trim().length > 0 && action.icon.startsWith('pi-'))).toBe(true);
      expect(workspace.searchPlaceholder).not.toMatch(/ID|id/);
    }
  });

  it('ships enough seed rows for offline contract checks', () => {
    for (const workspace of Object.values(WORKSPACES)) {
      expect(workspace.seedRows.length).toBeGreaterThanOrEqual(2);
    }
    expect(WORKSPACES.materials.seedRows.length).toBeGreaterThanOrEqual(6);
    expect(WORKSPACES.procurement.seedRows.length).toBeGreaterThanOrEqual(4);
    expect(WORKSPACES.fulfillment.seedRows.length).toBeGreaterThanOrEqual(4);
  });

  it('defines a centered dock navigation model with valid labels and paths', () => {
    expect(DOCK_ITEMS.length).toBeGreaterThanOrEqual(10);
    for (const item of [...DOCK_ITEMS, ...MORE_DOCK_ITEMS]) {
      expect(item.label.trim()).not.toBe('');
      expect(item.shortLabel.trim()).not.toBe('');
      expect(item.path).toMatch(/^\/app\//);
      expect(item.icon.trim()).not.toBe('');
      expect(item.dockGroup).toBeTruthy();
      expect(DOCK_GROUP_LABELS[item.dockGroup]).toBeTruthy();
      expect(item.quickActions.length).toBeGreaterThan(0);
    }
    const groups = groupedDockItems(DOCK_ITEMS);
    expect(groups.length).toBeGreaterThanOrEqual(6);
    expect(groups.every(group => group.items.length > 0 && group.label.trim().length > 0)).toBe(true);
    expect(dockItemForUrl('/app/procurement/orders/1').key).toBe('procurement');
    expect(dockItemForUrl('/app/inventory/replenishment').key).toBe('procurement');
    expect(dockItemForUrl('/app/finance/credits/2').key).toBe('credits');
    expect(dockItemForUrl('/app/content/articles').key).toBe('content');
    expect(dockItemForUrl('/app/system/audit').key).toBe('audit');
    expect(dockItemForUrl('/app/ai').key).toBe('ai');
    expect(dockItemForUrl('/app/notifications').key).toBe('notifications');
  });

  it('defines richer visual contracts for every workspace', () => {
    const variants = new Set(Object.values(WORKSPACES).map(workspace => workspace.heroVariant));
    expect(variants.size).toBeGreaterThanOrEqual(8);
    for (const workspace of Object.values(WORKSPACES)) {
      expect(['compact', 'balanced', 'immersive']).toContain(workspace.visualDensity);
      expect(workspace.heroVariant.trim()).not.toBe('');
      expect(workspace.storyBlocks.length).toBeGreaterThanOrEqual(3);
      expect(workspace.storyBlocks.every(block => block.title.trim() && block.body.trim())).toBe(true);
    }
    expect(WORKSPACES.materials.heroVariant).toBe('material-lab');
    expect(WORKSPACES.flow.heroVariant).toBe('flow-network');
    expect(WORKSPACES.procurement.heroVariant).toBe('approval-lane');
    expect(WORKSPACES.fulfillment.heroVariant).toBe('fulfillment-lane');
    expect(WORKSPACES.reports.heroVariant).toBe('report-studio');
    expect(WORKSPACES.security.heroVariant).toBe('security-matrix');
  });

  it('adds a dedicated business board to avoid generic table-only pages', () => {
    const distinctTitles = new Set<string>();
    for (const workspace of Object.values(WORKSPACES)) {
      const lanes = buildBoardLanes(workspace, workspace.seedRows);
      expect(lanes.length).toBe(3);
      expect(lanes.every(lane => lane.title.trim() && lane.body.trim() && lane.items.length >= 2)).toBe(true);
      lanes.forEach(lane => distinctTitles.add(`${workspace.key}:${lane.title}`));
    }
    expect(distinctTitles.size).toBeGreaterThan(Object.keys(WORKSPACES).length * 2);
    expect(buildBoardLanes(WORKSPACES.procurement, WORKSPACES.procurement.seedRows).some(lane => lane.title.includes('收货'))).toBe(true);
    expect(buildBoardLanes(WORKSPACES.receivables, WORKSPACES.receivables.seedRows).some(lane => lane.title.includes('收款'))).toBe(true);
  });

  it('gives every data workspace a standalone detail entry when applicable', () => {
    const pagesWithoutDetail = new Set(['profile']);
    for (const workspace of Object.values(WORKSPACES)) {
      if (pagesWithoutDetail.has(workspace.key)) {
        continue;
      }
      expect(PAGE_DETAIL_PATH[workspace.key]).toMatch(/^\/app\//);
    }
    expect(Object.keys(DETAIL_CONFIGS).length).toBeGreaterThanOrEqual(14);
    for (const detail of Object.values(DETAIL_CONFIGS)) {
      expect(detail.resource.trim()).not.toBe('');
      expect(detail.backPath).toMatch(/^\/app\//);
      expect(detail.fields.length).toBeGreaterThan(0);
      expect(detail.timeline.length).toBeGreaterThan(0);
      expect(detail.actions.every(action => action.label.trim().length > 0 && action.icon.startsWith('pi-'))).toBe(true);
    }
  });

  it('keeps runtime workspace and detail copy product-grade', () => {
    const scan = (value: unknown): void => {
      if (typeof value === 'string') {
        expect(value).not.toMatch(RUNTIME_FORBIDDEN_COPY);
        return;
      }
      if (Array.isArray(value)) {
        value.forEach(scan);
        return;
      }
      if (value && typeof value === 'object') {
        Object.entries(value as Record<string, unknown>)
          .filter(([key]) => !['seedRows'].includes(key))
          .forEach(([, item]) => scan(item));
      }
    };
    scan(WORKSPACES);
    scan(DETAIL_CONFIGS);
  });
});

