"""Best-effort flush of ended sessions into long-term memory.

Ending a session must never fail because the memory service is down —
the flush result is reported to the caller instead.
"""

import json
from typing import Protocol

from convmem_shared.http_client import ServiceClient, ServiceUnavailable
from convmem_shared.schemas import Session


class MemoryFlusher(Protocol):
    async def flush(self, session: Session) -> bool: ...


class HttpMemoryFlusher:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._client = ServiceClient(base_url, "memory", timeout=timeout)

    async def flush(self, session: Session) -> bool:
        try:
            resp = await self._client.post(
                "/api/v1/memories",
                json={
                    "session_id": session.session_id,
                    "role": "system",
                    "content": f"Session ended with state: {json.dumps(session.state)}",
                    "metadata": {"intent": "session_summary"},
                },
                headers={"X-User-ID": session.user_id},
            )
            return resp.status_code == 201
        except ServiceUnavailable:
            return False
