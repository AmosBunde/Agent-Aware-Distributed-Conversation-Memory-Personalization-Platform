"""Shared fixtures for integration and e2e suites.

These suites talk to a running stack (`make dev`). URLs are overridable so
the same tests run against compose locally, CI, or a remote environment.
"""

import os
import uuid

import httpx
import pytest

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
MEMORY_URL = os.environ.get("MEMORY_URL", "http://localhost:8001")
PERSONALIZATION_URL = os.environ.get("PERSONALIZATION_URL", "http://localhost:8002")
SESSION_URL = os.environ.get("SESSION_URL", "http://localhost:8004")


@pytest.fixture
def user_id() -> str:
    """Unique per test, so tests and reruns never see each other's data."""
    return f"it-user-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def gateway() -> httpx.Client:
    with httpx.Client(base_url=GATEWAY_URL, timeout=30) as client:
        yield client
