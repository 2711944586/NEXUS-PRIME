from decimal import Decimal

from app.extensions import db
from app.models.base import BaseModel
from app.models.notification import GeneratedReport, ReportSubscription


class ReportingMetricDaily(BaseModel):
    __tablename__ = "reporting_daily_metrics"
    __table_args__ = (
        db.UniqueConstraint(
            "tenant_id",
            "metric_date",
            "metric_name",
            "dimension_type",
            "dimension_id",
            name="uq_reporting_daily_metric_key",
        ),
    )

    tenant_id = db.Column(db.String(128), nullable=False, default="default")
    metric_date = db.Column(db.Date, nullable=False, index=True)
    metric_name = db.Column(db.String(128), nullable=False, index=True)
    dimension_type = db.Column(db.String(64), nullable=False, default="global")
    dimension_id = db.Column(db.String(128), nullable=False, default="all")
    value = db.Column(db.Numeric(18, 4), nullable=False, default=Decimal("0"))
    count = db.Column(db.Integer, nullable=False, default=0)
    last_event_id = db.Column(db.String(36))
    last_event_type = db.Column(db.String(128))
    last_projected_at = db.Column(db.DateTime)
    attributes = db.Column(db.JSON, default=dict)


class ReportingProjectionState(BaseModel):
    __tablename__ = "reporting_projection_states"

    event_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(128), nullable=False, index=True)
    tenant_id = db.Column(db.String(128), nullable=False, default="default")
    metrics_count = db.Column(db.Integer, nullable=False, default=0)
    projected_at = db.Column(db.DateTime, nullable=False)

__all__ = [
    "GeneratedReport",
    "ReportSubscription",
    "ReportingMetricDaily",
    "ReportingProjectionState",
]
