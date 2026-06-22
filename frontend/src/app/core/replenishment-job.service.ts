import { inject, Injectable } from '@angular/core';
import { catchError, concat, last, Observable, of, switchMap, timer } from 'rxjs';

import { ApiService } from './api.service';

export const REPLENISHMENT_GENERATE_JOB_ENDPOINT = 'inventory/replenishment-suggestions/generate-job';
export const REPLENISHMENT_JOB_ENDPOINT_PREFIX = 'inventory/replenishment-suggestions/jobs';
export const REPLENISHMENT_JOB_POLL_MS = 2200;
export const REPLENISHMENT_JOB_MAX_ATTEMPTS = 25;

export type ReplenishmentJobStatus = 'pending' | 'running' | 'success' | 'failed' | string;

export interface ReplenishmentJobRecord {
  id: string;
  job_id?: string;
  status?: ReplenishmentJobStatus;
  error_message?: string | null;
  finished_at?: string | null;
  result?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ReplenishmentJobResult {
  job_id: string;
  job: ReplenishmentJobRecord;
  result?: {
    source?: string;
    alerts_created?: number;
    created?: number;
    suggestion_count?: number;
    [key: string]: unknown;
  } | null;
  created?: number | null;
}

export interface ReplenishmentJobRunOptions {
  pollIntervalMs?: number;
  maxAttempts?: number;
}

export interface ReplenishmentJobRunEvent {
  result: ReplenishmentJobResult;
  attempts: number;
  terminal: boolean;
  timedOut: boolean;
}

interface NormalizedRunOptions {
  pollIntervalMs: number;
  maxAttempts: number;
}

@Injectable({ providedIn: 'root' })
export class ReplenishmentJobService {
  private readonly api = inject(ApiService);

  startGeneration(): Observable<ReplenishmentJobResult> {
    return this.api.post<ReplenishmentJobResult>(REPLENISHMENT_GENERATE_JOB_ENDPOINT, {});
  }

  getJob(jobId: string): Observable<ReplenishmentJobResult> {
    return this.api.get<ReplenishmentJobResult>(`${REPLENISHMENT_JOB_ENDPOINT_PREFIX}/${jobId}`, undefined, { silent: true });
  }

  runGeneration(options: ReplenishmentJobRunOptions = {}): Observable<ReplenishmentJobRunEvent> {
    const normalized = normalizeOptions(options);
    return this.startGeneration().pipe(
      switchMap(result => this.emitUntilDone(result, 0, normalized))
    );
  }

  runGenerationToFinal(options: ReplenishmentJobRunOptions = {}): Observable<ReplenishmentJobRunEvent> {
    return this.runGeneration(options).pipe(last());
  }

  private emitUntilDone(result: ReplenishmentJobResult, attempts: number, options: NormalizedRunOptions): Observable<ReplenishmentJobRunEvent> {
    const status = replenishmentJobStatus(result);
    const terminal = isReplenishmentJobTerminal(status);
    const timedOut = !terminal && attempts >= options.maxAttempts;
    const event: ReplenishmentJobRunEvent = { result, attempts, terminal, timedOut };

    if (terminal || timedOut) {
      return of(event);
    }

    return concat(
      of(event),
      timer(options.pollIntervalMs).pipe(
        switchMap(() => this.getJob(result.job_id).pipe(catchError(() => of(result)))),
        switchMap(next => this.emitUntilDone(next, attempts + 1, options))
      )
    );
  }
}

export function replenishmentJobStatus(result: ReplenishmentJobResult | null | undefined): ReplenishmentJobStatus {
  return result?.job?.status || 'pending';
}

export function isReplenishmentJobTerminal(status: ReplenishmentJobStatus): boolean {
  return status === 'success' || status === 'failed';
}

export function replenishmentCreatedCount(result: ReplenishmentJobResult | null | undefined): number {
  const created = result?.created ?? result?.result?.created ?? result?.result?.suggestion_count ?? result?.result?.alerts_created ?? 0;
  const count = Number(created);
  return Number.isFinite(count) ? count : 0;
}

function normalizeOptions(options: ReplenishmentJobRunOptions): NormalizedRunOptions {
  return {
    pollIntervalMs: Math.max(0, Math.trunc(options.pollIntervalMs ?? REPLENISHMENT_JOB_POLL_MS)),
    maxAttempts: Math.max(0, Math.trunc(options.maxAttempts ?? REPLENISHMENT_JOB_MAX_ATTEMPTS))
  };
}
