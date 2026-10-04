"""In-process pub/sub used to stream live execution updates to WebSocket clients."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class EventBus:
    def __init__(self):
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, execution_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[execution_id].add(q)
        return q

    def unsubscribe(self, execution_id: int, q: asyncio.Queue) -> None:
        self._subs[execution_id].discard(q)
        if not self._subs[execution_id]:
            self._subs.pop(execution_id, None)

    def publish(self, execution_id: int, event: dict[str, Any]) -> None:
        for q in list(self._subs.get(execution_id, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow client: drop; it can re-fetch the execution over REST


bus = EventBus()
