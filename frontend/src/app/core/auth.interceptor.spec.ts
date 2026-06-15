import { HttpHandlerFn, HttpRequest, HttpResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { MessageService } from 'primeng/api';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';

import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  it('sends credentials and csrf header for write requests', () => {
    document.cookie = 'nexus_csrf_token=csrf-test';
    const seen = vi.fn();
    const next: HttpHandlerFn = (req: HttpRequest<unknown>) => {
      seen(req);
      expect(req.withCredentials).toBe(true);
      expect(req.headers.get('X-CSRF-Token')).toBe('csrf-test');
      return of(new HttpResponse({ status: 200 }));
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: Router, useValue: { navigate: vi.fn() } },
        { provide: MessageService, useValue: { add: vi.fn() } }
      ]
    });

    TestBed.runInInjectionContext(() => {
      authInterceptor(new HttpRequest('POST', '/api/v1/products', {}), next).subscribe();
    });

    expect(seen).toHaveBeenCalled();
  });
});
