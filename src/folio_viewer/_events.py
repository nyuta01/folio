"""In-process pub/sub for Phase 5 V6 SSE streaming.

The bus is intentionally tiny: one ``asyncio.Queue`` per subscriber
with a fixed maxsize so a slow client cannot pin memory. Multi-process
coordination is out of scope for Phase 5 — when the Viewer ever moves
to a multi-worker deployment the wire format stays the same and the
bus can be backed by Redis pub/sub or Postgres LISTEN/NOTIFY.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any


class EventBus:
    """Bounded in-process pub/sub used by ``GET /events``."""

    def __init__(self, *, queue_size: int = 64) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._queue_size = queue_size

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def publish(self, event: dict[str, Any]) -> None:
        """Broadcast ``event`` to every subscriber. Drops oldest on overflow."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Subscriber is wedged; skip rather than block the
                    # publisher. The keepalive frame on the SSE side
                    # eventually shakes it loose.
                    pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


def make_event(kind: str, **payload: Any) -> dict[str, Any]:
    """Construct the canonical event envelope.

    Every event carries ``kind`` (e.g., ``materialize.start``) and a
    UTC ISO-8601 ``ts`` so consumers can filter and order without
    relying on stream order.
    """
    return {
        "kind": kind,
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


__all__ = ["EventBus", "make_event"]
