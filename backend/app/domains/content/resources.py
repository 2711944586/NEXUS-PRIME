from app.models.content import Article, ArticleComment


content_resources = {
    "articles": {
        "model": Article,
        "serializer_extra": "article",
        "search": ["title", "content", "category"],
        "filterable": ["status", "category"],
        "create": ["title", "content", "content_raw", "category", "status"],
        "update": ["title", "content", "content_raw", "category", "status"],
        "permission": "content.write",
    },
    "article-comments": {
        "model": ArticleComment,
        "serializer_extra": "comment",
        "search": ["content", "status"],
        "filterable": ["article_id", "status"],
        "create": ["article_id", "content", "parent_id", "status"],
        "update": ["content", "status"],
    },
}
