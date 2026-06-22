from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

import httpx
from flask import current_app


@dataclass(frozen=True)
class EmbeddingResult:
    embedding: list[float]
    model: str


class EmbeddingProvider(Protocol):
    model: str

    def embed_text(self, text: str) -> EmbeddingResult:
        ...


class LocalHashEmbeddingProvider:
    """Deterministic offline embedding for dev/test and cold-start RAG plumbing."""

    def __init__(self, *, model: str = "local-hash-v1", dimensions: int = 32):
        self.model = model
        self.dimensions = max(int(dimensions or 32), 8)

    def embed_text(self, text: str) -> EmbeddingResult:
        content = (text or "").strip()
        if not content:
            raise ValueError("Embedding text is required")

        vector = [0.0 for _ in range(self.dimensions)]
        tokens = _tokens(content) or [content[:512]]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            signed = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 0.5 + (digest[3] / 255.0)
            vector[index] += signed * weight

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return EmbeddingResult(
            embedding=[round(value / norm, 6) for value in vector],
            model=self.model,
        )


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float = 20.0):
        if not api_key:
            raise ValueError("AI embedding API key is required")
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com").rstrip("/")
        self.model = model or "text-embedding-3-small"
        self.timeout = timeout

    def embed_text(self, text: str) -> EmbeddingResult:
        content = (text or "").strip()
        if not content:
            raise ValueError("Embedding text is required")
        api_url = self.base_url
        if not api_url.endswith("/v1"):
            api_url += "/v1"
        response = httpx.post(
            f"{api_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": content[:16000]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("data", [{}])[0].get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise ValueError("Embedding provider returned an empty vector")
        return EmbeddingResult(embedding=[float(value) for value in embedding], model=self.model)


def get_embedding_provider() -> EmbeddingProvider:
    provider = str(current_app.config.get("AI_EMBEDDING_PROVIDER") or "local").strip().lower()
    model = str(current_app.config.get("AI_EMBEDDING_MODEL") or "").strip()
    if provider in {"local", "local-hash", "offline"}:
        return LocalHashEmbeddingProvider(
            model=model or "local-hash-v1",
            dimensions=int(current_app.config.get("AI_EMBEDDING_DIMENSIONS") or 32),
        )
    if provider in {"openai", "openai-compatible", "external"}:
        api_key = (
            current_app.config.get("AI_EMBEDDING_API_KEY")
            or current_app.config.get("AI_API_KEY")
            or current_app.config.get("OPENAI_API_KEY")
            or ""
        )
        base_url = (
            current_app.config.get("AI_EMBEDDING_BASE_URL")
            or current_app.config.get("AI_BASE_URL")
            or current_app.config.get("OPENAI_BASE_URL")
            or "https://api.openai.com"
        )
        return OpenAICompatibleEmbeddingProvider(
            api_key=api_key,
            base_url=base_url,
            model=model or "text-embedding-3-small",
            timeout=float(current_app.config.get("AI_EMBEDDING_TIMEOUT_SECONDS") or 20.0),
        )
    raise ValueError(f"Unsupported AI embedding provider: {provider}")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_.:/-]+|[\u4e00-\u9fff]{1,2}", text.lower())
