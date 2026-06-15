import { environment } from '../../environments/environment';

type RuntimeConfig = typeof globalThis & {
  NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
};

const API_PREFIX = '/api/v1';

export function runtimeApiBaseUrl(): string {
  const runtime = (globalThis as RuntimeConfig).NEXUS_RUNTIME_CONFIG;
  const baseUrl = runtime?.apiBaseUrl || environment.apiBaseUrl || '';
  return baseUrl.replace(/\/$/, '');
}

export function apiBaseRoot(): string {
  const baseUrl = runtimeApiBaseUrl();
  if (!baseUrl) {
    return typeof window === 'undefined' ? '' : window.location.origin;
  }
  return baseUrl.replace(/\/api\/v1\/?$/, '');
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (normalizedPath.startsWith(API_PREFIX)) {
    return `${apiBaseRoot()}${normalizedPath}`;
  }

  return `${runtimeApiBaseUrl()}${normalizedPath}`;
}
