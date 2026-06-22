import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { InventoryProduct, InventoryProductPage } from './api/typed-api';
import { DomainQueryParams, domainListQuery } from './domain-query';
import { DataRecord, PageResult } from './models';

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly api = inject(ApiService);

  products(params: Record<string, unknown> = {}): Observable<InventoryProductPage> {
    return this.api.list('products', params);
  }

  productsQuery(params: DomainQueryParams = {}) {
    return domainListQuery<InventoryProduct>(this.api, 'inventory', 'products', params);
  }

  stock(params: Record<string, unknown> = {}): Observable<PageResult<DataRecord>> {
    return this.api.list('stock', params);
  }

  stockQuery(params: DomainQueryParams = {}) {
    return domainListQuery<DataRecord>(this.api, 'inventory', 'stock', params);
  }

  replenishments(params: Record<string, unknown> = {}): Observable<PageResult<DataRecord>> {
    return this.api.list('replenishment-suggestions', params);
  }

  replenishmentsQuery(params: DomainQueryParams = {}) {
    return domainListQuery<DataRecord>(this.api, 'inventory', 'replenishment-suggestions', params);
  }

  generateReplenishment(id: number): Observable<DataRecord> {
    return this.api.post(`replenishment-suggestions/${id}/generate`, {});
  }

  acceptReplenishment(id: number): Observable<DataRecord> {
    return this.api.post(`replenishment-suggestions/${id}/accept`, {});
  }

  stocktakes(params: Record<string, unknown> = {}): Observable<PageResult<DataRecord>> {
    return this.api.list('stocktakes', params);
  }

  stocktakesQuery(params: DomainQueryParams = {}) {
    return domainListQuery<DataRecord>(this.api, 'inventory', 'stocktakes', params);
  }
}
