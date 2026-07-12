import httpx
from convmem_shared.health import health_router
from fastapi import FastAPI


def make_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_healthz_ok_with_no_checks():
    app = FastAPI()
    app.include_router(health_router("demo"))
    async with make_client(app) as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "demo"
    assert body["status"] == "ok"


async def test_healthz_degraded_when_a_dependency_fails():
    async def up() -> bool:
        return True

    async def down() -> bool:
        raise ConnectionError("boom")

    app = FastAPI()
    app.include_router(health_router("demo", checks={"redis": up, "postgres": down}))
    async with make_client(app) as client:
        body = (await client.get("/healthz")).json()
    assert body["status"] == "degraded"
    assert body["dependencies"] == {"redis": "ok", "postgres": "down"}
