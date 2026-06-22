from app.models.sys import AiChatMessage, AiChatSession


ai_resources = {
    "ai-sessions": {
        "model": AiChatSession,
        "serializer_extra": "ai_session",
        "search": ["title"],
        "filterable": ["is_archived", "user_id"],
        "create": ["title"],
        "update": ["title", "is_archived"],
    },
    "ai-messages": {
        "model": AiChatMessage,
        "search": ["role", "content"],
        "filterable": ["session_id", "role"],
        "create": [],
        "update": [],
    },
}
