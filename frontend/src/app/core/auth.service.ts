import { inject, Injectable } from '@angular/core';
import { BehaviorSubject, catchError, map, Observable, of, tap, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginResult, RegisterPayload, User } from './models';

const USER_KEY = 'nexus_user_profile';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly userSubject = new BehaviorSubject<User | null>(this.readStoredUser());

  readonly currentUser$ = this.userSubject.asObservable();

  ensureCsrfToken(): Observable<{ csrf_token: string }> {
    return this.api.get<{ csrf_token: string }>('auth/csrf').pipe(
      tap(result => this.storeCsrfToken(result.csrf_token))
    );
  }

  login(credentials: { email: string; password: string }): Observable<User> {
    return this.api.post<LoginResult>('auth/login', credentials).pipe(
      tap(result => {
        this.storeCsrfToken(result.csrf_token);
        this.setUser(result.user);
      }),
      map(result => result.user),
      catchError(error => throwError(() => error))
    );
  }

  register(payload: RegisterPayload): Observable<User> {
    return this.api.post<LoginResult>('auth/register', payload).pipe(
      tap(result => {
        this.storeCsrfToken(result.csrf_token);
        this.setUser(result.user);
      }),
      map(result => result.user),
      catchError(error => throwError(() => error))
    );
  }

  updateProfile(payload: Partial<User>): Observable<User> {
    return this.api.put<User>('me/profile', payload).pipe(
      tap(user => this.setUser(user)),
      catchError(error => throwError(() => error))
    );
  }

  updateCurrentUser(user: User): void {
    this.setUser(user);
  }

  refreshCurrentUser(): Observable<User | null> {
    return this.api.get<User>('auth/me').pipe(
      tap(user => this.setUser(user)),
      catchError(() => {
        this.clearSession();
        return of(null);
      })
    );
  }

  logout(): void {
    this.api.post('auth/logout', {}).pipe(catchError(() => of(null))).subscribe();
    this.clearSession();
  }

  isAuthenticated(): boolean {
    return Boolean(this.userSubject.value && this.hasSessionCookieHint());
  }

  hasSessionCookieHint(): boolean {
    return document.cookie.split(';').some(item => item.trim().startsWith('nexus_csrf_token='));
  }

  private setUser(user: User): void {
    localStorage.removeItem(USER_KEY);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    this.userSubject.next(user);
  }

  private clearSession(): void {
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(CSRF_STORAGE_KEY);
    this.userSubject.next(null);
  }

  private storeCsrfToken(token: string | null | undefined): void {
    if (token) {
      sessionStorage.setItem(CSRF_STORAGE_KEY, token);
    }
  }

  private readStoredUser(): User | null {
    localStorage.removeItem(USER_KEY);
    const raw = sessionStorage.getItem(USER_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  }
}
