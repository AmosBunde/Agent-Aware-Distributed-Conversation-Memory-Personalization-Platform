"""Metrics and tracing for every service.

``instrument(app, service_name)`` adds:

- Prometheus metrics: ``http_requests_total`` and
  ``http_request_duration_seconds`` labelled by service, method, and the
  *route template* (``/api/v1/memories/{user_id}`` — never the raw path, so
  label cardinality stays bounded), served at ``/metrics``.
- OpenTelemetry tracing, only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set:
  FastAPI server spans plus httpx client spans, so one request traces
  across the gateway → service → dependency chain. Without the env var
  (or the optional otel packages), tracing is a silent no-op.
"""

import os
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests processed",
    ["service", "method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
)


def instrument(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        if path != "/metrics":
            HTTP_REQUESTS.labels(
                service_name, request.method, path, str(response.status_code)
            ).inc()
            HTTP_LATENCY.labels(service_name, request.method, path).observe(
                time.perf_counter() - start
            )
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    _setup_tracing(app, service_name)


def _setup_tracing(app: FastAPI, service_name: str) -> None:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return  # otel packages not installed; metrics still work

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
