"""Execution context: stores node outputs and resolves {{templates}}.

Template syntax
    {{trigger.field}}            data the run was started with (manual input / webhook body)
    {{node_id.output.field}}     output of an earlier node
    {{n2.output.items[0].name}}  list indexes work too
    {{trigger.name | default('anonymous')}}   fallback when the path is missing

If a string is *only* one template, the raw value is returned (lists stay lists,
numbers stay numbers). If the template is embedded in text, it is stringified.
"""
from __future__ import annotations

import ast
import json
import math
import re
from datetime import date, datetime
from typing import Any

from ..config import settings

_TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}", re.S)
_FULL_RE = re.compile(r"^\s*\{\{\s*(.+?)\s*\}\}\s*$", re.S)
_DEFAULT_RE = re.compile(r"^(.*?)\s*\|\s*default\((.*)\)\s*$", re.S)
_MISSING = object()

SENSITIVE_KEYS = {"authorization", "password", "passwd", "secret", "token", "api_key", "apikey", "x-api-key"}


class TemplateError(Exception):
    """A {{reference}} could not be resolved."""


class ExecutionContext:
    def __init__(self, trigger_data: Any = None, execution_id: int | None = None):
        if trigger_data is None:
            trigger_data = {}
        self.trigger_data: dict = trigger_data if isinstance(trigger_data, dict) else {"value": trigger_data}
        self.outputs: dict[str, Any] = {}
        self.execution_id = execution_id

    def set_output(self, node_id: str, output: Any) -> None:
        self.outputs[node_id] = output

    # ---- resolving -------------------------------------------------------
    def resolve(self, expr: str) -> Any:
        default: Any = _MISSING
        m = _DEFAULT_RE.match(expr)
        if m:
            expr = m.group(1).strip()
            default = _parse_literal(m.group(2))
        path = re.sub(r"\[(\d+)\]", r".\1", expr).strip(".")
        parts = [p for p in path.split(".") if p]
        if not parts:
            raise TemplateError("Empty template expression '{{}}'")
        try:
            root = parts[0]
            if root == "trigger":
                cur: Any = self.trigger_data
            elif root in self.outputs:
                cur = {"output": self.outputs[root]}
            else:
                raise TemplateError(f"Unknown reference '{root}' (node does not exist or has not run yet)")
            for p in parts[1:]:
                cur = _step(cur, p, expr)
            return cur
        except TemplateError:
            if default is not _MISSING:
                return default
            raise

    def render(self, value: Any, skip_keys: tuple[str, ...] = ()) -> Any:
        """Recursively resolve templates in strings / dicts / lists."""
        if isinstance(value, str):
            return self._render_str(value)
        if isinstance(value, dict):
            return {k: (v if k in skip_keys else self.render(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render(v) for v in value]
        return value

    def _render_str(self, s: str) -> Any:
        if "{{" not in s:
            return s
        m = _FULL_RE.match(s)
        if m and s.count("{{") == 1:
            return self.resolve(m.group(1))
        return _TEMPLATE_RE.sub(lambda mm: _stringify(self.resolve(mm.group(1))), s)


def _step(cur: Any, key: str, full_expr: str) -> Any:
    if isinstance(cur, dict) and key in cur:
        return cur[key]
    if isinstance(cur, (list, tuple)) and key.isdigit() and int(key) < len(cur):
        return cur[int(key)]
    raise TemplateError(f"Cannot find '{key}' while resolving '{{{{{full_expr}}}}}'")


def _parse_literal(text: str) -> Any:
    try:
        return ast.literal_eval(text.strip())
    except Exception:
        return text.strip()


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)


# ---- helpers used when storing / emitting data ---------------------------
def to_json_safe(obj: Any, max_str: int | None = None, _depth: int = 0) -> Any:
    """Convert arbitrary Python data into JSON-storable data (truncating long strings)."""
    limit = max_str or settings.max_log_string
    if _depth > 20:
        return "<max depth>"
    if obj is None or isinstance(obj, (bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, str):
        return obj if len(obj) <= limit else obj[:limit] + f"... [truncated {len(obj) - limit} chars]"
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v, limit, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(v, limit, _depth + 1) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"
    return to_json_safe(str(obj), limit, _depth + 1)


def redact(obj: Any) -> Any:
    """Mask values whose key looks like a credential before they are logged."""
    if isinstance(obj, dict):
        return {k: ("***" if str(k).lower() in SENSITIVE_KEYS else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str) and obj.lstrip().startswith("{"):   # JSON text typed into a config field
        try:
            parsed = json.loads(obj)
        except ValueError:
            return obj
        return redact(parsed) if isinstance(parsed, dict) else obj
    return obj
