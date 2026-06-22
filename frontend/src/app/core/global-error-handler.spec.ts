import { TestBed } from '@angular/core/testing';
import { MessageService } from 'primeng/api';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { GlobalErrorHandler } from './global-error-handler';
import { FrontendObservabilityService } from './observability';

describe('GlobalErrorHandler', () => {
  const add = vi.fn();
  const captureException = vi.fn();
  const reloadWindow = vi.fn();

  beforeEach(() => {
    add.mockReset();
    captureException.mockReset();
    reloadWindow.mockReset();
    TestBed.configureTestingModule({
      providers: [
        GlobalErrorHandler,
        { provide: FrontendObservabilityService, useValue: { captureException, reloadWindow } },
        { provide: MessageService, useValue: { add } }
      ]
    });
  });

  it('captures unexpected errors and shows a user-facing message', () => {
    const handler = TestBed.inject(GlobalErrorHandler);
    const error = new Error('unexpected');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    handler.handleError(error);

    expect(captureException).toHaveBeenCalledWith(error);
    expect(add).toHaveBeenCalledWith({
      severity: 'error',
      summary: '系统错误',
      detail: '页面发生意外错误，请刷新后重试',
      life: 6000
    });

    consoleSpy.mockRestore();
  });

  it('reloads on chunk load errors without capturing to Sentry', () => {
    const handler = TestBed.inject(GlobalErrorHandler);

    handler.handleError(new Error('ChunkLoadError: loading chunk failed'));

    expect(reloadWindow).toHaveBeenCalled();
    expect(captureException).not.toHaveBeenCalled();
    expect(add).not.toHaveBeenCalled();
  });
});
