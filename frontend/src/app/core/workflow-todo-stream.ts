import { apiUrl } from './api-url';
import { DataRecord } from './models';
import { SseMessage, SseParser } from './sse';

const CSRF_COOKIE_NAME = 'nexus_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

export interface WorkflowTodoSnapshot {
  items: DataRecord[];
  total: number;
  generated_at?: string;
}

export interface WorkflowTodoStreamHandlers {
  onSnapshot?: (snapshot: WorkflowTodoSnapshot) => void;
}

export interface WorkflowTodoStreamOptions {
  signal?: AbortSignal;
}

export class WorkflowTodoStreamError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, options: { status?: number; code?: string } = {}) {
    super(message);
    this.name = 'WorkflowTodoStreamError';
    this.status = options.status;
    this.code = options.code;
  }
}

export async function streamWorkflowTodo(
  handlers: WorkflowTodoStreamHandlers = {},
  options: WorkflowTodoStreamOptions = {}
): Promise<WorkflowTodoSnapshot | null> {
  if (typeof fetch === 'undefined') {
    throw new WorkflowTodoStreamError('当前环境不支持工作流待办流');
  }

  const headers = new Headers({ Accept: 'text/event-stream' });
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(apiUrl('workflows/tasks/todo/stream'), {
    method: 'GET',
    credentials: 'include',
    headers,
    signal: options.signal
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!response.body) {
    throw new WorkflowTodoStreamError('当前浏览器不支持工作流待办流');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  let latestSnapshot: WorkflowTodoSnapshot | null = null;

  const onMessage = (message: SseMessage): void => {
    const data = parseJsonObject(message.data);
    if (message.event === 'snapshot') {
      latestSnapshot = normalizeSnapshot(data);
      handlers.onSnapshot?.(latestSnapshot);
      return;
    }
    if (message.event === 'error') {
      const errorData = data as Record<string, unknown>;
      throw new WorkflowTodoStreamError(
        typeof errorData['message'] === 'string' ? errorData['message'] : '工作流待办流失败',
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

function normalizeSnapshot(value: Record<string, unknown>): WorkflowTodoSnapshot {
  return {
    items: Array.isArray(value['items']) ? value['items'] as DataRecord[] : [],
    total: typeof value['total'] === 'number' ? value['total'] : 0,
    generated_at: typeof value['generated_at'] === 'string' ? value['generated_at'] : undefined
  };
}

function parseJsonObject(data: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(data || '{}');
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
  } catch {
    throw new WorkflowTodoStreamError('工作流待办流格式异常', { code: 'invalid_sse_payload' });
  }
}

async function errorFromResponse(response: Response): Promise<WorkflowTodoStreamError> {
  const text = await response.text().catch(() => '');
  let message = response.statusText || '工作流待办流请求失败';
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

  return new WorkflowTodoStreamError(message, { status: response.status, code });
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
