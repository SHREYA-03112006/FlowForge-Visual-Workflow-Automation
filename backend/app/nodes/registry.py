"""Node-type registry. Handlers register themselves with @register."""
from __future__ import annotations

from .base import BaseNode, NodeConfigError

_REGISTRY: dict[str, BaseNode] = {}


def register(cls):
    if not cls.type:
        raise ValueError(f"{cls.__name__} has no 'type'")
    _REGISTRY[cls.type] = cls()
    return cls


def is_known_type(node_type: str | None) -> bool:
    return node_type in _REGISTRY


def get_handler(node_type: str) -> BaseNode:
    try:
        return _REGISTRY[node_type]
    except KeyError:
        raise NodeConfigError(f"Unknown node type '{node_type}'") from None


def list_node_types() -> list[dict]:
    order = {"trigger": 0, "action": 1, "logic": 2, "transform": 3, "ml": 4}
    return [h.meta() for h in sorted(_REGISTRY.values(), key=lambda h: (order.get(h.category, 9), h.label))]


# Config fields every node supports (retry / timeout), shown in the config panel.
COMMON_FIELDS = [
    {"name": "retries", "label": "Retries", "type": "number", "required": False, "default": 0,
     "options": [], "placeholder": "0", "help": "Extra attempts after a failure (max 10)"},
    {"name": "retry_delay_seconds", "label": "Retry delay (s)", "type": "number", "required": False,
     "default": 1, "options": [], "placeholder": "1", "help": "Wait before the first retry"},
    {"name": "retry_backoff", "label": "Retry backoff", "type": "number", "required": False,
     "default": 2, "options": [], "placeholder": "2", "help": "Delay multiplier per retry"},
    {"name": "timeout_seconds", "label": "Timeout (s)", "type": "number", "required": False,
     "default": 60, "options": [], "placeholder": "60", "help": "Max time for one attempt"},
]
