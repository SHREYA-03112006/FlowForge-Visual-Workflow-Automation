from ...engine.safe_eval import SafeEvalError, safe_eval
from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, as_list, field_spec
from ..registry import register

MAX_ITEMS = 10_000


@register
class MapNode(BaseNode):
    type = "map"
    category = "transform"
    label = "Map (Transform List)"
    description = "Applies an expression to every item. Variables: item, index. Output: {items, count}."
    fields = [
        field_spec("source", "List", required=True, placeholder="{{n2.output.numbers}}"),
        field_spec("expression", "Expression", required=True, default="item",
                   placeholder="item['price'] * 2   or   item.upper()"),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        items = as_list(config.get("source"))
        if len(items) > MAX_ITEMS:
            raise NodeConfigError(f"List too large (max {MAX_ITEMS} items)")
        expr = str(config.get("expression") or "item")
        try:
            out = [safe_eval(expr, {"item": it, "index": i}) for i, it in enumerate(items)]
        except SafeEvalError as e:
            raise NodeConfigError(f"Expression error: {e}") from None
        return NodeResult(output={"items": out, "count": len(out)}, message=f"Mapped {len(out)} item(s)")
