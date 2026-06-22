import { TestBed } from '@angular/core/testing';
import { QueryClient } from '@tanstack/angular-query-experimental';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { SalesOrderPage } from './api/typed-api';
import { SalesService } from './sales.service';

describe('SalesService query options', () => {
  it('keeps ordersQuery on the existing orders resource URL', async () => {
    const page: SalesOrderPage = {
      items: [{ id: 21, order_no: 'SO-2026-001', customer_name: '星河制造' }],
      pagination: {
        page: 1,
        page_size: 100,
        total: 1,
        pages: 1,
        has_next: false,
        has_prev: false
      }
    };
    const api = {
      list: vi.fn(() => of(page))
    };

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: api }]
    });

    const service = TestBed.inject(SalesService);
    const options = service.ordersQuery({ page: 1, page_size: 100, q: 'SO-2026' });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'sales', 'orders', { page: 1, page_size: 100, q: 'SO-2026' }]);
    expect(api.list).toHaveBeenCalledWith('orders', { page: 1, page_size: 100, q: 'SO-2026' });
    expect(result).toBe(page);
  });

  it('types the sales order list response from the generated OpenAPI schema', async () => {
    const page: SalesOrderPage = {
      items: [{ id: 22, order_no: 'SO-2026-002', status: 'confirmed', customer_name: '星河制造' }],
      pagination: {
        page: 1,
        page_size: 20,
        total: 1,
        pages: 1,
        has_next: false,
        has_prev: false
      }
    };
    const api = {
      list: vi.fn(() => of(page))
    };

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: api }]
    });

    const service = TestBed.inject(SalesService);
    const result = await new QueryClient().fetchQuery(service.ordersQuery({ page: 1, page_size: 20 }));

    expect(result.items[0].order_no).toBe('SO-2026-002');
    expect(result.items[0]['customer_name']).toBe('星河制造');
  });
});
