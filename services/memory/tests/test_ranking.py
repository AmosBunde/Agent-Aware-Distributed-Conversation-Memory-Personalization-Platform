from datetime import timedelta

from convmem_shared.schemas import Memory, utcnow

from services.memory.app.ranking import rank, recency_factor

HALF_LIFE = 3600.0  # 1 hour, for readable tests


def make_memory(content: str, age_seconds: float) -> Memory:
    return Memory(
        user_id="u1",
        session_id="s1",
        role="user",
        content=content,
        created_at=utcnow() - timedelta(seconds=age_seconds),
    )


def test_recency_factor_halves_every_half_life():
    now = utcnow()
    fresh = recency_factor(now, HALF_LIFE, now=now)
    one_half_life = recency_factor(now - timedelta(seconds=HALF_LIFE), HALF_LIFE, now=now)
    two_half_lives = recency_factor(now - timedelta(seconds=2 * HALF_LIFE), HALF_LIFE, now=now)
    assert fresh == 1.0
    assert abs(one_half_life - 0.5) < 1e-9
    assert abs(two_half_lives - 0.25) < 1e-9


def test_recency_breaks_similarity_ties():
    old = make_memory("same similarity, old", age_seconds=10 * HALF_LIFE)
    new = make_memory("same similarity, new", age_seconds=0)
    ranked = rank(
        [(old, 0.9), (new, 0.9)],
        weight_similarity=0.75,
        weight_recency=0.25,
        half_life_seconds=HALF_LIFE,
    )
    assert ranked[0].memory.id == new.id


def test_high_similarity_beats_recency():
    similar_old = make_memory("very similar but old", age_seconds=10 * HALF_LIFE)
    dissimilar_new = make_memory("fresh but unrelated", age_seconds=0)
    ranked = rank(
        [(similar_old, 0.95), (dissimilar_new, 0.05)],
        weight_similarity=0.75,
        weight_recency=0.25,
        half_life_seconds=HALF_LIFE,
    )
    assert ranked[0].memory.id == similar_old.id


def test_scores_expose_their_breakdown():
    m = make_memory("x", age_seconds=0)
    [scored] = rank(
        [(m, 0.8)], weight_similarity=0.75, weight_recency=0.25, half_life_seconds=HALF_LIFE
    )
    assert scored.similarity == 0.8
    assert 0.99 <= scored.recency <= 1.0
    assert abs(scored.score - (0.75 * 0.8 + 0.25 * scored.recency)) < 1e-9
