from __future__ import annotations

from typing import BinaryIO

from .storage_service import StoredObject


class CloudinaryStorageService:
    provider = "cloudinary"

    def upload(
        self,
        file: BinaryIO,
        *,
        path: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> StoredObject:
        from app.utils.cloud_storage import upload_to_cloud

        folder = str(path or "uploads").replace("\\", "/").split("/", 1)[0] or "uploads"
        result = upload_to_cloud(file, folder=folder, resource_type="auto")
        if not result:
            raise RuntimeError("Cloudinary upload failed")
        object_key = result.get("public_id")
        if not object_key:
            raise RuntimeError("Cloudinary upload returned no object key")
        return StoredObject(
            object_key=f"cloudinary:{object_key}",
            size=int(result.get("bytes") or 0),
            content_type=content_type,
            url=result.get("secure_url") or result.get("url"),
            provider=self.provider,
        )

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str | None:
        if not object_key:
            return None
        if object_key.startswith(("http://", "https://")):
            return object_key
        public_id = object_key.removeprefix("cloudinary:")
        from app.utils.cloud_storage import get_cloud_url

        return get_cloud_url(public_id, resource_type="auto")

    def delete(self, object_key: str) -> bool:
        if not object_key:
            return False
        public_id = object_key.removeprefix("cloudinary:")
        from app.utils.cloud_storage import delete_from_cloud

        return delete_from_cloud(public_id, resource_type="auto")
