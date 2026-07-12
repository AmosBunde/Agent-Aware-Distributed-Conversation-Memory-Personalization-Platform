import httpx
import pytest
from convmem_shared.schemas import Memory, ScoredMemory

from services.personalization.app.config import Settings
from services.personalization.app.main import create_app
from services.personalization.app.signals import InMemorySignalStore


class FakeMemoryGateway:
    """Serves canned memories; flips to 'down' mode to test degradation."""

    def __init__(self, memories: list[Memory] | None = None, down: bool = False):
        self.memories = memories or []
        self.down = down

    async def recent_memories(self, user_id: str, limit: int) -> list[Memory]:
        if self.down:
            return []
        return [m for m in self.memories if m.user_id == user_id][:limit]

    async def search_context(self, user_id: str, query: str, top_k: int) -> list[ScoredMemory]:
        if self.down:
            return []
        hits = [m for m in self.memories if m.user_id == user_id][:top_k]
        return [ScoredMemory(memory=m, similarity=0.9, recency=1.0, score=0.925) for m in hits]


def make_memory(content: str, intent: str | None = None, user_id: str = "u1") -> Memory:
    metadata = {"intent": intent} if intent else {}
    return Memory(user_id=user_id, session_id="s1", role="user", content=content, metadata=metadata)


@pytest.fixture
def gateway() -> FakeMemoryGateway:
    return FakeMemoryGateway(
        memories=[
            make_memory("help me debug asyncio", intent="coding_help"),
            make_memory("review my python PR", intent="coding_help"),
            make_memory("I prefer concise answers", intent="preference_setting"),
        ]
    )


@pytest.fixture
def client(gateway) -> httpx.AsyncClient:
    app = create_app(
        settings=Settings(_env_file=None),
        signal_store=InMemorySignalStore(),
        memory_gateway=gateway,
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
