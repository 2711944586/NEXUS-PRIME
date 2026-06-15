import { DOCUMENT } from '@angular/common';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, of, tap } from 'rxjs';

import { ApiService } from './api.service';
import { ThemeMode, UserPreferences } from './models';

const THEME_KEY = 'nexus_theme_mode_v2';
const PREFERENCES_KEY = 'nexus_ui_preferences_v1';
const THEME_CLASSES: ThemeMode[] = ['dark-cockpit', 'light-luxury'];
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
const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'light-luxury',
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

  readonly mode = signal<ThemeMode>(this.readTheme());
  readonly preferences = signal<UserPreferences>({ ...DEFAULT_PREFERENCES, ...this.readStoredPreferences(), theme: this.readTheme() });

  constructor() {
    this.applyAll();
  }

  hydrateFromServer(): void {
    const localTheme = this.storedTheme();
    this.api.preferences().pipe(
      tap(prefs => {
        const nextTheme = localTheme ?? validTheme(prefs.theme) ?? this.mode();
        this.setPreferences({ ...prefs, theme: nextTheme }, false);
        if (localTheme && prefs.theme !== localTheme) {
          this.api.savePreferences({ theme: localTheme }).pipe(catchError(() => of(null))).subscribe();
        }
      }),
      catchError(() => of(null))
    ).subscribe();
  }

  toggle(sync = true): void {
    this.setTheme(this.mode() === 'dark-cockpit' ? 'light-luxury' : 'dark-cockpit', sync);
  }

  setTheme(mode: ThemeMode, sync = true): void {
    this.setPreferences({ ...this.preferences(), theme: mode }, sync);
  }

  setPreferences(preferences: UserPreferences, sync = true): void {
    const next = this.normalizePreferences({ ...this.preferences(), ...preferences });
    this.preferences.set(next);
    this.mode.set(next.theme ?? 'light-luxury');
    localStorage.setItem(THEME_KEY, this.mode());
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
    this.applyAll();
    if (sync) {
      this.api.savePreferences(next).pipe(catchError(() => of(null))).subscribe();
    }
  }

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
  }

  private readTheme(): ThemeMode {
    const stored = this.storedTheme();
    return stored ?? 'light-luxury';
  }

  private storedTheme(): ThemeMode | null {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light-luxury' || stored === 'dark-cockpit') {
      return stored;
    }
    return null;
  }

  private readStoredPreferences(): UserPreferences {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    if (!raw) {
      return {};
    }
    try {
      return this.normalizePreferences(JSON.parse(raw) as UserPreferences);
    } catch {
      return {};
    }
  }

  private normalizePreferences(preferences: UserPreferences): UserPreferences {
    return {
      ...DEFAULT_PREFERENCES,
      ...preferences,
      theme: validTheme(preferences.theme) ?? DEFAULT_PREFERENCES.theme,
      density: preferences.density === 'comfortable' ? 'comfortable' : 'compact',
      charts_motion: preferences.charts_motion === 'reduced' ? 'reduced' : 'standard',
      dock_labels: preferences.dock_labels === 'always' ? 'always' : 'hover',
      context_panel: preferences.context_panel === 'compact' ? 'compact' : 'visible'
    };
  }
}

function validTheme(mode: unknown): ThemeMode | null {
  return mode === 'dark-cockpit' || mode === 'light-luxury' ? mode : null;
}
