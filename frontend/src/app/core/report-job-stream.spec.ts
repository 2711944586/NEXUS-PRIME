import { afterEach, describe, expect, it, vi } from 'vitest';

import { ReportJobStreamError, streamReportJob } from './report-job-stream';

describe('Report job stream client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG;
  });

  it('streams report job status and done events with credentials', async () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1' };
    vi.stubGlobal('document', { cookie: 'nexus_csrf_token=csrf-report' });
    const body = [
      'event: status\ndata: {"job_id":"job-1","job":{"id":"job-1","status":"running"}}\n\n',
      'event: done\ndata: {"job_id":"job-1","job":{"id":"job-1","status":"success"},"report":{"id":8,"report_name":"销售日报"}}\n\n'
    ];
    const fetchMock = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      expect(url).toBe('https://api.example.com/api/v1/reports/jobs/job-1/stream');
      expect(init?.credentials).toBe('include');
      expect(init?.method).toBe('GET');
      expect((init?.headers as Headers).get('X-CSRF-Token')).toBe('csrf-report');
      return Promise.resolve(new Response(new Blob(body), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const statuses: unknown[] = [];
    const result = await streamReportJob('job-1', {
      onStatus: status => statuses.push(status)
    });

    expect(statuses).toEqual([{ job_id: 'job-1', job: { id: 'job-1', status: 'running' } }]);
    expect(result.report?.['report_name']).toBe('销售日报');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('returns failed events as final results', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      'event: failed\ndata: {"job_id":"job-2","job":{"id":"job-2","status":"failed","error_message":"模板失败"}}\n\n',
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));

    const failed: unknown[] = [];
    const result = await streamReportJob('job-2', {
      onFailed: data => failed.push(data)
    });

    expect(result.job.status).toBe('failed');
    expect(result.job.error_message).toBe('模板失败');
    expect(failed).toHaveLength(1);
  });

  it('converts non-OK responses into stream errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ message: '权限不足', error: 'permission_denied' }),
      { status: 403 }
    ))));

    await expect(streamReportJob('job-3')).rejects.toEqual(new ReportJobStreamError('权限不足', {
      status: 403,
      code: 'permission_denied'
    }));
  });
});
