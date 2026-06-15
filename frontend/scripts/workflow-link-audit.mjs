import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `workflow-link-audit-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const coreRoutes = [
  '/app/overview',
  '/app/inventory/stock',
  '/app/procurement/orders',
  '/app/sales/orders',
  '/app/finance/receivables',
  '/app/reports'
];
const extendedRoutes = [
  '/app/quality',
  '/app/integrations'
];
const routes = process.env.NEXUS_AUDIT_WORKFLOW_ROUTES === 'core'
  ? coreRoutes
  : [...coreRoutes, ...extendedRoutes];

const allViewports = [
  { name: 'desktop', width: 1440, height: 950 },
  { name: 'mobile', width: 390, height: 844 }
];
const viewports = process.env.NEXUS_AUDIT_WORKFLOW_VIEWPORTS === 'desktop'
  ? [allViewports[0]]
  : allViewports;

const linkGroups = [
  { key: 'pageEvidence', label: '页面现场', selector: '.page-evidence-grid a', required: true, min: 3 },
  { key: 'fieldEvidence', label: '现场证据', selector: '.field-evidence-grid a', required: true, min: 3 },
  { key: 'handoff', label: '当班交接', selector: '.shift-handoff-list a', required: true, min: 3 },
  { key: 'workflowSignal', label: '执行信号', selector: '.workflow-signal-list a', required: false, min: 0 },
  { key: 'workflowRail', label: '闭环节点', selector: '.workflow-step-rail a', required: false, min: 0 },
  { key: 'nextAction', label: '下一步', selector: '.context-action', required: false, min: 0 }
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
    await page.waitForTimeout(650);

    const snapshot = await collectWorkflowLinks(page);
    const clicks = [];
    const clickTargets = pickClickTargets(snapshot.groups);

    for (const target of clickTargets) {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
      await page.waitForTimeout(250);
      const clickResult = await clickWorkflowTarget(page, target);
      clicks.push(clickResult);
      if (!clickResult.passed) {
        const slug = `${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[/:]/g, '-') || 'home'}-${target.group}`;
        await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
      }
    }

    results.push({
      viewport: viewport.name,
      route,
      ...snapshot,
      clicks
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
  result.totalWorkflowLinks < 9 ||
  result.deadLinks.length ||
  result.requiredGroupFailures.length ||
  result.clicks.some(click => !click.passed) ||
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
    totalWorkflowLinks: result.totalWorkflowLinks,
    deadLinks: result.deadLinks.length,
    requiredGroupFailures: result.requiredGroupFailures.length,
    clicked: result.clicks.length,
    clickFailures: result.clicks.filter(click => !click.passed).length,
    groups: Object.fromEntries(Object.entries(result.groups).map(([key, value]) => [key, value.length]))
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

async function collectWorkflowLinks(page) {
  return page.evaluate(groups => {
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
    const byGroup = {};
    const deadLinks = [];

    for (const group of groups) {
      const links = [...document.querySelectorAll(group.selector)]
        .filter(visible)
        .map((element, index) => {
          const href = element.getAttribute('href') || '';
          const text = element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 120) || '';
          const isDead = !href || href === '#' || href.startsWith('javascript:') || !href.startsWith('/app/');
          const item = { group: group.key, label: group.label, selector: group.selector, index, href, text, isDead };
          if (isDead) {
            deadLinks.push(item);
          }
          return item;
        });
      byGroup[group.key] = links;
    }

    const requiredGroupFailures = groups
      .filter(group => group.required)
      .map(group => ({ group: group.key, label: group.label, expected: group.min, actual: byGroup[group.key]?.length ?? 0 }))
      .filter(group => group.actual < group.expected);

    return {
      path: location.pathname,
      title: document.title,
      groups: byGroup,
      totalWorkflowLinks: Object.values(byGroup).reduce((total, items) => total + items.length, 0),
      deadLinks,
      requiredGroupFailures,
      apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null
    };
  }, linkGroups);
}

function pickClickTargets(groups) {
  return linkGroups
    .map(group => groups[group.key]?.find(item => !item.isDead))
    .filter(Boolean)
    .slice(0, 4);
}

async function clickWorkflowTarget(page, target) {
  const marked = await page.evaluate(targetData => {
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
    document.querySelectorAll('[data-workflow-audit-target]').forEach(element => element.removeAttribute('data-workflow-audit-target'));
    const element = [...document.querySelectorAll(targetData.selector)]
      .filter(visible)
      .find(item =>
        item.getAttribute('href') === targetData.href &&
        (item.textContent?.trim().replace(/\s+/g, ' ').slice(0, 120) || '') === targetData.text
      );
    if (!element) {
      return false;
    }
    element.setAttribute('data-workflow-audit-target', 'true');
    return true;
  }, target);

  if (!marked) {
    return {
      ...target,
      passed: false,
      reason: 'target_not_found_after_reload',
      actualPath: new URL(page.url()).pathname
    };
  }

  await page.locator('[data-workflow-audit-target="true"]').first()
    .evaluate(element => {
      element.scrollIntoView({ block: 'center', inline: 'center' });
      element.click();
    });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 }).catch(() => null);
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => null);
  await page.waitForTimeout(250);

  const actualPath = new URL(page.url()).pathname;
  const expectedPath = new URL(target.href, baseUrl).pathname;
  const passed = actualPath === expectedPath || actualPath.startsWith(`${expectedPath}/`);
  return {
    ...target,
    expectedPath,
    actualPath,
    passed,
    reason: passed ? '' : 'unexpected_navigation'
  };
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
