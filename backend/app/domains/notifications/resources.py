from app.models.notification import Notification


notification_resources = {
    "notifications": {
        "model": Notification,
        "serializer_extra": "notification",
        "search": ["title", "content", "type", "category"],
        "filterable": ["is_read", "type", "category", "user_id"],
        "create": ["user_id", "title", "content", "type", "category", "related_type", "related_id"],
        "update": ["title", "content", "type", "category", "is_read"],
    },
}
