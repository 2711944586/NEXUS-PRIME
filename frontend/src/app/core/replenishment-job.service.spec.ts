import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { firstValueFrom, of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import {
  replenishmentCreatedCount,
  ReplenishmentJobService,
  REPLENISHMENT_GENERATE_JOB_ENDPOINT,
  REPLENISHMENT_JOB_ENDPOINT_PREFIX
} from './replenishment-job.service';

function createService(api: Partial<ApiService>): ReplenishmentJobService {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api }
    ]
  });
  return runInInjectionContext(injector, () => new ReplenishmentJobService());
}

describe('ReplenishmentJobService', () => {
  it('starts the async replenishment generation endpoint and polls until success', async () => {
    const api = {
      post: vi.fn(() => of({ job_id: 'job-1', job: { id: 'job-1', status: 'pending' } })),
      get: vi.fn(() => of({
        job_id: 'job-1',
        job: { id: 'job-1', status: 'success' },
        result: { created: 3 }
      }))
    };
    const service = createService(api as Partial<ApiService>);

    const final = await firstValueFrom(service.runGenerationToFinal({ pollIntervalMs: 0, maxAttempts: 2 }));

    expect(api.post).toHaveBeenCalledWith(REPLENISHMENT_GENERATE_JOB_ENDPOINT, {});
    expect(api.get).toHaveBeenCalledWith(`${REPLENISHMENT_JOB_ENDPOINT_PREFIX}/job-1`, undefined, { silent: true });
    expect(final).toMatchObject({ attempts: 1, terminal: true, timedOut: false });
    expect(replenishmentCreatedCount(final.result)).toBe(3);
  });

  it('returns a timed-out event when the job never reaches a terminal state', async () => {
    const api = {
      post: vi.fn(() => of({ job_id: 'job-slow', job: { id: 'job-slow', status: 'running' } })),
      get: vi.fn(() => of({ job_id: 'job-slow', job: { id: 'job-slow', status: 'running' } }))
    };
    const service = createService(api as Partial<ApiService>);

    const final = await firstValueFrom(service.runGenerationToFinal({ pollIntervalMs: 0, maxAttempts: 1 }));

    expect(api.get).toHaveBeenCalledTimes(1);
    expect(final).toMatchObject({ attempts: 1, terminal: false, timedOut: true });
  });
});
