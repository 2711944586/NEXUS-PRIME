import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { expectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `topbar-operations-audit-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const viewports = [
  { name: 'desktop', width: 1440, height: 950 },
  { name: 'mobile', width: 390, height: 844 }
];

const navigationTargets = [
  { key: 'serviceHealth', label: '服务健康', selector: '.service-health-chip', expectedPath: '/app/integrations' },
  { key: 'analytics', label: '经营分析', selector: 'a[aria-label="打开经营分析台"], .ai-topbar-action', expectedPath: '/app/ai' },
  { key: 'settings', label: '全局设置', selector: 'a[aria-label="全局设置"]', expectedPath: '/app/settings' },
  { key: 'notifications', label: '通知中心', selector: 'a[aria-label="通知中心"]', expectedPath: '/app/notifications' },
  { key: 'profile', label: '个人工作台', selector: 'a[aria-label="个人工作台"]', expectedPath: '/app/profile' }
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

  const baseline = await collectTopbarBaseline(page, viewport.name);
  const search = await safeAudit('search', () => auditSearch(page, viewport.name, screenshots));
  const quickCreate = await safeAudit('quickCreate', () => auditQuickCreate(page, viewport.name, screenshots));
  const sync = await safeAudit('sync', () => auditSync(page, viewport.name));
  const navigation = [];

  for (const target of navigationTargets) {
    navigation.push(await safeAudit(target.key, () => auditNavigation(page, target, viewport.name)));
  }

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));

  results.push({
    viewport: viewport.name,
    screenshots,
    baseline,
    search,
    quickCreate,
    sync,
    navigation,
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
  !result.baseline.passed ||
  !result.search.passed ||
  !result.quickCreate.passed ||
  !result.sync.passed ||
  result.navigation.some(item => !item.passed)
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

const summary = {
  outDir,
  passed: failed.length === 0,
  results: results.map(result => ({
    viewport: result.viewport,
    baseline: {
      passed: result.baseline.passed,
      visibleActionCount: result.baseline.visibleActionCount,
      searchVisible: result.baseline.visible.search,
      bodyOverflowX: result.baseline.bodyOverflowX,
      nowrap: result.baseline.overflowingNoWrapText.length,
      badRects: result.baseline.badRects.length
    },
    search: compactOperation(result.search),
    quickCreate: compactOperation(result.quickCreate),
    sync: compactOperation(result.sync),
    navigation: result.navigation.map(item => ({
      key: item.key,
      passed: item.passed,
      actualPath: item.actualPath,
      expectedPath: item.expectedPath
    })),
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

async function safeAudit(key, fn) {
  try {
    return await fn();
  } catch (error) {
    return {
      key,
      passed: false,
      error: error instanceof Error ? error.stack || error.message : String(error)
    };
  }
}

function compactOperation(operation) {
  return {
    key: operation.key,
    passed: operation.passed,
    skipped: operation.skipped || false,
    count: operation.count,
    navigationPassed: operation.navigationPassed,
    closedByEscape: operation.closedByEscape,
    actualPath: operation.actualPath,
    error: operation.error ? String(operation.error).split('\n')[0] : undefined
  };
}

async function auditSearch(page, viewportName, screenshots) {
  await gotoApp(page, '/app/overview');
  const input = page.locator('.atlas-search input').first();
  const visibleInput = await input.isVisible().catch(() => false);
  if (!visibleInput) {
    return {
      key: 'search',
      passed: viewportName === 'mobile',
      skipped: true,
      reason: 'responsive-hidden'
    };
  }

  await input.click();
  await page.waitForSelector('.atlas-search-popover a', { state: 'visible', timeout: 8000 });
  await page.waitForTimeout(150);
  const suggestions = await collectPopoverLinks(page, '.atlas-search-popover');
  const suggestionScreenshot = `${viewportName}-01-search-suggestions.png`;
  await page.screenshot({ path: path.join(outDir, suggestionScreenshot), fullPage: false });
  screenshots.push(suggestionScreenshot);

  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.atlas-search-popover'), null, { timeout: 6000 });
  const closedByEscape = await page.locator('.atlas-search-popover').count().then(count => count === 0);

  await input.click();
  await input.fill('');
  const searchResponsePromise = page.waitForResponse(response =>
    response.url().includes('/api/v1/search') &&
    new URL(response.url()).searchParams.get('q') === 'MFG' &&
    response.status() < 400,
  { timeout: 12000 }).catch(() => null);
  await input.fill('MFG');
  await page.keyboard.press('Enter');
  const searchResponse = await searchResponsePromise;
  const searchPayload = searchResponse ? await searchResponse.json().catch(() => null) : null;
  await page.waitForFunction(() => {
    return [...document.querySelectorAll('.atlas-search-popover a')]
      .some(element => (element.getAttribute('href') || '').startsWith('/app/') && (element.textContent || '').includes('MFG-'));
  }, null, { timeout: 12000 });
  await page.locator('.atlas-search-popover a').filter({ hasText: 'MFG-' }).first().waitFor({ state: 'visible', timeout: 12000 });
  await page.waitForTimeout(450);
  const results = await collectPopoverLinks(page, '.atlas-search-popover');
  const resultScreenshot = `${viewportName}-02-search-results.png`;
  await page.screenshot({ path: path.join(outDir, resultScreenshot), fullPage: false });
  screenshots.push(resultScreenshot);

  const expectedPath = normalizeExpectedPath(results.firstHref);
  if (results.count > 0) {
    await page.locator('.atlas-search-popover a').first().click();
    await page.waitForURL(url => pathMatches(url.pathname, expectedPath), { timeout: 15000 });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  }
  const actualPath = new URL(page.url()).pathname;
  const navigationPassed = results.count > 0 && pathMatches(actualPath, expectedPath);

  return {
    key: 'search',
    passed:
      suggestions.count >= 5 &&
      suggestions.deadLinks.length === 0 &&
      results.count >= 1 &&
      results.deadLinks.length === 0 &&
      Boolean(searchResponse) &&
      closedByEscape &&
      navigationPassed,
    query: 'MFG',
    count: results.count,
    apiResultCount: searchPayload?.data?.items?.length ?? null,
    searchStatus: searchResponse?.status() ?? null,
    suggestions,
    results,
    closedByEscape,
    expectedPath,
    actualPath,
    navigationPassed
  };
}

async function auditQuickCreate(page, viewportName, screenshots) {
  await gotoApp(page, '/app/overview');
  const button = page.locator('button[aria-label="打开快捷创建"]').first();
  const visibleButton = await button.isVisible().catch(() => false);
  if (!visibleButton) {
    return {
      key: 'quickCreate',
      passed: false,
      reason: 'trigger-not-visible'
    };
  }

  await button.click();
  await page.waitForSelector('.quick-create-popover a', { state: 'visible', timeout: 8000 });
  await page.waitForTimeout(180);
  const links = await collectPopoverLinks(page, '.quick-create-popover');
  const layout = await collectPopoverLayout(page, '.quick-create-popover');
  const screenshot = `${viewportName}-03-quick-create.png`;
  await page.screenshot({ path: path.join(outDir, screenshot), fullPage: false });
  screenshots.push(screenshot);

  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.quick-create-popover'), null, { timeout: 6000 });
  const closedByEscape = await page.locator('.quick-create-popover').count().then(count => count === 0);

  await button.click();
  await page.waitForSelector('.quick-create-popover a', { state: 'visible', timeout: 8000 });
  const expectedPath = normalizeExpectedPath(links.firstHref);
  await page.locator('.quick-create-popover a').first().click();
  await page.waitForURL(url => pathMatches(url.pathname, expectedPath), { timeout: 15000 });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  const actualPath = new URL(page.url()).pathname;
  const navigationPassed = pathMatches(actualPath, expectedPath);

  return {
    key: 'quickCreate',
    passed:
      links.count >= 5 &&
      links.deadLinks.length === 0 &&
      layout.inViewport &&
      layout.badRects.length === 0 &&
      layout.overflowingNoWrapText.length === 0 &&
      closedByEscape &&
      navigationPassed,
    count: links.count,
    links,
    layout,
    closedByEscape,
    expectedPath,
    actualPath,
    navigationPassed
  };
}

async function auditSync(page, viewportName) {
  await gotoApp(page, '/app/overview');
  const button = page.locator('button[aria-label="同步运营数据"]').first();
  const visibleButton = await button.isVisible().catch(() => false);
  if (!visibleButton) {
    return {
      key: 'sync',
      passed: viewportName === 'mobile',
      skipped: true,
      reason: 'responsive-hidden'
    };
  }

  const commandResponse = page.waitForResponse(response =>
    response.url().includes('/api/v1/manufacturing/command-center') && response.status() < 400,
  { timeout: 9000 }).catch(() => null);
  const healthResponse = page.waitForResponse(response =>
    response.url().includes('/api/v1/health') && response.status() < 400,
  { timeout: 9000 }).catch(() => null);

  await button.click();
  const [command, health] = await Promise.all([commandResponse, healthResponse]);
  await page.waitForSelector('.p-toast-message', { state: 'visible', timeout: 6000 }).catch(() => null);
  const toastVisible = await page.locator('.p-toast-message').first().isVisible().catch(() => false);

  return {
    key: 'sync',
    passed: Boolean(command && health && toastVisible),
    commandStatus: command?.status() ?? null,
    healthStatus: health?.status() ?? null,
    toastVisible
  };
}

async function auditNavigation(page, target, viewportName) {
  await gotoApp(page, '/app/overview');
  const trigger = page.locator(target.selector).first();
  const visibleTrigger = await trigger.isVisible().catch(() => false);
  if (!visibleTrigger) {
    return {
      key: target.key,
      label: target.label,
      passed: false,
      viewport: viewportName,
      reason: 'trigger-not-visible',
      expectedPath: target.expectedPath
    };
  }

  await trigger.click();
  await page.waitForURL(url => pathMatches(url.pathname, target.expectedPath), { timeout: 15000 });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => null);
  const actualPath = new URL(page.url()).pathname;

  return {
    key: target.key,
    label: target.label,
    passed: pathMatches(actualPath, target.expectedPath),
    expectedPath: target.expectedPath,
    actualPath
  };
}

async function collectTopbarBaseline(page, viewportName) {
  return page.evaluate(({ name, expectedApiBaseUrl }) => {
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
    const isVisible = selector => {
      const element = document.querySelector(selector);
      return Boolean(element && visible(element));
    };
    const topbar = document.querySelector('.atlas-topbar');
    const topbarRect = topbar?.getBoundingClientRect();
    const visibleActionCount = [...document.querySelectorAll('.atlas-actions a, .atlas-actions button')].filter(visible).length;
    const overflowingNoWrapText = [...document.querySelectorAll('.atlas-topbar button, .atlas-topbar a, .atlas-topbar strong, .atlas-topbar em, .atlas-topbar span')]
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
    const badRects = [...document.querySelectorAll('.atlas-topbar, .atlas-topbar a, .atlas-topbar button, .atlas-search')]
      .filter(visible)
      .map(element => ({ element, box: element.getBoundingClientRect() }))
      .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2 || box.top < -2)
      .slice(0, 12)
      .map(({ element, box }) => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
        left: Math.round(box.left),
        right: Math.round(box.right),
        width: Math.round(box.width)
      }));
    const requiredDesktop = name === 'desktop'
      ? isVisible('.atlas-search') && isVisible('.service-health-chip') && isVisible('a[aria-label="打开经营分析台"]')
      : true;

    return {
      viewport: name,
      passed:
        Boolean(topbar && visible(topbar)) &&
        requiredDesktop &&
        visibleActionCount >= (name === 'desktop' ? 9 : 6) &&
        document.documentElement.scrollWidth - window.innerWidth <= 3 &&
        overflowingNoWrapText.length === 0 &&
        badRects.length === 0 &&
        window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl === expectedApiBaseUrl,
      topbarRect: topbarRect
        ? {
            x: Math.round(topbarRect.x),
            y: Math.round(topbarRect.y),
            width: Math.round(topbarRect.width),
            height: Math.round(topbarRect.height),
            right: Math.round(topbarRect.right)
          }
        : null,
      visibleActionCount,
      visible: {
        brand: isVisible('.atlas-brand'),
        location: isVisible('.atlas-location'),
        search: isVisible('.atlas-search'),
        serviceHealth: isVisible('.service-health-chip'),
        analytics: isVisible('a[aria-label="打开经营分析台"], .ai-topbar-action'),
        settings: isVisible('a[aria-label="全局设置"]'),
        create: isVisible('button[aria-label="打开快捷创建"]'),
        sync: isVisible('button[aria-label="同步运营数据"]'),
        notifications: isVisible('a[aria-label="通知中心"]'),
        profile: isVisible('a[aria-label="个人工作台"]'),
        more: isVisible('button[aria-label="更多模块"]')
      },
      bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
      overflowingNoWrapText,
      badRects,
      apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null
    };
  }, { name: viewportName, expectedApiBaseUrl: expectedAuditApiBaseUrl });
}

async function collectPopoverLinks(page, selector) {
  return page.evaluate(popoverSelector => {
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
    const links = [...document.querySelectorAll(`${popoverSelector} a`)]
      .filter(visible)
      .map((element, index) => {
        const href = element.getAttribute('href') || '';
        const text = element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 140) || '';
        return { index, href, text, isDead: !href || href === '#' || href.startsWith('javascript:') || !href.startsWith('/app/') };
      });
    return {
      count: links.length,
      firstHref: links[0]?.href || '',
      firstText: links[0]?.text || '',
      deadLinks: links.filter(item => item.isDead),
      sample: links.slice(0, 8)
    };
  }, selector);
}

async function collectPopoverLayout(page, selector) {
  return page.evaluate(popoverSelector => {
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
    const popover = document.querySelector(popoverSelector);
    const popoverBox = popover?.getBoundingClientRect();
    const overflowingNoWrapText = [...document.querySelectorAll(`${popoverSelector} a, ${popoverSelector} strong, ${popoverSelector} em, ${popoverSelector} span`)]
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
    const badRects = [...document.querySelectorAll(`${popoverSelector}, ${popoverSelector} a, ${popoverSelector} button`)]
      .filter(visible)
      .map(element => ({ element, box: element.getBoundingClientRect() }))
      .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2 || box.top < -2)
      .slice(0, 12)
      .map(({ element, box }) => ({
        tag: element.tagName.toLowerCase(),
        className: [...element.classList].slice(0, 4).join('.'),
        text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 90),
        left: Math.round(box.left),
        right: Math.round(box.right),
        width: Math.round(box.width)
      }));
    return {
      rect: popoverBox
        ? {
            x: Math.round(popoverBox.x),
            y: Math.round(popoverBox.y),
            width: Math.round(popoverBox.width),
            height: Math.round(popoverBox.height),
            right: Math.round(popoverBox.right),
            bottom: Math.round(popoverBox.bottom)
          }
        : null,
      inViewport: Boolean(
        popoverBox &&
        popoverBox.left >= -1 &&
        popoverBox.top >= -1 &&
        popoverBox.right <= window.innerWidth + 2 &&
        popoverBox.bottom <= window.innerHeight + 2
      ),
      overflowingNoWrapText,
      badRects
    };
  }, selector);
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

function normalizeExpectedPath(href) {
  return new URL(href || '/app/overview', baseUrl).pathname;
}

function pathMatches(actualPath, expectedPath) {
  return actualPath === expectedPath || actualPath.startsWith(`${expectedPath}/`);
}
