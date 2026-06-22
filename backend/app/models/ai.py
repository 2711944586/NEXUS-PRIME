from app.extensions import db
from app.utils.time import utcnow
from .base import BaseModel


class DocumentChunk(BaseModel):
    """RAG document chunk prepared for retrieval and future pgvector indexing."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        db.UniqueConstraint("source_type", "source_id", "chunk_index", name="uq_document_chunk_source_index"),
    )

    tenant_id = db.Column(db.String(128), nullable=False, default="default", index=True)
    source_type = db.Column(db.String(64), nullable=False, index=True)
    source_id = db.Column(db.String(128), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(256))
    content = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    embedding = db.Column(db.JSON)
    embedding_model = db.Column(db.String(128))
    metadata_json = db.Column(db.JSON)


class AiActionDraft(BaseModel):
    """Human-confirmed AI action draft.

    AI may persist draft proposals here, but formal ERP records are created
    only when a user confirms the draft through an explicit API action.
    """

    __tablename__ = "ai_action_drafts"

    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"

    draft_type = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_DRAFT, index=True)
    title = db.Column(db.String(256))
    source_tool = db.Column(db.String(128), index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    result_type = db.Column(db.String(128))
    result_id = db.Column(db.String(255))
    note = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=True, index=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=True)
    confirmed_at = db.Column(db.DateTime)
    rejected_by = db.Column(db.Integer, db.ForeignKey("auth_users.id"), nullable=True)
    rejected_at = db.Column(db.DateTime)

    creator = db.relationship("User", foreign_keys=[created_by])
    confirmer = db.relationship("User", foreign_keys=[confirmed_by])
    rejecter = db.relationship("User", foreign_keys=[rejected_by])

    def mark_confirmed(self, user, *, result_type=None, result_id=None, note=None):
        self.status = self.STATUS_CONFIRMED
        self.confirmed_by = getattr(user, "id", user)
        self.confirmed_at = utcnow()
        if result_type:
            self.result_type = result_type
        if result_id is not None:
            self.result_id = str(result_id)
        if note:
            self.note = note

    def mark_rejected(self, user, *, note=None):
        self.status = self.STATUS_REJECTED
        self.rejected_by = getattr(user, "id", user)
        self.rejected_at = utcnow()
        if note:
            self.note = note
