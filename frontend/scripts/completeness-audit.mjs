import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { apiBaseFailureLabel, hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `completeness-audit-${Date.now()}`);
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

const routeThresholds = new Map([
  ['/app/overview', { mainDataRows: 0, mainActionSurfaces: 3, mainSections: 2 }],
  ['/app/settings', { mainDataRows: 4, mainActionSurfaces: 4, mainSections: 3 }],
  ['/app/ai', { mainDataRows: 4, mainActionSurfaces: 4, mainSections: 3 }]
]);

const defaultThresholds = {
  visualAssets: 1,
  workflowLinks: 0,
  handoffActions: 0,
  mainDataRows: 0,
  mainActionSurfaces: 1,
  mainSections: 1,
  mainTextBlocks: 6
};

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
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
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
      const count = (selector, root = document) => [...root.querySelectorAll(selector)].filter(visible).length;
      const texts = (selector, root = document, limit = 10) =>
        [...root.querySelectorAll(selector)]
          .filter(visible)
          .map(element => element.textContent?.trim().replace(/\s+/g, ' '))
          .filter(Boolean)
          .slice(0, limit);
      const main = document.querySelector('#main-content');
      const normalizeAssetPath = value => {
        try {
          return new URL(value, window.location.origin).pathname;
        } catch {
          return value;
        }
      };
      const backgroundAssets = [...document.querySelectorAll('#main-content *')]
        .filter(visible)
        .flatMap(element => {
          const image = getComputedStyle(element).backgroundImage || '';
          return [...image.matchAll(/url\(["']?([^"')]+)["']?\)/g)]
            .map(match => normalizeAssetPath(match[1]))
            .filter(src => src.startsWith('/images/'));
        });
      const visibleImages = [...document.querySelectorAll('img')]
        .filter(visible)
        .filter(image => image.complete && image.naturalWidth > 0)
        .map(image => {
          const box = image.getBoundingClientRect();
          return {
            src: image.getAttribute('src') || '',
            alt: image.getAttribute('alt') || '',
            width: Math.round(box.width),
            height: Math.round(box.height)
          };
        });
      const mainImages = main
        ? [...main.querySelectorAll('img')]
          .filter(visible)
          .filter(image => image.complete && image.naturalWidth > 0)
          .map(image => image.getAttribute('src') || '')
        : [];
      const deadLinks = [...document.querySelectorAll('a')]
        .filter(visible)
        .map(element => ({
          href: element.getAttribute('href') || '',
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90) || '',
          inMain: Boolean(main && main.contains(element))
        }))
        .filter(item => !item.href || item.href === '#' || item.href.startsWith('javascript:'))
        .slice(0, 20);
      const placeholderPattern = new RegExp([
        '占' + '位',
        '内容待' + '完善',
        '截图占' + '位',
        'lorem\\s+ipsum',
        'TODO',
        'FIXME'
      ].join('|'), 'gi');
      const placeholderMatches = texts('body', document, 1)
        .join(' ')
        .match(placeholderPattern) || [];
      const overflowingNoWrapText = [...document.querySelectorAll('button, a, .p-tag, h1, h2, h3, strong, em, span')]
        .filter(visible)
        .filter(element => !element.closest('.module-photo-rail, .command-photo-strip, .field-evidence-grid'))
        .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
        .slice(0, 18)
        .map(element => ({
          tag: element.tagName.toLowerCase(),
          className: [...element.classList].slice(0, 4).join('.'),
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
          width: Math.round(element.clientWidth),
          scroll: Math.round(element.scrollWidth)
        }));
      const badRects = [...document.querySelectorAll('button, a, .atlas-panel, .context-block, .page-evidence-strip, .mobile-field-evidence-strip, .field-evidence-grid a, .shift-handoff-list a')]
        .filter(visible)
        .filter(element => !element.closest('.module-photo-rail, .field-evidence-grid'))
        .map(element => ({ element, box: element.getBoundingClientRect() }))
        .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2)
        .slice(0, 18)
        .map(({ element, box }) => ({
          tag: element.tagName.toLowerCase(),
          className: [...element.classList].slice(0, 4).join('.'),
          text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
          left: Math.round(box.left),
          right: Math.round(box.right),
          width: Math.round(box.width)
        }));
      const mainDataRows = main ? count(
        '.business-data-row, .atlas-record-row, .ledger-row, .risk-brick, article, .home-system-card, .service-line-card, .report-template-list button, .settings-option-grid button, .settings-link-list a, .profile-work-card, .ai-action-list a, .shift-event-timeline a, .shift-action-queue a, .command-lean-metrics a, .command-workflow-rail a, .command-domain-grid a, .command-action-list a',
        main
      ) : 0;
      const mainActionSurfaces = main ? count('a[href], button:not([disabled]), input, textarea, select, .atlas-record-row', main) : 0;
      const mainSections = main ? count('section, article, .atlas-panel, .context-block, .home-system-card, .risk-brick', main) : 0;
      const mainTextBlocks = main ? texts('h1, h2, h3, p, strong, em, span, small', main, 80).length : 0;
      const workflowLinks = count('.page-evidence-grid a, .field-evidence-grid a, .shift-handoff-list a, .workflow-signal-list a, .workflow-step-rail a, .context-action, .command-hero-actions a, .command-lean-metrics a, .command-workflow-rail a, .command-domain-grid a, .command-action-list a, .atlas-actions-row a[href^="/app/"]');
      const handoffActions = count('.shift-handoff-list a');
      const shellEvidenceImages = visibleImages.filter(image => image.src.includes('/images/')).length;
      const pageEvidenceImages = [...document.querySelectorAll('.page-evidence-strip img')]
        .filter(visible)
        .filter(image => image.complete && image.naturalWidth > 0)
        .length;
      const h1 = main?.querySelector('h1')?.textContent?.trim() || document.querySelector('h1')?.textContent?.trim() || '';

      return {
        path: location.pathname,
        title: document.title,
        h1,
        viewportSize: { width: window.innerWidth, height: window.innerHeight },
        apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null,
        bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
        shellEvidenceImages,
        pageEvidenceImages,
        visualAssets: [...new Set([
          ...mainImages.map(src => normalizeAssetPath(src)).filter(src => src.startsWith('/images/')),
          ...backgroundAssets
        ])],
        mainImages: mainImages.slice(0, 8),
        workflowLinks,
        handoffActions,
        mainDataRows,
        mainActionSurfaces,
        mainSections,
        mainTextBlocks,
        deadLinks,
        placeholderMatches: [...new Set(placeholderMatches)].slice(0, 8),
        overflowingNoWrapText,
        badRects,
        samples: {
          mainData: texts('.business-data-row, .atlas-record-row, .ledger-row, article, .risk-brick, .home-system-card', main || document, 8),
          mainActions: texts('a[href], button:not([disabled])', main || document, 8),
          workflow: texts('.page-evidence-grid a, .field-evidence-grid a, .shift-handoff-list a, .workflow-step-rail a', document, 8),
          images: visibleImages.slice(0, 8)
        }
      };
    });

    const thresholds = { ...defaultThresholds, ...(routeThresholds.get(route) || {}) };
    const failures = evaluateRoute(audit, thresholds);
    const slug = `${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[/:]/g, '-') || 'home'}`;
    if (failures.length || route === '/app/overview' || route === '/app/settings') {
      await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
    }

    results.push({
      viewport: viewport.name,
      route,
      thresholds,
      failures,
      ...audit
    });
  }

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
  results.push({
    viewport: viewport.name,
    route: '__network__',
    failures: [
      ...consoleErrors.map(message => `console:${message}`),
      ...failedRequests.map(item => `request:${item.method} ${item.url} ${item.error}`),
      ...badResponses.map(item => `response:${item.status} ${item.url}`)
    ],
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses
  });

  await context.close();
}

