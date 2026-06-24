import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { MessageService } from 'primeng/api';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from '../core/api.service';
import { OperationsTasksPage } from './operations-tasks.page';

function emptyTodo() {
  return { items: [], stock_quantity: 0 };
}

function emptyExceptions() {
  return { items: [], total: 0 };
}

function emptyAnalytics() {
  return {
    kpis: { total_sales: 0, unpaid_amount: 0, pending_purchase: 0, active_alerts: 0, collaboration_items: 0 },
    sales_trend: [],
    risk_mix: [],
    collaboration: [],
    top_customers: [],
    procurement_stages: [],
    aging_buckets: [],
    warehouse_turnover: [],
    supplier_score: [],
    inventory_risk_rank: [],
    order_status_flow: [],
    cash_collection_trend: [],
    action_queue: [],
    operational_efficiency: [],
    module_throughput: []
  };
}

function baseQueue() {
  return {
    summary: {
      total: 1,
      open_notifications: 1,
      deployment_attention: 0,
      business_exceptions: 0,
      p0: 0,
      p1: 0,
      p2: 1,
      generated_at: '2026-06-22T09:00:00',
      next_action: '先处理队列。'
    },
    items: [
      {
        id: 'notification-1',
        source_id: 1,
        source: 'notification',
        title: '原始通知',
        description: 'legacy',
        priority: 'P2',
        status: 'open',
        owner: 'member',
        source_path: '/app/notifications/1',
        detail_path: '/app/notifications/1',
        action_label: '处理完成',
        action_kind: 'complete_notification',
        category: 'system',
        created_at: '2026-06-22T09:00:00'
      }
    ]
  };
}

function createPage(api: Partial<ApiService>, messages = { add: vi.fn() }): OperationsTasksPage {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api },
      { provide: MessageService, useValue: messages }
    ]
  });
  return runInInjectionContext(injector, () => new OperationsTasksPage());
}

