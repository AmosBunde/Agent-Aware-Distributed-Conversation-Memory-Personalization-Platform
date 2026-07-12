from convmem_shared.schemas import PreferenceSignal

from services.personalization.app.profile import build_profile
from services.personalization.tests.conftest import make_memory


def test_top_intents_ordered_by_frequency():
    memories = [
        make_memory("a", intent="coding_help"),
        make_memory("b", intent="coding_help"),
        make_memory("c", intent="preference_setting"),
    ]
    profile = build_profile("u1", memories, signals=[])
    assert profile.top_intents == ["coding_help", "preference_setting"]
    assert profile.memory_count == 3


def test_explicit_signals_become_preferences():
    signals = [
        PreferenceSignal(key="tone", value="concise", strength=1.0),
        PreferenceSignal(key="language", value="python", strength=0.8),
    ]
    profile = build_profile("u1", [], signals)
    assert profile.preferences == {"tone": "concise", "language": "python"}


def test_empty_history_yields_empty_profile():
    profile = build_profile("u1", [], [])
    assert profile.memory_count == 0
    assert profile.first_seen is None and profile.last_seen is None
    assert profile.top_intents == []


def test_first_and_last_seen_span_history():
    memories = [make_memory("a"), make_memory("b")]
    profile = build_profile("u1", memories, [])
    assert profile.first_seen == min(m.created_at for m in memories)
    assert profile.last_seen == max(m.created_at for m in memories)
