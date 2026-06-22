from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size: int
    content_type: str | None = None
    url: str | None = None
    provider: str = "local"


class StorageService(Protocol):
    provider: str

    def upload(
        self,
        file: BinaryIO,
        *,
        path: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> StoredObject:
        ...

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str | None:
        ...

    def delete(self, object_key: str) -> bool:
        ...


def get_storage_service() -> StorageService:
    from app.utils.cloud_storage import is_cloud_storage_enabled

    if is_cloud_storage_enabled():
        from .cloudinary_storage import CloudinaryStorageService

        return CloudinaryStorageService()

    from .local_storage import LocalStorageService

    return LocalStorageService()
