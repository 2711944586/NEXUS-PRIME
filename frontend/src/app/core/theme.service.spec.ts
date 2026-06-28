// @vitest-environment jsdom
import '@angular/compiler';
import { DOCUMENT } from '@angular/common';
import { createEnvironmentInjector, EnvironmentInjector } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiService } from './api.service';
import { ThemeMode, UserPreferences } from './models';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  let injector: EnvironmentInjector | null = null;
  let media: MockMediaQueryList;

  beforeEach(() => {
    media = createMatchMedia(false);
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    Object.defineProperty(document, 'defaultView', {
      configurable: true,
      value: window
    });
  });

  afterEach(() => {
    injector?.destroy();
    injector = null;
    vi.unstubAllGlobals();
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
    document.documentElement.removeAttribute('data-theme-source');
  });

  it('defaults to system source and resolves light mode when the OS is light', () => {
    const service = createThemeService(apiMock({}));

    expect(service.source()).toBe('system');
    expect(service.mode()).toBe('light-luxury');
    expect(document.documentElement.classList.contains('light-luxury')).toBe(true);
    expect(document.documentElement.dataset['themeSource']).toBe('system');
  });

  it('tracks prefers-color-scheme changes while source is system', () => {
    const service = createThemeService(apiMock({}));

    media.setMatches(true);

    expect(service.source()).toBe('system');
    expect(service.mode()).toBe('dark-cockpit');
    expect(document.documentElement.classList.contains('dark-cockpit')).toBe(true);
  });

  it('cycles source in an intuitive system to light to dark order', () => {
    const service = createThemeService(apiMock({}));

    service.cycleSource(false);
    expect(service.source()).toBe('light-luxury');
    expect(service.mode()).toBe('light-luxury');

    service.cycleSource(false);
    expect(service.source()).toBe('dark-cockpit');
    expect(service.mode()).toBe('dark-cockpit');

    media.setMatches(false);
    service.cycleSource(false);
    expect(service.source()).toBe('system');
    expect(service.mode()).toBe('light-luxury');
  });

  it('toggles to an explicit theme and ignores later OS changes', () => {
    const savePreferences = vi.fn((prefs: UserPreferences) => of(prefs));
    const service = createThemeService(apiMock({}, savePreferences));

    service.setTheme('dark-cockpit');
    media.setMatches(false);

    expect(service.source()).toBe('dark-cockpit');
    expect(service.mode()).toBe('dark-cockpit');
    expect(savePreferences).toHaveBeenCalledWith(expect.objectContaining({
      theme: 'dark-cockpit',
      theme_source: 'dark-cockpit'
    }));
  });

  it('keeps an explicit local source when server preferences are stale', () => {
    localStorage.setItem('nexus_theme_mode_v2', 'light-luxury');
    localStorage.setItem('nexus_ui_preferences_v1', JSON.stringify({ theme: 'light-luxury', theme_source: 'light-luxury' }));
    const savePreferences = vi.fn((prefs: UserPreferences) => of(prefs));
    const service = createThemeService(apiMock({ theme: 'dark-cockpit', theme_source: 'dark-cockpit' }, savePreferences));

    service.hydrateFromServer();

    expect(service.source()).toBe('light-luxury');
    expect(service.mode()).toBe('light-luxury');
    expect(savePreferences).toHaveBeenCalledWith({ theme: 'light-luxury', theme_source: 'light-luxury' });
  });

  it('resolves server system source before applying hydrated preferences', () => {
    media.setMatches(true);
    const service = createThemeService(apiMock({ theme: 'light-luxury', theme_source: 'system' }));

    service.hydrateFromServer();

    expect(service.source()).toBe('system');
    expect(service.mode()).toBe('dark-cockpit');
    expect(document.documentElement.dataset['theme']).toBe('dark-cockpit');
  });

  it('broadcasts theme changes so rendered charts can refresh their canvas colors', () => {
    const events: Array<{ theme?: string; source?: string }> = [];
    const listener = (event: Event) => {
      events.push((event as CustomEvent).detail ?? {});
    };
    window.addEventListener('nexus-theme-change', listener);
    const service = createThemeService(apiMock({}));

    service.setTheme('dark-cockpit', false);
    window.removeEventListener('nexus-theme-change', listener);

    expect(events.at(-1)).toMatchObject({ theme: 'dark-cockpit', source: 'dark-cockpit' });
    expect(document.documentElement.dataset['theme']).toBe('dark-cockpit');
  });

  function createThemeService(api: Pick<ApiService, 'preferences' | 'savePreferences'>): ThemeService {
    TestBed.configureTestingModule({});
    const parent = TestBed.inject(EnvironmentInjector);
    injector = createEnvironmentInjector([
      ThemeService,
      { provide: DOCUMENT, useValue: document },
      { provide: ApiService, useValue: api }
    ], parent);
    return injector.get(ThemeService);
  }
});

function apiMock(
  preferences: UserPreferences,
  savePreferences: (preferences: UserPreferences) => Observable<UserPreferences> = (prefs) => of(prefs)
): Pick<ApiService, 'preferences' | 'savePreferences'> {
  return {
    preferences: vi.fn(() => of(preferences)),
    savePreferences: vi.fn(savePreferences)
  };
}

type MockMediaQueryList = MediaQueryList & {
  setMatches(matches: boolean): void;
};

function createMatchMedia(initialMatches: boolean): MockMediaQueryList {
  let matches = initialMatches;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const mediaList = {
    get matches() {
      return matches;
    },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
    addListener: (listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
    removeListener: (listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
    dispatchEvent: () => true,
    setMatches(next: boolean) {
      matches = next;
      const event = { matches, media: '(prefers-color-scheme: dark)' } as MediaQueryListEvent;
      listeners.forEach(listener => listener(event));
    }
  };
  return mediaList as MockMediaQueryList;
}
