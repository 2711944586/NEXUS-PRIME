import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { hasExpectedAuditApiBaseUrl } from './audit-config.mjs';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `theme-contrast-audit-${Date.now()}`);
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const themes = ['light-luxury', 'dark-cockpit'];
const routes = [
  '/app/overview',
  '/app/inventory/stock',
  '/app/procurement/orders',
  '/app/sales/orders',
  '/app/finance/receivables',
  '/app/reports'
];
const viewports = [
  { name: 'desktop', width: 1440, height: 950 },
  { name: 'mobile', width: 390, height: 844 }
];

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const results = [];

for (const theme of themes) {
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

    await login(page, theme);

    for (const route of routes) {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
      await page.waitForTimeout(600);
      await applyTheme(page, theme);
      await page.waitForTimeout(150);

      const audit = await page.evaluate(() => {
        const selectors = [
          'h1',
          'h2',
          'h3',
          'p',
          'small',
          'strong',
          'em',
          'button',
          'a[href]',
          'label',
          'input',
          'textarea',
          'select',
          '.p-button',
          '.p-tag',
          '.p-datatable td',
          '.p-datatable th',
          '.atlas-kicker',
          '.entry-kicker',
          '.context-title span',
          '.business-data-row',
          '.atlas-record-row',
          '.ledger-row',
          '.workbench-form',
          '.workbench-result-bar',
          '.workflow-step-rail a',
          '.field-evidence-grid a',
          '.shift-handoff-list a',
          '.report-template-list button'
        ].join(',');

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

        const parseColor = value => {
          if (!value || value === 'transparent') {
            return null;
          }
          const hexMatch = value.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
          if (hexMatch) {
            const raw = hexMatch[1].length === 3
              ? hexMatch[1].split('').map(char => `${char}${char}`).join('')
              : hexMatch[1];
            return {
              r: Number.parseInt(raw.slice(0, 2), 16),
              g: Number.parseInt(raw.slice(2, 4), 16),
              b: Number.parseInt(raw.slice(4, 6), 16),
              a: 1
            };
          }
          const rgbMatch = value.match(/rgba?\(([^)]+)\)/);
          if (rgbMatch) {
            const parts = rgbMatch[1].split(',').map(part => part.trim());
            const [r, g, b] = parts.slice(0, 3).map(Number);
            const alpha = parts[3] === undefined ? 1 : Number(parts[3]);
            if ([r, g, b, alpha].some(Number.isNaN) || alpha <= 0) {
              return null;
            }
            return { r, g, b, a: Math.min(alpha, 1) };
          }
          const srgbMatch = value.match(/color\(srgb\s+([^)]+)\)/);
          if (!srgbMatch) {
            return null;
          }
          const srgbParts = srgbMatch[1].split(/\s+/).filter(Boolean);
          const [r, g, b] = srgbParts.slice(0, 3).map(part => Math.round(Number(part) * 255));
          const slashIndex = srgbParts.indexOf('/');
          const alpha = slashIndex >= 0 ? Number(srgbParts[slashIndex + 1]) : 1;
          if ([r, g, b, alpha].some(Number.isNaN) || alpha <= 0) {
            return null;
          }
          return { r, g, b, a: Math.min(alpha, 1) };
        };

        const blend = (top, bottom) => {
          const alpha = top.a + bottom.a * (1 - top.a);
          if (alpha === 0) {
            return { r: 255, g: 255, b: 255, a: 1 };
          }
          return {
            r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / alpha,
            g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / alpha,
            b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / alpha,
            a: alpha
          };
        };

        const relativeLuminance = color => {
          const convert = channel => {
            const value = channel / 255;
            return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
          };
          return 0.2126 * convert(color.r) + 0.7152 * convert(color.g) + 0.0722 * convert(color.b);
        };

        const contrastRatio = (foreground, background) => {
          const fg = foreground.a < 1 ? blend(foreground, background) : foreground;
          const lighter = Math.max(relativeLuminance(fg), relativeLuminance(background));
          const darker = Math.min(relativeLuminance(fg), relativeLuminance(background));
          return (lighter + 0.05) / (darker + 0.05);
        };

        const nearestBackground = element => {
          const rootStyle = getComputedStyle(document.documentElement);
          let background = parseColor(rootStyle.getPropertyValue('--bg').trim()) ||
            parseColor(getComputedStyle(document.body).backgroundColor) ||
            parseColor(rootStyle.backgroundColor) ||
            { r: 255, g: 255, b: 255, a: 1 };

          const chain = [];
          for (let current = element; current && current !== document.documentElement; current = current.parentElement) {
            chain.unshift(current);
          }
          for (const current of chain) {
            const color = parseColor(getComputedStyle(current).backgroundColor);
            if (color) {
              background = color.a < 1 ? blend(color, background) : color;
            }
          }
          background.a = 1;
          return background;
        };
        const imageCardSelector = [
          '.field-evidence-grid a',
          '.page-evidence-grid a',
          '.mobile-field-evidence-strip a',
          '.context-workflow-photo',
          '.command-photo-strip a',
          '.command-evidence-rail figure',
          '.module-photo-rail a',
          '.command-visual-board figure',
          '.settings-visual-rail figure'
        ].join(',');
        const effectiveBackground = element => {
          const imageCard = element.closest(imageCardSelector);
          if (imageCard) {
            return { r: 14, g: 23, b: 20, a: 1 };
          }
          return nearestBackground(element);
        };

        const rgbaText = color => `rgba(${Math.round(color.r)}, ${Math.round(color.g)}, ${Math.round(color.b)}, ${Number(color.a.toFixed(3))})`;
        const hasDirectText = element => [...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
        const textSample = element => {
          if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
            return element.value || element.placeholder || element.getAttribute('aria-label') || '';
          }
          return element.textContent?.trim().replace(/\s+/g, ' ') || element.getAttribute('aria-label') || '';
        };

        const candidates = [...document.querySelectorAll(selectors)]
          .filter(visible)
          .filter(element => {
            const text = textSample(element);
            if (!text.length || element.closest('.module-photo-rail, .command-photo-strip')) {
              return false;
            }
            if (element.matches('.field-evidence-grid a, .page-evidence-grid a, .mobile-field-evidence-strip a, .context-workflow-photo, .command-evidence-rail figure, .command-visual-board figure, .settings-visual-rail figure')) {
              return false;
            }
            if (element.children.length && !hasDirectText(element) && !element.matches('button, .p-button, input, textarea, select')) {
              return false;
            }
            return true;
          });

        const checked = candidates.slice(0, 900).map(element => {
          const style = getComputedStyle(element);
          const disabled = element.matches(':disabled, [aria-disabled="true"]');
          const foreground = parseColor(style.color);
          const background = effectiveBackground(element);
          const box = element.getBoundingClientRect();
          const fontSize = Number.parseFloat(style.fontSize) || 14;
          const fontWeight = Number.parseInt(style.fontWeight, 10) || 400;
          const isLarge = fontSize >= 24 || (fontSize >= 18.67 && fontWeight >= 700);
          const ratio = foreground ? contrastRatio(foreground, background) : 0;
          const required = disabled ? 0 : isLarge ? 3 : 4.5;
          const sample = textSample(element).slice(0, 120);
          return {
            tag: element.tagName.toLowerCase(),
            className: [...element.classList].slice(0, 5).join('.'),
            sample,
            ratio: Number(ratio.toFixed(2)),
            required,
            color: foreground ? rgbaText(foreground) : style.color,
            background: rgbaText(background),
            fontSize: Number(fontSize.toFixed(1)),
            fontWeight,
            width: Math.round(box.width),
            height: Math.round(box.height),
            invisible: !foreground || foreground.a === 0,
            nowrapOverflow: !disabled && element.scrollWidth > element.clientWidth + 2 && style.whiteSpace === 'nowrap'
          };
        });

        const lowContrast = checked
          .filter(item => item.ratio < item.required)
          .slice(0, 40);
        const invisibleText = checked
          .filter(item => item.invisible)
          .slice(0, 20);
        const nowrapOverflow = checked
          .filter(item => item.nowrapOverflow)
          .slice(0, 20);
        const badRects = [...document.querySelectorAll('button, a[href], input, select, textarea, .atlas-panel, .module-workbench, .context-block')]
          .filter(visible)
          .map(element => ({ element, box: element.getBoundingClientRect() }))
          .filter(({ box }) => box.right > window.innerWidth + 2 || box.left < -2)
          .slice(0, 20)
          .map(({ element, box }) => ({
            tag: element.tagName.toLowerCase(),
            className: [...element.classList].slice(0, 5).join('.'),
            sample: textSample(element).slice(0, 120),
            left: Math.round(box.left),
            right: Math.round(box.right),
            width: Math.round(box.width)
          }));

        const ratios = checked.map(item => item.ratio).filter(Number.isFinite).sort((a, b) => a - b);
        return {
          path: location.pathname,
          title: document.title,
          viewportSize: { width: window.innerWidth, height: window.innerHeight },
          htmlClass: document.documentElement.className,
          dataTheme: document.documentElement.getAttribute('data-theme'),
          bodyOverflowX: document.documentElement.scrollWidth - window.innerWidth,
          checkedCount: checked.length,
          minContrast: ratios.length ? ratios[0] : 0,
          lowContrast,
          invisibleText,
          nowrapOverflow,
          badRects,
          hasRuntimeConfig: !!window.NEXUS_RUNTIME_CONFIG,
          apiBaseUrl: window.NEXUS_RUNTIME_CONFIG?.apiBaseUrl ?? null
        };
      });

      const failures = [
        ...audit.lowContrast.map(item => ({ type: 'low_contrast', ...item })),
        ...audit.invisibleText.map(item => ({ type: 'invisible_text', ...item })),
        ...audit.nowrapOverflow.map(item => ({ type: 'nowrap_overflow', ...item })),
        ...audit.badRects.map(item => ({ type: 'horizontal_overflow', ...item }))
      ];
      if (audit.bodyOverflowX > 3) {
        failures.push({ type: 'body_horizontal_overflow', amount: audit.bodyOverflowX });
      }
      if (audit.dataTheme !== theme || !audit.htmlClass.includes(theme)) {
        failures.push({ type: 'theme_not_applied', dataTheme: audit.dataTheme, htmlClass: audit.htmlClass });
      }
      if (!hasExpectedAuditApiBaseUrl(audit.apiBaseUrl)) {
        failures.push({ type: 'api_base', apiBaseUrl: audit.apiBaseUrl });
      }

      const slug = `${theme}-${viewport.name}-${route.replace(/^\/app\/?/, '').replace(/[/:]/g, '-') || 'home'}`;
      if (failures.length) {
        await page.screenshot({ path: path.join(outDir, `${slug}.png`), fullPage: false });
      }
      results.push({
        theme,
        viewport: viewport.name,
        route,
        ...audit,
        failures
      });
    }

    const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
    const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
    results.push({
      theme,
      viewport: viewport.name,
      route: '__network__',
      consoleErrors,
      failedRequests,
      abortedRequests,
      badResponses,
      failures: consoleErrors.length || failedRequests.length || badResponses.length
        ? [{ type: 'network_or_console' }]
        : []
    });

    await context.close();
  }
}

