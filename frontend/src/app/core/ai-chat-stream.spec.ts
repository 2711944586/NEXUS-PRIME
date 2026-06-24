import { afterEach, describe, expect, it, vi } from 'vitest';

import { AiChatStreamError, streamAiChat } from './ai-chat-stream';

describe('AI chat stream client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG;
  });

  it('posts to the stream endpoint with credentials and emits status, chunks, and done', async () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1' };
    vi.stubGlobal('document', { cookie: 'nexus_csrf_token=csrf-stream' });
    const body = [
      'event: status\ndata: {"phase":"accepted","session":{"id":9,"title":"经营分析"}}\n\n',
      'event: chunk\ndata: {"content":"库存"}\n\n',
      'event: chunk\ndata: {"content":"正常"}\n\n',
      'event: done\ndata: {"session":{"id":9,"title":"经营分析"},"message":{"id":12,"role":"assistant","content":"库存正常"},"source":"operations_engine"}\n\n'
    ].join('');
    const fetchMock = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      expect(url).toBe('https://api.example.com/api/v1/ai/chat/stream');
      expect(init?.credentials).toBe('include');
      expect(init?.method).toBe('POST');
      expect((init?.headers as Headers).get('X-CSRF-Token')).toBe('csrf-stream');
      expect(JSON.parse(String(init?.body))).toEqual({ message: '分析库存', session_id: null });
      return Promise.resolve(new Response(body, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const chunks: string[] = [];
    const statuses: unknown[] = [];
    const result = await streamAiChat(
      { message: '分析库存', session_id: null },
      {
        onStatus: status => statuses.push(status),
        onChunk: content => chunks.push(content)
      }
    );

    expect(statuses).toEqual([{ phase: 'accepted', session: { id: 9, title: '经营分析' } }]);
    expect(chunks).toEqual(['库存', '正常']);
    expect(result.message.content).toBe('库存正常');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('surfaces backend SSE error events', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      'event: error\ndata: {"message":"AI 请求过于频繁","error":"ai_rate_limited","status":429}\n\n',
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
    ))));

    await expect(streamAiChat({ message: '继续分析' })).rejects.toMatchObject({
      name: 'AiChatStreamError',
      message: 'AI 请求过于频繁',
      status: 429,
      code: 'ai_rate_limited'
    });
  });

  it('converts non-OK responses into stream errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ message: 'Not found', error: 'not_found' }),
      { status: 404 }
    ))));

    await expect(streamAiChat({ message: 'ping' })).rejects.toEqual(new AiChatStreamError('Not found', {
      status: 404,
      code: 'not_found'
    }));
  });
});
