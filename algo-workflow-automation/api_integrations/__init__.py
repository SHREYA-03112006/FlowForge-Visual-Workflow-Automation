"""Reusable connectors used by the backend action nodes.

    http_client.request(...)     -> http_request node
    email_client.send_email(...) -> send_email node
    webhook_client.post_webhook  -> signed outbound webhooks (helper)
    llm_client.complete(...)     -> optional LLM call (helper)
"""
