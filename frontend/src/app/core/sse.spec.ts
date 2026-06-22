import { describe, expect, it } from 'vitest';

import { parseSseFrame, parseSseStreamText, SseParser } from './sse';

describe('SSE parser', () => {
  it('parses named events with JSON data', () => {
    expect(parseSseFrame('event: chunk\ndata: {"content":"经营"}')).toEqual({
      event: 'chunk',
      data: '{"content":"经营"}'
    });
  });

  it('combines multiline data and ignores comments', () => {
    expect(parseSseFrame(': keepalive\nevent: done\ndata: {"a":1}\ndata: {"b":2}\nid: 42')).toEqual({
      event: 'done',
      data: '{"a":1}\n{"b":2}',
      id: '42'
    });
  });

  it('handles frames split across network chunks', () => {
    const parser = new SseParser();
    const messages: unknown[] = [];

    parser.push('event: chunk\ndata: {"content":"A"}\n\nevent: ch', message => messages.push(message));
    parser.push('unk\ndata: {"content":"B"}\n\n', message => messages.push(message));

    expect(messages).toEqual([
      { event: 'chunk', data: '{"content":"A"}' },
      { event: 'chunk', data: '{"content":"B"}' }
    ]);
  });

  it('flushes the final frame when a stream closes without a trailing blank line', () => {
    expect(parseSseStreamText('event: error\r\ndata: {"message":"失败"}')).toEqual([
      { event: 'error', data: '{"message":"失败"}' }
    ]);
  });
});
