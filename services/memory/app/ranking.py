"""Re-ranking of vector-search hits by similarity and recency.

pgvector returns nearest neighbours by cosine similarity alone; a memory from
ten minutes ago should usually beat an equally-similar one from last year.
The final score blends both:

    score = w_sim * similarity + w_rec * exp(-age / half_life)

Weights and half-life are settings, so operators can tune retrieval
behaviour without a deploy.
"""

import math
from datetime import datetime

from convmem_shared.schemas import Memory, ScoredMemory, utcnow


def recency_factor(
    created_at: datetime, half_life_seconds: float, now: datetime | None = None
) -> float:
    age = ((now or utcnow()) - created_at).total_seconds()
    if age <= 0:
        return 1.0
    return math.exp(-age * math.log(2) / half_life_seconds)


def rank(
    hits: list[tuple[Memory, float]],
    weight_similarity: float,
    weight_recency: float,
    half_life_seconds: float,
    now: datetime | None = None,
) -> list[ScoredMemory]:
    scored = [
        ScoredMemory(
            memory=memory,
            similarity=similarity,
            recency=(rec := recency_factor(memory.created_at, half_life_seconds, now)),
            score=weight_similarity * similarity + weight_recency * rec,
        )
        for memory, similarity in hits
    ]
    return sorted(scored, key=lambda s: s.score, reverse=True)
