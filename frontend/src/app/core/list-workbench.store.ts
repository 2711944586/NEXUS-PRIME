import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';

export interface ListWorkbenchState {
  query: string;
  statusFilter: string;
  categoryFilter: string;
  selectedWarehouseId: string;
  page: number;
  pageSize: number;
  chartMode: string;
}

export function createInitialListWorkbenchState(): ListWorkbenchState {
  return {
    query: '',
    statusFilter: '',
    categoryFilter: '',
    selectedWarehouseId: '',
    page: 1,
    pageSize: 12,
    chartMode: 'category'
  };
}

function positiveInteger(value: number, fallback = 1): number {
  return Number.isFinite(value) ? Math.max(1, Math.trunc(value)) : fallback;
}

export const ListWorkbenchStore = signalStore(
  withState(createInitialListWorkbenchState),
  withMethods((store) => ({
    setQuery(query: string): void {
      patchState(store, { query, page: 1 });
    },
    setStatusFilter(statusFilter: string): void {
      patchState(store, { statusFilter, page: 1 });
    },
    setCategoryFilter(categoryFilter: string): void {
      patchState(store, { categoryFilter, page: 1 });
    },
    setSelectedWarehouseId(selectedWarehouseId: string): void {
      patchState(store, { selectedWarehouseId, page: 1 });
    },
    setPage(page: number): void {
      patchState(store, { page: positiveInteger(page) });
    },
    setPageSize(pageSize: number): void {
      patchState(store, { pageSize: positiveInteger(pageSize, 12), page: 1 });
    },
    setChartMode(chartMode: string): void {
      patchState(store, { chartMode });
    },
    reset(): void {
      patchState(store, createInitialListWorkbenchState());
    }
  }))
);
