"""Storage adapters used by platform and domain code."""

from .storage_service import StoredObject, StorageService, get_storage_service
from .local_storage import LocalStorageService
from .cloudinary_storage import CloudinaryStorageService

__all__ = [
    "CloudinaryStorageService",
    "LocalStorageService",
    "StorageService",
    "StoredObject",
    "get_storage_service",
]
