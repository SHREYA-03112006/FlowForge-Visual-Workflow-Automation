from ..base import BaseNode, NodeResult, NodeRun
from ..registry import register


@register
class WebhookTrigger(BaseNode):
    type = "webhook_trigger"
    category = "trigger"
    label = "Webhook Trigger"
    description = "Starts when an HTTP POST hits /api/webhooks/{token}. The JSON body is available as {{trigger.field}}."

    async def execute(self, config, run: NodeRun) -> NodeResult:
        return NodeResult(output=dict(run.ctx.trigger_data), message="Webhook received")
