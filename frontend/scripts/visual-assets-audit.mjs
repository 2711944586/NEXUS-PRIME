import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `visual-assets-audit-${Date.now()}`);
const imageDir = path.resolve(process.cwd(), 'public', 'images');
const sourceManifestPath = path.join(imageDir, 'image-sources.md');
const credentials = {
  email: process.env.NEXUS_AUDIT_EMAIL || 'admin@nexus.com',
  password: process.env.NEXUS_AUDIT_PASSWORD || 'admin123'
};

const coreRoutes = [
  '/app/overview',
  '/app/metrics',
  '/app/tasks',
  '/app/inventory/products',
  '/app/inventory/stock',
  '/app/inventory/replenishment',
  '/app/sales/orders',
  '/app/procurement/orders',
  '/app/finance/receivables',
  '/app/reports'
];
const extendedRoutes = [
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
  '/app/finance/credits',
  '/app/stocktakes',
  '/app/files',
  '/app/content/articles',
  '/app/system/users',
  '/app/system/audit',
  '/app/notifications',
  '/app/ai',
  '/app/profile',
  '/app/settings'
];
const routes = process.env.NEXUS_AUDIT_VISUAL_ROUTES === 'core'
  ? coreRoutes
  : [...coreRoutes, ...extendedRoutes];

const allViewports = [
  { name: 'desktop', width: 1440, height: 950, minEvidenceImages: 6, minUniqueEvidenceImages: 4, minPageEvidenceImages: 3 },
  { name: 'mobile', width: 390, height: 844, minEvidenceImages: 3, minUniqueEvidenceImages: 3, minPageEvidenceImages: 3 }
];
const viewportMode = process.env.NEXUS_AUDIT_VISUAL_VIEWPORTS || 'all';
const viewports = viewportMode === 'desktop'
  ? [allViewports[0]]
  : viewportMode === 'mobile'
    ? [allViewports[1]]
    : allViewports;

await mkdir(outDir, { recursive: true });

const [assetInventory, sourceManifest] = await Promise.all([
  collectAssetInventory(),
  readFile(sourceManifestPath, 'utf8')
]);

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

  const routeResults = [];
  for (const route of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.atlas-shell', { state: 'visible', timeout: 15000 });
    await page.waitForTimeout(650);
    await page.evaluate(async () => {
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
      const images = [...document.querySelectorAll('.field-evidence-grid img, .page-evidence-grid img, .module-photo-rail img')]
        .filter(visible)
        .filter(image => image.currentSrc || image.src || image.getAttribute('src'));
      const decodeAll = Promise.all(images.map(image => {
        if (image.complete && image.naturalWidth > 0) {
          return Promise.resolve();
        }
        if (typeof image.decode === 'function') {
          return image.decode().catch(() => null);
        }
        return new Promise(resolve => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
          setTimeout(resolve, 1200);
        });
      }));
      const timeout = new Promise(resolve => setTimeout(resolve, 1600));
      await Promise.race([decodeAll, timeout]);
    });

    const audit = await page.evaluate(({ viewportName, minEvidenceImages, minUniqueEvidenceImages, minPageEvidenceImages }) => {
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
      const normalizeSrc = src => {
        try {
          const url = new URL(src, window.location.origin);
          return url.pathname;
        } catch {
          return src;
        }
      };
      const imageInfo = image => {
        const box = image.getBoundingClientRect();
        const src = normalizeSrc(image.currentSrc || image.src || image.getAttribute('src') || '');
        const alt = image.getAttribute('alt') || '';
        const contextText = image.closest('a, figure, article, section')?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 120) || '';
        return {
          src,
          alt,
          contextText,
          width: Math.round(box.width),
          height: Math.round(box.height),
          naturalWidth: image.naturalWidth,
          naturalHeight: image.naturalHeight,
          complete: image.complete,
          visible: visible(image),
          className: [...image.classList].slice(0, 4).join('.')
        };
      };

      const visibleImages = [...document.querySelectorAll('img')].filter(visible).map(imageInfo);
      const evidenceImages = visibleImages.filter(image =>
        image.src.startsWith('/images/') &&
        image.width >= 48 &&
        image.height >= 36 &&
        /现场|仓|工厂|工单|数据|财务|质量|维护|合同|服务|终端|扫码|经营|分析|监控|档案|团队|车间|设备|收货|采购/.test(`${image.alt} ${image.contextText}`)
      );
      const pageEvidenceImages = [...document.querySelectorAll('.page-evidence-grid img, .mobile-field-evidence-strip .field-evidence-grid img')]
        .filter(visible)
        .map(imageInfo)
        .filter(image => image.src.startsWith('/images/'));
      const brokenImages = visibleImages.filter(image => image.naturalWidth <= 0 || image.naturalHeight <= 0);
      const remoteImages = visibleImages.filter(image => image.src.startsWith('http://') || image.src.startsWith('https://'));
      const genericAlt = visibleImages.filter(image => {
        const alt = image.alt.trim().toLowerCase();
        return !alt || alt === 'image' || alt === 'photo' || alt === 'picture' || alt === '图片' || alt === '照片';
      });
      const tinyEvidenceImages = evidenceImages.filter(image => image.naturalWidth < 320 || image.naturalHeight < 180);
      const uniqueEvidenceSources = [...new Set(evidenceImages.map(image => image.src))];
      const uniquePageEvidenceSources = [...new Set(pageEvidenceImages.map(image => image.src))];
      const failures = [];

      if (evidenceImages.length < minEvidenceImages) {
        failures.push(`evidence_images:${evidenceImages.length}<${minEvidenceImages}`);
      }
      if (uniqueEvidenceSources.length < minUniqueEvidenceImages) {
        failures.push(`unique_evidence:${uniqueEvidenceSources.length}<${minUniqueEvidenceImages}`);
      }
      if (pageEvidenceImages.length < minPageEvidenceImages) {
        failures.push(`page_evidence:${pageEvidenceImages.length}<${minPageEvidenceImages}`);
      }
      if (uniquePageEvidenceSources.length < minPageEvidenceImages) {
        failures.push(`unique_page_evidence:${uniquePageEvidenceSources.length}<${minPageEvidenceImages}`);
      }
      if (brokenImages.length) {
        failures.push(`broken_images:${brokenImages.length}`);
      }
      if (remoteImages.length) {
        failures.push(`remote_images:${remoteImages.length}`);
      }
      if (genericAlt.length) {
        failures.push(`generic_alt:${genericAlt.length}`);
      }
      if (tinyEvidenceImages.length) {
        failures.push(`tiny_evidence:${tinyEvidenceImages.length}`);
      }

      return {
        viewport: viewportName,
        path: window.location.pathname,
        failures,
        visibleImages: visibleImages.length,
        evidenceImages: evidenceImages.length,
        pageEvidenceImages: pageEvidenceImages.length,
        uniqueEvidenceSources,
        uniquePageEvidenceSources,
        brokenImages: brokenImages.slice(0, 8),
        remoteImages: remoteImages.slice(0, 8),
        genericAlt: genericAlt.slice(0, 8),
        tinyEvidenceImages: tinyEvidenceImages.slice(0, 8),
        sampleEvidence: evidenceImages.slice(0, 8),
        viewportSize: { width: window.innerWidth, height: window.innerHeight }
      };
    }, viewport);

    routeResults.push(audit);
  }

  const abortedRequests = requestFailures.filter(item => item.error.includes('ERR_ABORTED'));
  const failedRequests = requestFailures.filter(item => !item.error.includes('ERR_ABORTED'));
  results.push({
    viewport: viewport.name,
    routeResults,
    consoleErrors,
    failedRequests,
    abortedRequests,
    badResponses
  });

  await context.close();
}

