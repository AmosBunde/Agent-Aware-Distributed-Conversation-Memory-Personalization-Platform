import httpx
import pytest

from services.gateway.app.config import Settings
from services.gateway.app.main import create_app, resolve_upstream


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def echo_transport(name: str, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(
            200,
            json={
                "upstream": name,
                "path": request.url.path,
                "user": request.headers.get("X-User-ID", ""),
            },
        )

    return httpx.MockTransport(handler)


def make_client(transports=None, settings=None, clock=None) -> httpx.AsyncClient:
    app = create_app(
        settings=settings or Settings(_env_file=None),
        transports=transports,
        clock=clock,
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize(
    ("path", "upstream"),
    [
        ("/api/v1/memories", "memory"),
        ("/api/v1/memories/u1/context", "memory"),
        ("/api/v1/sessions/sess-1", "session"),
        ("/api/v1/personalization/u1/profile", "personalization"),
        ("/api/v1/embed", "embedding"),
    ],
)
def test_route_table(path, upstream):
    assert resolve_upstream(path) == upstream


def test_unknown_route_is_none():
    assert resolve_upstream("/api/v1/unknown") is None


async def test_proxies_to_correct_upstream_with_headers():
    transports = {
        name: echo_transport(name) for name in ("memory", "session", "personalization", "embedding")
    }
    async with make_client(transports) as client:
        resp = await client.get("/api/v1/personalization/u1/profile", headers={"X-User-ID": "u1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["upstream"] == "personalization"
    assert body["path"] == "/api/v1/personalization/u1/profile"
    assert body["user"] == "u1"


async def test_rate_limit_returns_429():
    transports = {
        name: echo_transport(name) for name in ("memory", "session", "personalization", "embedding")
    }
    settings = Settings(_env_file=None, rate_limit_rps=1, rate_limit_burst=2)
    async with make_client(transports, settings, clock=FakeClock()) as client:
        codes = [
            (await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})).status_code
            for _ in range(3)
        ]
    assert codes == [200, 200, 429]


async def test_circuit_opens_after_repeated_upstream_failures():
    transports = {
        "memory": echo_transport("memory", fail=True),
        "session": echo_transport("session"),
        "personalization": echo_transport("personalization"),
        "embedding": echo_transport("embedding"),
    }
    settings = Settings(
        _env_file=None,
        circuit_failure_threshold=2,
        rate_limit_burst=100,
        rate_limit_rps=100,
    )
    async with make_client(transports, settings, clock=FakeClock()) as client:
        first = await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})
        second = await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})
        third = await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})
        healthy = await client.get("/api/v1/sessions/s1", headers={"X-User-ID": "u1"})

    assert (first.status_code, second.status_code) == (502, 502)
    assert third.status_code == 503  # circuit open: fail fast, no upstream call
    assert "circuit open" in third.json()["detail"]
    assert healthy.status_code == 200  # other upstreams unaffected


async def test_unknown_api_route_404():
    async with make_client() as client:
        resp = await client.get("/api/v1/nope", headers={"X-User-ID": "u1"})
    assert resp.status_code == 404


async def test_console_served_at_root():
    async with make_client() as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_api_key_required_when_configured():
    transports = {
        name: echo_transport(name) for name in ("memory", "session", "personalization", "embedding")
    }
    settings = Settings(_env_file=None, gateway_api_key="s3cret")
    async with make_client(transports, settings) as client:
        no_key = await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})
        wrong = await client.get(
            "/api/v1/memories/u1", headers={"X-User-ID": "u1", "X-API-Key": "nope"}
        )
        right = await client.get(
            "/api/v1/memories/u1", headers={"X-User-ID": "u1", "X-API-Key": "s3cret"}
        )
        console = await client.get("/")  # console itself stays reachable
    assert no_key.status_code == 401
    assert wrong.status_code == 401
    assert right.status_code == 200
    assert console.status_code == 200


async def test_no_api_key_configured_means_open():
    transports = {
        name: echo_transport(name) for name in ("memory", "session", "personalization", "embedding")
    }
    async with make_client(transports) as client:
        resp = await client.get("/api/v1/memories/u1", headers={"X-User-ID": "u1"})
    assert resp.status_code == 200
