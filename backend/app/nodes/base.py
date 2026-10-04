"""Base class and helpers shared by every node handler."""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any, ClassVar


class NodeError(Exception):
    """Runtime failure inside a node (will be retried if retries are configured)."""


class NodeConfigError(NodeError):
    """The node is misconfigured. Never retried."""


@dataclass
class NodeResult:
    output: Any
    branch: str | None = None     # which outgoing handle to follow (condition/switch)
    message: str | None = None    # short human-readable summary shown in the logs


@dataclass
class NodeRun:
    node_id: str
    inputs: dict                  # {parent_node_id: parent_output} for active parents
    ctx: Any                      # ExecutionContext
    attempt: int = 1
    trigger_type: str = "manual"


def field_spec(name: str, label: str | None = None, type: str = "text", required: bool = False,
               default: Any = None, options: list | None = None, placeholder: str = "", help: str = "") -> dict:
    """Describes one config field; the frontend builds the config form from this."""
    return {"name": name, "label": label or name.replace("_", " ").title(), "type": type,
            "required": required, "default": default, "options": options or [],
            "placeholder": placeholder, "help": help}


class BaseNode:
    type: ClassVar[str] = ""
    category: ClassVar[str] = ""          # trigger | action | logic | transform | ml
    label: ClassVar[str] = ""
    description: ClassVar[str] = ""
    fields: ClassVar[list[dict]] = []
    no_render: ClassVar[tuple[str, ...]] = ()   # config keys NOT template-rendered (e.g. code)
    branches: ClassVar[list[str]] = []          # fixed output handles, e.g. ["true", "false"]
    dynamic_branches: ClassVar[bool] = False    # handles depend on config (switch)

    def check_config(self, config: dict) -> None:
        for f in self.fields:
            if f.get("required") and config.get(f["name"]) in (None, ""):
                raise NodeConfigError(f"'{f['label']}' is required")

    async def execute(self, config: dict, run: NodeRun) -> NodeResult:  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def meta(cls) -> dict:
        return {"type": cls.type, "category": cls.category, "label": cls.label,
                "description": cls.description, "fields": cls.fields,
                "branches": cls.branches, "dynamic_branches": cls.dynamic_branches}


# ---- config helpers -------------------------------------------------------
def as_dict(value: Any, name: str = "value") -> dict:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise NodeConfigError(f"{name} must be valid JSON: {e.msg}") from None
        if isinstance(parsed, dict):
            return parsed
    raise NodeConfigError(f"{name} must be a JSON object")


def as_json_value(value: Any) -> Any:
    """Return parsed JSON if value is a JSON string, else value unchanged."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def as_list(value: Any, name: str = "source") -> list:
    value = as_json_value(value)
    if isinstance(value, list):
        return value
    raise NodeConfigError(f"{name} must be a list (got {type(value).__name__})")


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_integration(module_path: str):
    """Import an integration module lazily so the engine works without it."""
    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise NodeConfigError(
            f"Integration '{module_path}' could not be imported ({e}). "
            f"Make sure the api_integrations / ml_model_train folders exist."
        ) from None
