from ...engine.safe_eval import SafeEvalError, safe_eval
from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, as_list, field_spec
from ..registry import register
from .map_node import MAX_ITEMS


@register
class FilterNode(BaseNode):
    type = "filter"
    category = "transform"
    label = "Filter List"
    description = "Keeps items where the condition is true. Variables: item, index. Output: {items, count}."
    fields = [
        field_spec("source", "List", required=True, placeholder="{{n2.output.items}}"),
        field_spec("condition", "Condition", required=True, placeholder="item % 2 == 0   or   item['age'] >= 18"),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        items = as_list(config.get("source"))
        if len(items) > MAX_ITEMS:
            raise NodeConfigError(f"List too large (max {MAX_ITEMS} items)")
        cond = str(config["condition"])
        try:
            kept = [it for i, it in enumerate(items) if safe_eval(cond, {"item": it, "index": i})]
        except SafeEvalError as e:
            raise NodeConfigError(f"Condition error: {e}") from None
        return NodeResult(output={"items": kept, "count": len(kept)}, message=f"Kept {len(kept)} of {len(items)}")
