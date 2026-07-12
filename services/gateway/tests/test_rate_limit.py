from services.gateway.app.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_burst_allows_then_blocks():
    clock = FakeClock()
    limiter = RateLimiter(rps=1, burst=3, clock=clock)
    assert [limiter.allow("u1") for _ in range(4)] == [True, True, True, False]


def test_tokens_refill_over_time():
    clock = FakeClock()
    limiter = RateLimiter(rps=2, burst=2, clock=clock)
    assert limiter.allow("u1") and limiter.allow("u1")
    assert not limiter.allow("u1")
    clock.now += 0.5  # refills one token at 2 rps
    assert limiter.allow("u1")
    assert not limiter.allow("u1")


def test_users_have_independent_buckets():
    limiter = RateLimiter(rps=1, burst=1, clock=FakeClock())
    assert limiter.allow("u1")
    assert not limiter.allow("u1")
    assert limiter.allow("u2")


def test_tokens_cap_at_burst():
    clock = FakeClock()
    limiter = RateLimiter(rps=100, burst=2, clock=clock)
    clock.now += 60  # long idle must not accumulate more than burst
    assert [limiter.allow("u1") for _ in range(3)] == [True, True, False]
