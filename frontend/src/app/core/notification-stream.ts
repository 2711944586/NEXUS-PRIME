import { apiUrl } from './api-url';
import { DataRecord } from './models';
import { SseMessage, SseParser } from './sse';

const CSRF_COOKIE_NAME = 'nexus_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

export interface NotificationStreamSnapshot {
  items: DataRecord[];
  unread: number;
  generated_at?: string;
}

export interface NotificationStreamHandlers {
  onSnapshot?: (snapshot: NotificationStreamSnapshot) => void;
}

export interface NotificationStreamOptions {
  signal?: AbortSignal;
}

export class NotificationStreamError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, options: { status?: number; code?: string } = {}) {
    super(message);
    this.name = 'NotificationStreamError';
    this.status = options.status;
    this.code = options.code;
  }
}

export async function streamNotifications(
  handlers: NotificationStreamHandlers = {},
  options: NotificationStreamOptions = {}
): Promise<NotificationStreamSnapshot | null> {
  if (typeof fetch === 'undefined') {
    throw new NotificationStreamError('当前环境不支持通知实时流');
  }

  const headers = new Headers({ Accept: 'text/event-stream' });
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(apiUrl('notifications/stream'), {
    method: 'GET',
    credentials: 'include',
    headers,
    signal: options.signal
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!response.body) {
    throw new NotificationStreamError('当前浏览器不支持通知实时流');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  let latestSnapshot: NotificationStreamSnapshot | null = null;

  const onMessage = (message: SseMessage): void => {
    const data = parseJsonObject(message.data);
    if (message.event === 'snapshot') {
      latestSnapshot = normalizeSnapshot(data);
      handlers.onSnapshot?.(latestSnapshot);
      return;
    }
    if (message.event === 'error') {
      const errorData = data as Record<string, unknown>;
      throw new NotificationStreamError(
        typeof errorData['message'] === 'string' ? errorData['message'] : '通知实时流失败',
        {
          status: typeof errorData['status'] === 'number' ? errorData['status'] : undefined,
          code: typeof errorData['error'] === 'string' ? errorData['error'] : undefined
        }
      );
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    parser.push(decoder.decode(value, { stream: true }), onMessage);
  }

  const tail = decoder.decode();
  if (tail) {
    parser.push(tail, onMessage);
  }
  parser.flush(onMessage);

  return latestSnapshot;
}

function normalizeSnapshot(value: Record<string, unknown>): NotificationStreamSnapshot {
  return {
    items: Array.isArray(value['items']) ? value['items'] as DataRecord[] : [],
    unread: typeof value['unread'] === 'number' ? value['unread'] : 0,
    generated_at: typeof value['generated_at'] === 'string' ? value['generated_at'] : undefined
  };
}

function parseJsonObject(data: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(data || '{}');
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
  } catch {
    throw new NotificationStreamError('通知实时流格式异常', { code: 'invalid_sse_payload' });
  }
}

async function errorFromResponse(response: Response): Promise<NotificationStreamError> {
  const text = await response.text().catch(() => '');
  let message = response.statusText || '通知实时流请求失败';
  let code: string | undefined;

  if (text) {
    try {
      const parsed = JSON.parse(text) as { message?: unknown; error?: unknown };
      message = typeof parsed.message === 'string' ? parsed.message : message;
      code = typeof parsed.error === 'string' ? parsed.error : undefined;
    } catch {
      message = text.slice(0, 180) || message;
    }
  }

  return new NotificationStreamError(message, { status: response.status, code });
}

function readCsrfToken(): string {
  const cookieToken = typeof document === 'undefined' ? '' : readCookie(CSRF_COOKIE_NAME);
  if (cookieToken) {
    return cookieToken;
  }
  try {
    return typeof sessionStorage === 'undefined' ? '' : sessionStorage.getItem(CSRF_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function readCookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split(';')
    .map(item => item.trim())
    .find(item => item.startsWith(prefix))
    ?.slice(prefix.length) ?? '';
}
