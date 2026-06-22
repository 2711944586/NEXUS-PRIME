from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonRequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in (
            "trace_id",
            "request_id",
            "tenant_id",
            "user_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "operation",
            "error_code",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def request_log_extra(**values) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
