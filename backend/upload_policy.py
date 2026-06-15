import mimetypes
import os
from zipfile import BadZipFile, ZipFile


SAFE_UPLOAD_MIME_BY_EXT = {
    'txt': {'text/plain'},
    'csv': {'text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel'},
    'pdf': {'application/pdf'},
    'png': {'image/png'},
    'jpg': {'image/jpeg'},
    'jpeg': {'image/jpeg'},
    'gif': {'image/gif'},
    'doc': {'application/msword'},
    'docx': {'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    'xls': {'application/vnd.ms-excel'},
    'xlsx': {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
}

DANGEROUS_UPLOAD_EXTENSIONS = {
    'html', 'htm', 'svg', 'js', 'mjs', 'css', 'exe', 'dll', 'bat', 'cmd', 'ps1',
    'sh', 'php', 'py', 'jar', 'msi', 'scr', 'com'
}

DANGEROUS_UPLOAD_MIME_PREFIXES = (
    'text/html',
    'image/svg+xml',
    'application/javascript',
    'text/javascript',
)

SIGNATURE_REQUIRED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'xls', 'docx', 'xlsx', 'txt', 'csv'}


def allowed_upload_extensions():
    return set(SAFE_UPLOAD_MIME_BY_EXT)


def normalized_upload_mime(file, ext):
    ext = ext.lower().lstrip('.')
    declared = (getattr(file, 'mimetype', '') or '').split(';', 1)[0].lower()
    guessed = (mimetypes.guess_type(f'file.{ext}')[0] or '').lower()
    return declared or guessed or 'application/octet-stream'


def upload_header(file, size=16):
    stream = file.stream
    position = stream.tell()
    header = stream.read(size)
    stream.seek(position)
    return header or b''


def upload_signature_matches(file, ext):
    ext = ext.lower().lstrip('.')
    header = upload_header(file, 16)
    if ext == 'pdf':
        return header.startswith(b'%PDF')
    if ext == 'png':
        return header.startswith(b'\x89PNG\r\n\x1a\n')
    if ext in {'jpg', 'jpeg'}:
        return header.startswith(b'\xff\xd8\xff')
    if ext == 'gif':
        return header.startswith((b'GIF87a', b'GIF89a'))
    if ext in {'docx', 'xlsx'}:
        return header.startswith(b'PK\x03\x04') and office_zip_signature_matches(file, ext)
    if ext in {'txt', 'csv'}:
        sample = header.lower()
        return b'\x00' not in sample and not sample.lstrip().startswith((b'<html', b'<!doctype', b'<script', b'<?xml'))
    if ext in {'doc', 'xls'}:
        return header.startswith(b'\xd0\xcf\x11\xe0')
    return False


def office_zip_signature_matches(file, ext):
    ext = ext.lower().lstrip('.')
    stream = file.stream
    position = stream.tell()
    try:
        stream.seek(0)
        with ZipFile(stream) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError, ValueError):
        return False
    finally:
        stream.seek(position)

    if '[Content_Types].xml' not in names:
        return False
    if ext == 'docx':
        return any(name.startswith('word/') for name in names)
    if ext == 'xlsx':
        return any(name.startswith('xl/') for name in names)
    return False


def validate_upload_type(file, ext):
    ext = ext.lower().lstrip('.')
    mimetype = normalized_upload_mime(file, ext)
    if ext in DANGEROUS_UPLOAD_EXTENSIONS or any(mimetype.startswith(prefix) for prefix in DANGEROUS_UPLOAD_MIME_PREFIXES):
        return False
    allowed_mimes = SAFE_UPLOAD_MIME_BY_EXT.get(ext)
    if not allowed_mimes:
        return False
    if mimetype in allowed_mimes:
        if ext in SIGNATURE_REQUIRED_EXTENSIONS:
            return upload_signature_matches(file, ext)
        return True
    if mimetype in {'application/octet-stream', 'binary/octet-stream'}:
        return upload_signature_matches(file, ext)
    return False


def upload_size(file):
    content_length = getattr(file, 'content_length', None)
    if content_length:
        return int(content_length)
    stream = file.stream
    position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size
