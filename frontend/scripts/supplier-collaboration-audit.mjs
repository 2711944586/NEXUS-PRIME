import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const route = '/app/suppliers/performance';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `supplier-collaboration-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

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
  const supplierResponse = page
    .waitForResponse(response => response.url().includes('/api/v1/operations/supplier-collaboration'), {
      timeout: 20000
    })
    .catch(error => ({ timedOut: true, message: error.message }));

  await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
  const apiResponse = await supplierResponse;
  await page.waitForFunction(
    () =>
      document.querySelectorAll('.supplier-lane-strip a').length >= 5 &&
      document.querySelectorAll('.supplier-360-card').length >= 8 &&
      document.querySelectorAll('.supplier-task-stack article').length >= 8 &&
      document.querySelectorAll('.supplier-delivery-list a').length >= 8 &&
      document.querySelectorAll('.supplier-boundary-list article').length >= 5,
    { timeout: 20000 }
  );
  await page.waitForTimeout(900);

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
    const texts = (selector, limit = 6) =>
      [...document.querySelectorAll(selector)]
        .filter(visible)
        .map(element => element.textContent?.trim().replace(/\s+/g, ' '))
        .filter(Boolean)
        .slice(0, limit);

    const selectors = [
      'button',
      'a',
      '.atlas-panel',
      '.atlas-panel-head',
      '.atlas-record-row',
      '.p-tag',
      '.supplier-360-card',
      '.supplier-task-stack article',
      '.supplier-boundary-list article',
      '.supplier-delivery-list a',
      '.supplier-flow-list article'
    ];
    const overflowingText = [...document.querySelectorAll('button, a, .p-tag, h1, h2, h3, strong, em, span')]
      .filter(visible)
      .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
      .slice(0, 16)
      .map(element => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
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
            text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
            left: Math.round(box.left),
            right: Math.round(box.right),
            width: Math.round(box.width)
          });
        }
        if (badRects.length >= 16) {
          break;
        }
      }
    }

    const chartRects = [...document.querySelectorAll('.supplier-radar, .supplier-chart, [_echarts_instance_], canvas')]
      .filter(visible)
      .map(element => {
        const box = element.getBoundingClientRect();
        return {
          selector: element.className?.toString() || element.tagName.toLowerCase(),
          width: Math.round(box.width),
          height: Math.round(box.height)
        };
      });

    const overlapCandidates = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent?.trim().replace(/\s+/g, ' ');
      if (!text || text.length < 2) {
        continue;
      }
      const element = node.parentElement;
      if (!element || element.closest('script, style, svg, canvas, .p-toast, .p-tooltip, [role="tooltip"]')) {
        continue;
      }
      if (!visible(element)) {
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
            a: {
              tag: a.tag,
              className: a.className,
              text: a.text,
              left: Math.round(a.left),
              top: Math.round(a.top)
            },
            b: {
              tag: b.tag,
              className: b.className,
              text: b.text,
              left: Math.round(b.left),
              top: Math.round(b.top)
            },
            overlapX: Math.round(overlapX),
            overlapY: Math.round(overlapY)
          });
        }
      }
    }

    return {
      path: location.pathname,
      title: document.title,
      h1: document.querySelector('h1')?.textContent?.trim() || '',
      viewportSize: { width: window.innerWidth, height: window.innerHeight },
      bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
      moduleCounts: {
        laneCount: count('.supplier-lane-strip a'),
        taskCount: count('.supplier-task-stack article'),
        supplier360Count: count('.supplier-360-card'),
        deliveryWindowCount: count('.supplier-delivery-list a'),
        serviceBoundaryCount: count('.supplier-boundary-list article'),
        deploymentCheckCount: count('.supplier-deploy-checks > div'),
        flowStepCount: count('.supplier-flow-list article'),
        ledgerRowCount: count('.atlas-record-ledger .atlas-record-row'),
        chartCanvasCount: count('canvas'),
        emptyStateCount: count('.empty-state'),
        skeletonCount: count('p-skeleton, .p-skeleton')
      },
      samples: {
        lanes: texts('.supplier-lane-strip a span', 5),
        supplierCards: texts('.supplier-360-card > strong', 5),
        taskTitles: texts('.supplier-task-stack article > strong', 5),
        deliveryWindows: texts('.supplier-delivery-list strong', 5),
        boundaries: texts('.supplier-boundary-list strong', 5),
        deployChecks: texts('.supplier-deploy-checks strong', 5),
        flowSteps: texts('.supplier-flow-list strong', 5),
        ledgerRows: texts('.atlas-record-row .record-code', 5)
      },
      chartRects,
      overflowingText,
      badRects,
      overlapIssues,
      hasExpectedHero: (document.querySelector('h1')?.textContent || '').includes('供应商协同与资质风险工作台'),
      hasRuntimeConfig: !!window.NEXUS_RUNTIME_CONFIG,
      apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null
    };
  });

  await page.screenshot({ path: path.join(outDir, `${viewport.name}-supplier-collaboration-viewport.png`), fullPage: false });
  await page.screenshot({ path: path.join(outDir, `${viewport.name}-supplier-collaboration-full.png`), fullPage: true });

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
  results.push({
    viewport: viewport.name,
    supplierApiStatus: typeof apiResponse.status === 'function' ? apiResponse.status() : null,
    supplierApiTimedOut: Boolean(apiResponse.timedOut),
    supplierApiError: apiResponse.message || null,
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses,
    ...audit
  });
  await context.close();
}

await browser.close();

const failed = results.filter(
  result =>
    !result.hasExpectedHero ||
    result.supplierApiTimedOut ||
    result.supplierApiStatus >= 400 ||
    result.consoleErrors.length ||
    result.failedRequests.length ||
    result.badResponses.length ||
    result.bodyOverflowX > 3 ||
    result.overflowingText.length ||
    result.badRects.length ||
    result.overlapIssues.length ||
    result.moduleCounts.laneCount < 5 ||
    result.moduleCounts.supplier360Count < 1 ||
    result.moduleCounts.taskCount < 1 ||
    result.moduleCounts.deliveryWindowCount < 1 ||
    result.moduleCounts.serviceBoundaryCount < 5 ||
    result.moduleCounts.deploymentCheckCount < 4 ||
    result.moduleCounts.chartCanvasCount < 2 ||
    result.moduleCounts.ledgerRowCount < 1 ||
    !hasExpectedAuditApiBaseUrl(result.apiBaseUrl)
);

const report = {
  baseUrl,
  route,
  generatedAt: new Date().toISOString(),
  screenshots: results.flatMap(result => [
    `${result.viewport}-supplier-collaboration-viewport.png`,
    `${result.viewport}-supplier-collaboration-full.png`
  ]),
  results,
  failed
};
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

const summary = results.map(result => ({
  viewport: result.viewport,
  h1: result.h1,
  supplierApiStatus: result.supplierApiStatus,
  bodyOverflowX: result.bodyOverflowX,
  consoleErrors: result.consoleErrors.length,
  badResponses: result.badResponses.length,
  failedRequests: result.failedRequests.length,
  abortedRequests: result.abortedRequests.length,
  overflowingText: result.overflowingText.length,
  badRects: result.badRects.length,
  overlapIssues: result.overlapIssues.length,
  ...result.moduleCounts
}));
console.log(JSON.stringify({ outDir, passed: failed.length === 0, summary }, null, 2));
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
