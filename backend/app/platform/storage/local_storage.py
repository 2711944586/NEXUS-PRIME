from __future__ import annotations

import os
from typing import BinaryIO

from flask import current_app

from .storage_service import StoredObject


class LocalStorageService:
    provider = "local"

    def upload(
        self,
        file: BinaryIO,
        *,
        path: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> StoredObject:
        object_key = normalize_object_key(path)
        root = current_app.config["UPLOAD_FOLDER"]
        target = safe_local_path(root, object_key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        file.save(target)
        return StoredObject(
            object_key=object_key,
            size=os.path.getsize(target),
            content_type=content_type,
            provider=self.provider,
        )

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str | None:
        return normalize_object_key(object_key)

    def delete(self, object_key: str) -> bool:
        root = current_app.config["UPLOAD_FOLDER"]
        try:
            target = safe_local_path(root, object_key)
        except ValueError:
            return False
        if not os.path.exists(target):
            return False
        os.remove(target)
        return True


def normalize_object_key(path: str) -> str:
    object_key = str(path or "").replace("\\", "/").lstrip("/")
    if not object_key or object_key.startswith("../") or "/../" in object_key:
        raise ValueError("Invalid storage object key")
    return object_key


def safe_local_path(root: str, object_key: str) -> str:
    root_abs = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(root_abs, normalize_object_key(object_key)))
    try:
        if os.path.commonpath([root_abs, candidate]) != root_abs:
            raise ValueError("Storage object escapes upload root")
    except ValueError as exc:
        raise ValueError("Storage object escapes upload root") from exc
    return candidate


def resolve_local_object(object_key: str) -> tuple[str, str] | None:
    root = current_app.config["UPLOAD_FOLDER"]
    try:
        target = safe_local_path(root, object_key)
    except ValueError:
        return None
    if not os.path.exists(target):
        return None
    relative_path = os.path.relpath(target, os.path.abspath(root)).replace(os.sep, "/")
    return root, relative_path
