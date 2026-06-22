from app.models.content import Attachment


file_resources = {
    "files": {
        "model": Attachment,
        "serializer_extra": "attachment",
        "search": ["filename", "mimetype"],
        "filterable": ["mimetype"],
        "create": [],
        "update": [],
    },
}
