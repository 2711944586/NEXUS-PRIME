import { QueryClient } from '@tanstack/angular-query-experimental';

export const NEXUS_QUERY_STALE_TIME_MS = 30_000;
export const NEXUS_QUERY_GC_TIME_MS = 5 * 60_000;

export function createNexusQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: NEXUS_QUERY_STALE_TIME_MS,
        gcTime: NEXUS_QUERY_GC_TIME_MS,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => failureCount < 2 && !isAuthorizationError(error)
      },
      mutations: {
        retry: false
      }
    }
  });
}

export function isAuthorizationError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /401|403|unauthorized|forbidden|未登录|未授权|权限不足/i.test(message);
}
