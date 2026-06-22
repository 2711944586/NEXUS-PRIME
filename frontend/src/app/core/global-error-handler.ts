import { ErrorHandler, inject, Injectable } from '@angular/core';
import { MessageService } from 'primeng/api';

import { FrontendObservabilityService } from './observability';

@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  private readonly messages = inject(MessageService);
  private readonly observability = inject(FrontendObservabilityService);

  handleError(error: unknown): void {
    const msg = error instanceof Error ? error.message : String(error);
    // Suppress chunk-load errors (lazy route not yet loaded) by reloading
    if (msg.includes('ChunkLoadError') || msg.includes('Loading chunk')) {
      this.observability.reloadWindow();
      return;
    }
    this.observability.captureException(error);
    console.error('[GlobalErrorHandler]', error);
    this.messages.add({ severity: 'error', summary: '系统错误', detail: '页面发生意外错误，请刷新后重试', life: 6000 });
  }
}
