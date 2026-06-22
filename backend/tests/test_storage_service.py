import os
from io import BytesIO

import pytest

from app import create_app
from app.platform.storage import LocalStorageService
from app.platform.storage.local_storage import resolve_local_object


class UploadStub(BytesIO):
    def save(self, target):
        with open(target, "wb") as output:
            output.write(self.getvalue())


def test_local_storage_service_stores_object_key_under_upload_root(tmp_path):
    app = create_app("testing")
    app.config.update({"UPLOAD_FOLDER": os.fspath(tmp_path / "uploads")})

    with app.app_context():
        stored = LocalStorageService().upload(
            UploadStub(b"storage boundary"),
            path="files/storage-boundary.txt",
            content_type="text/plain",
            metadata={"source": "unit-test"},
        )

        assert stored.provider == "local"
        assert stored.object_key == "files/storage-boundary.txt"
        assert stored.size == len(b"storage boundary")

        resolved = resolve_local_object(stored.object_key)
        assert resolved is not None
        root, relative_path = resolved
        assert root == app.config["UPLOAD_FOLDER"]
        assert relative_path == "files/storage-boundary.txt"
        assert (tmp_path / "uploads" / "files" / "storage-boundary.txt").read_bytes() == b"storage boundary"


def test_local_storage_service_rejects_path_traversal(tmp_path):
    app = create_app("testing")
    app.config.update({"UPLOAD_FOLDER": os.fspath(tmp_path / "uploads")})

    with app.app_context():
        with pytest.raises(ValueError):
            LocalStorageService().upload(UploadStub(b"bad"), path="../escape.txt", content_type="text/plain")
