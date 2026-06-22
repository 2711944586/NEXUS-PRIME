import { apiUrl } from './api-url';
import { SseMessage, SseParser } from './sse';

const CSRF_COOKIE_NAME = 'nexus_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

export interface AiChatStreamSession {
  id: number;
  title: string;
  created_at?: string | null;
  last_message_at?: string | null;
  message_count?: number;
}

export interface AiChatStreamMessage {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  tokens?: number;
  created_at?: string | null;
  source?: string;
  provider_warning?: string | null;
}

export interface AiChatStreamResult {
  session: AiChatStreamSession;
  message: AiChatStreamMessage;
  source?: string;
  provider_warning?: string | null;
  usage?: Record<string, unknown>;
  rag_sources?: unknown[];
}

export interface AiChatStreamStatus {
  phase?: string;
  session?: AiChatStreamSession;
  rag_sources?: unknown[];
}

export interface AiChatStreamHandlers {
  onStatus?: (status: AiChatStreamStatus) => void;
  onChunk?: (content: string) => void;
  onDone?: (result: AiChatStreamResult) => void;
}

export class AiChatStreamError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, options: { status?: number; code?: string } = {}) {
    super(message);
    this.name = 'AiChatStreamError';
    this.status = options.status;
    this.code = options.code;
  }
}

export async function streamAiChat(
  payload: { message: string; session_id?: number | null },
  handlers: AiChatStreamHandlers = {}
): Promise<AiChatStreamResult> {
  if (typeof fetch === 'undefined') {
    throw new AiChatStreamError('当前环境不支持流式响应');
  }

  const headers = new Headers({
    Accept: 'text/event-stream',
    'Content-Type': 'application/json'
  });
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(apiUrl('ai/chat/stream'), {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!response.body) {
    throw new AiChatStreamError('当前浏览器不支持流式响应');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  let finalResult: AiChatStreamResult | null = null;

  const onMessage = (message: SseMessage): void => {
    const data = parseJsonObject(message.data);
    if (message.event === 'status') {
      handlers.onStatus?.(data as AiChatStreamStatus);
      return;
    }
    if (message.event === 'chunk') {
      const content = typeof data['content'] === 'string' ? data['content'] : '';
      if (content) {
        handlers.onChunk?.(content);
      }
      return;
    }
    if (message.event === 'done') {
      finalResult = data as unknown as AiChatStreamResult;
      handlers.onDone?.(finalResult);
      return;
    }
    if (message.event === 'error') {
      throw new AiChatStreamError(
        typeof data['message'] === 'string' ? data['message'] : 'AI 流式响应失败',
        {
          status: typeof data['status'] === 'number' ? data['status'] : undefined,
          code: typeof data['error'] === 'string' ? data['error'] : undefined
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

  if (!finalResult) {
    throw new AiChatStreamError('AI 流式响应未返回完成事件');
  }

  return finalResult;
}

function parseJsonObject(data: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(data || '{}');
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
  } catch {
    throw new AiChatStreamError('AI 流式响应格式异常', { code: 'invalid_sse_payload' });
  }
}

async function errorFromResponse(response: Response): Promise<AiChatStreamError> {
  const text = await response.text().catch(() => '');
  let message = response.statusText || 'AI 流式请求失败';
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

  return new AiChatStreamError(message, { status: response.status, code });
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
