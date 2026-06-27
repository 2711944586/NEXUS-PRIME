import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const docsDir = path.resolve(process.cwd(), '..', 'docs', 'images', 'final');
const pagesDir = path.join(docsDir, 'pages');
const onlyExtras = process.env.NEXUS_CAPTURE_ONLY_EXTRAS === '1';
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const desktop = { name: 'desktop', width: 1440, height: 950 };
const mobile = { name: 'mobile', width: 390, height: 844, isMobile: true };
const routeCaptureMatrix = process.env.NEXUS_CAPTURE_ALL_THEMES === '1'
  ? [
      { theme: 'light-luxury', viewport: desktop },
      { theme: 'light-luxury', viewport: mobile },
      { theme: 'dark-cockpit', viewport: desktop },
      { theme: 'dark-cockpit', viewport: mobile }
    ]
  : [
      { theme: 'light-luxury', viewport: desktop },
      { theme: 'light-luxury', viewport: mobile }
    ];

const appRoutes = [
  ['overview', '/app/overview', '运营控制塔'],
  ['metrics', '/app/metrics', '经营指标中心'],
  ['tasks', '/app/tasks', '任务异常中心'],
  ['inventory-products', '/app/inventory/products', '物料库存图谱'],
  ['inventory-stock', '/app/inventory/stock', '仓配流向图'],
  ['inventory-replenishment', '/app/inventory/replenishment', '采购补货建议'],
  ['sales-orders', '/app/sales/orders', '客户窗口与发货调度台'],
  ['procurement-orders', '/app/procurement/orders', '采购协同控制台'],
  ['suppliers-performance', '/app/suppliers/performance', '供应商协同'],
  ['dispatch', '/app/dispatch', '仓配调度中心'],
  ['data-quality', '/app/data-quality', '数据质量中心'],
  ['quality', '/app/quality', '质量检验中心'],
  ['customers', '/app/customers', '客户经营中心'],
  ['capacity', '/app/capacity', '产能计划中心'],
  ['maintenance', '/app/maintenance', '设备维护中心'],
  ['contracts', '/app/contracts', '合同回款中心'],
  ['service', '/app/service', '售后服务中心'],
  ['rules', '/app/rules', '规则引擎中心'],
  ['integrations', '/app/integrations', '集成监控中心'],
  ['budget', '/app/budget', '预算成本中心'],
  ['mobile-terminal', '/app/mobile-terminal', '移动扫码终端'],
  ['finance-receivables', '/app/finance/receivables', '账龄风险墙'],
  ['finance-credits', '/app/finance/credits', '客户信用中心'],
  ['stocktakes', '/app/stocktakes', '库存盘点中心'],
  ['reports', '/app/reports', '报表工作室'],
  ['files', '/app/files', '文件资料库'],
  ['content-articles', '/app/content/articles', '公告与知识库'],
  ['system-users', '/app/system/users', '系统安全中心'],
  ['system-audit', '/app/system/audit', '审计日志'],
  ['notifications', '/app/notifications', '任务通知中心'],
  ['ai', '/app/ai', '经营分析台'],
  ['profile', '/app/profile', '个人中心'],
  ['settings', '/app/settings', '控制中心']
];

