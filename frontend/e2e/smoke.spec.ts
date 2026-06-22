import { expect, test } from '@playwright/test';

test('login surface renders with runtime API configuration', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });
  await page.route('**/api/v1/auth/csrf', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ data: { csrf_token: 'e2e-csrf-token' }, message: 'ok', error: null }),
    });
  });
  await page.route('**/api/v1/auth/register-policy', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          terms_version: 'e2e',
          permissions: [],
          required_acceptances: ['terms', 'privacy', 'data_scope'],
        },
        message: 'ok',
        error: null,
      }),
    });
  });

  await page.goto('/auth/login');

  await expect(page.getByRole('heading', { name: /欢迎回来|创建账号/ })).toBeVisible();
  await expect(page.locator('#login-form')).toBeVisible();
  await expect(page.getByRole('button', { name: /进入系统/ })).toBeVisible();

  const apiBase = await page.evaluate(() => window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl || '');
  expect(apiBase).toMatch(/\/api\/v1$/);
  expect(apiBase).not.toContain('example.com');
  expect(apiBase).not.toContain('localhost');
  expect(consoleErrors).toEqual([]);
});
