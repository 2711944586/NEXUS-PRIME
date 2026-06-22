import { describe, expect, it, vi, afterEach } from 'vitest';

import { captureFrontendException, initFrontendObservability, isSentryEnabled } from './observability';

vi.mock('@sentry/angular', () => ({
  init: vi.fn(),
  captureException: vi.fn()
}));

describe('frontend observability', () => {
  afterEach(() => {
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: {
        sentryDsn?: string;
        sentryEnvironment?: string;
        sentryRelease?: string;
        sentryTracesSampleRate?: number;
      };
    }).NEXUS_RUNTIME_CONFIG;
    vi.clearAllMocks();
    initFrontendObservability();
  });

  it('does not initialize Sentry when no DSN is configured', async () => {
    const Sentry = await import('@sentry/angular');

    expect(initFrontendObservability()).toBe(false);
    expect(isSentryEnabled()).toBe(false);
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('initializes Sentry from runtime config and captures errors', async () => {
    const Sentry = await import('@sentry/angular');
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: {
        sentryDsn?: string;
        sentryEnvironment?: string;
        sentryRelease?: string;
        sentryTracesSampleRate?: number;
      };
    }).NEXUS_RUNTIME_CONFIG = {
      sentryDsn: 'https://public@example.ingest.sentry.io/1',
      sentryEnvironment: 'preview',
      sentryRelease: 'abc123',
      sentryTracesSampleRate: 0.2
    };

    expect(initFrontendObservability()).toBe(true);
    expect(isSentryEnabled()).toBe(true);
    expect(Sentry.init).toHaveBeenCalledWith({
      dsn: 'https://public@example.ingest.sentry.io/1',
      environment: 'preview',
      release: 'abc123',
      tracesSampleRate: 0.2
    });

    const error = new Error('boom');
    captureFrontendException(error);
    expect(Sentry.captureException).toHaveBeenCalledWith(error);
  });
});
