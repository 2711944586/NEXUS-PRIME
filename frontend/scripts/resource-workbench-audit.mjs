import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `resource-workbench-audit-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const coreRoutes = [
  '/app/inventory/products',
  '/app/inventory/stock',
  '/app/procurement/orders',
  '/app/sales/orders',
  '/app/customers',
  '/app/finance/receivables',
  '/app/stocktakes',
  '/app/reports'
];

const extendedRoutes = [
  '/app/inventory/replenishment',
  '/app/finance/credits',
  '/app/files',
  '/app/content/articles',
  '/app/system/users',
  '/app/system/audit',
  '/app/notifications',
  '/app/ai'
];

const routes = process.env.NEXUS_AUDIT_FULL_WORKBENCH === '1'
  ? [...coreRoutes, ...extendedRoutes]
  : coreRoutes;

const allViewports = [
  { name: 'desktop', width: 1440, height: 950 },
  { name: 'mobile', width: 390, height: 844 }
];
const viewports = process.env.NEXUS_AUDIT_WORKBENCH_VIEWPORTS === 'all'
  ? allViewports
  : [allViewports[0]];

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
    await page.waitForSelector('.module-workbench', { state: 'visible', timeout: 15000 });
    await page.waitForTimeout(550);

    const baseline = await collectWorkbench(page);
    const interactions = [];
    const deepInteractions = viewport.name === 'desktop' || process.env.NEXUS_AUDIT_MOBILE_DEEP_WORKBENCH === '1';

    interactions.push(await safeAudit('modeWorkflow', () => auditMode(page, '流程', '.workflow-stack, .workflow-actions')));
    interactions.push(await safeAudit('modeInspect', () => auditMode(page, '查看', '.field-grid, .workbench-empty')));

    if (deepInteractions && baseline.canCreate) {
      interactions.push(await safeAudit('createValidation', () => auditCreateValidation(page)));
    }
    if (deepInteractions && baseline.rows > 0 && baseline.canEdit) {
      interactions.push(await safeAudit('editMode', () => auditEditMode(page)));
    }
    if (deepInteractions && baseline.rows > 0) {
      interactions.push(await safeAudit('rowSelection', () => auditRowSelection(page)));
    }
    interactions.push(await safeAudit('query', () => auditQuery(page)));

    const after = await collectWorkbench(page);
    const failures = evaluateWorkbench(route, baseline, after, interactions);
    const slug = `${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[/:]/g, '-')}`;
    if (failures.length) {
      await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
    }

    results.push({
      viewport: viewport.name,
      route,
      baseline,
      deepInteractions,
      interactions,
      after,
      failures
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
const failed = [
  ...pageResults.filter(result => result.failures.length),
  ...networkResults.filter(result => result.consoleErrors.length || result.failedRequests.length || result.badResponses.length)
];

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
    title: result.baseline.title,
    rows: result.baseline.rows,
    controls: result.baseline.controls,
    modes: result.baseline.modes,
    canCreate: result.baseline.canCreate,
    canEdit: result.baseline.canEdit,
    canDelete: result.baseline.canDelete,
    deepInteractions: result.deepInteractions,
    workflowActions: result.after.workflowActions,
    interactions: result.interactions.map(item => ({ key: item.key, passed: item.passed, skipped: item.skipped || false })),
    failures: result.failures
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

async function auditQuery(page) {
  const searchInput = page.locator('.workbench-search input').first();
  const queryButton = page.getByRole('button', { name: '查询当前模块' }).first();
  if (!(await searchInput.isVisible().catch(() => false))) {
    return { key: 'query', passed: false, reason: 'search_input_missing' };
  }
  await searchInput.fill('MFG');
  await queryButton.click();
  await page.waitForTimeout(450);
  const summary = await page.locator('.workbench-result-bar, .workbench-empty-state').first().textContent().catch(() => '');
  await searchInput.fill('');
  await queryButton.click();
  await page.waitForTimeout(350);
  return {
    key: 'query',
    passed: Boolean(summary),
    summary: summary?.trim().replace(/\s+/g, ' ').slice(0, 120) || ''
  };
}

async function auditMode(page, label, expectedSelector) {
  const button = page.locator('.mode-tabs button').filter({ hasText: label }).first();
  await button.click();
  await page.waitForSelector(expectedSelector, { state: 'visible', timeout: 8000 });
  const key = label === '流程' ? 'modeWorkflow' : label === '查看' ? 'modeInspect' : `mode${label}`;
  return {
    key,
    passed: true,
    label
  };
}

async function auditCreateValidation(page) {
  const createButton = page.getByRole('button', { name: '新建当前模块记录' }).first();
  await createButton.click();
  await page.waitForSelector('.workbench-form', { state: 'visible', timeout: 8000 });
  const fields = await page.locator('.workbench-form label').count();
  const validationState = await page.evaluate(() => {
    const fields = [...document.querySelectorAll('.workbench-form input, .workbench-form select, .workbench-form textarea')];
    const required = fields.filter(field => field.hasAttribute('required'));
    const invalidRequired = required.filter(field => field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement
      ? !field.checkValidity()
      : false);
    return {
      required: required.length,
      invalidRequired: invalidRequired.length
    };
  });
  let validationErrors = 0;
  if (validationState.invalidRequired > 0) {
    await page.locator('.workbench-form button[type="submit"]').first().click();
    await page.waitForTimeout(350);
    validationErrors = await page.locator('.field-error').count();
  }
  const cancelButton = page.locator('.workbench-form button').filter({ hasText: '取消' }).first();
  if (await cancelButton.isVisible().catch(() => false)) {
    await cancelButton.click();
  }
  return {
    key: 'createValidation',
    passed: fields > 0 && (validationState.invalidRequired === 0 || validationErrors > 0),
    fields,
    required: validationState.required,
    invalidRequired: validationState.invalidRequired,
    validationErrors,
    skippedSubmit: validationState.invalidRequired === 0
  };
}

async function auditEditMode(page) {
  await page.locator('.workbench-record .record-main').first().click();
  await page.locator('.workbench-record-actions button').filter({ hasText: '编辑' }).first().click();
  await page.waitForSelector('.workbench-form', { state: 'visible', timeout: 8000 });
  const fields = await page.locator('.workbench-form label').count();
  const title = await page.locator('.workbench-inspector .workbench-title strong').first().textContent().catch(() => '');
  const cancelButton = page.locator('.workbench-form button').filter({ hasText: '取消' }).first();
  if (await cancelButton.isVisible().catch(() => false)) {
    await cancelButton.click();
  }
  return {
    key: 'editMode',
    passed: fields > 0 && Boolean(title?.trim()),
    fields,
    title: title?.trim() || ''
  };
}

async function auditRowSelection(page) {
  const first = page.locator('.workbench-record .record-main').first();
  await first.click();
  await page.waitForTimeout(250);
  const activeRows = await page.locator('.workbench-record.active').count();
  const inspectText = await page.locator('.workbench-inspector').first().textContent().catch(() => '');
  return {
    key: 'rowSelection',
    passed: activeRows >= 1 && Boolean(inspectText?.trim()),
    activeRows,
    inspectText: inspectText?.trim().replace(/\s+/g, ' ').slice(0, 160) || ''
  };
}

async function collectWorkbench(page) {
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
    const text = selector => [...document.querySelectorAll(selector)]
      .filter(visible)
      .map(element => element.textContent?.trim().replace(/\s+/g, ' '))
      .filter(Boolean);
    const buttons = text('.module-workbench button');
    const links = [...document.querySelectorAll('.module-workbench a[href]')]
      .filter(visible)
      .map(element => ({ href: element.getAttribute('href') || '', text: element.textContent?.trim().replace(/\s+/g, ' ') || '' }));
    const actionButtons = text('.workbench-record-actions button, .workbench-record-actions a');
    const modes = text('.mode-tabs button');
    const rows = [...document.querySelectorAll('.workbench-record')].filter(visible).length;
    const disabledEdit = [...document.querySelectorAll('.workbench-record-actions button')]
      .filter(visible)
      .filter(element => element.textContent?.includes('编辑') && element.hasAttribute('disabled'))
      .length;
    const disabledDelete = [...document.querySelectorAll('.workbench-record-actions button')]
      .filter(visible)
      .filter(element => element.textContent?.includes('删除') && element.hasAttribute('disabled'))
      .length;

    return {
      path: location.pathname,
      apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null,
      title: document.querySelector('.module-workbench .workbench-title strong')?.textContent?.trim() || '',
      summary: document.querySelector('.module-workbench .workbench-title p')?.textContent?.trim() || '',
      controls: {
        search: Boolean(document.querySelector('.workbench-search input')),
        query: buttons.some(item => item.includes('查询')),
        refresh: Boolean(document.querySelector('button[aria-label="刷新当前模块"]')),
        create: Boolean(document.querySelector('button[aria-label="新建当前模块记录"]')),
        export: buttons.some(item => item.includes('导出'))
      },
      capabilityCards: text('.workbench-capability').length,
      rows,
      actionButtons,
      modes,
      workflowSteps: text('.workflow-step').length,
      workflowActions: text('.workflow-action').length,
      formFields: text('.workbench-form label').length,
      canCreate: buttons.some(item => item.includes('新建')) && !document.querySelector('button[aria-label="新建当前模块记录"]')?.hasAttribute('disabled'),
      canEdit: rows > 0 && actionButtons.some(item => item.includes('编辑')) && disabledEdit < rows,
      canDelete: rows > 0 && actionButtons.some(item => item.includes('删除')) && disabledDelete < rows,
      hasCopy: actionButtons.some(item => item.includes('复制')),
      hasView: actionButtons.some(item => item.includes('查看')),
      deadLinks: links.filter(item => !item.href || item.href === '#' || item.href.startsWith('javascript:')),
      bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth
    };
  });
}

function evaluateWorkbench(route, baseline, after, interactions) {
  const failures = [];
  const workflowPassed = interactions.some(item => item.key === 'modeWorkflow' && item.passed);
  if (!hasExpectedAuditApiBaseUrl(baseline.apiBaseUrl)) {
    failures.push('runtime_config_wrong');
  }
  if (!baseline.title) {
    failures.push('title_missing');
  }
  if (baseline.capabilityCards < 4) {
    failures.push('capability_cards_missing');
  }
  for (const [key, value] of Object.entries(baseline.controls)) {
    if (key !== 'export' && !value) {
      failures.push(`${key}_control_missing`);
    }
  }
  for (const mode of ['查看', '编辑', '流程']) {
    if (!baseline.modes.includes(mode)) {
      failures.push(`mode_${mode}_missing`);
    }
  }
  if (baseline.rows > 0) {
    if (!baseline.hasView) failures.push('view_action_missing');
    if (!baseline.hasCopy) failures.push('copy_action_missing');
    if (!baseline.actionButtons.some(item => item.includes('编辑'))) failures.push('edit_action_missing');
    if (!baseline.actionButtons.some(item => item.includes('删除'))) failures.push('delete_action_missing');
  }
  if (!workflowPassed && after.workflowSteps < 1 && after.workflowActions < 1) {
    failures.push('workflow_panel_empty');
  }
  if (baseline.deadLinks.length) {
    failures.push('dead_workbench_links');
  }
  if (baseline.bodyOverflowX > 2) {
    failures.push('horizontal_overflow');
  }
  for (const interaction of interactions) {
    if (!interaction.passed && !interaction.skipped) {
      failures.push(`${interaction.key}_failed`);
    }
  }
  return failures;
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
