import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import {
  FinanceCustomerCredit,
  FinanceCustomerCreditPage,
  FinancePaymentRecord,
  FinanceReceivable,
  FinanceReceivablePage
} from './api/typed-api';
import { DomainQueryParams, domainDetailQuery, domainListQuery } from './domain-query';

@Injectable({ providedIn: 'root' })
export class FinanceService {
  private readonly api = inject(ApiService);

  receivables(params: Record<string, unknown> = {}): Observable<FinanceReceivablePage> {
    return this.api.list('receivables', params);
  }

  receivablesQuery(params: DomainQueryParams = {}) {
    return domainListQuery<FinanceReceivable>(this.api, 'finance', 'receivables', params);
  }

  receivable(id: number): Observable<FinanceReceivable> {
    return this.api.get(`receivables/${id}`);
  }

  receivableQuery(id: number) {
    return domainDetailQuery<FinanceReceivable>(this.api, 'finance', 'receivables', id);
  }

  recordPayment(id: number, payload: Record<string, unknown>): Observable<FinancePaymentRecord> {
    return this.api.post(`receivables/${id}/payment`, payload);
  }

  credits(params: Record<string, unknown> = {}): Observable<FinanceCustomerCreditPage> {
    return this.api.list('credits', params);
  }

  creditsQuery(params: DomainQueryParams = {}) {
    return domainListQuery<FinanceCustomerCredit>(this.api, 'finance', 'credits', params);
  }

  credit(id: number): Observable<FinanceCustomerCredit> {
    return this.api.get(`credits/${id}`);
  }

  creditQuery(id: number) {
    return domainDetailQuery<FinanceCustomerCredit>(this.api, 'finance', 'credits', id);
  }
}
