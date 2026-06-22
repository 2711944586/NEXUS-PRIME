import { describe, expect, it } from 'vitest';

import { NEXUS_QUERY_GC_TIME_MS, NEXUS_QUERY_STALE_TIME_MS, createNexusQueryClient, isAuthorizationError } from './query-client';

describe('Nexus query client', () => {
  it('uses ERP-friendly cache defaults', () => {
    const client = createNexusQueryClient();
    const options = client.getDefaultOptions();

    expect(options.queries?.staleTime).toBe(NEXUS_QUERY_STALE_TIME_MS);
    expect(options.queries?.gcTime).toBe(NEXUS_QUERY_GC_TIME_MS);
    expect(options.queries?.refetchOnWindowFocus).toBe(false);
    expect(options.mutations?.retry).toBe(false);
  });

  it('does not retry authorization failures', () => {
    const client = createNexusQueryClient();
    const retry = client.getDefaultOptions().queries?.retry;

    expect(isAuthorizationError(new Error('权限不足'))).toBe(true);
    expect(typeof retry).toBe('function');
    expect(typeof retry === 'function' ? retry(0, new Error('403 forbidden')) : retry).toBe(false);
    expect(typeof retry === 'function' ? retry(1, new Error('network down')) : retry).toBe(true);
    expect(typeof retry === 'function' ? retry(2, new Error('network down')) : retry).toBe(false);
  });
});
