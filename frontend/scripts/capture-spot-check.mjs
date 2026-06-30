import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'docs', 'images', 'spot-check');
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const routes = [
  ['budget', '/app/budget'],
  ['inventory-stock', '/app/inventory/stock'],
  ['ai', '/app/ai'],
  ['profile', '/app/profile'],
  ['settings', '/app/settings']
];

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 1 });
  await context.addInitScript(() => {
    localStorage.setItem('nexus_theme_mode_v2', 'light-luxury');
    localStorage.setItem('nexus_ui_preferences_v1', JSON.stringify({
      theme: 'light-luxury',
      density: 'compact',
      charts_motion: 'reduced',
      dock_labels: 'hover',
      context_panel: 'visible',
      default_workspace: '/app/overview'
    }));
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });

  for (const [slug, route] of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
    await page.waitForLoadState('networkidle', { timeout: 2500 }).catch(() => undefined);
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
  }
  await context.close();
  console.log(JSON.stringify({ outDir, routes: routes.length }, null, 2));
} finally {
  await browser.close();
}
