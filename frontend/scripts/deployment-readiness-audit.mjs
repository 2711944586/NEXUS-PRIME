import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.NEXUS_AUDIT_BASE_URL || 'http://127.0.0.1:4200';
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `deployment-readiness-audit-${Date.now()}`);
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
  const badResponses = [];
  page.on('console', message => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });
  page.on('response', response => {
    if (response.status() >= 400) {
      badResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  await login(page);
  await page.goto(`${baseUrl}/app/settings`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);

  const audit = await page.evaluate(() => {
    const visible = selector => [...document.querySelectorAll(selector)]
      .filter(element => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
      });
    const text = selector => visible(selector).map(element => element.textContent?.trim().replace(/\s+/g, ' ') || '');
    const bodyText = document.body.textContent || '';
    const postgresLeaks = (bodyText.match(/postgresql:\/\/[^\s"']+/g) || [])
      .filter(value => !value.includes('<project-ref>') && !value.includes('<password>'));
    const cloudinaryLeaks = (bodyText.match(/cloudinary:\/\/[^\s"']+/g) || [])
      .filter(value => !value.includes('api_key:api_secret@cloud_name'));
    const envSecretLeaks = (bodyText.match(/\b(?:SECRET_KEY|VERCEL_TOKEN)=[^\s"']+/g) || [])
      .filter(value => !value.includes('<') && !value.includes('placeholder'));
    const overflow = Math.max(0, document.documentElement.scrollWidth - window.innerWidth);
    return {
      path: location.pathname,
      overflow,
      readinessChecks: visible('.deployment-check-board article').length,
      domainCards: visible('.deployment-domain-grid article').length,
      maturityDimensions: visible('.erp-maturity-dimensions article').length,
      capabilityCards: visible('.erp-capability-grid article').length,
      topologyNodes: visible('.erp-topology-list a').length,
      evidenceCards: visible('.erp-evidence-strip article').length,
      runbookItems: visible('.deployment-copy-grid article').length,
      tokenLinks: visible('.deployment-token-grid a').length,
      maturityText: text('.erp-maturity-score strong, .erp-maturity-score em, .erp-maturity-dimensions article strong'),
      hasIndustryTarget: bodyText.includes('行业头部级制造开发管理 ERP'),
      secretLeakCandidates: [...postgresLeaks, ...cloudinaryLeaks, ...envSecretLeaks],
    };
  });

  const failures = [];
  if (audit.overflow > 3) failures.push(`horizontal overflow ${audit.overflow}`);
  if (audit.readinessChecks < 10) failures.push(`readiness checks ${audit.readinessChecks}`);
  if (audit.domainCards < 3) failures.push(`domain cards ${audit.domainCards}`);
  if (audit.maturityDimensions < 6) failures.push(`maturity dimensions ${audit.maturityDimensions}`);
  if (audit.capabilityCards < 3) failures.push(`capability cards ${audit.capabilityCards}`);
  if (audit.topologyNodes < 8) failures.push(`topology nodes ${audit.topologyNodes}`);
  if (audit.evidenceCards < 6) failures.push(`evidence cards ${audit.evidenceCards}`);
  if (audit.runbookItems < 5) failures.push(`runbook items ${audit.runbookItems}`);
  if (audit.tokenLinks < 6) failures.push(`token links ${audit.tokenLinks}`);
  if (!audit.hasIndustryTarget) failures.push('missing industry target');
  if (audit.secretLeakCandidates.length) failures.push('visible secret-like value');
  if (consoleErrors.length) failures.push(`console errors ${consoleErrors.length}`);
  if (badResponses.length) failures.push(`HTTP errors ${badResponses.length}`);

  await page.screenshot({ path: path.join(outDir, `${viewport.name}-deployment-readiness.png`), fullPage: true });
  results.push({ viewport: viewport.name, ...audit, consoleErrors, badResponses, failures });
  await context.close();
}

await browser.close();

const failed = results.filter(result => result.failures.length);
await writeFile(path.join(outDir, 'report.json'), JSON.stringify({ baseUrl, results, failed }, null, 2));

if (failed.length) {
  console.error(`Deployment readiness audit failed: ${failed.length} viewports. Report: ${path.join(outDir, 'report.json')}`);
  for (const item of failed) {
    console.error(`${item.viewport}: ${item.failures.join('; ')}`);
  }
  process.exit(1);
}

console.log(`Deployment readiness audit passed for ${results.length} viewports. Report: ${path.join(outDir, 'report.json')}`);

async function login(page) {
  await page.goto(`${baseUrl}/auth/login`, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').first().fill(credentials.email);
  await page.locator('input[type="password"], input[name="password"]').first().fill(credentials.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/app/**', { timeout: 15000 });
}
