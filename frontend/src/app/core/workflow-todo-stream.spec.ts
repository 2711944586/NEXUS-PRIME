import { afterEach, describe, expect, it, vi } from 'vitest';

import { streamWorkflowTodo, WorkflowTodoStreamError } from './workflow-todo-stream';

describe('Workflow todo stream client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG;
  });

  it('streams workflow todo snapshots with credentials and CSRF headers', async () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1' };
    vi.stubGlobal('document', { cookie: 'nexus_csrf_token=csrf-workflow' });
    const fetchMock = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      expect(url).toBe('https://api.example.com/api/v1/workflows/tasks/todo/stream');
      expect(init?.credentials).toBe('include');
      expect(init?.method).toBe('GET');
      expect((init?.headers as Headers).get('X-CSRF-Token')).toBe('csrf-workflow');
      return Promise.resolve(new Response(
        'event: snapshot\ndata: {"items":[{"id":8,"title":"采购审批","business_type":"purchase_order","business_id":"42"}],"total":1,"generated_at":"2026-06-22T10:00:00"}\n\n',
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      ));
    });
    vi.stubGlobal('fetch', fetchMock);

    const snapshots: unknown[] = [];
    const result = await streamWorkflowTodo({ onSnapshot: snapshot => snapshots.push(snapshot) });

    expect(result?.items[0]['title']).toBe('采购审批');
    expect(result?.total).toBe(1);
    expect(snapshots).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('converts non-OK responses into stream errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ message: '需要登录', error: 'unauthorized' }),
      { status: 401 }
    ))));

    await expect(streamWorkflowTodo()).rejects.toEqual(new WorkflowTodoStreamError('需要登录', {
      status: 401,
      code: 'unauthorized'
    }));
  });
});
