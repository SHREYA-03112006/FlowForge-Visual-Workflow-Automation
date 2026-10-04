import asyncio

from ..base import (BaseNode, NodeConfigError, NodeError, NodeResult, NodeRun, as_bool, as_dict,
                    as_float, as_json_value, field_spec, load_integration)
from ..registry import register

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@register
class HttpRequestNode(BaseNode):
    type = "http_request"
    category = "action"
    label = "HTTP Request"
    description = "Call any REST API. Output: {status_code, headers, body}."
    fields = [
        field_spec("method", "Method", "select", default="GET", options=METHODS),
        field_spec("url", "URL", required=True, placeholder="https://api.example.com/items/{{trigger.id}}"),
        field_spec("headers", "Headers (JSON)", "json", placeholder='{"Accept": "application/json"}'),
        field_spec("params", "Query params (JSON)", "json"),
        field_spec("body", "Body (JSON)", "json"),
        field_spec("timeout", "Request timeout (s)", "number", default=30),
        field_spec("fail_on_error", "Fail on HTTP status >= 400", "boolean", default=True,
                   help="When on, 4xx/5xx marks the node failed (and triggers retries)."),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        method = str(config.get("method") or "GET").upper()
        if method not in METHODS:
            raise NodeConfigError(f"Unsupported method '{method}'")
        url = str(config["url"]).strip()
        if not url.lower().startswith(("http://", "https://")):
            raise NodeConfigError("URL must start with http:// or https://")
        headers = as_dict(config.get("headers"), "Headers")
        params = as_dict(config.get("params"), "Query params")
        body = as_json_value(config.get("body")) if config.get("body") not in (None, "") else None
        timeout = as_float(config.get("timeout"), 30.0)

        http_client = load_integration("api_integrations.http_client")
        resp = await asyncio.to_thread(
            http_client.request, method=method, url=url, headers=headers,
            params=params, json_body=body, timeout=timeout,
        )
        status = int(resp.get("status_code", 0))
        if as_bool(config.get("fail_on_error"), True) and status >= 400:
            raise NodeError(f"HTTP {status} from {method} {url}")
        return NodeResult(
            output={"status_code": status, "headers": resp.get("headers", {}), "body": resp.get("body")},
            message=f"{method} {url} -> {status}",
        )
