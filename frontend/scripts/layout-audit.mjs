import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `layout-audit-${Date.now()}`);
const captureAll = process.env.NEXUS_AUDIT_SCREENSHOTS === 'all';
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const routes = [
  '/app/overview',
  '/app/metrics',
  '/app/tasks',
  '/app/inventory/products',
  '/app/inventory/stock',
  '/app/inventory/replenishment',
  '/app/sales/orders',
  '/app/procurement/orders',
  '/app/suppliers/performance',
  '/app/dispatch',
  '/app/data-quality',
  '/app/quality',
  '/app/customers',
  '/app/capacity',
  '/app/maintenance',
  '/app/contracts',
  '/app/service',
  '/app/rules',
  '/app/integrations',
  '/app/budget',
  '/app/mobile-terminal',
  '/app/finance/receivables',
  '/app/finance/credits',
  '/app/stocktakes',
  '/app/reports',
  '/app/files',
  '/app/content/articles',
  '/app/system/users',
  '/app/system/audit',
  '/app/notifications',
  '/app/ai',
  '/app/profile',
  '/app/settings'
];

const viewports = [
  { name: 'desktop', width: 1440, height: 950 },
  { name: 'mobile', width: 390, height: 844 }
];

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const results = [];

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('requestfailed', request => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
  });

  await login(page);

  for (const route of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
    await page.waitForTimeout(650);
    const audit = await page.evaluate(() => {
      const selectors = [
        'button',
        'a',
        '.atlas-panel',
        '.atlas-panel-head',
        '.atlas-record-row',
        '.p-tag',
        '.profile-avatar',
        '.p-drawer',
        '.p-dialog'
      ];
      const visible = element => {
        const box = element.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0) {
          return false;
        }
        for (let current = element; current && current !== document.documentElement; current = current.parentElement) {
          const style = getComputedStyle(current);
          if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) {
            return false;
          }
        }
        return true;
      };
      const overflowingText = [...document.querySelectorAll('button, a, .p-tag, h1, h2, strong')]
        .filter(visible)
        .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
        .slice(0, 12)
        .map(element => ({
          tag: element.tagName.toLowerCase(),
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
          width: Math.round(element.clientWidth),
          scroll: Math.round(element.scrollWidth)
        }));
      const badRects = [];
      for (const selector of selectors) {
        for (const element of [...document.querySelectorAll(selector)].filter(visible)) {
          const box = element.getBoundingClientRect();
          if (box.right > window.innerWidth + 2 || box.left < -2) {
            badRects.push({
              selector,
              text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
              left: Math.round(box.left),
              right: Math.round(box.right),
              width: Math.round(box.width)
            });
          }
          if (badRects.length >= 12) {
            break;
          }
        }
      }
      const charts = [...document.querySelectorAll('[_echarts_instance_], .echarts, canvas')]
        .filter(visible)
        .map(element => {
          const box = element.getBoundingClientRect();
          return { width: Math.round(box.width), height: Math.round(box.height), tag: element.tagName.toLowerCase() };
        });
      const chartSizeIssues = charts
        .filter(chart => chart.width > 0 && (chart.width < 180 || chart.height < 180))
        .slice(0, 12);
      const dock = [...document.querySelectorAll('.atlas-dock')]
        .filter(visible)
        .map(element => element.getBoundingClientRect())[0];
      const dockOverlaps = dock
        ? [...document.querySelectorAll('[_echarts_instance_]')]
          .filter(visible)
          .map(element => {
            const box = element.getBoundingClientRect();
            const overlapX = Math.max(0, Math.min(dock.right, box.right) - Math.max(dock.left, box.left));
            const overlapY = Math.max(0, Math.min(dock.bottom, box.bottom) - Math.max(dock.top, box.top));
            return {
              width: Math.round(box.width),
              height: Math.round(box.height),
              overlapX: Math.round(overlapX),
              overlapY: Math.round(overlapY),
              overlapArea: Math.round(overlapX * overlapY)
            };
          })
          .filter(item => item.overlapArea > 1200)
          .slice(0, 8)
        : [];
      const overlapCandidates = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const text = node.textContent?.trim().replace(/\s+/g, ' ');
        if (!text || text.length < 2) {
          continue;
        }
        const element = node.parentElement;
        if (!element || element.closest('script, style, svg, canvas, .p-toast, .p-tooltip, .dock-popover, [role="tooltip"]')) {
          continue;
        }
        if (element.closest('.field-evidence-grid a, .page-evidence-grid a, .mobile-field-evidence-strip a, .context-workflow-photo, .command-photo-strip a, .command-evidence-rail figure, .module-photo-rail a, .command-visual-board figure, .settings-visual-rail figure')) {
          continue;
        }
        if (!visible(element)) {
          continue;
        }
        const style = getComputedStyle(element);
        if (style.opacity === '0' || style.visibility === 'hidden') {
          continue;
        }
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const rect of [...range.getClientRects()]) {
          if (rect.width < 4 || rect.height < 7) {
            continue;
          }
          if (rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) {
            continue;
          }
          overlapCandidates.push({
            element,
            text: text.slice(0, 70),
            tag: element.tagName.toLowerCase(),
            className: [...element.classList].slice(0, 3).join('.'),
            left: rect.left,
            right: rect.right,
            top: rect.top,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height
          });
        }
      }
      overlapCandidates.sort((a, b) => a.top - b.top || a.left - b.left);
      const overlapIssues = [];
      for (let i = 0; i < overlapCandidates.length && overlapIssues.length < 12; i++) {
        const a = overlapCandidates[i];
        for (let j = i + 1; j < overlapCandidates.length && overlapIssues.length < 12; j++) {
          const b = overlapCandidates[j];
          if (b.top > a.bottom - 1) {
            break;
          }
          if (a.element === b.element || a.element.contains(b.element) || b.element.contains(a.element)) {
            continue;
          }
          const overlapX = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
          const overlapY = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
          const area = overlapX * overlapY;
          const minArea = Math.min(a.width * a.height, b.width * b.height);
          if (area > 24 && area > minArea * 0.18) {
            overlapIssues.push({
              a: { tag: a.tag, className: a.className, text: a.text, left: Math.round(a.left), top: Math.round(a.top) },
              b: { tag: b.tag, className: b.className, text: b.text, left: Math.round(b.left), top: Math.round(b.top) },
              overlapX: Math.round(overlapX),
              overlapY: Math.round(overlapY)
            });
          }
        }
      }
      return {
        path: location.pathname,
        viewportSize: { width: window.innerWidth, height: window.innerHeight },
        bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
        overflowingText,
        badRects,
        charts,
        chartCount: charts.length,
        chartSizeIssues,
        dockOverlaps,
        overlapIssues,
        echartsLayoutGuard: window.__NEXUS_ECHARTS_LAYOUT_GUARD__ === true
      };
    });
    const slug = `${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[\/:]/g, '-') || 'home'}`;
    const failedPage = audit.bodyOverflowX > 3 ||
      audit.overflowingText.length ||
      audit.badRects.length ||
      audit.chartSizeIssues.length ||
      audit.dockOverlaps.length ||
      audit.overlapIssues.length ||
      !audit.echartsLayoutGuard;
    if (captureAll || failedPage) {
      await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
    }
    results.push({ route, ...audit, viewport: viewport.name });
  }

  await context.close();
}

