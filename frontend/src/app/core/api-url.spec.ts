import { afterEach, describe, expect, it } from 'vitest';

import { apiBaseRoot, apiUrl, runtimeApiBaseUrl } from './api-url';

describe('api-url helpers', () => {
  afterEach(() => {
    delete (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG;
  });

  it('uses runtime API base URL for regular API paths', () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1/' };

    expect(runtimeApiBaseUrl()).toBe('https://api.example.com/api/v1');
    expect(apiUrl('files/1/download')).toBe('https://api.example.com/api/v1/files/1/download');
    expect(apiBaseRoot()).toBe('https://api.example.com');
  });

  it('resolves backend-provided absolute API paths against the same API host', () => {
    (globalThis as typeof globalThis & {
      NEXUS_RUNTIME_CONFIG?: { apiBaseUrl?: string };
    }).NEXUS_RUNTIME_CONFIG = { apiBaseUrl: 'https://api.example.com/api/v1' };

    expect(apiUrl('/api/v1/files/1/download')).toBe('https://api.example.com/api/v1/files/1/download');
    expect(apiUrl('https://cdn.example.com/file.pdf')).toBe('https://cdn.example.com/file.pdf');
  });
});
