import { TestBed } from '@angular/core/testing';
import { QueryClient } from '@tanstack/angular-query-experimental';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { PurchaseOrderPage } from './api/typed-api';
import { ProcurementService } from './procurement.service';

describe('ProcurementService query options', () => {
  it('keeps ordersQuery on the existing purchase-orders resource URL', async () => {
    const page: PurchaseOrderPage = {
      items: [{ id: 11, po_no: 'PO-2026-001', supplier_name: '华东供应链' }],
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

    const service = TestBed.inject(ProcurementService);
    const options = service.ordersQuery({ page: 1, page_size: 100, q: 'PO-2026' });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'procurement', 'purchase-orders', { page: 1, page_size: 100, q: 'PO-2026' }]);
    expect(api.list).toHaveBeenCalledWith('purchase-orders', { page: 1, page_size: 100, q: 'PO-2026' });
    expect(result).toBe(page);
  });

  it('types the purchase order list response from the generated OpenAPI schema', async () => {
    const page: PurchaseOrderPage = {
      items: [{ id: 12, po_no: 'PO-2026-002', status: 'approved', supplier_name: '华东供应链' }],
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

    const service = TestBed.inject(ProcurementService);
    const result = await new QueryClient().fetchQuery(service.ordersQuery({ page: 1, page_size: 20 }));

    expect(result.items[0].po_no).toBe('PO-2026-002');
    expect(result.items[0]['supplier_name']).toBe('华东供应链');
  });
});
