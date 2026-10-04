import re
from typing import Any

from ...engine.safe_eval import SafeEvalError, safe_eval
from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, field_spec
from ..registry import register

OPERATORS = ["==", "!=", ">", "<", ">=", "<=", "contains", "not_contains", "starts_with",
             "ends_with", "matches_regex", "is_empty", "is_not_empty", "is_true", "is_false"]


def _num(x: Any):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.strip())
        except ValueError:
            return None
    return None


def _s(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    return "" if x is None else str(x)


def values_equal(a: Any, b: Any) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return na == nb
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return a == b
    return _s(a) == _s(b)


def _is_empty(x: Any) -> bool:
    return x is None or (isinstance(x, (str, list, dict, tuple)) and len(x) == 0)


def compare(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return values_equal(left, right)
    if op == "!=":
        return not values_equal(left, right)
    if op in (">", "<", ">=", "<="):
        nl, nr = _num(left), _num(right)
        a, b = (nl, nr) if nl is not None and nr is not None else (_s(left), _s(right))
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]
    if op in ("contains", "not_contains"):
        if isinstance(left, (list, tuple)):
            hit = any(values_equal(i, right) for i in left)
        elif isinstance(left, dict):
            hit = _s(right) in {str(k) for k in left}
        else:
            hit = _s(right) in _s(left)
        return hit if op == "contains" else not hit
    if op == "starts_with":
        return _s(left).startswith(_s(right))
    if op == "ends_with":
        return _s(left).endswith(_s(right))
    if op == "matches_regex":
        try:
            return re.search(_s(right)[:200], _s(left)[:10000]) is not None
        except re.error as e:
            raise NodeConfigError(f"Invalid regex: {e}") from None
    if op == "is_empty":
        return _is_empty(left)
    if op == "is_not_empty":
        return not _is_empty(left)
    if op == "is_true":
        return left is True or _s(left).lower() in ("true", "1", "yes")
    if op == "is_false":
        return left is False or _s(left).lower() in ("false", "0", "no", "")
    raise NodeConfigError(f"Unknown operator '{op}'")


@register
class ConditionNode(BaseNode):
    type = "condition"
    category = "logic"
    label = "Condition (If/Else)"
    description = "Routes the flow down the 'true' or 'false' handle."
    branches = ["true", "false"]
    fields = [
        field_spec("left", "Value", placeholder="{{n2.output.body.userId}}"),
        field_spec("operator", "Operator", "select", default="==", options=OPERATORS),
        field_spec("right", "Compare to", placeholder="1"),
        field_spec("expression", "Or safe expression", "text",
                   help="Optional. If set it replaces the fields above. Variables: inputs, trigger. "
                        "Example: inputs['n2']['status_code'] == 200"),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        expr = config.get("expression")
        if expr not in (None, ""):
            try:
                result = bool(safe_eval(str(expr), {"inputs": run.inputs, "trigger": run.ctx.trigger_data}))
            except SafeEvalError as e:
                raise NodeConfigError(f"Expression error: {e}") from None
            detail = f"expression -> {result}"
        else:
            op = str(config.get("operator") or "==")
            if op not in OPERATORS:
                raise NodeConfigError(f"Unknown operator '{op}'")
            left, right = config.get("left"), config.get("right")
            result = compare(left, op, right)
            detail = f"{_s(left)!r} {op} {_s(right)!r} -> {result}"
        return NodeResult(output={"result": result}, branch="true" if result else "false", message=detail)
