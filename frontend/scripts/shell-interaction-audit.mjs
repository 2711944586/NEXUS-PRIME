import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `shell-interaction-${Date.now()}`);
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
  await page.goto(`${baseUrl}/app/overview`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(700);
  const spotlightAudit = await auditSpotlight(page);
  const overviewScreenshot = `${viewport.name}-01-overview.png`;
  await page.screenshot({ path: path.join(outDir, overviewScreenshot), fullPage: false });

  const dockWorkflow = await auditDockWorkflow(page, `${viewport.name}-02-dock-workflow.png`);

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
  results.push({
    viewport: viewport.name,
    screenshots: [
      overviewScreenshot,
      dockWorkflow.screenshot
    ].filter(Boolean),
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses,
    spotlight: spotlightAudit,
    dockWorkflow
  });

  await context.close();
}

await browser.close();

const failed = results.filter(result =>
  result.consoleErrors.length ||
  result.failedRequests.length ||
  result.badResponses.length ||
  !result.spotlight.hasActiveSurface ||
  !result.spotlight.hasCoordinates ||
  !result.dockWorkflow.passed
);

const report = {
  baseUrl,
  route: '/app/overview',
  generatedAt: new Date().toISOString(),
  screenshots: results.flatMap(result => result.screenshots),
  results,
  failed
};

await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

const summary = results.map(result => ({
  viewport: result.viewport,
    consoleErrors: result.consoleErrors.length,
    failedRequests: result.failedRequests.length,
    badResponses: result.badResponses.length,
    spotlight: result.spotlight,
    dockWorkflow: {
      passed: result.dockWorkflow.passed,
      dockItems: result.dockWorkflow.dockItems,
      dockGroups: result.dockWorkflow.dockGroups,
      visibleGroupLabels: result.dockWorkflow.visibleGroupLabels,
      currentPath: result.dockWorkflow.currentPath,
      hiddenMoreTriggers: result.dockWorkflow.hiddenMoreTriggers,
      bodyOverflowX: result.dockWorkflow.bodyOverflowX,
      overflowingNoWrapText: result.dockWorkflow.overflowingNoWrapText.length,
      badRects: result.dockWorkflow.badRects.length
    }
}));

console.log(JSON.stringify({ outDir, passed: failed.length === 0, summary }, null, 2));
if (failed.length) {
  process.exit(1);
}

async function auditSpotlight(page) {
  const target = page.locator('.atlas-panel, .shift-stage-card, .atlas-record-row, .dock-item').first();
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) {
    return {
      hasTarget: false,
      hasActiveSurface: false,
      hasCoordinates: false,
      className: '',
      spotlightX: '',
      spotlightY: ''
    };
  }
  await page.mouse.move(box.x + Math.min(box.width - 8, Math.max(8, box.width * 0.62)), box.y + Math.min(box.height - 8, Math.max(8, box.height * 0.42)));
  await page.waitForTimeout(120);
  return page.evaluate(() => {
    const active = document.querySelector('.spotlight-active');
    const styles = active instanceof HTMLElement ? active.style : null;
    return {
      hasTarget: true,
      hasActiveSurface: Boolean(active),
      hasCoordinates: Boolean(styles?.getPropertyValue('--spotlight-x') && styles?.getPropertyValue('--spotlight-y')),
      className: active instanceof HTMLElement ? [...active.classList].slice(0, 6).join(' ') : '',
      spotlightX: styles?.getPropertyValue('--spotlight-x') || '',
      spotlightY: styles?.getPropertyValue('--spotlight-y') || ''
    };
  });
}

