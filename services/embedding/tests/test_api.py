import httpx

from services.embedding.app.main import app


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_embed_endpoint_returns_vectors():
    async with make_client() as client:
        resp = await client.post("/api/v1/embed", json={"texts": ["hello world", "goodbye"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "local"
    assert body["dim"] == 384
    assert len(body["vectors"]) == 2
    assert len(body["vectors"][0]) == 384


async def test_embed_rejects_empty_batch():
    async with make_client() as client:
        resp = await client.post("/api/v1/embed", json={"texts": []})
    assert resp.status_code == 422


async def test_healthz():
    async with make_client() as client:
        resp = await client.get("/healthz")
    assert resp.json()["service"] == "embedding"
    assert resp.json()["status"] == "ok"
