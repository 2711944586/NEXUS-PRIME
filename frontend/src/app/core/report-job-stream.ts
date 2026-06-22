import { apiUrl } from './api-url';
import { DataRecord } from './models';
import { SseMessage, SseParser } from './sse';

const CSRF_COOKIE_NAME = 'nexus_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

export type ReportJobStatus = 'pending' | 'running' | 'success' | 'failed' | string;

export interface ReportJobRecord {
  id: string;
  job_id?: string;
  status?: ReportJobStatus;
  error_message?: string | null;
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  created_at?: string | null;
  finished_at?: string | null;
  [key: string]: unknown;
}

export interface ReportJobStreamResult {
  job_id: string;
  job: ReportJobRecord;
  report?: DataRecord | null;
  data?: unknown;
}

export interface ReportJobStreamHandlers {
  onStatus?: (result: ReportJobStreamResult) => void;
  onDone?: (result: ReportJobStreamResult) => void;
  onFailed?: (result: ReportJobStreamResult) => void;
}

export class ReportJobStreamError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, options: { status?: number; code?: string } = {}) {
    super(message);
    this.name = 'ReportJobStreamError';
    this.status = options.status;
    this.code = options.code;
  }
}

export async function streamReportJob(jobId: string, handlers: ReportJobStreamHandlers = {}): Promise<ReportJobStreamResult> {
  if (typeof fetch === 'undefined') {
    throw new ReportJobStreamError('当前环境不支持报表任务流');
  }
  if (!jobId) {
    throw new ReportJobStreamError('报表任务编号不能为空', { code: 'missing_job_id' });
  }

  const headers = new Headers({ Accept: 'text/event-stream' });
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(apiUrl(`reports/jobs/${jobId}/stream`), {
    method: 'GET',
    credentials: 'include',
    headers
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!response.body) {
    throw new ReportJobStreamError('当前浏览器不支持报表任务流');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  let finalResult: ReportJobStreamResult | null = null;

  const onMessage = (message: SseMessage): void => {
    const data = parseJsonObject(message.data);
    if (message.event === 'status') {
      handlers.onStatus?.(data);
      return;
    }
    if (message.event === 'done') {
      finalResult = data;
      handlers.onDone?.(data);
      return;
    }
    if (message.event === 'failed') {
      finalResult = data;
      handlers.onFailed?.(data);
      return;
    }
    if (message.event === 'error') {
      const errorData = data as unknown as Record<string, unknown>;
      throw new ReportJobStreamError(
        typeof errorData['message'] === 'string' ? errorData['message'] : '报表任务流失败',
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

  if (!finalResult) {
    throw new ReportJobStreamError('报表任务流未返回完成事件', { code: 'missing_final_event' });
  }

  return finalResult;
}

function parseJsonObject(data: string): ReportJobStreamResult {
  try {
    const parsed = JSON.parse(data || '{}');
    return parsed && typeof parsed === 'object' ? parsed as ReportJobStreamResult : ({} as ReportJobStreamResult);
  } catch {
    throw new ReportJobStreamError('报表任务流格式异常', { code: 'invalid_sse_payload' });
  }
}

async function errorFromResponse(response: Response): Promise<ReportJobStreamError> {
  const text = await response.text().catch(() => '');
  let message = response.statusText || '报表任务流请求失败';
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

  return new ReportJobStreamError(message, { status: response.status, code });
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
