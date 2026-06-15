import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `experience-audit-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const routes = [
  '/app/overview',
  '/app/inventory/stock',
  '/app/procurement/orders',
  '/app/quality',
  '/app/sales/orders',
  '/app/finance/receivables',
  '/app/integrations',
  '/app/reports'
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
  const requestFailures = [];
  const badResponses = [];

  page.on('console', message => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });
  page.on('requestfailed', request => {
    requestFailures.push({
      method: request.method(),
      url: request.url(),
      error: request.failure()?.errorText || ''
    });
  });
  page.on('response', response => {
    if (response.status() >= 400) {
      badResponses.push({ status: response.status(), url: response.url() });
    }
  });

  await login(page);

  for (const route of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
    await page.waitForTimeout(800);

    const audit = await page.evaluate(() => {
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
      const count = selector => [...document.querySelectorAll(selector)].filter(visible).length;
      const texts = (selector, limit = 8) =>
        [...document.querySelectorAll(selector)]
          .filter(visible)
          .map(element => element.textContent?.trim().replace(/\s+/g, ' '))
          .filter(Boolean)
          .slice(0, limit);

      const visibleImages = [...document.querySelectorAll('img')]
        .filter(visible)
        .filter(image => image.complete && image.naturalWidth > 0)
        .map(image => {
          const box = image.getBoundingClientRect();
          return {
            src: image.getAttribute('src'),
            alt: image.getAttribute('alt') || '',
            width: Math.round(box.width),
            height: Math.round(box.height)
          };
        });
      const loadedEvidenceImages = visibleImages.filter(image => image.src?.includes('/images/'));
      const pageLevelEvidenceImages = [...document.querySelectorAll('.page-evidence-strip img')]
        .filter(visible)
        .filter(image => image.complete && image.naturalWidth > 0)
        .map(image => {
          const box = image.getBoundingClientRect();
          return {
            src: image.getAttribute('src'),
            alt: image.getAttribute('alt') || '',
            width: Math.round(box.width),
            height: Math.round(box.height)
          };
        });
      const workflowAnchors = count('.workflow-step-rail a, .field-evidence-grid a, .shift-handoff-list a, .map-step, .shift-stage-card, .shift-action-queue a, .shift-role-command a');
      const actionSurfaces = count('a[href], button:not([disabled]), .atlas-record-row, article, .home-system-card, .risk-brick');
      const chartCount = count('canvas, [_echarts_instance_], .echarts');
      const dataRows = count('.business-data-row, .atlas-record-row, .ledger-row, .risk-brick, .shift-event-timeline a, .shift-action-queue a, .shift-handoff-list a, .supplier-task-stack article, .service-line-card, .report-template-list button');
      const evidenceLinks = count('.field-evidence-grid a');
      const handoffActions = count('.shift-handoff-list a');
      const moduleLinks = count('.module-card-link, .dock-item, .atlas-dock-more');
      const overflowingNoWrapText = [...document.querySelectorAll('button, a, .p-tag, h1, h2, h3, strong, em, span')]
        .filter(visible)
        .filter(element => !element.closest('.module-photo-rail, .command-photo-strip, .field-evidence-grid'))
        .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
        .slice(0, 16)
        .map(element => ({
          tag: element.tagName.toLowerCase(),
          className: [...element.classList].slice(0, 4).join('.'),
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
          width: Math.round(element.clientWidth),
          scroll: Math.round(element.scrollWidth)
        }));
      const badRects = [...document.querySelectorAll('button, a, .atlas-panel, .context-block, .mobile-field-evidence-strip, .field-evidence-grid a, .shift-handoff-list a')]
        .filter(visible)
        .filter(element => !element.closest('.module-photo-rail, .field-evidence-grid'))
        .map(element => ({ element, box: element.getBoundingClientRect() }))
        .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2)
        .slice(0, 16)
        .map(({ element, box }) => ({
          tag: element.tagName.toLowerCase(),
          className: [...element.classList].slice(0, 4).join('.'),
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
          left: Math.round(box.left),
          right: Math.round(box.right),
          width: Math.round(box.width)
        }));

      return {
        path: location.pathname,
        title: document.title,
        viewportSize: { width: window.innerWidth, height: window.innerHeight },
        bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
        h1: document.querySelector('h1')?.textContent?.trim() || '',
        loadedEvidenceImageCount: loadedEvidenceImages.length,
        pageLevelEvidenceImageCount: pageLevelEvidenceImages.length,
        visibleImageCount: visibleImages.length,
        workflowAnchors,
        actionSurfaces,
        chartCount,
        dataRows,
        evidenceLinks,
        handoffActions,
        moduleLinks,
        samples: {
          images: loadedEvidenceImages.slice(0, 8),
          pageImages: pageLevelEvidenceImages.slice(0, 6),
          workflow: texts('.workflow-step-rail a, .field-evidence-grid a, .shift-handoff-list a, .map-step, .shift-stage-card', 8),
          data: texts('.business-data-row, .ledger-row, .atlas-record-row, article, .risk-brick', 8)
        },
        overflowingNoWrapText,
        badRects,
        hasRuntimeConfig: !!window.NEXUS_RUNTIME_CONFIG,
        apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null
      };
    });

    const slug = `${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[/:]/g, '-') || 'home'}`;
    if (route === '/app/overview' || audit.loadedEvidenceImageCount < 3 || audit.pageLevelEvidenceImageCount < 3 || audit.workflowAnchors < 3 || audit.handoffActions < 3 || audit.bodyOverflowX > 3 || audit.overflowingNoWrapText.length || audit.badRects.length) {
      await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
    }

    results.push({
      viewport: viewport.name,
      route,
      ...audit
    });
  }

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
  results.push({
    viewport: viewport.name,
    route: '__network__',
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses
  });

  await context.close();
}

await browser.close();

const pageResults = results.filter(result => result.route !== '__network__');
const networkResults = results.filter(result => result.route === '__network__');
const failedPages = pageResults.filter(result =>
  result.loadedEvidenceImageCount < 3 ||
  result.pageLevelEvidenceImageCount < 3 ||
  result.workflowAnchors < 3 ||
  result.handoffActions < 3 ||
  result.dataRows < 12 ||
  result.actionSurfaces < 18 ||
  result.bodyOverflowX > 3 ||
  result.overflowingNoWrapText.length ||
  result.badRects.length ||
  !hasExpectedAuditApiBaseUrl(result.apiBaseUrl)
);
const failedNetwork = networkResults.filter(result =>
  result.consoleErrors.length ||
  result.failedRequests.length ||
  result.badResponses.length
);
const failed = [...failedPages, ...failedNetwork];

const report = {
  baseUrl,
  routes,
  generatedAt: new Date().toISOString(),
  results,
  failed
};
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

const summary = {
  outDir,
  passed: failed.length === 0,
  pageSummary: pageResults.map(result => ({
    viewport: result.viewport,
    route: result.route,
    evidenceImages: result.loadedEvidenceImageCount,
    pageEvidenceImages: result.pageLevelEvidenceImageCount,
    workflowAnchors: result.workflowAnchors,
    handoffActions: result.handoffActions,
    actionSurfaces: result.actionSurfaces,
    dataRows: result.dataRows,
    charts: result.chartCount,
    overflow: result.bodyOverflowX,
    nowrap: result.overflowingNoWrapText.length,
    badRects: result.badRects.length
  })),
  networkSummary: networkResults.map(result => ({
    viewport: result.viewport,
    consoleErrors: result.consoleErrors.length,
    failedRequests: result.failedRequests.length,
    abortedRequests: result.abortedRequests.length,
    badResponses: result.badResponses.length
  }))
};

console.log(JSON.stringify(summary, null, 2));
if (failed.length) {
  process.exit(1);
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
