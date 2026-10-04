from ..base import BaseNode, NodeResult, NodeRun, field_spec
from ..registry import register


@register
class ManualTrigger(BaseNode):
    type = "manual_trigger"
    category = "trigger"
    label = "Manual Trigger"
    description = "Starts the workflow when you click Run. Optional input JSON is available as {{trigger.field}}."

    async def execute(self, config, run: NodeRun) -> NodeResult:
        return NodeResult(output=dict(run.ctx.trigger_data), message="Started manually")
