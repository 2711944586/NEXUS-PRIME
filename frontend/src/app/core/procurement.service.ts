import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { PurchaseOrder, PurchaseOrderPage } from './api/typed-api';
import { DomainQueryParams, domainDetailQuery, domainListQuery } from './domain-query';
import { DataRecord } from './models';

@Injectable({ providedIn: 'root' })
export class ProcurementService {
  private readonly api = inject(ApiService);

  orders(params: Record<string, unknown> = {}): Observable<PurchaseOrderPage> {
    return this.api.list('purchase-orders', params);
  }

  ordersQuery(params: DomainQueryParams = {}) {
    return domainListQuery<PurchaseOrder>(this.api, 'procurement', 'purchase-orders', params);
  }

  order(id: number): Observable<PurchaseOrder> {
    return this.api.get(`purchase-orders/${id}`);
  }

  orderQuery(id: number) {
    return domainDetailQuery<PurchaseOrder>(this.api, 'procurement', 'purchase-orders', id);
  }

  create(payload: Record<string, unknown>): Observable<DataRecord> {
    return this.api.post('purchase-orders', payload);
  }

  submit(id: number): Observable<DataRecord> {
    return this.api.post(`purchase-orders/${id}/submit`, {});
  }

  approve(id: number): Observable<DataRecord> {
    return this.api.post(`purchase-orders/${id}/approve`, {});
  }

  reject(id: number, reason: string): Observable<DataRecord> {
    return this.api.post(`purchase-orders/${id}/reject`, { reason });
  }

  receive(id: number, payload: Record<string, unknown>): Observable<DataRecord> {
    return this.api.post(`purchase-orders/${id}/receive`, payload);
  }
}
