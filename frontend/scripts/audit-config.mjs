export const expectedAuditApiBaseUrl =
  process.env.NEXUS_AUDIT_API_BASE_URL || 'http://127.0.0.1:5001/api/v1';

export function hasExpectedAuditApiBaseUrl(apiBaseUrl) {
  if (process.env.NEXUS_AUDIT_STRICT_API_BASE === '1') {
    return apiBaseUrl === expectedAuditApiBaseUrl;
  }
  return ['', '/api/v1', expectedAuditApiBaseUrl].includes(apiBaseUrl || '');
}

export function apiBaseFailureLabel(apiBaseUrl) {
  return `api_base:${apiBaseUrl || 'empty'}`;
}
