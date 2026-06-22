import { QueryClient } from '@tanstack/angular-query-experimental';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { domainDetailQuery, domainListQuery, domainQueryKeys, emptyDomainPage, stableParams } from './domain-query';

describe('domain query helpers', () => {
  it('builds stable resource keys without empty params', () => {
    expect(stableParams({ q: 'pump', page: 2, empty: '', nil: null, undef: undefined })).toEqual({
      page: 2,
      q: 'pump'
    });

    expect(domainQueryKeys.resource('inventory', 'stock', { q: 'pump', page: 2 })).toEqual([
      'domains',
      'inventory',
      'stock',
      { page: 2, q: 'pump' }
    ]);
  });

  it('wraps ApiService list requests in query options', async () => {
    const page = emptyDomainPage();
    const api = {
      list: vi.fn(() => of(page))
    } as unknown as ApiService;

    const options = domainListQuery(api, 'procurement', 'purchase-orders', { page: 1, page_size: 20 });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'procurement', 'purchase-orders', { page: 1, page_size: 20 }]);
    expect(api.list).toHaveBeenCalledWith('purchase-orders', { page: 1, page_size: 20 });
    expect(result).toBe(page);
  });

  it('wraps detail lookups with a typed detail key', async () => {
    const row = { id: 17, po_no: 'PO-17' };
    const api = {
      get: vi.fn(() => of(row))
    } as unknown as ApiService;

    const options = domainDetailQuery(api, 'procurement', 'purchase-orders', 17);
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'procurement', 'purchase-orders', 'detail', '17']);
    expect(api.get).toHaveBeenCalledWith('purchase-orders/17');
    expect(result).toBe(row);
  });
});
