import { TestBed } from '@angular/core/testing';
import { getState } from '@ngrx/signals';
import { describe, expect, it } from 'vitest';

import { ListWorkbenchStore } from './list-workbench.store';

describe('ListWorkbenchStore', () => {
  function createStore() {
    TestBed.configureTestingModule({
      providers: [ListWorkbenchStore]
    });

    return TestBed.inject(ListWorkbenchStore);
  }

  it('starts with interaction-only list state', () => {
    const store = createStore();

    expect(getState(store)).toEqual({
      query: '',
      statusFilter: '',
      categoryFilter: '',
      selectedWarehouseId: '',
      page: 1,
      pageSize: 12,
      chartMode: 'category'
    });
    expect(Object.keys(getState(store))).not.toEqual(expect.arrayContaining(['items', 'rows', 'data', 'records']));
  });

  it('resets pagination when filters change', () => {
    const store = createStore();

    store.setPage(4);
    store.setQuery('bearing');

    expect(store.query()).toBe('bearing');
    expect(store.page()).toBe(1);

    store.setPage(3);
    store.setCategoryFilter('传动件');

    expect(store.categoryFilter()).toBe('传动件');
    expect(store.page()).toBe(1);
  });

  it('normalizes pagination values', () => {
    const store = createStore();

    store.setPage(3.8);
    store.setPageSize(25.9);

    expect(store.page()).toBe(1);
    expect(store.pageSize()).toBe(25);

    store.setPage(0);
    store.setPageSize(Number.NaN);

    expect(store.page()).toBe(1);
    expect(store.pageSize()).toBe(12);
  });

  it('resets back to the initial workbench state', () => {
    const store = createStore();

    store.setQuery('pump');
    store.setCategoryFilter('泵阀');
    store.setChartMode('risk');
    store.reset();

    expect(store.query()).toBe('');
    expect(store.categoryFilter()).toBe('');
    expect(store.chartMode()).toBe('category');
  });
});
