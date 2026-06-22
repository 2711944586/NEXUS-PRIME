import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.FRONTEND_PORT || 4200);

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  reporter: [['list'], ['html', { outputFolder: '../output/playwright/e2e-report', open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `npm start -- --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === '1',
    timeout: 120_000,
    env: {
      NEXUS_RUNTIME_CONFIG_LOCAL: '1',
      NEXUS_LOCAL_API_BASE_URL: process.env.NEXUS_LOCAL_API_BASE_URL || '/api/v1',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
