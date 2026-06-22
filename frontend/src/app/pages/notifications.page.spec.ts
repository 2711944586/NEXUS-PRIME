import '@angular/compiler';

import { Injector, runInInjectionContext } from '@angular/core';
import { MessageService } from 'primeng/api';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from '../core/api.service';
import { NotificationsPage } from './notifications.page';

function createPage(api: Partial<ApiService>, messages = { add: vi.fn() }): NotificationsPage {
  const injector = Injector.create({
    providers: [
      { provide: ApiService, useValue: api },
      { provide: MessageService, useValue: messages }
    ]
  });
  return runInInjectionContext(injector, () => new NotificationsPage());
}

describe('NotificationsPage realtime stream', () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('loads the legacy list and applies streamed snapshots without duplicate rows', async () => {
    const api = {
      list: vi.fn(() => of({
        items: [{ id: 1, title: '原始通知', content: 'legacy', is_read: false, category: 'system', type: 'info' }],
        pagination: { page: 1, page_size: 100, total: 1, pages: 1, has_next: false, has_prev: false }
      }))
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      'event: snapshot\ndata: {"items":[{"id":2,"title":"库存预警","content":"stock","is_read":false,"category":"stock","type":"warning"},{"id":2,"title":"库存预警重复","content":"stock","is_read":false,"category":"stock","type":"warning"}],"unread":1}\n\n',
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));
    const page = createPage(api as Partial<ApiService>) as unknown as {
      ngOnInit: () => void;
      ngOnDestroy: () => void;
      notifications: () => Array<{ id?: number; title?: string }>;
      unreadCount: () => number;
    };

    page.ngOnInit();

    expect(page.notifications()).toEqual([expect.objectContaining({ id: 1, title: '原始通知' })]);
    await Promise.resolve();
    await Promise.resolve();

    expect(page.notifications()).toEqual([expect.objectContaining({ id: 2, title: '库存预警' })]);
    expect(page.unreadCount()).toBe(1);

    page.ngOnDestroy();
  });

  it('reconnects after a completed stream and aborts on destroy', async () => {
    vi.useFakeTimers();
    const api = {
      list: vi.fn(() => of({
        items: [],
        pagination: { page: 1, page_size: 100, total: 0, pages: 0, has_next: false, has_prev: false }
      }))
    };
    const fetchMock = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      return Promise.resolve(new Response(
        'event: snapshot\ndata: {"items":[],"unread":0}\n\n',
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

  it('aborts an active notification stream when the page is destroyed', async () => {
    const api = {
      list: vi.fn(() => of({
        items: [],
        pagination: { page: 1, page_size: 100, total: 0, pages: 0, has_next: false, has_prev: false }
      }))
    };
    const abortSignals: AbortSignal[] = [];
    vi.stubGlobal('fetch', vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal) {
        abortSignals.push(init.signal);
      }
      return Promise.resolve(new Response(new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('event: snapshot\ndata: {"items":[],"unread":0}\n\n'));
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
});

async function flushPromises(): Promise<void> {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
  }
}