await browser.close();

const failed = results.filter(result =>
  result.bodyOverflowX > 3 ||
  result.overflowingText.length ||
  result.badRects.length ||
  result.chartSizeIssues.length ||
  result.dockOverlaps.length ||
  result.overlapIssues.length ||
  !result.echartsLayoutGuard
);

await writeFile(path.join(outDir, 'report.json'), JSON.stringify({ baseUrl, results, failed }, null, 2));

if (failed.length) {
  console.error(`Layout audit failed: ${failed.length} pages. Report: ${path.join(outDir, 'report.json')}`);
  for (const item of failed.slice(0, 12)) {
    console.error(`${item.viewport} ${item.route}: overflow=${item.bodyOverflowX}, text=${item.overflowingText.length}, rects=${item.badRects.length}, chartSize=${item.chartSizeIssues.length}, dockOverlap=${item.dockOverlaps.length}, overlap=${item.overlapIssues.length}, echartsGuard=${item.echartsLayoutGuard}`);
  }
  process.exit(1);
}

console.log(`Layout audit passed for ${results.length} page checks. Report: ${path.join(outDir, 'report.json')}`);

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  const email = page.locator('input[type="email"], input[name="email"]').first();
  const password = page.locator('input[type="password"], input[name="password"]').first();
  await email.fill(credentials.email);
  await password.fill(credentials.password);
  const submit = page.locator('button[type="submit"]').first();
  await submit.waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForFunction(() => {
    const button = document.querySelector('button[type="submit"]');
    return button && !button.hasAttribute('disabled');
  }, null, { timeout: 15000 });
  await submit.click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
