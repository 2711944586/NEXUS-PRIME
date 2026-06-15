from app.extensions import db
from app.models.notification import GeneratedReport
from app.services.audit_service import AuditService
from app.services.report_service import ReportService

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import current_payload, require_permission, serialize_model


@api_bp.post('/reports/generate/<report_type>')
@jwt_required
def api_report_generate(report_type):
    denied = require_permission('reports.generate', '需要报表生成权限')
    if denied:
        return denied
    data, error = ReportService.generate_report(report_type, current_payload().get('params'))
    if error:
        return api_error(error, status=400)
    values = {
        'report_type': report_type,
        'report_name': ReportService.REPORT_TYPES.get(report_type, {}).get('name', report_type),
        'report_data': data,
        'generated_by': current_api_user().id,
    }
    if 'subscription_id' in GeneratedReport.__table__.columns:
        values['subscription_id'] = None
    report = GeneratedReport(**values)
    db.session.add(report)
    db.session.flush()
    AuditService.record('reports', 'generate', current_api_user(), {'id': report.id, 'report_type': report_type})
    db.session.commit()
    return api_success({'report': serialize_model(report), 'data': data}, '报表生成成功')


@api_bp.get('/reports/types')
@jwt_required
def api_report_types():
    return api_success(ReportService.get_available_reports(), '报表类型')
