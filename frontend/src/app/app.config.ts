import { registerLocaleData } from '@angular/common';
import zh from '@angular/common/locales/zh';
import { ApplicationConfig, ErrorHandler } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import Aura from '@primeng/themes/aura';
import { provideTanStackQuery } from '@tanstack/angular-query-experimental';
import * as echarts from 'echarts';
import { provideEchartsCore } from 'ngx-echarts';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';
import { authInterceptor } from './core/auth.interceptor';
import { configureEchartsLayout } from './core/echarts-layout';
import { GlobalErrorHandler } from './core/global-error-handler';
import { createNexusQueryClient } from './core/query-client';

registerLocaleData(zh);
configureEchartsLayout(echarts);

export const appConfig: ApplicationConfig = {
  providers: [
    provideAnimations(),
    provideRouter(routes, withInMemoryScrolling({
      anchorScrolling: 'enabled',
      scrollPositionRestoration: 'top'
    })),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideTanStackQuery(createNexusQueryClient()),
    providePrimeNG({
      ripple: true,
      theme: {
        preset: Aura,
        options: {
          darkModeSelector: '.dark-cockpit',
          cssLayer: {
            name: 'primeng',
            order: 'reset, base, primeng, app'
          }
        }
      }
    }),
    provideEchartsCore({ echarts }),
    MessageService,
    ConfirmationService,
    { provide: ErrorHandler, useClass: GlobalErrorHandler }
  ]
};
