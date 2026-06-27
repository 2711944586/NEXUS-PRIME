import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const args = new Set(process.argv.slice(2));
const explicitApiBaseUrl = process.env.NEXUS_API_BASE_URL || process.env.VITE_NEXUS_API_BASE_URL || '';
const sentryDsn = process.env.NEXUS_SENTRY_DSN || process.env.SENTRY_DSN || '';
const sentryEnvironment = process.env.NEXUS_SENTRY_ENVIRONMENT || process.env.VERCEL_ENV || process.env.NODE_ENV || '';
const sentryRelease = process.env.NEXUS_SENTRY_RELEASE || process.env.VERCEL_GIT_COMMIT_SHA || '';
const sentryTracesSampleRate = Number(process.env.NEXUS_SENTRY_TRACES_SAMPLE_RATE || 0);
const localApiBaseUrl = process.env.NEXUS_LOCAL_API_BASE_URL || 'http://127.0.0.1:5001/api/v1';
const useLocalDefault = args.has('--local') || process.env.NEXUS_RUNTIME_CONFIG_LOCAL === '1';
const apiBaseUrl = explicitApiBaseUrl || (useLocalDefault ? localApiBaseUrl : '');
const isManagedDeployBuild = process.env.VERCEL === '1' || process.env.NETLIFY === 'true' || process.env.CF_PAGES === '1';
const target = resolve(__dirname, '..', 'public', 'runtime-config.js');

if (isManagedDeployBuild && !explicitApiBaseUrl) {
  console.error('NEXUS_API_BASE_URL is required for managed deploy builds. Example: https://your-api-host.example.com/api/v1');
  process.exit(1);
}

mkdirSync(dirname(target), { recursive: true });
writeFileSync(
  target,
  `window.NEXUS_RUNTIME_CONFIG = {\n  apiBaseUrl: ${JSON.stringify(apiBaseUrl)},\n  sentryDsn: ${JSON.stringify(sentryDsn)},\n  sentryEnvironment: ${JSON.stringify(sentryEnvironment)},\n  sentryRelease: ${JSON.stringify(sentryRelease)},\n  sentryTracesSampleRate: ${Number.isFinite(sentryTracesSampleRate) ? sentryTracesSampleRate : 0}\n};\n`,
  'utf8'
);

console.log(apiBaseUrl ? `runtime-config.js -> ${apiBaseUrl}` : 'runtime-config.js -> build-time environment fallback');