async function openModulePanel(page, selector, screenshotName, source) {
  const trigger = page.locator(selector).first();
  const visibleTrigger = await trigger.isVisible().catch(() => false);
  if (!visibleTrigger) {
    return {
      source,
      skipped: true,
      screenshot: null,
      visible: false,
      inViewport: false,
      closedByEscape: false,
      moduleLinkCount: 0,
      photoCount: 0,
      commandCardCount: 0,
      groupCount: 0,
      bodyOverflowX: 0,
      overflowingNoWrapText: [],
      badRects: []
    };
  }

  await trigger.click();
  await page.waitForSelector('.module-panel', { state: 'visible', timeout: 10000 });
  await page.waitForFunction(() => {
    const panel = document.querySelector('.module-panel');
    if (!panel) {
      return false;
    }
    const box = panel.getBoundingClientRect();
    return box.width > 200 && box.height > 300 && box.top >= 0 && box.left >= 0 && box.bottom <= window.innerHeight + 2 && box.right <= window.innerWidth + 2;
  }, { timeout: 10000 });
  await page.waitForTimeout(350);

  const audit = await page.evaluate(sourceName => {
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
    const panel = document.querySelector('.module-panel');
    const panelBox = panel?.getBoundingClientRect();
    const inViewport = Boolean(
      panelBox &&
      panelBox.top >= -1 &&
      panelBox.left >= -1 &&
      panelBox.right <= window.innerWidth + 2 &&
      panelBox.bottom <= window.innerHeight + 2
    );
    const count = selector => [...document.querySelectorAll(selector)].filter(visible).length;
    const overflowingNoWrapText = [...document.querySelectorAll('.module-panel button, .module-panel a, .module-panel strong, .module-panel em, .module-panel span')]
      .filter(visible)
      .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
      .slice(0, 12)
      .map(element => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
        width: Math.round(element.clientWidth),
        scroll: Math.round(element.scrollWidth)
      }));
    const badRects = [...document.querySelectorAll('.module-panel, .module-panel a, .module-panel button')]
      .filter(visible)
      .filter(element => !element.closest('.module-photo-rail'))
      .map(element => ({ element, box: element.getBoundingClientRect() }))
      .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2)
      .slice(0, 12)
      .map(({ element, box }) => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
        left: Math.round(box.left),
        right: Math.round(box.right),
        width: Math.round(box.width)
      }));

    return {
      source: sourceName,
      skipped: false,
      visible: Boolean(panel && visible(panel)),
      inViewport,
      panelRect: panelBox
        ? {
            x: Math.round(panelBox.x),
            y: Math.round(panelBox.y),
            width: Math.round(panelBox.width),
            height: Math.round(panelBox.height),
            bottom: Math.round(panelBox.bottom),
            right: Math.round(panelBox.right)
          }
        : null,
      viewportSize: { width: window.innerWidth, height: window.innerHeight },
      bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
      moduleLinkCount: count('.module-panel .module-card-link'),
      photoCount: count('.module-panel .module-photo-rail figure'),
      loadedPhotoCount: [...document.querySelectorAll('.module-panel .module-photo-rail img')]
        .filter(visible)
        .filter(image => image.complete && image.naturalWidth > 0)
        .length,
      commandCardCount: count('.module-panel .module-command-deck article'),
      groupCount: count('.module-panel .drawer-group'),
      closeButtonCount: count('.module-panel button[aria-label="关闭更多模块"]'),
      sampleModules: [...document.querySelectorAll('.module-panel .module-card-link strong')]
        .filter(visible)
        .map(element => element.textContent?.trim())
        .filter(Boolean)
        .slice(0, 10),
      samplePhotos: [...document.querySelectorAll('.module-panel .module-photo-rail figcaption strong')]
        .filter(visible)
        .map(element => element.textContent?.trim())
        .filter(Boolean)
        .slice(0, 10),
      overflowingNoWrapText,
      badRects
    };
  }, source);

  await page.screenshot({ path: path.join(outDir, screenshotName), fullPage: false });
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.module-panel-backdrop'), { timeout: 8000 });
  return {
    ...audit,
    screenshot: screenshotName,
    closedByEscape: true
  };
}

