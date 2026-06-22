import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { MessageService } from 'primeng/api';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from '../core/api.service';
import { DataQualityPayload } from '../core/models';
import { DataQualityPage } from './data-quality.page';

const payload: DataQualityPayload = {
  generated_at: '2026-06-22T10:00:00',
  source: 'database_quality_contract',
  summary: {
    score: 92,
    level: 'ready',
    issue_count: 0,
    failed_tests: 0,
    passed_tests: 14,
    total_tests: 14,
    p0: 0,
    p1: 0,
    coverage: 96,
    next_action: '保持每日抽检。',
    primary_owner: '数据治理台'
  },
  dimensions: [],
  issue_queue: [],
  test_suites: [],
  lineage: [],
  runbook: []
};

function createPage(api: Partial<ApiService>, messages = { add: vi.fn() }): DataQualityPage {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api },
      { provide: MessageService, useValue: messages }
    ]
  });
  return runInInjectionContext(injector, () => new DataQualityPage());
}

describe('DataQualityPage background scan jobs', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('starts a queued scan job, polls status, and refreshes the quality payload on success', async () => {
    const api = {
      post: vi.fn(() => of({ job_id: 'dq-job-1', job: { id: 'dq-job-1', status: 'pending' } })),
      get: vi.fn((path: string) => {
        if (path === 'operations/data-quality/jobs/dq-job-1') {
          return of({
            job_id: 'dq-job-1',
            job: { id: 'dq-job-1', status: 'success', finished_at: '2026-06-22T10:01:00' },
            result: { source: 'database_quality_contract', summary: payload.summary }
          });
        }
        return of(payload);
      })
    };
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      startScan: () => void;
      ngOnDestroy: () => void;
      scanJob: () => { id: string; status: string; message: string } | null;
      data: () => DataQualityPayload;
    };

    page.startScan();

    expect(api.post).toHaveBeenCalledWith('operations/data-quality/scan', {});
    expect(page.scanJob()).toMatchObject({ id: 'dq-job-1', status: 'pending' });
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'info', summary: '扫描已入队' }));

    await vi.advanceTimersByTimeAsync(2200);

    expect(api.get).toHaveBeenCalledWith('operations/data-quality/jobs/dq-job-1', undefined, { silent: true });
    expect(api.get).toHaveBeenCalledWith('operations/data-quality');
    expect(page.scanJob()).toMatchObject({ id: 'dq-job-1', status: 'success' });
    expect(page.data().summary.score).toBe(92);
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '扫描完成' }));

    page.ngOnDestroy();
  });

  it('handles eager scan completion without scheduling a poll', () => {
    const api = {
      post: vi.fn(() => of({
        job_id: 'dq-eager',
        job: { id: 'dq-eager', status: 'success', finished_at: '2026-06-22T10:02:00' },
        result: { source: 'database_quality_contract', summary: payload.summary }
      })),
      get: vi.fn(() => of(payload))
    };
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      startScan: () => void;
      scanJob: () => { id: string; status: string; message: string } | null;
    };

    page.startScan();

    expect(page.scanJob()).toMatchObject({ id: 'dq-eager', status: 'success' });
    expect(api.get).toHaveBeenCalledWith('operations/data-quality');
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '扫描完成' }));
  });
});
