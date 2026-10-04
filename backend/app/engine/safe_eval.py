"""Tiny safe expression evaluator (no eval/exec) for map/filter/condition nodes.

Supports: literals, variables you pass in (e.g. item, index), + - * / // % **,
comparisons, and/or/not, `x if c else y`, indexing/slicing, list/dict/tuple
literals, a few builtin functions and string/dict methods. Anything else
(attribute access, imports, lambdas, comprehensions...) is rejected.
"""
from __future__ import annotations

import ast
import operator
from typing import Any

MAX_LEN = 500
MAX_SEQ = 100_000


class SafeEvalError(Exception):
    pass


_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_, ast.IsNot: operator.is_not,
}
_FUNCS = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool, "abs": abs,
    "round": round, "min": min, "max": max, "sum": sum, "sorted": sorted, "list": list,
}
_METHODS = {
    "lower", "upper", "strip", "lstrip", "rstrip", "startswith", "endswith", "title",
    "split", "replace", "join", "count", "get", "keys", "values", "items",
}


def safe_eval(expr: str, variables: dict[str, Any] | None = None) -> Any:
    if not isinstance(expr, str) or not expr.strip():
        raise SafeEvalError("Expression is empty")
    if len(expr) > MAX_LEN:
        raise SafeEvalError(f"Expression too long (max {MAX_LEN} characters)")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise SafeEvalError(f"Invalid expression: {e.msg}") from None
    try:
        return _ev(tree.body, variables or {})
    except SafeEvalError:
        raise
    except Exception as e:  # TypeError, KeyError, ZeroDivisionError...
        raise SafeEvalError(f"{type(e).__name__}: {e}") from None


def _ev(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise SafeEvalError(f"Unknown name '{node.id}' (available: {', '.join(sorted(env)) or 'none'})")
    if isinstance(node, ast.BinOp):
        op = _BIN.get(type(node.op))
        if not op:
            raise SafeEvalError("Unsupported operator")
        left, right = _ev(node.left, env), _ev(node.right, env)
        if isinstance(node.op, ast.Pow) and (not isinstance(right, (int, float)) or abs(right) > 100):
            raise SafeEvalError("Exponent too large")
        if isinstance(node.op, ast.Mult):
            for seq, n in ((left, right), (right, left)):
                if isinstance(seq, (str, list, tuple)) and isinstance(n, int) and len(seq) * max(n, 0) > MAX_SEQ:
                    raise SafeEvalError("Result too large")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        v = _ev(node.operand, env)
        if isinstance(node.op, ast.Not):
            return not v
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
        raise SafeEvalError("Unsupported unary operator")
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for v in node.values:
                result = _ev(v, env)
                if not result:
                    return result
            return result
        result = False
        for v in node.values:
            result = _ev(v, env)
            if result:
                return result
        return result
    if isinstance(node, ast.Compare):
        left = _ev(node.left, env)
        for op_node, comp in zip(node.ops, node.comparators):
            op = _CMP.get(type(op_node))
            if not op:
                raise SafeEvalError("Unsupported comparison")
            right = _ev(comp, env)
            if not op(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _ev(node.body, env) if _ev(node.test, env) else _ev(node.orelse, env)
    if isinstance(node, ast.Subscript):
        target = _ev(node.value, env)
        if isinstance(node.slice, ast.Slice):
            sl = slice(*(_ev(p, env) if p else None for p in (node.slice.lower, node.slice.upper, node.slice.step)))
            return target[sl]
        return target[_ev(node.slice, env)]
    if isinstance(node, (ast.List, ast.Tuple)):
        items = [_ev(e, env) for e in node.elts]
        return items if isinstance(node, ast.List) else tuple(items)
    if isinstance(node, ast.Dict):
        return {_ev(k, env): _ev(v, env) for k, v in zip(node.keys, node.values) if k is not None}
    if isinstance(node, ast.Call):
        if node.keywords:
            raise SafeEvalError("Keyword arguments are not supported")
        args = [_ev(a, env) for a in node.args]
        f = node.func
        if isinstance(f, ast.Name) and f.id in _FUNCS:
            return _FUNCS[f.id](*args)
        if isinstance(f, ast.Attribute) and f.attr in _METHODS:
            obj = _ev(f.value, env)
            if isinstance(obj, (str, dict, list)):
                return getattr(obj, f.attr)(*args)
        raise SafeEvalError("Function or method call not allowed")
    raise SafeEvalError(f"Unsupported syntax: {type(node).__name__}")
