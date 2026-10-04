"""Retry policy. Any node can set in its config:
    retries (0-10), retry_delay_seconds (default 1), retry_backoff (default 2.0)
Delay for attempt n = delay * backoff^(n-1), capped at 60s.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..nodes.base import NodeConfigError

MAX_RETRIES = 10


def _num(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    delay: float = 1.0
    backoff: float = 2.0
    max_delay: float = 60.0

    @classmethod
    def from_config(cls, config: dict) -> "RetryPolicy":
        retries = int(min(max(_num(config.get("retries"), 0), 0), MAX_RETRIES))
        delay = min(max(_num(config.get("retry_delay_seconds"), 1.0), 0.0), 60.0)
        backoff = min(max(_num(config.get("retry_backoff"), 2.0), 1.0), 10.0)
        return cls(max_attempts=retries + 1, delay=delay, backoff=backoff)

    def delay_for(self, attempt: int) -> float:
        return min(self.delay * (self.backoff ** (attempt - 1)), self.max_delay)


def is_retryable(exc: BaseException) -> bool:
    """Bad configuration will never succeed on retry; everything else may."""
    return not isinstance(exc, NodeConfigError)
