import json
import time

from flask import Response, current_app, stream_with_context

from app.extensions import db
from app.models.jobs import BackgroundJob
from app.models.notification import GeneratedReport
from app.platform.jobs import create_background_job, get_background_job, serialize_background_job
from app.platform.jobs.reports import generate_report_job
from app.services.report_service import ReportService

from . import api_bp
from .auth import current_api_user, jwt_required
from .responses import api_error, api_success
from .routes import current_payload, require_permission, serialize_model


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f"event: {event}\ndata: {payload}\n\n"


def _is_report_job_admin(user) -> bool:
    return bool(user and (user.is_admin or (user.role and user.role.is_admin)))


def _can_access_report_job(job, user) -> bool:
    return bool(job and (job.created_by == user.id or _is_report_job_admin(user)))


def _report_job_payload(job):
    report = None
    if job.resource_type == 'generated_report' and job.resource_id:
        report = db.session.get(GeneratedReport, int(job.resource_id))
    return {
        'job_id': job.job_id,
        'job': serialize_background_job(job),
        'report': serialize_model(report) if report else None,
        'data': (job.result or {}).get('data') if job.result else None,
    }


@api_bp.post('/reports/generate/<report_type>')
@jwt_required
def api_report_generate(report_type):
    denied = require_permission('reports.generate', '需要报表生成权限')
    if denied:
        return denied
    if report_type not in ReportService.REPORT_TYPES:
        return api_error(f"报表生成器不存在: {report_type}", status=400)

    payload = current_payload()
    params = payload.get('params')
    user = current_api_user()
    job = create_background_job(
        'report.generate',
        {'report_type': report_type, 'params': params},
        created_by=user,
        queue='reports',
        task_name='nexus.reports.generate',
    )
    from app.platform.events import outbox

    outbox.add(
        "ReportRequested",
        "BackgroundJob",
        job.job_id,
        {
            "job_id": job.job_id,
            "report_type": report_type,
            "params": params,
            "requested_by": user.id,
            "queue": job.queue,
            "task_name": job.task_name,
        },
        created_by=user.id,
    )
    db.session.commit()
    job_id = job.job_id

    try:
        if current_app.config.get('CELERY_TASK_ALWAYS_EAGER', False):
            generate_report_job(job_id, report_type, params=params, user_id=user.id, celery_task_id=f'eager-{job_id}')
        else:
            from app.platform.jobs.tasks.reports import generate_report_task

            async_result = generate_report_task.apply_async(
                kwargs={'job_id': job_id, 'report_type': report_type, 'params': params, 'user_id': user.id},
                queue='reports',
            )
            job.celery_task_id = async_result.id
            db.session.add(job)
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        job = get_background_job(job_id)
        if job and job.status != BackgroundJob.STATUS_FAILED:
            job.mark_failed(exc)
            db.session.add(job)
            db.session.commit()
        return api_error(str(exc), status=500, error='report_job_failed', job=serialize_background_job(job) if job else None)

    job = get_background_job(job_id)
    if job.status == BackgroundJob.STATUS_SUCCESS and job.resource_id:
        report = db.session.get(GeneratedReport, int(job.resource_id))
        data = (job.result or {}).get('data')
        return api_success({
            'job_id': job.job_id,
            'job': serialize_background_job(job),
            'report': serialize_model(report),
            'data': data,
        }, '报表生成成功')

    if job.status == BackgroundJob.STATUS_FAILED:
        return api_error(job.error_message or '报表生成失败', status=500, error='report_job_failed', job=serialize_background_job(job))

    return api_success({
        'job_id': job.job_id,
        'job': serialize_background_job(job),
        'status': job.status,
    }, '报表生成任务已入队', status=202)


@api_bp.get('/reports/jobs/<job_id>')
@jwt_required
def api_report_job(job_id):
    job = get_background_job(job_id)
    if not job or job.job_type != 'report.generate':
        return api_error('报表任务不存在', status=404, error='job_not_found')
    user = current_api_user()
    if not _can_access_report_job(job, user):
        return api_error('权限不足', status=403, error='permission_denied')

    return api_success(_report_job_payload(job), '报表任务状态')


@api_bp.get('/reports/jobs/<job_id>/stream')
@jwt_required
def api_report_job_stream(job_id):
    job = get_background_job(job_id)
    if not job or job.job_type != 'report.generate':
        return api_error('报表任务不存在', status=404, error='job_not_found')
    user = current_api_user()
    if not _can_access_report_job(job, user):
        return api_error('权限不足', status=403, error='permission_denied')

    max_events = max(1, int(current_app.config.get('REPORT_JOB_STREAM_MAX_EVENTS', 25)))
    interval_seconds = max(0.0, float(current_app.config.get('REPORT_JOB_STREAM_INTERVAL_SECONDS', 2.0)))

    def generate():
        for index in range(max_events):
            current_job = get_background_job(job_id)
            if not current_job or current_job.job_type != 'report.generate':
                yield _sse_event('error', {'message': '报表任务不存在', 'error': 'job_not_found', 'status': 404})
                return

            payload = _report_job_payload(current_job)
            if current_job.status == BackgroundJob.STATUS_SUCCESS:
                yield _sse_event('done', payload)
                return
            if current_job.status == BackgroundJob.STATUS_FAILED:
                yield _sse_event('failed', payload)
                return

            yield _sse_event('status', payload)
            if index < max_events - 1 and interval_seconds:
                time.sleep(interval_seconds)

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@api_bp.get('/reports/types')
@jwt_required
def api_report_types():
    return api_success(ReportService.get_available_reports(), '报表类型')
