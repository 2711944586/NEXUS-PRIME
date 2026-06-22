import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { MessageService } from 'primeng/api';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from '../core/api.service';
import { ReportsPage } from './reports.page';

function createPage(api: Partial<ApiService>, messages = { add: vi.fn() }): ReportsPage {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api },
      { provide: MessageService, useValue: messages }
    ]
  });
  return runInInjectionContext(injector, () => new ReportsPage());
}

describe('ReportsPage background report jobs', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('streams queued report jobs and inserts the archived report on success', async () => {
    const report = { id: 77, report_type: 'sales_daily', report_name: '销售日报', generated_at: '2026-06-21T10:00:00Z' };
    const api = {
      post: vi.fn(() => of({ job_id: 'job-77', job: { id: 'job-77', status: 'pending' } })),
      get: vi.fn()
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      `event: status\ndata: {"job_id":"job-77","job":{"id":"job-77","status":"running"}}\n\n` +
      `event: done\ndata: {"job_id":"job-77","job":{"id":"job-77","status":"success","finished_at":"2026-06-21T10:01:00Z"},"report":{"id":77,"report_type":"sales_daily","report_name":"销售日报","generated_at":"2026-06-21T10:00:00Z"}}\n\n`,
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      generate: (type: string) => void;
      ngOnDestroy: () => void;
      activeReportJobs: () => Array<{ id: string; status: string; message: string }>;
      reports: () => Array<{ id?: number; report_name?: string }>;
    };

    page.generate('sales_daily');

    expect(api.post).toHaveBeenCalledWith('reports/generate/sales_daily', { params: {} });
    expect(page.activeReportJobs()[0]).toMatchObject({ id: 'job-77', status: 'pending' });

    await Promise.resolve();
    await Promise.resolve();

    expect(api.get).not.toHaveBeenCalled();
    expect(page.activeReportJobs()[0]).toMatchObject({ id: 'job-77', status: 'success' });
    expect(page.reports()[0]).toMatchObject(report);
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '报表已归档' }));

    page.ngOnDestroy();
  });

  it('falls back to polling when the stream request fails', async () => {
    const report = { id: 88, report_type: 'inventory_summary', report_name: '库存汇总', generated_at: '2026-06-21T10:02:00Z' };
    const api = {
      post: vi.fn(() => of({ job_id: 'job-fallback', job: { id: 'job-fallback', status: 'pending' } })),
      get: vi.fn(() => of({
        job_id: 'job-fallback',
        job: { id: 'job-fallback', status: 'success', finished_at: '2026-06-21T10:03:00Z' },
        report
      }))
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('stream unavailable'))));
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      generate: (type: string) => void;
      ngOnDestroy: () => void;
      activeReportJobs: () => Array<{ id: string; status: string; message: string }>;
      reports: () => Array<{ id?: number; report_name?: string }>;
    };

    page.generate('inventory_summary');
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    vi.advanceTimersByTime(2400);

    expect(api.get).toHaveBeenCalledWith('reports/jobs/job-fallback', undefined, { silent: true });
    expect(page.activeReportJobs()[0]).toMatchObject({ id: 'job-fallback', status: 'success' });
    expect(page.reports()[0]).toMatchObject(report);

    page.ngOnDestroy();
  });

  it('stops tracking failed streamed report jobs and surfaces the backend error', async () => {
    const api = {
      post: vi.fn(() => of({ job_id: 'job-failed', job: { id: 'job-failed', status: 'pending' } })),
      get: vi.fn()
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      'event: failed\ndata: {"job_id":"job-failed","job":{"id":"job-failed","status":"failed","error_message":"模板计算失败"},"report":null}\n\n',
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      generate: (type: string) => void;
      ngOnDestroy: () => void;
      activeReportJobs: () => Array<{ id: string; status: string; message: string }>;
    };

    page.generate('financial_overview');
    await Promise.resolve();
    await Promise.resolve();

    expect(api.get).not.toHaveBeenCalled();
    expect(page.activeReportJobs()[0]).toMatchObject({ id: 'job-failed', status: 'failed', message: '模板计算失败' });
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'warn', summary: '报表生成失败', detail: '模板计算失败' }));

    page.ngOnDestroy();
  });
});
