from pathlib import Path

import httpx
from convmem_shared.observability import instrument
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .config import Settings, get_settings
from .rate_limit import RateLimiter

STATIC_DIR = Path(__file__).parent / "static"

# Longest prefix wins; order here is documentation, matching is by prefix length.
ROUTE_TABLE: list[tuple[str, str]] = [
    ("/api/v1/memories", "memory"),
    ("/api/v1/sessions", "session"),
    ("/api/v1/personalization", "personalization"),
    ("/api/v1/embed", "embedding"),
]

# Hop-by-hop headers must not be forwarded either direction.
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def resolve_upstream(path: str) -> str | None:
    matches = [(prefix, name) for prefix, name in ROUTE_TABLE if path.startswith(prefix)]
    if not matches:
        return None
    return max(matches, key=lambda m: len(m[0]))[1]


def create_app(
    settings: Settings | None = None,
    transports: dict[str, httpx.AsyncBaseTransport] | None = None,
    clock=None,
) -> FastAPI:
    """Gateway app factory.

    ``transports`` lets tests wire httpx.MockTransport per upstream;
    production uses real network transports against the configured URLs.
    """
    settings = settings or get_settings()

    upstream_urls = {
        "memory": settings.memory_service_url,
        "session": settings.session_service_url,
        "personalization": settings.personalization_service_url,
        "embedding": settings.embedding_service_url,
    }
    clients = {
        name: httpx.AsyncClient(
            base_url=url,
            timeout=settings.http_timeout_seconds,
            transport=(transports or {}).get(name),
        )
        for name, url in upstream_urls.items()
    }
    limiter_kwargs = {"clock": clock} if clock else {}
    limiter = RateLimiter(settings.rate_limit_rps, settings.rate_limit_burst, **limiter_kwargs)
    breakers = {
        name: CircuitBreaker(
            name,
            settings.circuit_failure_threshold,
            settings.circuit_reset_seconds,
            **limiter_kwargs,
        )
        for name in upstream_urls
    }

    app = FastAPI(title="Conversation Memory Platform — API Gateway", version="0.1.0")
    instrument(app, settings.service_name)
    app.state.breakers = breakers

    @app.get("/", include_in_schema=False)
    async def console() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        upstreams: dict[str, dict] = {}
        healthy = True
        for name, client in clients.items():
            entry: dict = {"circuit": breakers[name].state.value}
            try:
                resp = await client.get("/healthz")
                entry["status"] = resp.json().get("status", "unknown")
            except Exception:
                entry["status"] = "down"
            healthy = healthy and entry["status"] == "ok"
            upstreams[name] = entry
        return JSONResponse(
            {
                "service": "gateway",
                "status": "ok" if healthy else "degraded",
                "upstreams": upstreams,
            },
            status_code=200 if healthy else 503,
        )

    @app.api_route(
        "/api/v1/{rest:path}",
        methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        include_in_schema=False,
    )
    async def proxy(request: Request, rest: str) -> Response:
        path = f"/api/v1/{rest}"
        upstream = resolve_upstream(path)
        if upstream is None:
            return JSONResponse({"detail": "unknown route"}, status_code=404)

        if (
            settings.gateway_api_key
            and request.headers.get("X-API-Key") != settings.gateway_api_key
        ):
            return JSONResponse(
                {"detail": "missing or invalid API key (X-API-Key header)"},
                status_code=401,
            )

        user_id = request.headers.get(
            "X-User-ID", request.client.host if request.client else "anonymous"
        )
        if not limiter.allow(user_id):
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "1"},
            )

        breaker = breakers[upstream]
        try:
            breaker.before_request()
        except CircuitOpenError:
            return JSONResponse(
                {"detail": f"{upstream} temporarily unavailable (circuit open)"},
                status_code=503,
            )

        headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
        try:
            upstream_resp = await clients[upstream].request(
                request.method,
                path,
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
        except httpx.HTTPError:
            breaker.record_failure()
            return JSONResponse({"detail": f"{upstream} unreachable"}, status_code=502)

        if upstream_resp.status_code >= 500:
            breaker.record_failure()
        else:
            breaker.record_success()

        response_headers = {
            k: v for k, v in upstream_resp.headers.items() if k.lower() not in _HOP_BY_HOP
        }
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=response_headers,
        )

    return app


app = create_app()
