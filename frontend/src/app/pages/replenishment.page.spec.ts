import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { MessageService } from 'primeng/api';
import { of, Subject } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { ReplenishmentJobService } from '../core/replenishment-job.service';
import { ReplenishmentPage } from './replenishment.page';

const firstSuggestion: DataRecord = {
  id: 1,
  product_name: '伺服电机组件',
  product_sku: 'MFG-T-001',
  warehouse_name: '主仓',
  supplier_name: '测试供应商',
  current_qty: 0,
  suggested_qty: 12,
  status: 'pending'
};

const secondSuggestion: DataRecord = {
  id: 2,
  product_name: '传感器模块',
  product_sku: 'MFG-T-002',
  warehouse_name: '二号仓',
  supplier_name: '测试供应商',
  current_qty: 1,
  suggested_qty: 8,
  status: 'pending'
};

const emptyPage = { items: [], total: 0, page: 1, page_size: 180, pages: 1 };

function createPage(api: Partial<ApiService>, jobs: Partial<ReplenishmentJobService>, messages = { add: vi.fn() }): ReplenishmentPage {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api },
      { provide: ReplenishmentJobService, useValue: jobs },
      { provide: MessageService, useValue: messages }
    ]
  });
  return runInInjectionContext(injector, () => new ReplenishmentPage());
}

describe('ReplenishmentPage generation jobs', () => {
  it('starts a queued generation job and refreshes suggestions on success', () => {
    const generationEvents = new Subject<{
      result: { job_id: string; job: { id: string; status: string; finished_at?: string }; result?: { source: string; alerts_created: number; created: number } };
      attempts: number;
      terminal: boolean;
      timedOut: boolean;
    }>();
    const api = {
      post: vi.fn(),
      get: vi.fn(),
      list: vi.fn((resource: string) => {
        if (resource === 'replenishment-suggestions') {
          return of({ ...emptyPage, items: [firstSuggestion, secondSuggestion], total: 2 });
        }
        return of({ ...emptyPage, items: [], total: 0 });
      })
    };
    const jobs = {
      runGeneration: vi.fn(() => generationEvents.asObservable())
    };
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, jobs as Partial<ReplenishmentJobService>, messages) as unknown as {
      regenerate: () => void;
      generationJob: () => { id: string; status: string; message: string } | null;
      suggestions: () => DataRecord[];
    };

    page.regenerate();
    generationEvents.next({
      result: { job_id: 'repl-job-1', job: { id: 'repl-job-1', status: 'pending' } },
      attempts: 0,
      terminal: false,
      timedOut: false
    });

    expect(jobs.runGeneration).toHaveBeenCalled();
    expect(page.generationJob()).toMatchObject({ id: 'repl-job-1', status: 'pending' });
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'info', summary: '补货任务已入队' }));

    generationEvents.next({
      result: {
        job_id: 'repl-job-1',
        job: { id: 'repl-job-1', status: 'success', finished_at: '2026-06-22T12:00:00' },
        result: { source: 'stock_alerts', alerts_created: 1, created: 1 }
      },
      attempts: 1,
      terminal: true,
      timedOut: false
    });
    generationEvents.complete();

    expect(api.list).toHaveBeenCalledWith('replenishment-suggestions', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' });
    expect(page.generationJob()).toMatchObject({ id: 'repl-job-1', status: 'success' });
    expect(page.suggestions()).toHaveLength(2);
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '建议已更新' }));
  });

  it('handles eager generation completion without scheduling a poll', () => {
    const api = {
      post: vi.fn(),
      get: vi.fn(),
      list: vi.fn((resource: string) => {
        if (resource === 'replenishment-suggestions') {
          return of({ ...emptyPage, items: [firstSuggestion], total: 1 });
        }
        return of({ ...emptyPage, items: [], total: 0 });
      })
    };
    const jobs = {
      runGeneration: vi.fn(() => of({
        result: {
          job_id: 'repl-eager',
          job: { id: 'repl-eager', status: 'success', finished_at: '2026-06-22T12:01:00' },
          result: { source: 'stock_alerts', alerts_created: 1, created: 1 },
          created: 1
        },
        attempts: 0,
        terminal: true,
        timedOut: false
      }))
    };
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, jobs as Partial<ReplenishmentJobService>, messages) as unknown as {
      regenerate: () => void;
      generationJob: () => { id: string; status: string; message: string } | null;
      suggestions: () => DataRecord[];
    };

    page.regenerate();

    expect(page.generationJob()).toMatchObject({ id: 'repl-eager', status: 'success' });
    expect(jobs.runGeneration).toHaveBeenCalled();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.list).toHaveBeenCalledWith('replenishment-suggestions', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' });
    expect(page.suggestions()).toHaveLength(1);
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '建议已更新' }));
  });
});
