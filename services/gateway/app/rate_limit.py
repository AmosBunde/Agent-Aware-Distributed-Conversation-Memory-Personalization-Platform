"""Per-user token-bucket rate limiting.

Each user gets a bucket of ``burst`` tokens refilled at ``rps`` tokens per
second. The clock is injectable so tests can verify refill behaviour without
sleeping.
"""

import time


class RateLimiter:
    def __init__(self, rps: float, burst: int, clock=time.monotonic):
        self.rps = rps
        self.burst = burst
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # user -> (tokens, last_refill)

    def allow(self, user_id: str) -> bool:
        now = self._clock()
        tokens, last = self._buckets.get(user_id, (float(self.burst), now))
        tokens = min(float(self.burst), tokens + (now - last) * self.rps)
        if tokens < 1.0:
            self._buckets[user_id] = (tokens, now)
            return False
        self._buckets[user_id] = (tokens - 1.0, now)
        return True