await browser.close();

const pageResults = results.filter(result => result.route !== '__network__');
const networkResults = results.filter(result => result.route === '__network__');
const failed = results.filter(result => result.failures.length);

const report = {
  baseUrl,
  themes,
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
    theme: result.theme,
    viewport: result.viewport,
    route: result.route,
    checked: result.checkedCount,
    minContrast: result.minContrast,
    lowContrast: result.lowContrast.length,
    invisibleText: result.invisibleText.length,
    nowrapOverflow: result.nowrapOverflow.length,
    badRects: result.badRects.length,
    overflow: result.bodyOverflowX,
    failures: result.failures.map(item => item.type).slice(0, 8)
  })),
  networkSummary: networkResults.map(result => ({
    theme: result.theme,
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

async function login(page, theme) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'domcontentloaded' });
  await applyTheme(page, theme);
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
  await applyTheme(page, theme);
}

async function applyTheme(page, theme) {
  await page.evaluate(nextTheme => {
    const preferences = {
      theme: nextTheme,
      density: 'compact',
      default_workspace: '/app/overview',
      charts_motion: 'reduced',
      dock_labels: 'hover',
      context_panel: 'visible'
    };
    localStorage.setItem('nexus_theme_mode_v2', nextTheme);
    localStorage.setItem('nexus_ui_preferences_v1', JSON.stringify(preferences));
    document.documentElement.classList.remove('light-luxury', 'dark-cockpit');
    document.documentElement.classList.add('operations-console', nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
  }, theme);
}