await browser.close();

const usedSources = [...new Set(results.flatMap(result => result.routeResults.flatMap(route => route.uniqueEvidenceSources)))].sort();
const assetFailures = [];
const manifestMissing = assetInventory.jpgFiles.filter(file => !sourceManifest.includes(file));
if (assetInventory.jpgFiles.length < 30) {
  assetFailures.push(`local_jpg_assets:${assetInventory.jpgFiles.length}<30`);
}
if (usedSources.length < 22) {
  assetFailures.push(`used_unique_sources:${usedSources.length}<22`);
}
if (manifestMissing.length) {
  assetFailures.push(`manifest_missing:${manifestMissing.length}`);
}

const failed = results.filter(result =>
  result.consoleErrors.length ||
  result.failedRequests.length ||
  result.badResponses.length ||
  result.routeResults.some(route => route.failures.length)
);

const passed = failed.length === 0 && assetFailures.length === 0;
const report = {
  baseUrl,
  routes,
  generatedAt: new Date().toISOString(),
  assetInventory: {
    ...assetInventory,
    manifestMissing,
    usedSources
  },
  assetFailures,
  results,
  failed
};

await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

console.log(JSON.stringify({
  outDir,
  passed,
  assetSummary: {
    localJpgAssets: assetInventory.jpgFiles.length,
    usedUniqueSources: usedSources.length,
    manifestMissing: manifestMissing.length,
    assetFailures
  },
  pageSummary: results.flatMap(result => result.routeResults.map(route => ({
    viewport: result.viewport,
    route: route.path,
    failures: route.failures,
    evidenceImages: route.evidenceImages,
    pageEvidenceImages: route.pageEvidenceImages,
    uniqueEvidenceSources: route.uniqueEvidenceSources.length,
    uniquePageEvidenceSources: route.uniquePageEvidenceSources.length,
    brokenImages: route.brokenImages.length,
    remoteImages: route.remoteImages.length,
    genericAlt: route.genericAlt.length
  }))),
  networkSummary: results.map(result => ({
    viewport: result.viewport,
    consoleErrors: result.consoleErrors.length,
    failedRequests: result.failedRequests.length,
    abortedRequests: result.abortedRequests.length,
    badResponses: result.badResponses.length
  }))
}, null, 2));

if (!passed) {
  process.exit(1);
}

async function collectAssetInventory() {
  const entries = await readdir(imageDir, { withFileTypes: true });
  const jpgFiles = entries
    .filter(entry => entry.isFile() && /\.(jpe?g)$/i.test(entry.name))
    .map(entry => entry.name)
    .sort();
  return { jpgFiles };
}

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
