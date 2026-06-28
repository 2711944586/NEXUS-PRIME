import { DOCUMENT } from '@angular/common';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, of, tap } from 'rxjs';

import { ApiService } from './api.service';
import { ThemeMode, ThemeSource, UserPreferences } from './models';

const THEME_KEY = 'nexus_theme_mode_v2';
const PREFERENCES_KEY = 'nexus_ui_preferences_v1';
const THEME_CLASSES: ThemeMode[] = ['dark-cockpit', 'light-luxury'];
const THEME_SOURCES: ThemeSource[] = ['system', 'light-luxury', 'dark-cockpit'];
const PREFERENCE_CLASSES = [
  'density-compact',
  'density-comfortable',
  'dock-labels-hover',
  'dock-labels-always',
  'context-panel-visible',
  'context-panel-compact',
  'charts-motion-standard',
  'charts-motion-reduced'
];
const EXPERIENCE_CLASS = 'operations-console';
const DEFAULT_SOURCE: ThemeSource = 'system';
const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'light-luxury',
  theme_source: DEFAULT_SOURCE,
  density: 'compact',
  default_workspace: '/app/overview',
  charts_motion: 'reduced',
  dock_labels: 'hover',
  context_panel: 'visible'
};

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly api = inject(ApiService);
  private readonly mediaQuery = this.document.defaultView?.matchMedia?.('(prefers-color-scheme: dark)') ?? null;

  readonly source = signal<ThemeSource>(this.readInitialSource());
  readonly mode = signal<ThemeMode>(this.resolveMode(this.source(), this.readStoredMode() ?? DEFAULT_PREFERENCES.theme!));
  readonly preferences = signal<UserPreferences>(
    this.normalizePreferences({ ...this.readStoredPreferences(), theme_source: this.source(), theme: this.mode() })
  );

  constructor() {
    this.mediaQuery?.addEventListener?.('change', this.onSystemThemeChange);
    this.applyAll();
  }

  hydrateFromServer(): void {
    const localSource = this.readStoredSource();
    const localTheme = this.readStoredMode();
    this.api.preferences().pipe(
      tap(prefs => {
        const nextSource = localSource ?? validSource(prefs.theme_source) ?? (localTheme ? localTheme : DEFAULT_SOURCE);
        const serverTheme = validTheme(prefs.theme) ?? localTheme ?? this.mode();
        const nextMode = this.resolveMode(nextSource, serverTheme);
        const nextPreferences = this.normalizePreferences({
          ...prefs,
          theme_source: nextSource,
          theme: nextMode
        });
        this.setPreferences(nextPreferences, false);
        if (localSource || localTheme) {
          this.api.savePreferences({
            theme: nextMode,
            theme_source: nextSource
          }).pipe(catchError(() => of(null))).subscribe();
        }
      }),
      catchError(() => of(null))
    ).subscribe();
  }

  toggle(sync = true): void {
    this.setTheme(this.mode() === 'dark-cockpit' ? 'light-luxury' : 'dark-cockpit', sync);
  }

  cycleSource(sync = true): void {
    const currentIndex = THEME_SOURCES.indexOf(this.source());
    const next = THEME_SOURCES[(currentIndex + 1) % THEME_SOURCES.length] ?? DEFAULT_SOURCE;
    this.setSource(next, sync);
  }

  setTheme(mode: ThemeMode, sync = true): void {
    this.setSource(mode, sync);
  }

  setSource(source: ThemeSource, sync = true): void {
    const nextSource = validSource(source) ?? DEFAULT_SOURCE;
    const nextMode = this.resolveMode(nextSource, this.mode());
    this.setPreferences({ ...this.preferences(), theme_source: nextSource, theme: nextMode }, sync);
  }

  setPreferences(preferences: UserPreferences, sync = true): void {
    const merged = { ...this.preferences(), ...preferences };
    const hasSource = Object.prototype.hasOwnProperty.call(preferences, 'theme_source');
    const hasTheme = Object.prototype.hasOwnProperty.call(preferences, 'theme');
    const nextSource = hasSource
      ? validSource(preferences.theme_source) ?? this.source() ?? DEFAULT_SOURCE
      : hasTheme
        ? validTheme(preferences.theme) ?? this.source() ?? DEFAULT_SOURCE
        : validSource(merged.theme_source) ?? this.source() ?? DEFAULT_SOURCE;
    const explicitTheme = validTheme(merged.theme) ?? this.mode();
    const nextMode = this.resolveMode(nextSource, explicitTheme);
    const next = this.normalizePreferences({ ...merged, theme_source: nextSource, theme: nextMode });
    this.source.set(nextSource);
    this.mode.set(nextMode);
    this.preferences.set(next);
    this.writeStorage(THEME_KEY, nextMode);
    this.writeStorage(PREFERENCES_KEY, JSON.stringify(next));
    this.applyAll();
    if (sync) {
      this.api.savePreferences(next).pipe(catchError(() => of(null))).subscribe();
    }
  }

  sourceLabel(): string {
    switch (this.source()) {
      case 'system':
        return '跟随系统';
      case 'dark-cockpit':
        return '深色驾驶舱';
      case 'light-luxury':
        return '亮色系统';
    }
  }

  private readonly onSystemThemeChange = (): void => {
    if (this.source() !== 'system') {
      return;
    }
    this.setPreferences({ ...this.preferences(), theme_source: 'system', theme: this.resolveMode('system', this.mode()) }, false);
  };

  private applyAll(): void {
    const root = this.document.documentElement;
    root.classList.remove(...THEME_CLASSES);
    root.classList.remove(...PREFERENCE_CLASSES);
    root.classList.add(EXPERIENCE_CLASS);
    root.classList.add(this.mode());
    const prefs = this.preferences();
    root.classList.add(`density-${prefs.density ?? 'compact'}`);
    root.classList.add(`dock-labels-${prefs.dock_labels ?? 'hover'}`);
    root.classList.add(`context-panel-${prefs.context_panel ?? 'visible'}`);
    root.classList.add(`charts-motion-${prefs.charts_motion ?? 'standard'}`);
    root.setAttribute('data-theme', this.mode());
    root.setAttribute('data-theme-source', this.source());
    const win = this.document.defaultView;
    win?.dispatchEvent(new win.CustomEvent('nexus-theme-change', {
      detail: { theme: this.mode(), source: this.source(), preferences: prefs }
    }));
  }

  private readInitialSource(): ThemeSource {
    return this.readStoredSource() ?? this.legacyStoredTheme() ?? validTheme(this.readStoredPreferences().theme) ?? DEFAULT_SOURCE;
  }

  private readStoredSource(): ThemeSource | null {
    const stored = this.readStoredPreferences();
    return validSource(stored.theme_source) ?? null;
  }

  private readStoredMode(): ThemeMode | null {
    const stored = this.readStorage(THEME_KEY);
    if (stored === 'light-luxury' || stored === 'dark-cockpit') {
      return stored;
    }
    return validTheme(this.readStoredPreferences().theme);
  }

  private legacyStoredTheme(): ThemeMode | null {
    const stored = this.readStorage(THEME_KEY);
    return validTheme(stored);
  }

  private readStoredPreferences(): UserPreferences {
    const raw = this.readStorage(PREFERENCES_KEY);
    if (!raw) {
      return {};
    }
    try {
      return JSON.parse(raw) as UserPreferences;
    } catch {
      return {};
    }
  }

  private normalizePreferences(preferences: UserPreferences): UserPreferences {
    const source = validSource(preferences.theme_source) ?? validTheme(preferences.theme) ?? DEFAULT_SOURCE;
    const theme = this.resolveMode(source, validTheme(preferences.theme) ?? DEFAULT_PREFERENCES.theme!);
    return {
      ...DEFAULT_PREFERENCES,
      ...preferences,
      theme,
      theme_source: source,
      density: preferences.density === 'comfortable' ? 'comfortable' : 'compact',
      charts_motion: preferences.charts_motion === 'standard' ? 'standard' : 'reduced',
      dock_labels: preferences.dock_labels === 'always' ? 'always' : 'hover',
      context_panel: preferences.context_panel === 'compact' ? 'compact' : 'visible'
    };
  }

  private resolveMode(source: ThemeSource, fallback: ThemeMode): ThemeMode {
    if (source === 'dark-cockpit' || source === 'light-luxury') {
      return source;
    }
    if (this.mediaQuery) {
      return this.mediaQuery.matches ? 'dark-cockpit' : 'light-luxury';
    }
    return validTheme(fallback) ?? 'light-luxury';
  }

  private readStorage(key: string): string | null {
    try {
      return this.document.defaultView?.localStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }

  private writeStorage(key: string, value: string): void {
    try {
      this.document.defaultView?.localStorage?.setItem(key, value);
    } catch {
      // Storage may be unavailable in private mode or SSR-like tests.
    }
  }
}

function validTheme(mode: unknown): ThemeMode | null {
  return mode === 'dark-cockpit' || mode === 'light-luxury' ? mode : null;
}

function validSource(source: unknown): ThemeSource | null {
  return source === 'system' || source === 'dark-cockpit' || source === 'light-luxury' ? source : null;
}
