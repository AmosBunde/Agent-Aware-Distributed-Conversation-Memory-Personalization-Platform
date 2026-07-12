import pytest
from convmem_shared.schemas import Memory, MemoryCreate, PreferenceSignal, ScoredMemory
from pydantic import ValidationError


def test_memory_create_rejects_bad_role():
    with pytest.raises(ValidationError):
        MemoryCreate(session_id="s", role="robot", content="hi")


def test_memory_create_rejects_empty_content():
    with pytest.raises(ValidationError):
        MemoryCreate(session_id="s", role="user", content="")


def test_memory_defaults_are_generated():
    m = Memory(user_id="u1", session_id="s1", role="user", content="hello")
    assert m.id is not None
    assert m.created_at.tzinfo is not None
    assert m.metadata == {}


def test_scored_memory_round_trip():
    m = Memory(user_id="u1", session_id="s1", role="user", content="hello")
    scored = ScoredMemory(memory=m, similarity=0.9, recency=0.5, score=0.78)
    dumped = scored.model_dump(mode="json")
    assert ScoredMemory.model_validate(dumped) == scored


def test_preference_signal_strength_bounds():
    with pytest.raises(ValidationError):
        PreferenceSignal(key="tone", value="concise", strength=1.5)
