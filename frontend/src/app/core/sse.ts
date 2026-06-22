export interface SseMessage {
  event: string;
  data: string;
  id?: string;
  retry?: number;
}

type SseMessageHandler = (message: SseMessage) => void;

export class SseParser {
  private buffer = '';

  push(chunk: string, onMessage: SseMessageHandler): void {
    this.buffer += chunk;
    this.drain(onMessage, false);
  }

  flush(onMessage: SseMessageHandler): void {
    this.drain(onMessage, true);
  }

  private drain(onMessage: SseMessageHandler, flush: boolean): void {
    this.buffer = normalizeNewlines(this.buffer);
    let boundary = this.buffer.indexOf('\n\n');

    while (boundary >= 0) {
      const frame = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const message = parseSseFrame(frame);
      if (message) {
        onMessage(message);
      }
      boundary = this.buffer.indexOf('\n\n');
    }

    if (flush && this.buffer.trim()) {
      const message = parseSseFrame(this.buffer);
      this.buffer = '';
      if (message) {
        onMessage(message);
      }
    }
  }
}

export function parseSseFrame(frame: string): SseMessage | null {
  const data: string[] = [];
  let event = '';
  let id: string | undefined;
  let retry: number | undefined;

  for (const rawLine of normalizeNewlines(frame).split('\n')) {
    if (!rawLine || rawLine.startsWith(':')) {
      continue;
    }

    const colon = rawLine.indexOf(':');
    const field = colon >= 0 ? rawLine.slice(0, colon) : rawLine;
    const rawValue = colon >= 0 ? rawLine.slice(colon + 1) : '';
    const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue;

    if (field === 'event') {
      event = value;
    } else if (field === 'data') {
      data.push(value);
    } else if (field === 'id') {
      id = value;
    } else if (field === 'retry') {
      const retryValue = Number.parseInt(value, 10);
      retry = Number.isFinite(retryValue) ? retryValue : undefined;
    }
  }

  if (!event && data.length === 0 && id === undefined && retry === undefined) {
    return null;
  }

  return {
    event: event || 'message',
    data: data.join('\n'),
    ...(id !== undefined ? { id } : {}),
    ...(retry !== undefined ? { retry } : {})
  };
}

export function parseSseStreamText(text: string): SseMessage[] {
  const parser = new SseParser();
  const messages: SseMessage[] = [];
  parser.push(text, message => messages.push(message));
  parser.flush(message => messages.push(message));
  return messages;
}

function normalizeNewlines(value: string): string {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}
