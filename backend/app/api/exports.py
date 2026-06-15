from io import BytesIO

from flask import send_file

from app.services.export_service import ExportService

from . import api_bp
from .auth import jwt_required
from .responses import api_error
from .routes import query_for, require_resource_access, resource_config, serializer_for


@api_bp.get('/export/<resource>/<format_type>')
@jwt_required
def api_export_resource(resource, format_type):
    config = resource_config(resource)
    if not config:
        return api_error('资源不存在', status=404)
    denied = require_resource_access(config, 'list')
    if denied:
        return denied
    items = query_for(config).limit(1000).all()
    rows = [serializer_for(config)(item) for item in items]
    columns = [{'field': key, 'header': key, 'width': 18} for key in (rows[0].keys() if rows else ['id'])]
    if format_type == 'csv':
        stream = ExportService.export_to_csv(rows, columns)
        mimetype = 'text/csv'
        suffix = 'csv'
    elif format_type == 'excel':
        stream = ExportService.export_to_excel(rows, columns, sheet_name=resource[:31], title=f'{resource} 数据导出')
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        suffix = 'xlsx'
    elif format_type == 'pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        stream = BytesIO()
        pdf = canvas.Canvas(stream, pagesize=A4)
        pdf.drawString(40, 800, f'NEXUS {resource} export')
        y = 770
        for row in rows[:40]:
            pdf.drawString(40, y, str(row)[:110])
            y -= 18
            if y < 40:
                pdf.showPage()
                y = 800
        pdf.save()
        stream.seek(0)
        mimetype = 'application/pdf'
        suffix = 'pdf'
    else:
        return api_error('导出格式仅支持 csv/excel/pdf', status=400)
    return send_file(stream, mimetype=mimetype, as_attachment=True, download_name=f'{resource}.{suffix}')
