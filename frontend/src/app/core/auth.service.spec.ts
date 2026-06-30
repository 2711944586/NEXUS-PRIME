import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { LoginResult } from './models';

const USER_KEY = 'nexus_user_profile';
const CSRF_KEY = 'nexus_csrf_token';

const user = {
  id: 7,
  username: 'ops-member',
  email: 'ops@example.com',
  full_name: '运营成员',
  is_admin: false,
  is_active_user: true,
  avatar: '',
  role_id: 2,
  department_id: 1,
  department_name: '运营中心',
  position: '计划员',
  bio: '',
  phone: '',
  preferences: {}
};

describe('AuthService', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('stores user profile in session storage only after login', () => {
    const loginResult: LoginResult = {
      csrf_token: 'csrf-token',
      user,
      permissions: []
    };
    const api = {
      post: vi.fn().mockReturnValue(of(loginResult))
    };

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: api }]
    });

    const service = TestBed.inject(AuthService);
    service.login({ email: user.email, password: 'demo-password' }).subscribe();

    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(sessionStorage.getItem(USER_KEY)).toContain(user.email);
    expect(sessionStorage.getItem(CSRF_KEY)).toBe('csrf-token');
    expect(service.hasSessionCookieHint()).toBe(true);
  });

  it('clears legacy local storage profile during startup', () => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: {} }]
    });

    TestBed.inject(AuthService);

    expect(localStorage.getItem(USER_KEY)).toBeNull();
  });

  it('treats the session csrf token as a cloud cookie hint', () => {
    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: {} }]
    });

    sessionStorage.setItem(CSRF_KEY, 'cloud-cross-origin-csrf');
    const service = TestBed.inject(AuthService);

    expect(service.hasSessionCookieHint()).toBe(true);
  });
});
