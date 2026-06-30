import { inject, Injectable } from '@angular/core';
import { BehaviorSubject, catchError, map, Observable, of, shareReplay, tap, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginResult, PermissionSummary, RegisterPayload, User } from './models';

const USER_KEY = 'nexus_user_profile';
const PERMS_KEY = 'nexus_permissions';
const CSRF_STORAGE_KEY = 'nexus_csrf_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly userSubject = new BehaviorSubject<User | null>(this.readStoredUser());
  private readonly permissionsSubject = new BehaviorSubject<PermissionSummary[]>(this.readStoredPermissions());
  private refreshUser$: Observable<User | null> | null = null;

  readonly currentUser$ = this.userSubject.asObservable();

  hasPermission(name: string): boolean {
    const user = this.userSubject.value;
    if (!user) return false;
    if (user.is_admin_effective) return true;
    return this.permissionsSubject.value.some(p => p.name === name);
  }

  ensureCsrfToken(): Observable<{ csrf_token: string }> {
    return this.api.get<{ csrf_token: string }>('auth/csrf').pipe(
      tap(result => this.storeCsrfToken(result.csrf_token))
    );
  }

  login(credentials: { email: string; password: string }): Observable<User> {
    return this.api.post<LoginResult>('auth/login', credentials).pipe(
      tap(result => this.applyLoginResult(result)),
      map(result => result.user),
      catchError(error => throwError(() => error))
    );
  }

  register(payload: RegisterPayload): Observable<User> {
    return this.api.post<LoginResult>('auth/register', payload).pipe(
      tap(result => this.applyLoginResult(result)),
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
    if (!this.refreshUser$) {
      this.refreshUser$ = this.api.get<LoginResult>('auth/me').pipe(
        tap(result => this.applyLoginResult(result)),
        map(result => result.user),
        catchError(() => {
          this.clearSession();
          return of(null);
        }),
        shareReplay({ bufferSize: 1, refCount: false, windowTime: 5_000 })
      );
    }
    return this.refreshUser$;
  }

  logout(): void {
    this.api.post('auth/logout', {}).pipe(catchError(() => of(null))).subscribe();
    this.clearSession();
  }

  isAuthenticated(): boolean {
    return Boolean(this.userSubject.value && this.hasSessionCookieHint());
  }

  hasSessionCookieHint(): boolean {
    return document.cookie.split(';').some(item => item.trim().startsWith('nexus_csrf_token='))
      || Boolean(sessionStorage.getItem(CSRF_STORAGE_KEY));
  }

  private applyLoginResult(result: LoginResult): void {
    this.storeCsrfToken(result.csrf_token);
    this.setUser(result.user);
    this.setPermissions(result.permissions ?? []);
  }

  private setUser(user: User): void {
    localStorage.removeItem(USER_KEY);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    this.userSubject.next(user);
    this.refreshUser$ = null;
  }

  private setPermissions(permissions: PermissionSummary[]): void {
    sessionStorage.setItem(PERMS_KEY, JSON.stringify(permissions));
    this.permissionsSubject.next(permissions);
  }

  private clearSession(): void {
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(PERMS_KEY);
    sessionStorage.removeItem(CSRF_STORAGE_KEY);
    this.userSubject.next(null);
    this.permissionsSubject.next([]);
    this.refreshUser$ = null;
  }

  private storeCsrfToken(token: string | null | undefined): void {
    if (token) sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  }

  private readStoredUser(): User | null {
    localStorage.removeItem(USER_KEY);
    try {
      const raw = sessionStorage.getItem(USER_KEY);
      return raw ? (JSON.parse(raw) as User) : null;
    } catch { return null; }
  }

  private readStoredPermissions(): PermissionSummary[] {
    try {
      const raw = sessionStorage.getItem(PERMS_KEY);
      return raw ? (JSON.parse(raw) as PermissionSummary[]) : [];
    } catch { return []; }
  }
}
