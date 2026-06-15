import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { MessageService } from 'primeng/api';
import { catchError, throwError } from 'rxjs';

const CSRF_COOKIE_NAME = 'nexus_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const messages = inject(MessageService);
  const csrfToken = MUTATING_METHODS.has(req.method) ? readCookie(CSRF_COOKIE_NAME) || sessionStorage.getItem(CSRF_STORAGE_KEY) || '' : '';
  const request = req.clone({
    withCredentials: true,
    setHeaders: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}
  });

  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      const apiMessage = error.error?.message || error.message || '请求失败';
      const isSessionProbe = req.url.includes('/auth/me');
      const isLoginRequest = req.url.includes('/auth/login');
      if (error.status === 401 && !isLoginRequest && !isSessionProbe) {
        router.navigate(['/auth/login'], { queryParams: { redirect: router.url } });
      }
      if (error.status >= 400 && !(error.status === 401 && isSessionProbe) && !isLoginRequest) {
        messages.add({ severity: error.status >= 500 ? 'error' : 'warn', summary: '操作未完成', detail: apiMessage });
      }
      const normalized = new Error(apiMessage) as Error & { status?: number; code?: string; fields?: Record<string, string> };
      normalized.status = error.status;
      normalized.code = error.error?.error;
      normalized.fields = error.error?.fields;
      return throwError(() => normalized);
    })
  );
};

function readCookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split(';')
    .map(item => item.trim())
    .find(item => item.startsWith(prefix))
    ?.slice(prefix.length) ?? '';
}
