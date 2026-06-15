import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { ApiEnvelope, LookupItem, PageResult, UserPreferences } from './models';
import { apiUrl } from './api-url';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  get<T>(path: string, params?: Record<string, unknown>): Observable<T> {
    return this.http
      .get<ApiEnvelope<T>>(this.url(path), { params: this.toParams(params), withCredentials: true })
      .pipe(map(unwrapEnvelope));
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<ApiEnvelope<T>>(this.url(path), body, { withCredentials: true }).pipe(map(unwrapEnvelope));
  }

  postForm<T>(path: string, body: FormData): Observable<T> {
    return this.http.post<ApiEnvelope<T>>(this.url(path), body, { withCredentials: true }).pipe(map(unwrapEnvelope));
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<ApiEnvelope<T>>(this.url(path), body, { withCredentials: true }).pipe(map(unwrapEnvelope));
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<ApiEnvelope<T>>(this.url(path), body, { withCredentials: true }).pipe(map(unwrapEnvelope));
  }

  delete<T>(path: string): Observable<T> {
    return this.http.delete<ApiEnvelope<T>>(this.url(path), { withCredentials: true }).pipe(map(unwrapEnvelope));
  }

  list<T>(resource: string, params: Record<string, unknown>): Observable<PageResult<T>> {
    return this.get<PageResult<T>>(resource, params);
  }

  lookup(path: string, params?: Record<string, unknown>): Observable<LookupItem[]> {
    return this.get<{ items: LookupItem[] }>(path, params).pipe(map(result => result.items));
  }

  preferences(): Observable<UserPreferences> {
    return this.get<UserPreferences>('me/preferences');
  }

  savePreferences(preferences: UserPreferences): Observable<UserPreferences> {
    return this.put<UserPreferences>('me/preferences', preferences);
  }

  private url(path: string): string {
    return apiUrl(path);
  }

  private toParams(params?: Record<string, unknown>): HttpParams {
    let httpParams = new HttpParams();
    Object.entries(params ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        httpParams = httpParams.set(key, String(value));
      }
    });
    return httpParams;
  }
}

function unwrapEnvelope<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.error) {
    throw new Error(envelope.message || envelope.error);
  }
  return envelope.data;
}