async function auditDockWorkflow(page, screenshotName) {
  await page.waitForSelector('.atlas-dock .dock-item', { state: 'visible', timeout: 10000 });
  const target = page.locator('.atlas-dock .dock-item[href="/app/reports"], .atlas-dock .dock-item[href$="/app/reports"]').first();
  await target.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(outDir, screenshotName), fullPage: false });

  const before = await collectDockWorkflowState(page);
  await target.click();
  await page.waitForURL('**/app/reports', { timeout: 15000 });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  const after = await collectDockWorkflowState(page);

  const requiredPaths = [
    '/app/overview',
    '/app/inventory/products',
    '/app/inventory/stock',
    '/app/procurement/orders',
    '/app/quality',
    '/app/sales/orders',
    '/app/finance/receivables',
    '/app/reports'
  ];
  const missingPaths = requiredPaths.filter(route => !before.paths.includes(route));
  const requiredGroupCount = before.isCompactDock ? 0 : 6;

  return {
    ...before,
    screenshot: screenshotName,
    currentPath: new URL(page.url()).pathname,
    activeAfterNavigation: after.activePath,
    missingPaths,
    passed:
      before.visible &&
      before.dockItems >= requiredPaths.length &&
      before.dockGroups >= requiredGroupCount &&
      missingPaths.length === 0 &&
      before.hiddenMoreTriggers &&
      before.bodyOverflowX <= 3 &&
      before.overflowingNoWrapText.length === 0 &&
      before.badRects.length === 0 &&
      new URL(page.url()).pathname === '/app/reports' &&
      after.activePath === '/app/reports'
  };
}

async function collectDockWorkflowState(page) {
  return page.evaluate(() => {
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
    const dock = document.querySelector('.atlas-dock');
    const dockItems = [...document.querySelectorAll('.atlas-dock .dock-item')].filter(visible);
    const moreTriggers = [...document.querySelectorAll('.atlas-dock-more, button[aria-label="更多模块"]')].filter(visible);
    const overflowingNoWrapText = [...document.querySelectorAll('.atlas-dock, .atlas-dock .dock-item, .atlas-dock .dock-label, .atlas-dock .dock-capsule-label, .atlas-location em')]
      .filter(visible)
      .filter(element => element.scrollWidth > element.clientWidth + 2 && getComputedStyle(element).whiteSpace === 'nowrap')
      .slice(0, 12)
      .map(element => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
        width: Math.round(element.clientWidth),
        scroll: Math.round(element.scrollWidth)
      }));
    const badRects = [...document.querySelectorAll('.atlas-dock, .atlas-dock .dock-item, .atlas-topbar, .workflow-command-strip')]
      .filter(visible)
      .map(element => ({ element, box: element.getBoundingClientRect() }))
      .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2)
      .slice(0, 12)
      .map(({ element, box }) => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
        left: Math.round(box.left),
        right: Math.round(box.right),
        width: Math.round(box.width)
      }));
    return {
      visible: Boolean(dock && visible(dock)),
      dockItems: dockItems.length,
      dockGroups: [...document.querySelectorAll('.atlas-dock .dock-capsule')].filter(visible).length,
      visibleGroupLabels: [...document.querySelectorAll('.atlas-dock .dock-capsule-label')].filter(visible).length,
      isCompactDock: window.innerWidth <= 1280,
      paths: dockItems.map(item => item.getAttribute('href') || ''),
      activePath: document.querySelector('.atlas-dock .dock-item.active')?.getAttribute('href') || null,
      currentDomain: document.querySelector('.dock-current-domain strong')?.textContent?.trim() || '',
      hiddenMoreTriggers: moreTriggers.length === 0,
      bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
      overflowingNoWrapText,
      badRects
    };
  });
}

async function visibleTriggerSelector(page, selectors) {
  for (const selector of selectors) {
    const trigger = page.locator(selector).first();
    if (await trigger.isVisible().catch(() => false)) {
      return selector;
    }
  }
  throw new Error(`No visible module trigger found: ${selectors.join(', ')}`);
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  const submit = page.locator('button[type="submit"]').first();
  await submit.waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForFunction(() => {
    const button = document.querySelector('button[type="submit"]');
    return button && !button.hasAttribute('disabled');
  }, null, { timeout: 15000 });
  await submit.click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
