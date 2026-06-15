from flask import jsonify


def api_success(data=None, message='success', status=200, **extra):
    payload = {
        'data': data,
        'message': message,
        'error': None,
    }
    payload.update(extra)
    return jsonify(payload), status


def api_error(message='error', status=400, error=None, **extra):
    payload = {
        'data': None,
        'message': message,
        'error': error or message,
    }
    payload.update(extra)
    return jsonify(payload), status
