export const expectedAuditApiBaseUrl =
  process.env.NEXUS_AUDIT_API_BASE_URL || 'http://127.0.0.1:5000/api/v1';

export function hasExpectedAuditApiBaseUrl(apiBaseUrl) {
  return apiBaseUrl === expectedAuditApiBaseUrl;
}

export function apiBaseFailureLabel(apiBaseUrl) {
  return `api_base:${apiBaseUrl || 'empty'}`;
}
