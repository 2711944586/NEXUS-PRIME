from app.models.notification import GeneratedReport, ReportSubscription
from .models import ReportingMetricDaily


reporting_resources = {
    "report-subscriptions": {
        "model": ReportSubscription,
        "search": ["report_type", "report_name"],
        "filterable": ["report_type", "is_active", "user_id"],
        "create": ["user_id", "report_type", "report_name", "frequency", "send_email", "send_notification", "send_hour", "send_weekday", "send_day", "params"],
        "update": ["frequency", "send_email", "send_notification", "send_hour", "send_weekday", "send_day", "params", "is_active"],
    },
    "generated-reports": {
        "model": GeneratedReport,
        "serializer_extra": "report",
        "search": ["report_type", "report_name"],
        "filterable": ["report_type"],
        "create": [],
        "update": [],
    },
    "reporting-daily-metrics": {
        "model": ReportingMetricDaily,
        "search": ["metric_name", "dimension_type", "dimension_id"],
        "filterable": ["tenant_id", "metric_date", "metric_name", "dimension_type", "dimension_id"],
        "create": [],
        "update": [],
        "permission": "reports.generate",
        "read_permissions": ["reports.generate"],
    },
}
