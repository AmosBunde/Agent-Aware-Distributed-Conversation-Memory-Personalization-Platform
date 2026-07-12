"""Standard health endpoint mounted by every service."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter

DependencyCheck = Callable[[], Awaitable[bool]]


def health_router(
    service_name: str,
    version: str = "0.1.0",
    checks: dict[str, DependencyCheck] | None = None,
) -> APIRouter:
    """Build a ``/healthz`` router.

    ``checks`` maps dependency names to async probes; the endpoint reports
    per-dependency status and is only ``ok`` when every probe passes.
    """
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict:
        dependencies: dict[str, str] = {}
        healthy = True
        for name, probe in (checks or {}).items():
            try:
                up = await probe()
            except Exception:
                up = False
            dependencies[name] = "ok" if up else "down"
            healthy = healthy and up
        return {
            "service": service_name,
            "version": version,
            "status": "ok" if healthy else "degraded",
            "dependencies": dependencies,
        }

    return router
