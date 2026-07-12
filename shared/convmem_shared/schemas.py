"""Core domain models shared across services.

These are the wire formats: the memory service produces them, the
personalization service and gateway consume them. Keeping them in one place
guarantees the services never drift apart.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


# ── Memories ─────────────────────────────────────────────────────────────────


class MemoryCreate(BaseModel):
    session_id: str
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=32_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    metadata: dict[str, Any]


class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    session_id: str
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class ScoredMemory(BaseModel):
    """A memory returned from semantic search, with scoring breakdown."""

    memory: Memory
    similarity: float
    recency: float
    score: float


# ── Sessions ─────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    user_id: str
    state: dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    state: dict[str, Any]


class Session(BaseModel):
    session_id: str
    user_id: str
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    ttl_seconds: int


# ── Personalization ──────────────────────────────────────────────────────────


class PreferenceSignal(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=1024)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)


class UserProfile(BaseModel):
    user_id: str
    preferences: dict[str, str] = Field(default_factory=dict)
    top_intents: list[str] = Field(default_factory=list)
    memory_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class ContextBundle(BaseModel):
    """Everything an AI agent needs before generating its next turn."""

    user_id: str
    profile: UserProfile
    memories: list[ScoredMemory] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)


# ── Embeddings ───────────────────────────────────────────────────────────────


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=256)


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    dim: int
    backend: str
