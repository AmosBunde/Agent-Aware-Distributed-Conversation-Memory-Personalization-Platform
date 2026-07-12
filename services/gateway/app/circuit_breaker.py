"""Per-upstream circuit breaker.

closed → (N consecutive failures) → open → (cooldown elapses) → half-open,
where a single probe decides: success closes the circuit, failure re-opens
it. While open, calls fail fast without touching the upstream.
"""

import time
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, upstream: str):
        self.upstream = upstream
        super().__init__(f"circuit open for {upstream}")


class CircuitBreaker:
    def __init__(
        self,
        upstream: str,
        failure_threshold: int = 5,
        reset_seconds: float = 30.0,
        clock=time.monotonic,
    ):
        self.upstream = upstream
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    @property
    def state(self) -> CircuitState:
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock() - self._opened_at >= self.reset_seconds:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def before_request(self) -> None:
        state = self.state
        if state is CircuitState.OPEN:
            raise CircuitOpenError(self.upstream)
        if state is CircuitState.HALF_OPEN:
            if self._probing:
                raise CircuitOpenError(self.upstream)  # one probe at a time
            self._probing = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._probing = False

    def record_failure(self) -> None:
        self._probing = False
        if self._opened_at is not None:
            # Failed probe while half-open: restart the cooldown.
            self._opened_at = self._clock()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
