import httpx
import pytest
from convmem_shared.http_client import ServiceClient, ServiceUnavailable


async def test_retries_then_succeeds():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"ok": True})

    client = ServiceClient("http://svc", "svc", retries=2, backoff_seconds=0)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://svc"
    )
    resp = await client.get("/ping")
    assert resp.json() == {"ok": True}
    assert attempts == 3


async def test_raises_service_unavailable_after_exhausting_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = ServiceClient("http://svc", "memory", retries=1, backoff_seconds=0)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://svc"
    )
    with pytest.raises(ServiceUnavailable) as exc:
        await client.get("/ping")
    assert exc.value.service == "memory"
