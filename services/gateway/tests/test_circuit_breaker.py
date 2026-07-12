import pytest

from services.gateway.app.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_breaker(clock, threshold=3, reset=30.0):
    return CircuitBreaker("memory", threshold, reset, clock=clock)


def trip(breaker, times):
    for _ in range(times):
        breaker.record_failure()


def test_opens_after_threshold_failures():
    breaker = make_breaker(FakeClock())
    trip(breaker, 2)
    assert breaker.state is CircuitState.CLOSED
    trip(breaker, 1)
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.before_request()


def test_success_resets_failure_count():
    breaker = make_breaker(FakeClock())
    trip(breaker, 2)
    breaker.record_success()
    trip(breaker, 2)
    assert breaker.state is CircuitState.CLOSED


def test_half_open_after_cooldown_then_closes_on_success():
    clock = FakeClock()
    breaker = make_breaker(clock, reset=30.0)
    trip(breaker, 3)
    clock.now += 31
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_request()  # probe allowed
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED


def test_half_open_allows_single_probe():
    clock = FakeClock()
    breaker = make_breaker(clock, reset=30.0)
    trip(breaker, 3)
    clock.now += 31
    breaker.before_request()
    with pytest.raises(CircuitOpenError):
        breaker.before_request()  # concurrent second probe rejected


def test_failed_probe_reopens_with_fresh_cooldown():
    clock = FakeClock()
    breaker = make_breaker(clock, reset=30.0)
    trip(breaker, 3)
    clock.now += 31
    breaker.before_request()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    clock.now += 29
    assert breaker.state is CircuitState.OPEN
    clock.now += 2
    assert breaker.state is CircuitState.HALF_OPEN
