import * as Sentry from '@sentry/angular';
import { Injectable } from '@angular/core';

type RuntimeObservabilityConfig = {
  sentryDsn?: string;
  sentryEnvironment?: string;
  sentryRelease?: string;
  sentryTracesSampleRate?: number;
};

type RuntimeWindow = typeof globalThis & {
  NEXUS_RUNTIME_CONFIG?: RuntimeObservabilityConfig;
};

let sentryEnabled = false;

export function runtimeObservabilityConfig(): RuntimeObservabilityConfig {
  return (globalThis as RuntimeWindow).NEXUS_RUNTIME_CONFIG ?? {};
}

export function initFrontendObservability(): boolean {
  const config = runtimeObservabilityConfig();
  const dsn = (config.sentryDsn ?? '').trim();
  if (!dsn) {
    sentryEnabled = false;
    return false;
  }

  Sentry.init({
    dsn,
    environment: config.sentryEnvironment || undefined,
    release: config.sentryRelease || undefined,
    tracesSampleRate: Number(config.sentryTracesSampleRate ?? 0),
  });
  sentryEnabled = true;
  return true;
}

export function captureFrontendException(error: unknown): void {
  if (!sentryEnabled) {
    return;
  }
  Sentry.captureException(error);
}

export function isSentryEnabled(): boolean {
  return sentryEnabled;
}

@Injectable({ providedIn: 'root' })
export class FrontendObservabilityService {
  captureException(error: unknown): void {
    captureFrontendException(error);
  }

  reloadWindow(): void {
    window.location.reload();
  }
}
