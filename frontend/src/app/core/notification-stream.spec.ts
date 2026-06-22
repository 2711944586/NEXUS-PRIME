import { afterEach, describe, expect, it, vi } from 'vitest';

import { NotificationStreamError, streamNotifications } from './notification-stream';

describe('Notification stream client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG;
  });

  it('streams snapshots with credentials and CSRF headers', async () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1' };
    vi.stubGlobal('document', { cookie: 'nexus_csrf_token=csrf-notify' });
    const fetchMock = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      expect(url).toBe('https://api.example.com/api/v1/notifications/stream');
      expect(init?.credentials).toBe('include');
      expect(init?.method).toBe('GET');
      expect((init?.headers as Headers).get('X-CSRF-Token')).toBe('csrf-notify');
      return Promise.resolve(new Response(
        'event: snapshot\ndata: {"items":[{"id":7,"title":"库存预警","is_read":false}],"unread":1,"generated_at":"2026-06-22T10:00:00"}\n\n',
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      ));
    });
    vi.stubGlobal('fetch', fetchMock);

    const snapshots: unknown[] = [];
    const result = await streamNotifications({
      onSnapshot: snapshot => snapshots.push(snapshot)
    });

    expect(result?.items[0]['title']).toBe('库存预警');
    expect(result?.unread).toBe(1);
    expect(snapshots).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('converts non-OK responses into stream errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ message: '权限不足', error: 'permission_denied' }),
      { status: 403 }
    ))));

    await expect(streamNotifications()).rejects.toEqual(new NotificationStreamError('权限不足', {
      status: 403,
      code: 'permission_denied'
    }));
  });
});
