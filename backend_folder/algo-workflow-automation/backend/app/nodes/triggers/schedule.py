from datetime import datetime, timezone

from ..base import BaseNode, NodeResult, NodeRun, field_spec
from ..registry import register


@register
class ScheduleTrigger(BaseNode):
    type = "schedule_trigger"
    category = "trigger"
    label = "Schedule Trigger"
    description = "Runs on a cron schedule (minute hour day month weekday), e.g. */5 * * * *"
    fields = [field_spec("cron", "Cron expression", required=True, default="*/5 * * * *",
                         placeholder="*/5 * * * *", help="5-field cron. Applied when the workflow is saved.")]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        out = dict(run.ctx.trigger_data)
        out.setdefault("triggered_at", datetime.now(timezone.utc).isoformat())
        return NodeResult(output=out, message=f"Scheduled run ({config.get('cron', '')})")
