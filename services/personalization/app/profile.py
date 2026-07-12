"""Profile aggregation: raw history + explicit signals → UserProfile."""

from collections import Counter

from convmem_shared.schemas import Memory, PreferenceSignal, UserProfile


def build_profile(
    user_id: str,
    memories: list[Memory],
    signals: list[PreferenceSignal],
    top_intents: int = 5,
) -> UserProfile:
    intent_counts = Counter(str(m.metadata["intent"]) for m in memories if "intent" in m.metadata)
    created = [m.created_at for m in memories]
    # Explicit signals win; strength orders them so a stronger signal for the
    # same key overwrites a weaker duplicate deterministically.
    preferences = {s.key: s.value for s in sorted(signals, key=lambda s: s.strength)}
    return UserProfile(
        user_id=user_id,
        preferences=preferences,
        top_intents=[intent for intent, _ in intent_counts.most_common(top_intents)],
        memory_count=len(memories),
        first_seen=min(created) if created else None,
        last_seen=max(created) if created else None,
    )
