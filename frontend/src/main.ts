import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';
import { captureFrontendException, initFrontendObservability } from './app/core/observability';

type RuntimeWindow = Window & typeof globalThis & {
  NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
  __NEXUS_CONFIG__?: { apiBase?: string };
};

// Fail fast if runtime config is missing or still pointing to placeholder
const runtimeWindow = window as unknown as RuntimeWindow;
const apiBase = runtimeWindow.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? runtimeWindow.__NEXUS_CONFIG__?.apiBase;
if (!apiBase || apiBase.includes('example.com') || apiBase.includes('localhost') && location.hostname !== 'localhost') {
  console.warn('[NEXUS] runtime-config.js may be misconfigured - apiBase:', apiBase);
}

initFrontendObservability();

bootstrapApplication(App, appConfig)
  .catch((err) => {
    captureFrontendException(err);
    console.error(err);
  });
