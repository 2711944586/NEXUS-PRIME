#!/bin/sh
set -eu

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

api_base_url="$(json_escape "${NEXUS_API_BASE_URL:-}")"
sentry_dsn="$(json_escape "${NEXUS_SENTRY_DSN:-}")"
sentry_environment="$(json_escape "${NEXUS_SENTRY_ENVIRONMENT:-production}")"
sentry_release="$(json_escape "${NEXUS_SENTRY_RELEASE:-}")"
sentry_traces_sample_rate="${NEXUS_SENTRY_TRACES_SAMPLE_RATE:-0}"
case "${sentry_traces_sample_rate}" in
  ''|*[!0-9.]*)
    sentry_traces_sample_rate="0"
    ;;
esac

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.NEXUS_RUNTIME_CONFIG = {
  apiBaseUrl: "${api_base_url}",
  sentryDsn: "${sentry_dsn}",
  sentryEnvironment: "${sentry_environment}",
  sentryRelease: "${sentry_release}",
  sentryTracesSampleRate: ${sentry_traces_sample_rate}
};
EOF
