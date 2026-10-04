import json

from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, field_spec
from ..registry import register
from .condition import values_equal


@register
class SwitchNode(BaseNode):
    type = "switch"
    category = "logic"
    label = "Switch (Multi-branch)"
    description = "Compares a value to a list of cases and follows the handle named after the matching case, else 'default'."
    dynamic_branches = True
    fields = [
        field_spec("value", "Value", required=True, placeholder="{{n2.output.label}}"),
        field_spec("cases", "Cases (JSON list)", "json", required=True, placeholder='["billing", "technical"]',
                   help="Draw an edge from the matching handle (named after the case) or from 'default'."),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        cases = config.get("cases")
        if isinstance(cases, str):
            try:
                cases = json.loads(cases)
            except json.JSONDecodeError:
                cases = [c.strip() for c in cases.split(",") if c.strip()]
        if not isinstance(cases, list) or not cases:
            raise NodeConfigError("Cases must be a non-empty list")
        value = config.get("value")
        for case in cases:
            if values_equal(value, case):
                return NodeResult(output={"matched": str(case)}, branch=str(case), message=f"Matched case '{case}'")
        return NodeResult(output={"matched": "default"}, branch="default", message="No case matched -> default")
