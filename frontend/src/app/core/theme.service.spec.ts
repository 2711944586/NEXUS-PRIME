import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  afterEach(() => {
    localStorage.removeItem('nexus_theme_mode');
    localStorage.removeItem('nexus_theme_mode_v2');
    document.documentElement.classList.remove('dark-cockpit', 'light-luxury', 'operations-console');
  });

  it('toggles between cockpit and luxury themes', () => {
    TestBed.configureTestingModule({
      providers: [
        ThemeService,
        {
          provide: ApiService,
          useValue: {
            preferences: vi.fn(() => of({ theme: 'dark-cockpit' })),
            savePreferences: vi.fn(() => of({ theme: 'light-luxury' }))
          }
        }
      ]
    });
    const service = TestBed.inject(ThemeService);
    service.setTheme('dark-cockpit', false);
    expect(document.documentElement.classList.contains('dark-cockpit')).toBe(true);
    service.toggle();
    expect(service.mode()).toBe('light-luxury');
    expect(document.documentElement.classList.contains('light-luxury')).toBe(true);
  });

  it('keeps an explicit local theme when server preferences are stale', () => {
    localStorage.setItem('nexus_theme_mode_v2', 'light-luxury');
    const savePreferences = vi.fn(() => of({ theme: 'light-luxury' }));
    TestBed.configureTestingModule({
      providers: [
        ThemeService,
        {
          provide: ApiService,
          useValue: {
            preferences: vi.fn(() => of({ theme: 'dark-cockpit' })),
            savePreferences
          }
        }
      ]
    });
    const service = TestBed.inject(ThemeService);
    service.hydrateFromServer();
    expect(service.mode()).toBe('light-luxury');
    expect(document.documentElement.classList.contains('light-luxury')).toBe(true);
    expect(savePreferences).toHaveBeenCalledWith({ theme: 'light-luxury' });
  });
});
