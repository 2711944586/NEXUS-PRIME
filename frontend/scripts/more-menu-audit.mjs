import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `more-menu-audit-${Date.now()}`);
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
  const screenshots = [];

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
  await gotoApp(page, '/app/overview');

  const quickCreate = await safeAudit('quickCreate', () => auditQuickCreate(page, viewport, screenshots));
  const topbarMore = await safeAudit('topbarMore', () => auditModulePanel(page, viewport, 'button[aria-label="更多模块"]', 'topbar', screenshots));
  const dockMore = await safeAudit('dockMore', () => auditModulePanel(page, viewport, '.atlas-dock-more', 'dock', screenshots));
  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));

  results.push({
    viewport: viewport.name,
    screenshots,
    quickCreate,
    topbarMore,
    dockMore,
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses
  });

  await context.close();
}

await browser.close();

const failed = results.filter(result =>
  result.consoleErrors.length ||
  result.failedRequests.length ||
  result.badResponses.length ||
  !result.quickCreate.passed ||
  !result.topbarMore.passed ||
  (!result.dockMore.passed && !(result.viewport === 'mobile' && result.dockMore.skipped))
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

console.log(JSON.stringify({
  outDir,
  passed: failed.length === 0,
  summary: results.map(result => ({
    viewport: result.viewport,
    quickCreate: compact(result.quickCreate),
    topbarMore: compact(result.topbarMore),
    dockMore: compact(result.dockMore),
    consoleErrors: result.consoleErrors.length,
    failedRequests: result.failedRequests.length,
    abortedRequests: result.abortedRequests.length,
    badResponses: result.badResponses.length
  }))
}, null, 2));

if (failed.length) {
  process.exit(1);
}

async function auditQuickCreate(page, viewport, screenshots) {
  await gotoApp(page, '/app/overview');
  const triggerSelector = 'button[aria-label="打开快捷创建"]';
  const trigger = page.locator(triggerSelector).first();
  const visibleTrigger = await trigger.isVisible().catch(() => false);
  if (!visibleTrigger) {
    return { key: 'quickCreate', passed: false, reason: 'trigger-not-visible' };
  }

  const initialExpanded = await trigger.getAttribute('aria-expanded');
  await trigger.click();
  await page.waitForSelector('#quick-create-popover[role="menu"] a[role="menuitem"]', { state: 'visible', timeout: 8000 });
  await page.waitForTimeout(180);

  const openState = await collectQuickCreateState(page, triggerSelector);
  const screenshot = `${viewport.name}-01-quick-create-open.png`;
  await page.screenshot({ path: path.join(outDir, screenshot), fullPage: false });
  screenshots.push(screenshot);

  await clickWorkbench(page);
  await page.waitForFunction(() => !document.querySelector('#quick-create-popover'), null, { timeout: 6000 });
  const closedByOutsideClick = await trigger.getAttribute('aria-expanded').then(value => value === 'false');

  await trigger.click();
  await page.waitForSelector('#quick-create-popover a[role="menuitem"]', { state: 'visible', timeout: 8000 });
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('#quick-create-popover'), null, { timeout: 6000 });
  const closedByEscape = await trigger.getAttribute('aria-expanded').then(value => value === 'false');

  await trigger.click();
  await page.waitForSelector('#quick-create-popover a[role="menuitem"]', { state: 'visible', timeout: 8000 });
  const expectedPath = await page.locator('#quick-create-popover a[role="menuitem"]').first().getAttribute('href');
  await page.locator('#quick-create-popover a[role="menuitem"]').first().click();
  await page.waitForURL(url => pathMatches(url.pathname, expectedPath), { timeout: 15000 });
  const navigatedPath = new URL(page.url()).pathname;

  return {
    key: 'quickCreate',
    passed:
      initialExpanded === 'false' &&
      openState.expanded === 'true' &&
      openState.popoverVisible &&
      openState.linkCount >= 5 &&
      openState.deadLinks.length === 0 &&
      openState.inViewport &&
      openState.badRects.length === 0 &&
      openState.overflowingNoWrapText.length === 0 &&
      openState.focusInside &&
      closedByOutsideClick &&
      closedByEscape &&
      pathMatches(navigatedPath, expectedPath),
    initialExpanded,
    openState,
    closedByOutsideClick,
    closedByEscape,
    expectedPath,
    navigatedPath
  };
}

