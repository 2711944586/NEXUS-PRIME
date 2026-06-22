import { describe, expect, it } from 'vitest';

import type { operations } from './generated/schema';
import type { ApiPath, ApiResourcePage, ApiSuccessData } from './typed-api';

describe('OpenAPI typed API helpers', () => {
  it('exposes generated runtime paths as TypeScript literals', () => {
    const productsPath: ApiPath = '/api/v1/products';

    expect(productsPath).toBe('/api/v1/products');
  });

  it('extracts success payload data from generated operations', () => {
    const page: ApiSuccessData<operations['list_products']> = {
      items: [],
      pagination: {
        page: 1,
        page_size: 20,
        total: 0,
        pages: 1,
        has_next: false,
        has_prev: false
      }
    };

    expect(page.pagination.page_size).toBe(20);
  });

  it('can express registry resource pages without storing API data in UI stores', () => {
    const page: ApiResourcePage<'Product'> = {
      items: [],
      pagination: {
        page: 1,
        page_size: 10,
        total: 0,
        pages: 1,
        has_next: false,
        has_prev: false
      }
    };

    expect(page.items).toEqual([]);
  });
});
