import type { ThemeMode } from './models';
import { OPERATIONS_VISUALS } from './visual-assets';

type AuthMode = 'login' | 'register';

interface ThemeVideoPair {
  dark: string;
  light: string;
}

interface AuthVisualSet {
  background: ThemeVideoPair;
  panel: ThemeVideoPair;
  image: string;
}

export const LANDING_POSTER = '/images/automated-production-line-wide.jpg';

export const LANDING_VIDEOS = {
  dataCenterCorridor: 'https://assets.mixkit.co/videos/23282/23282-720.mp4',
  serverRoomInspection: 'https://assets.mixkit.co/videos/23108/23108-720.mp4',
  fiberOpticRack: 'https://assets.mixkit.co/videos/47050/47050-720.mp4',
  roboticProductionLine: 'https://assets.mixkit.co/videos/47257/47257-720.mp4',
  electronicsManufacturingRobot: 'https://assets.mixkit.co/videos/47258/47258-720.mp4'
} as const;

const ENTRY_BACKGROUND: ThemeVideoPair = {
  dark: LANDING_VIDEOS.dataCenterCorridor,
  light: LANDING_VIDEOS.dataCenterCorridor
};

const AUTH_VISUALS: Record<AuthMode, AuthVisualSet> = {
  login: {
    background: {
      dark: LANDING_VIDEOS.serverRoomInspection,
      light: LANDING_VIDEOS.serverRoomInspection
    },
    panel: {
      dark: LANDING_VIDEOS.fiberOpticRack,
      light: LANDING_VIDEOS.fiberOpticRack
    },
    image: OPERATIONS_VISUALS.receivingDock
  },
  register: {
    background: {
      dark: LANDING_VIDEOS.electronicsManufacturingRobot,
      light: LANDING_VIDEOS.electronicsManufacturingRobot
    },
    panel: {
      dark: LANDING_VIDEOS.roboticProductionLine,
      light: LANDING_VIDEOS.roboticProductionLine
    },
    image: OPERATIONS_VISUALS.factoryEngineers
  }
};

const POLICY_BACKGROUND: ThemeVideoPair = {
  dark: LANDING_VIDEOS.dataCenterCorridor,
  light: LANDING_VIDEOS.dataCenterCorridor
};

const POLICY_PANEL: ThemeVideoPair = {
  dark: LANDING_VIDEOS.fiberOpticRack,
  light: LANDING_VIDEOS.fiberOpticRack
};

export function entryVideoSource(theme: ThemeMode): string {
  return selectThemeVideo(ENTRY_BACKGROUND, theme);
}

export function authVideoSource(mode: AuthMode, theme: ThemeMode): string {
  return selectThemeVideo(AUTH_VISUALS[mode].background, theme);
}

export function authPanelVideoSource(mode: AuthMode, theme: ThemeMode): string {
  return selectThemeVideo(AUTH_VISUALS[mode].panel, theme);
}

export function authFallbackImage(mode: AuthMode): string {
  return AUTH_VISUALS[mode].image;
}

export function policyVideoSource(theme: ThemeMode): string {
  return selectThemeVideo(POLICY_BACKGROUND, theme);
}

export function policyPanelVideoSource(theme: ThemeMode): string {
  return selectThemeVideo(POLICY_PANEL, theme);
}

export function policyFallbackImage(): string {
  return OPERATIONS_VISUALS.contractsDesk;
}

function selectThemeVideo(pair: ThemeVideoPair, theme: ThemeMode): string {
  return theme === 'dark-cockpit' ? pair.dark : pair.light;
}