async function auditModulePanel(page, viewport, selector, source, screenshots) {
  await gotoApp(page, '/app/overview');
  const trigger = page.locator(selector).first();
  const visibleTrigger = await trigger.isVisible().catch(() => false);
  if (!visibleTrigger) {
    return { key: source, source, skipped: true, passed: false, reason: 'trigger-not-visible' };
  }

  const initialExpanded = await trigger.getAttribute('aria-expanded');
  await trigger.click();
  await page.waitForSelector('#module-map-panel[role="dialog"] .module-card-link', { state: 'visible', timeout: 10000 });
  await page.waitForFunction(() => {
    const panel = document.querySelector('#module-map-panel');
    if (!panel) {
      return false;
    }
    const box = panel.getBoundingClientRect();
    return box.width > 200 && box.height > 300 && box.right <= window.innerWidth + 2 && box.bottom <= window.innerHeight + 2;
  }, { timeout: 10000 });
  await page.waitForTimeout(220);

  const openState = await collectModulePanelState(page, selector);
  const screenshot = `${viewport.name}-02-${source}-module-panel.png`;
  await page.screenshot({ path: path.join(outDir, screenshot), fullPage: false });
  screenshots.push(screenshot);

  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.module-panel-backdrop'), null, { timeout: 8000 });
  const closedByEscape = await trigger.getAttribute('aria-expanded').then(value => value === 'false');

  await trigger.click();
  await page.waitForSelector('#module-map-panel .module-card-link', { state: 'visible', timeout: 10000 });
  await clickOutsideModulePanel(page);
  await page.waitForFunction(() => !document.querySelector('.module-panel-backdrop'), null, { timeout: 8000 });
  const closedByBackdropClick = await trigger.getAttribute('aria-expanded').then(value => value === 'false');

  await trigger.click();
  await page.waitForSelector('#module-map-panel .module-card-link', { state: 'visible', timeout: 10000 });
  const target = page.locator('#module-map-panel .module-card-link[href="/app/reports"], #module-map-panel .module-card-link[href$="/app/reports"]').first();
  const expectedPath = await target.getAttribute('href');
  await target.click();
  await page.waitForURL(url => pathMatches(url.pathname, expectedPath), { timeout: 15000 });
  const navigatedPath = new URL(page.url()).pathname;

  return {
    key: source,
    source,
    skipped: false,
    passed:
      initialExpanded === 'false' &&
      openState.expanded === 'true' &&
      openState.panelVisible &&
      openState.moduleLinkCount >= 30 &&
      openState.photoCount >= 10 &&
      openState.commandCardCount >= 3 &&
      openState.groupCount >= 6 &&
      openState.closeButtonCount >= 1 &&
      openState.focusOnCloseButton &&
      openState.inViewport &&
      openState.deadLinks.length === 0 &&
      openState.badRects.length === 0 &&
      openState.overflowingNoWrapText.length === 0 &&
      closedByEscape &&
      closedByBackdropClick &&
      pathMatches(navigatedPath, expectedPath),
    initialExpanded,
    openState,
    closedByEscape,
    closedByBackdropClick,
    expectedPath,
    navigatedPath
  };
}

async function collectQuickCreateState(page, triggerSelector) {
  return page.evaluate(selector => {
    const visible = element => {
      const box = element.getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0) {
        return false;
      }
      for (let current = element; current && current !== document.documentElement; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.visibility === 'hidden' || style.display === 'none') {
          return false;
        }
      }
      return true;
    };
    const overflowingNoWrap = itemSelector => [...document.querySelectorAll(itemSelector)]
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
    const badRects = itemSelector => [...document.querySelectorAll(itemSelector)]
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
    const trigger = document.querySelector(selector);
    const popover = document.querySelector('#quick-create-popover');
    const popoverBox = popover?.getBoundingClientRect();
    const links = [...document.querySelectorAll('#quick-create-popover a[role="menuitem"]')].filter(visible);
    return {
      expanded: trigger?.getAttribute('aria-expanded') ?? null,
      controls: trigger?.getAttribute('aria-controls') ?? null,
      popoverVisible: Boolean(popover && visible(popover)),
      role: popover?.getAttribute('role') ?? null,
      linkCount: links.length,
      firstLinkText: links[0]?.textContent?.trim().replace(/\s+/g, ' ') ?? null,
      focusInside: Boolean(popover && popover.contains(document.activeElement)),
      inViewport: Boolean(popoverBox && popoverBox.left >= -1 && popoverBox.top >= -1 && popoverBox.right <= window.innerWidth + 2 && popoverBox.bottom <= window.innerHeight + 2),
      deadLinks: links
        .map(link => ({ href: link.getAttribute('href') || '', text: link.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) || '' }))
        .filter(link => !link.href || link.href === '#' || link.href.startsWith('javascript:')),
      overflowingNoWrapText: overflowingNoWrap('#quick-create-popover a, #quick-create-popover strong, #quick-create-popover em, #quick-create-popover span'),
      badRects: badRects('#quick-create-popover, #quick-create-popover a')
    };
  }, triggerSelector);
}

