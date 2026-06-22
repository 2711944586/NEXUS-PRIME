import { queryOptions } from '@tanstack/angular-query-experimental';
import { firstValueFrom, Observable } from 'rxjs';

import { ApiService } from './api.service';
import { DataRecord, PageResult } from './models';

export type DomainQueryScope = 'inventory' | 'procurement' | 'sales' | 'finance' | 'operations' | 'ai' | 'resources';
export type DomainQueryParams = Record<string, unknown>;

export const domainQueryKeys = {
  all: ['domains'] as const,
  scope: (scope: DomainQueryScope) => [...domainQueryKeys.all, scope] as const,
  resource: (scope: DomainQueryScope, resource: string, params: DomainQueryParams = {}) =>
    [...domainQueryKeys.scope(scope), resource, stableParams(params)] as const,
  detail: (scope: DomainQueryScope, resource: string, id: string | number) =>
    [...domainQueryKeys.scope(scope), resource, 'detail', String(id)] as const
};

export function domainListQuery<T>(
  api: ApiService,
  scope: DomainQueryScope,
  resource: string,
  params: DomainQueryParams = {}
) {
  return queryOptions({
    queryKey: domainQueryKeys.resource(scope, resource, params),
    queryFn: () => firstValueFrom(api.list<T>(resource, params))
  });
}

export function domainDetailQuery<T>(
  api: ApiService,
  scope: DomainQueryScope,
  resource: string,
  id: string | number
) {
  return queryOptions({
    queryKey: domainQueryKeys.detail(scope, resource, id),
    queryFn: () => firstValueFrom(api.get<T>(`${resource}/${id}`)),
    enabled: Boolean(id)
  });
}

export function observableQuery<T>(
  key: readonly unknown[],
  source: () => Observable<T>
) {
  return queryOptions({
    queryKey: key,
    queryFn: () => firstValueFrom(source())
  });
}

export function emptyDomainPage<T extends DataRecord = DataRecord>(pageSize = 50): PageResult<T> {
  return {
    items: [],
    pagination: {
      page: 1,
      page_size: pageSize,
      total: 0,
      pages: 1,
      has_next: false,
      has_prev: false
    }
  };
}

export function stableParams(params: DomainQueryParams): DomainQueryParams {
  return Object.keys(params)
    .filter(key => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .sort()
    .reduce<DomainQueryParams>((next, key) => {
      next[key] = params[key];
      return next;
    }, {});
}
