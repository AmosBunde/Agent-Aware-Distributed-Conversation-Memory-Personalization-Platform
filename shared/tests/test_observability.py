import httpx
from convmem_shared.observability import instrument
from fastapi import FastAPI


def make_app(service: str) -> FastAPI:
    app = FastAPI()
    instrument(app, service)

    @app.get("/api/v1/things/{thing_id}")
    async def get_thing(thing_id: str) -> dict:
        return {"thing_id": thing_id}

    return app


def make_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_metrics_use_route_template_not_raw_path():
    app = make_app("obs-template-test")
    async with make_client(app) as client:
        await client.get("/api/v1/things/abc-123")
        body = (await client.get("/metrics")).text
    assert (
        'http_requests_total{method="GET",path="/api/v1/things/{thing_id}",'
        'service="obs-template-test",status="200"}' in body
    )
    assert "abc-123" not in body  # raw path values must never become labels


async def test_latency_histogram_recorded():
    app = make_app("obs-latency-test")
    async with make_client(app) as client:
        await client.get("/api/v1/things/x")
        body = (await client.get("/metrics")).text
    assert (
        'http_request_duration_seconds_count{method="GET",'
        'path="/api/v1/things/{thing_id}",service="obs-latency-test"} 1.0' in body
    )


async def test_metrics_endpoint_does_not_count_itself():
    app = make_app("obs-self-test")
    async with make_client(app) as client:
        await client.get("/metrics")
        body = (await client.get("/metrics")).text
    assert 'path="/metrics"' not in body