async function collectModulePanelState(page, triggerSelector) {
  return page.evaluate(selector => {
    const visible = element => {
      const box = element.getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0) {
        return false;
      }
      for (let current = element; current && current !== document.documentElement; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.visibility === 'hidden' || style.display === 'none') {
          return false;
        }
      }
      return true;
    };
    const overflowingNoWrap = itemSelector => [...document.querySelectorAll(itemSelector)]
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
    const badRects = itemSelector => [...document.querySelectorAll(itemSelector)]
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
    const trigger = document.querySelector(selector);
    const panel = document.querySelector('#module-map-panel');
    const panelBox = panel?.getBoundingClientRect();
    const links = [...document.querySelectorAll('#module-map-panel .module-card-link')].filter(visible);
    return {
      expanded: trigger?.getAttribute('aria-expanded') ?? null,
      controls: trigger?.getAttribute('aria-controls') ?? null,
      panelVisible: Boolean(panel && visible(panel)),
      role: panel?.getAttribute('role') ?? null,
      inViewport: Boolean(panelBox && panelBox.left >= -1 && panelBox.top >= -1 && panelBox.right <= window.innerWidth + 2 && panelBox.bottom <= window.innerHeight + 2),
      panelRect: panelBox ? {
        left: Math.round(panelBox.left),
        top: Math.round(panelBox.top),
        right: Math.round(panelBox.right),
        bottom: Math.round(panelBox.bottom),
        width: Math.round(panelBox.width),
        height: Math.round(panelBox.height)
      } : null,
      focusOnCloseButton: Boolean(document.activeElement?.matches('#module-map-panel button[aria-label="关闭更多模块"]')),
      moduleLinkCount: links.length,
      photoCount: [...document.querySelectorAll('#module-map-panel .module-photo-rail figure')].filter(visible).length,
      commandCardCount: [...document.querySelectorAll('#module-map-panel .module-command-deck article')].filter(visible).length,
      groupCount: [...document.querySelectorAll('#module-map-panel .drawer-group')].filter(visible).length,
      closeButtonCount: [...document.querySelectorAll('#module-map-panel button[aria-label="关闭更多模块"]')].filter(visible).length,
      deadLinks: links
        .map(link => ({ href: link.getAttribute('href') || '', text: link.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) || '' }))
        .filter(link => !link.href || link.href === '#' || link.href.startsWith('javascript:')),
      overflowingNoWrapText: overflowingNoWrap('#module-map-panel button, #module-map-panel a, #module-map-panel strong, #module-map-panel em, #module-map-panel span'),
      badRects: badRects('#module-map-panel, #module-map-panel a, #module-map-panel button')
    };
  }, triggerSelector);
}

function compact(result) {
  return {
    key: result.key,
    source: result.source,
    passed: result.passed,
    skipped: result.skipped || false,
    reason: result.reason,
    expanded: result.openState?.expanded,
    links: result.openState?.linkCount ?? result.openState?.moduleLinkCount,
    focusInside: result.openState?.focusInside,
    focusOnCloseButton: result.openState?.focusOnCloseButton,
    closedByEscape: result.closedByEscape,
    closedByOutsideClick: result.closedByOutsideClick,
    closedByBackdropClick: result.closedByBackdropClick,
    navigatedPath: result.navigatedPath,
    nowrap: result.openState?.overflowingNoWrapText?.length,
    badRects: result.openState?.badRects?.length
  };
}

async function clickWorkbench(page) {
  const workbench = page.locator('.atlas-workbench').first();
  if (await workbench.isVisible().catch(() => false)) {
    await workbench.click({ position: { x: 8, y: 8 } });
    return;
  }
  await page.mouse.click(12, 180);
}

async function clickOutsideModulePanel(page) {
  const point = await page.evaluate(() => {
    const panel = document.querySelector('#module-map-panel');
    const box = panel?.getBoundingClientRect();
    if (!box) {
      return { x: 12, y: 12 };
    }
    if (box.left > 24) {
      return { x: Math.max(12, box.left - 16), y: Math.min(window.innerHeight - 12, box.top + 24) };
    }
    if (box.top > 24) {
      return { x: Math.round(window.innerWidth / 2), y: Math.max(12, box.top - 12) };
    }
    return { x: Math.min(window.innerWidth - 3, box.right + 16), y: Math.min(window.innerHeight - 12, box.top + 24) };
  });
  await page.mouse.click(point.x, point.y);
}

function visible(element) {
  const box = element.getBoundingClientRect();
  if (box.width <= 0 || box.height <= 0) {
    return false;
  }
  for (let current = element; current && current !== document.documentElement; current = current.parentElement) {
    const style = getComputedStyle(current);
    if (style.visibility === 'hidden' || style.display === 'none') {
      return false;
    }
  }
  return true;
}

function overflowingNoWrap(selector) {
  return [...document.querySelectorAll(selector)]
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
}

function badRects(selector) {
  return [...document.querySelectorAll(selector)]
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
}

function pathMatches(actualPath, expectedPath) {
  if (!expectedPath) {
    return false;
  }
  return actualPath === expectedPath || actualPath.endsWith(expectedPath);
}

async function safeAudit(key, fn) {
  try {
    return await fn();
  } catch (error) {
    return {
      key,
      passed: false,
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

async function gotoApp(page, route) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(450);
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
