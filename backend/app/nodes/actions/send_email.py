import asyncio

from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, field_spec, load_integration
from ..registry import register


@register
class SendEmailNode(BaseNode):
    type = "send_email"
    category = "action"
    label = "Send Email"
    description = "Send an email (simulated unless real SMTP is configured in api_integrations)."
    fields = [
        field_spec("to", "To", required=True, placeholder="user@example.com"),
        field_spec("subject", "Subject", required=True),
        field_spec("body", "Body", "textarea"),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        to = str(config["to"]).strip()
        if "@" not in to:
            raise NodeConfigError(f"'{to}' is not a valid email address")
        email_client = load_integration("api_integrations.email_client")
        result = await asyncio.to_thread(
            email_client.send_email, to=to, subject=str(config["subject"]), body=str(config.get("body") or ""),
        )
        output = result if isinstance(result, dict) else {"sent": True}
        output.setdefault("to", to)
        return NodeResult(output=output, message=f"Email to {to}")
