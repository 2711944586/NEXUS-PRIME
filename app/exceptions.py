class NexusException(Exception):
    """NEXUS 系统基础异常类"""
    def __init__(self, message, code=500, payload=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['code'] = self.code
        rv['success'] = False
        return rv

class ValidationError(NexusException):
    """表单验证错误"""
    def __init__(self, message="Invalid data", payload=None):
        super().__init__(message, code=400, payload=payload)

class PermissionDenied(NexusException):
    """权限不足"""
    def __init__(self, message="Access denied", payload=None):
        super().__init__(message, code=403, payload=payload)