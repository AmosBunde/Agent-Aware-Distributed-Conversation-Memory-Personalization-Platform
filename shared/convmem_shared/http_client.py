"""Thin async HTTP client for service-to-service calls.

Adds the two things every internal call needs — a bounded timeout and simple
retry with backoff — without hiding httpx underneath.
"""

import asyncio

import httpx


class ServiceUnavailable(Exception):
    """Raised when an upstream service cannot be reached after retries."""

    def __init__(self, service: str, detail: str):
        self.service = service
        super().__init__(f"{service} unavailable: {detail}")


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        service: str,
        timeout: float = 10.0,
        retries: int = 2,
        backoff_seconds: float = 0.2,
    ):
        self.service = service
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return await self._client.request(method, path, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff_seconds * (2**attempt))
        raise ServiceUnavailable(self.service, str(last_error))

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()