await browser.close();

const failed = results.filter(result => result.failures?.length);
const report = {
  baseUrl,
  routes,
  generatedAt: new Date().toISOString(),
  results,
  failed
};
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

const pageResults = results.filter(result => result.route !== '__network__');
const networkResults = results.filter(result => result.route === '__network__');
const summary = {
  outDir,
  passed: failed.length === 0,
  failedCount: failed.length,
  pageSummary: pageResults.map(result => ({
    viewport: result.viewport,
    route: result.route,
    failures: result.failures,
    h1: result.h1,
    evidenceImages: result.shellEvidenceImages,
    pageEvidenceImages: result.pageEvidenceImages,
    visualAssets: result.visualAssets.length,
    workflowLinks: result.workflowLinks,
    handoffActions: result.handoffActions,
    mainDataRows: result.mainDataRows,
    mainActionSurfaces: result.mainActionSurfaces,
    mainSections: result.mainSections,
    mainTextBlocks: result.mainTextBlocks,
    overflow: result.bodyOverflowX,
    deadLinks: result.deadLinks.length,
    placeholders: result.placeholderMatches.length,
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

function evaluateRoute(audit, thresholds) {
  const failures = [];
  if (!hasExpectedAuditApiBaseUrl(audit.apiBaseUrl)) {
    failures.push(apiBaseFailureLabel(audit.apiBaseUrl));
  }
  if (!audit.h1) {
    failures.push('missing_h1');
  }
  if (thresholds.shellEvidenceImages && audit.shellEvidenceImages < thresholds.shellEvidenceImages) {
    failures.push(`shell_evidence:${audit.shellEvidenceImages}<${thresholds.shellEvidenceImages}`);
  }
  if (thresholds.pageEvidenceImages && audit.pageEvidenceImages < thresholds.pageEvidenceImages) {
    failures.push(`page_evidence:${audit.pageEvidenceImages}<${thresholds.pageEvidenceImages}`);
  }
  if (audit.visualAssets.length < thresholds.visualAssets) {
    failures.push(`visual_assets:${audit.visualAssets.length}<${thresholds.visualAssets}`);
  }
  if (audit.workflowLinks < thresholds.workflowLinks) {
    failures.push(`workflow_links:${audit.workflowLinks}<${thresholds.workflowLinks}`);
  }
  if (audit.handoffActions < thresholds.handoffActions) {
    failures.push(`handoff:${audit.handoffActions}<${thresholds.handoffActions}`);
  }
  if (audit.mainDataRows < thresholds.mainDataRows) {
    failures.push(`main_data:${audit.mainDataRows}<${thresholds.mainDataRows}`);
  }
  if (audit.mainActionSurfaces < thresholds.mainActionSurfaces) {
    failures.push(`main_actions:${audit.mainActionSurfaces}<${thresholds.mainActionSurfaces}`);
  }
  if (audit.mainSections < thresholds.mainSections) {
    failures.push(`main_sections:${audit.mainSections}<${thresholds.mainSections}`);
  }
  if (audit.mainTextBlocks < thresholds.mainTextBlocks) {
    failures.push(`main_text:${audit.mainTextBlocks}<${thresholds.mainTextBlocks}`);
  }
  if (audit.bodyOverflowX > 3) {
    failures.push(`overflow_x:${audit.bodyOverflowX}`);
  }
  if (audit.deadLinks.length) {
    failures.push(`dead_links:${audit.deadLinks.length}`);
  }
  if (audit.placeholderMatches.length) {
    failures.push(`placeholder:${audit.placeholderMatches.join(',')}`);
  }
  if (audit.overflowingNoWrapText.length) {
    failures.push(`nowrap:${audit.overflowingNoWrapText.length}`);
  }
  if (audit.badRects.length) {
    failures.push(`bad_rects:${audit.badRects.length}`);
  }
  return failures;
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
