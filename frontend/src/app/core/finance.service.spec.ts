import { TestBed } from '@angular/core/testing';
import { QueryClient } from '@tanstack/angular-query-experimental';
import { firstValueFrom, of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import {
  FinanceCustomerCreditPage,
  FinancePaymentRecord,
  FinanceReceivablePage
} from './api/typed-api';
import { FinanceService } from './finance.service';

describe('FinanceService query options', () => {
  it('keeps receivablesQuery on the existing receivables resource URL', async () => {
    const page: FinanceReceivablePage = {
      items: [{ id: 31, receivable_no: 'AR-2026-001', customer_name: '星河制造', unpaid_amount: 1200 }],
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

    const service = TestBed.inject(FinanceService);
    const options = service.receivablesQuery({ page: 1, page_size: 100, status: 'overdue' });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'finance', 'receivables', { page: 1, page_size: 100, status: 'overdue' }]);
    expect(api.list).toHaveBeenCalledWith('receivables', { page: 1, page_size: 100, status: 'overdue' });
    expect(result).toBe(page);
  });

  it('types the receivables list response from the generated OpenAPI schema', async () => {
    const page: FinanceReceivablePage = {
      items: [{ id: 32, receivable_no: 'AR-2026-002', status: 'partial', customer_name: '星河制造' }],
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

    const service = TestBed.inject(FinanceService);
    const result = await firstValueFrom(service.receivables({ page: 1, page_size: 20 }));

    expect(result.items[0].receivable_no).toBe('AR-2026-002');
    expect(result.items[0]['customer_name']).toBe('星河制造');
  });

  it('keeps creditsQuery on the existing credits resource URL', async () => {
    const page: FinanceCustomerCreditPage = {
      items: [{ id: 41, customer_id: 7, credit_limit: 500000, is_frozen: false, customer_name: '华东客户' }],
      pagination: {
        page: 1,
        page_size: 50,
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

    const service = TestBed.inject(FinanceService);
    const options = service.creditsQuery({ page: 1, page_size: 50, is_frozen: false });
    const result = await new QueryClient().fetchQuery(options);

    expect(options.queryKey).toEqual(['domains', 'finance', 'credits', { is_frozen: false, page: 1, page_size: 50 }]);
    expect(api.list).toHaveBeenCalledWith('credits', { page: 1, page_size: 50, is_frozen: false });
    expect(result.items[0].credit_limit).toBe(500000);
    expect(result.items[0]['customer_name']).toBe('华东客户');
  });

  it('types recordPayment as the payment record returned by the backend action', async () => {
    const payment: FinancePaymentRecord = {
      id: 51,
      payment_no: 'PAY-20260621-0001',
      receivable_id: 31,
      amount: 1200,
      payment_method: 'bank'
    };
    const api = {
      post: vi.fn(() => of(payment))
    };

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: api }]
    });

    const service = TestBed.inject(FinanceService);
    const result = await firstValueFrom(service.recordPayment(31, { amount: 1200, payment_method: 'bank' }));

    expect(api.post).toHaveBeenCalledWith('receivables/31/payment', { amount: 1200, payment_method: 'bank' });
    expect(result.payment_no).toBe('PAY-20260621-0001');
  });
});
