import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { SalesOrder, SalesOrderPage } from './api/typed-api';
import { DomainQueryParams, domainDetailQuery, domainListQuery } from './domain-query';

@Injectable({ providedIn: 'root' })
export class SalesService {
  private readonly api = inject(ApiService);

  orders(params: Record<string, unknown> = {}): Observable<SalesOrderPage> {
    return this.api.list('orders', params);
  }

  ordersQuery(params: DomainQueryParams = {}) {
    return domainListQuery<SalesOrder>(this.api, 'sales', 'orders', params);
  }

  order(id: number): Observable<SalesOrder> {
    return this.api.get(`orders/${id}`);
  }

  orderQuery(id: number) {
    return domainDetailQuery<SalesOrder>(this.api, 'sales', 'orders', id);
  }
}
