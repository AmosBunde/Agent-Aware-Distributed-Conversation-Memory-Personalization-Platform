import hashlib
import math

import httpx
import pytest

from services.memory.app.config import Settings
from services.memory.app.main import create_app
from services.memory.app.repository import InMemoryMemoryRepository


class FakeEmbedder:
    """Tiny deterministic embedder — same hashing idea as the real local backend."""

    dim = 16

    async def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            vec[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class RecordingPublisher:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish(self, topic: str, payload: dict) -> bool:
        self.events.append((topic, payload))
        return True


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def client(repo, publisher) -> httpx.AsyncClient:
    app = create_app(
        settings=Settings(_env_file=None, embedding_dim=FakeEmbedder.dim),
        repository=repo,
        embedder=FakeEmbedder(),
        publisher=publisher,
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
