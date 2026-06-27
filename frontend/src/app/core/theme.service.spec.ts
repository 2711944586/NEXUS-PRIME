// @vitest-environment jsdom
import '@angular/compiler';
import { DOCUMENT } from '@angular/common';
import { createEnvironmentInjector, EnvironmentInjector } from '@angular/core';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  let injector: EnvironmentInjector | null = null;

  afterEach(() => {
    injector?.destroy();
    injector = null;
    localStorage.removeItem('nexus_theme_mode');
    localStorage.removeItem('nexus_theme_mode_v2');
    localStorage.removeItem('nexus_ui_preferences_v1');
    document.documentElement.classList.remove(
      'dark-cockpit',
      'light-luxury',
      'operations-console',
      'density-compact',
      'density-comfortable',
      'dock-labels-hover',
      'dock-labels-always',
      'context-panel-visible',
      'context-panel-compact',
      'charts-motion-standard',
      'charts-motion-reduced'
    );
    document.documentElement.removeAttribute('data-theme');
  });

  it('toggles between cockpit and luxury themes', () => {
    const service = createThemeService({
      preferences: vi.fn(() => of({ theme: 'dark-cockpit' })),
      savePreferences: vi.fn(() => of({ theme: 'light-luxury' }))
    });

    service.setTheme('dark-cockpit', false);
    expect(document.documentElement.classList.contains('dark-cockpit')).toBe(true);

    service.toggle();
    expect(service.mode()).toBe('light-luxury');
    expect(document.documentElement.classList.contains('light-luxury')).toBe(true);
  });

  it('keeps an explicit local theme when server preferences are stale', () => {
    localStorage.setItem('nexus_theme_mode_v2', 'light-luxury');
    const savePreferences = vi.fn(() => of({ theme: 'light-luxury' }));
    const service = createThemeService({
      preferences: vi.fn(() => of({ theme: 'dark-cockpit' })),
      savePreferences
    });

    service.hydrateFromServer();

    expect(service.mode()).toBe('light-luxury');
    expect(document.documentElement.classList.contains('light-luxury')).toBe(true);
    expect(savePreferences).toHaveBeenCalledWith({ theme: 'light-luxury' });
  });

  it('broadcasts theme changes so rendered charts can refresh their canvas colors', () => {
    const events: Array<{ theme?: string }> = [];
    const listener = (event: Event) => {
      events.push((event as CustomEvent).detail ?? {});
    };
    window.addEventListener('nexus-theme-change', listener);
    const service = createThemeService({
      preferences: vi.fn(() => of({ theme: 'light-luxury' })),
      savePreferences: vi.fn(() => of({ theme: 'dark-cockpit' }))
    });

    service.setTheme('dark-cockpit', false);
    window.removeEventListener('nexus-theme-change', listener);

    expect(events.at(-1)?.theme).toBe('dark-cockpit');
    expect(document.documentElement.dataset['theme']).toBe('dark-cockpit');
  });

  function createThemeService(api: Pick<ApiService, 'preferences' | 'savePreferences'>): ThemeService {
    injector = createEnvironmentInjector([
      ThemeService,
      { provide: DOCUMENT, useValue: document },
      { provide: ApiService, useValue: api }
    ]);
    return injector.get(ThemeService);
  }
});