const namedCaptures = [
  { file: 'after-login.png', route: '/app/overview', theme: 'dark-cockpit', viewport: desktop },
  { file: 'overview.png', route: '/app/overview', theme: 'dark-cockpit', viewport: desktop },
  { file: 'command.png', route: '/app/overview', theme: 'dark-cockpit', viewport: desktop },
  { file: 'ai.png', route: '/app/ai', theme: 'dark-cockpit', viewport: desktop },
  { file: 'ai-fix.png', route: '/app/ai', theme: 'light-luxury', viewport: desktop },
  { file: 'settings.png', route: '/app/settings', theme: 'light-luxury', viewport: desktop },
  { file: 'profile.png', route: '/app/profile', theme: 'light-luxury', viewport: desktop },
  { file: 'files.png', route: '/app/files', theme: 'light-luxury', viewport: desktop },
  { file: 'reports.png', route: '/app/reports', theme: 'dark-cockpit', viewport: desktop },
  { file: 'mobile.png', route: '/app/mobile-terminal', theme: 'light-luxury', viewport: mobile },
  { file: 'final-dark-overview.png', route: '/app/overview', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-procurement.png', route: '/app/procurement/orders', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-fulfillment.png', route: '/app/sales/orders', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-receivables.png', route: '/app/finance/receivables', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-stocktakes.png', route: '/app/stocktakes', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-reports.png', route: '/app/reports', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-integrations.png', route: '/app/integrations', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-dark-supplier-collaboration.png', route: '/app/suppliers/performance', theme: 'dark-cockpit', viewport: desktop },
  { file: 'final-light-overview.png', route: '/app/overview', theme: 'light-luxury', viewport: desktop },
  { file: 'final-light-procurement.png', route: '/app/procurement/orders', theme: 'light-luxury', viewport: desktop },
  { file: 'final-light-receivables.png', route: '/app/finance/receivables', theme: 'light-luxury', viewport: desktop },
  { file: 'final-light-reports.png', route: '/app/reports', theme: 'light-luxury', viewport: desktop },
  { file: 'final-light-integrations.png', route: '/app/integrations', theme: 'light-luxury', viewport: desktop },
  { file: 'final-mobile-light-overview.png', route: '/app/overview', theme: 'light-luxury', viewport: mobile },
  { file: 'final-mobile-dark-stocktakes.png', route: '/app/stocktakes', theme: 'dark-cockpit', viewport: mobile },
  { file: 'final-mobile-supplier-collaboration.png', route: '/app/suppliers/performance', theme: 'light-luxury', viewport: mobile }
];

await mkdir(docsDir, { recursive: true });
await mkdir(pagesDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const manifest = [];

try {
  if (!onlyExtras) {
    await captureGuestPages();

    for (const item of routeCaptureMatrix) {
      const context = await newContext(item.viewport, item.theme);
      const page = await context.newPage();
      await login(page);
      for (const [slug, route, title] of appRoutes) {
        const file = `${item.viewport.name}-${item.theme}-${slug}.png`;
        await captureRoute(page, route, path.join(pagesDir, file));
        manifest.push({ file: `pages/${file}`, route, title, viewport: item.viewport.name, theme: item.theme });
      }
      await context.close();
    }

    for (const item of namedCaptures) {
      const context = await newContext(item.viewport, item.theme);
      const page = await context.newPage();
      await login(page);
      await captureRoute(page, item.route, path.join(docsDir, item.file));
      await context.close();
    }
  }

  await writeScreenshotManifest(manifest);
  await captureFileDetail().catch(error => console.warn(`file-detail skipped: ${error.message}`));
  await captureDockPanel().catch(error => console.warn(`dock skipped: ${error.message}`));
  console.log(JSON.stringify({ outDir: docsDir, pages: manifest.length || routeCaptureMatrix.length * appRoutes.length, named: namedCaptures.length + 5 }, null, 2));
} finally {
  await browser.close();
}

async function captureGuestPages() {
  const context = await newContext(desktop, 'light-luxury');
  const page = await context.newPage();
  await captureRoute(page, '/', path.join(docsDir, 'entry.png'), '.nexus-motion-entry');
  await captureRoute(page, '/auth/login', path.join(docsDir, 'login.png'), '.login-screen');
  await captureRoute(page, '/auth/login?mode=register', path.join(docsDir, 'register.png'), '.login-screen');
  await captureRoute(page, '/auth/register-policy', path.join(pagesDir, 'desktop-light-luxury-register-policy.png'), '.policy-screen');
  await context.close();
}

async function captureFileDetail() {
  const context = await newContext(desktop, 'light-luxury');
  const page = await context.newPage();
  await login(page);
  await page.goto(`${baseUrl}/app/files`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(900);
  const detailLinks = page.locator('#main-content a[href*="/app/files/"]');
  const href = await detailLinks.count() ? await detailLinks.first().getAttribute('href') : null;
  await captureRoute(page, href || '/app/files/1', path.join(docsDir, 'file-detail.png'), '.detail-page, .atlas-shell');
  await context.close();
}

async function captureDockPanel() {
  const context = await newContext(desktop, 'dark-cockpit');
  const page = await context.newPage();
  await login(page);
  await page.goto(`${baseUrl}/app/overview`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(900);
  const launcher = page.locator('.atlas-dock-more, button[aria-label="更多模块"]').first();
  await launcher.click({ timeout: 5000 });
  await page.waitForSelector('.module-panel', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(docsDir, 'dock.png'), fullPage: false });
  await context.close();
}

async function writeScreenshotManifest(captured) {
  const entries = captured.length ? captured : routeCaptureMatrix.flatMap(item =>
    appRoutes.map(([slug, route, title]) => ({
      file: `pages/${item.viewport.name}-${item.theme}-${slug}.png`,
      route,
      title,
      viewport: item.viewport.name,
      theme: item.theme
    }))
  );
  await writeFile(path.join(pagesDir, 'manifest.json'), JSON.stringify(entries, null, 2), 'utf-8');
}

async function newContext(viewport, theme) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    isMobile: Boolean(viewport.isMobile)
  });
  await context.addInitScript(({ themeMode }) => {
    const preferences = {
      theme: themeMode,
      density: 'compact',
      charts_motion: 'reduced',
      dock_labels: 'hover',
      context_panel: 'visible',
      default_workspace: '/app/overview'
    };
    localStorage.setItem('nexus_theme_mode_v2', themeMode);
    localStorage.setItem('nexus_ui_preferences_v1', JSON.stringify(preferences));
  }, { themeMode: theme });
  return context;
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}

async function captureRoute(page, route, filePath, selector = '.atlas-shell') {
  const url = route.startsWith('http') ? route : `${baseUrl}${route}`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector(selector, { state: 'visible', timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 2500 }).catch(() => undefined);
  await page.waitForTimeout(350);
  await page.screenshot({ path: filePath, fullPage: false });
}
