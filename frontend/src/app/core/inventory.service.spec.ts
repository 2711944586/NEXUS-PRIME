import { TestBed } from '@angular/core/testing';
import { QueryClient } from '@tanstack/angular-query-experimental';
import { firstValueFrom, of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { InventoryProductPage } from './api/typed-api';
import { InventoryService } from './inventory.service';

describe('InventoryService query options', () => {
  it('keeps productsQuery on the existing products resource URL', async () => {
    const page: InventoryProductPage = {
      items: [{ id: 1, sku: 'MFG-001', name: '轴承套件' }],
      pagination: {
        page: 1,
        page_size: 120,
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

    const service = TestBed.inject(InventoryService);
    const options = service.productsQuery({ page: 1, page_size: 120, q: 'MFG' });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'inventory', 'products', { page: 1, page_size: 120, q: 'MFG' }]);
    expect(api.list).toHaveBeenCalledWith('products', { page: 1, page_size: 120, q: 'MFG' });
    expect(result).toBe(page);
  });

  it('types the products list response from the generated OpenAPI schema', async () => {
    const page: InventoryProductPage = {
      items: [{ id: 2, sku: 'MFG-002', name: '伺服电机组件', total_stock: 32 }],
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

    const service = TestBed.inject(InventoryService);
    const result = await firstValueFrom(service.products({ page: 1, page_size: 20 }));

    expect(result.items[0].sku).toBe('MFG-002');
    expect(result.items[0]['total_stock']).toBe(32);
  });
});