describe('OperationsTasksPage workflow todo stream', () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('merges streamed workflow todo tasks into the shift queue without dropping legacy items', async () => {
    const api = {
      get: vi.fn((path: string) => {
        if (path === 'operations/task-queue') {
          return of(baseQueue());
        }
        if (path === 'operations/todo') {
          return of(emptyTodo());
        }
        if (path === 'operations/exceptions') {
          return of(emptyExceptions());
        }
        return of(emptyAnalytics());
      })
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      'event: snapshot\ndata: {"items":[{"id":9,"title":"采购单 42 审批","business_type":"purchase_order","business_id":"42","process_key":"purchase_order_approval","assignee_name":"approver","created_at":"2026-06-22T09:30:00"}],"total":1,"generated_at":"2026-06-22T09:30:00"}\n\n',
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));
    const page = createPage(api as Partial<ApiService>) as unknown as {
      ngOnInit: () => void;
      ngOnDestroy: () => void;
      taskQueue: () => ReturnType<typeof baseQueue>;
    };

    page.ngOnInit();
    expect(page.taskQueue().items.map(item => item.id)).toEqual(['notification-1']);

    await flushPromises();

    expect(page.taskQueue().items.map(item => item.id)).toContain('workflow-9');
    expect(page.taskQueue().items.map(item => item.id)).toContain('notification-1');
    expect(page.taskQueue().items.find(item => item.id === 'workflow-9')).toMatchObject({
      source: 'workflow',
      business_type: 'purchase_order',
      business_id: '42',
      source_path: '/app/procurement/orders/42',
      action_kind: 'navigate'
    });
    expect(page.taskQueue().summary.business_exceptions).toBe(1);
    expect(page.taskQueue().summary.p1).toBe(1);

    page.ngOnDestroy();
  });

  it('reconnects after a completed workflow stream', async () => {
    vi.useFakeTimers();
    const api = {
      get: vi.fn((path: string) => {
        if (path === 'operations/task-queue') {
          return of(baseQueue());
        }
        if (path === 'operations/todo') {
          return of(emptyTodo());
        }
        if (path === 'operations/exceptions') {
          return of(emptyExceptions());
        }
        return of(emptyAnalytics());
      })
    };
    const fetchMock = vi.fn((_url: RequestInfo | URL) => {
      return Promise.resolve(new Response(
        'event: snapshot\ndata: {"items":[],"total":0}\n\n',
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      ));
    });
    vi.stubGlobal('fetch', fetchMock);
    const page = createPage(api as Partial<ApiService>) as unknown as {
      ngOnInit: () => void;
      ngOnDestroy: () => void;
    };

    page.ngOnInit();
    await flushPromises();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    page.ngOnDestroy();
  });

  it('aborts an active workflow stream when the page is destroyed', async () => {
    const api = {
      get: vi.fn((path: string) => {
        if (path === 'operations/task-queue') {
          return of(baseQueue());
        }
        if (path === 'operations/todo') {
          return of(emptyTodo());
        }
        if (path === 'operations/exceptions') {
          return of(emptyExceptions());
        }
        return of(emptyAnalytics());
      })
    };
    const abortSignals: AbortSignal[] = [];
    vi.stubGlobal('fetch', vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal) {
        abortSignals.push(init.signal);
      }
      return Promise.resolve(new Response(new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('event: snapshot\ndata: {"items":[],"total":0}\n\n'));
        }
      }), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      }));
    }));
    const page = createPage(api as Partial<ApiService>) as unknown as {
      ngOnInit: () => void;
      ngOnDestroy: () => void;
    };

    page.ngOnInit();
    await flushPromises();
    page.ngOnDestroy();

    expect(abortSignals.some(signal => signal.aborted)).toBe(true);
  });

  it('approves purchase workflow queue items through the legacy procurement action endpoint', () => {
    const workflowItem = {
      id: 'workflow-9',
      source_id: 9,
      source: 'workflow',
      business_type: 'purchase_order',
      business_id: '42',
      title: '采购单 42 审批',
      description: 'purchase_order_approval · purchase_order #42',
      priority: 'P1',
      status: 'open',
      owner: 'approver',
      source_path: '/app/procurement/orders/42',
      detail_path: '/app/procurement/orders/42',
      action_label: '查看审批',
      action_kind: 'navigate',
      category: 'approval',
      created_at: '2026-06-22T09:30:00'
    };
    const api = {
      get: vi.fn((path: string) => {
        if (path === 'operations/task-queue') {
          return of({
            ...baseQueue(),
            summary: { ...baseQueue().summary, total: 1, business_exceptions: 1, p1: 1, p2: 0 },
            items: [workflowItem]
          });
        }
        if (path === 'operations/todo') {
          return of(emptyTodo());
        }
        if (path === 'operations/exceptions') {
          return of(emptyExceptions());
        }
        return of(emptyAnalytics());
      }),
      post: vi.fn(() => of({ id: 42 }))
    };
    const messages = { add: vi.fn() };
    const page = createPage(api as Partial<ApiService>, messages) as unknown as {
      approveWorkflowQueueTask: (item: typeof workflowItem) => void;
    };

    page.approveWorkflowQueueTask(workflowItem);

    expect(api.post).toHaveBeenCalledWith('procurement/orders/42/approve', expect.objectContaining({
      remark: expect.stringContaining('任务中心通过'),
      comment: expect.stringContaining('任务中心通过')
    }));
    expect(api.get).toHaveBeenCalledWith('operations/task-queue');
    expect(messages.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '审批已通过' }));
  });

  it('rejects non-purchase workflow queue items through the generic workflow endpoint', () => {
    const workflowItem = {
      id: 'workflow-15',
      source_id: 15,
      source: 'workflow',
      business_type: 'stocktake',
      business_id: '88',
      title: '盘点审批',
      description: 'stocktake_approval · stocktake #88',
      priority: 'P1',
      status: 'open',
      owner: 'approver',
      source_path: '/app/tasks',
      detail_path: '/app/tasks',
      action_label: '查看审批',
      action_kind: 'navigate',
      category: 'approval',
      created_at: '2026-06-22T09:30:00'
    };
    const api = {
      get: vi.fn((path: string) => {
        if (path === 'operations/task-queue') {
          return of(baseQueue());
        }
        if (path === 'operations/todo') {
          return of(emptyTodo());
        }
        if (path === 'operations/exceptions') {
          return of(emptyExceptions());
        }
        return of(emptyAnalytics());
      }),
      post: vi.fn(() => of({ id: 15 }))
    };
    const page = createPage(api as Partial<ApiService>) as unknown as {
      rejectWorkflowQueueTask: (item: typeof workflowItem) => void;
    };

    page.rejectWorkflowQueueTask(workflowItem);

    expect(api.post).toHaveBeenCalledWith('workflows/tasks/15/reject', expect.objectContaining({
      remark: expect.stringContaining('任务中心驳回'),
      comment: expect.stringContaining('任务中心驳回')
    }));
  });
});

async function flushPromises(): Promise<void> {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
  }
}
