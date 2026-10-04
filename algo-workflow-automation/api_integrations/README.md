# api_integrations/

Connectors used by the backend nodes. Standard library only - no extra pip packages.

| File | Used by | Function |
|---|---|---|
| `http_client.py` | `http_request` node | `request(method, url, headers, params, json_body, timeout)` -> `{status_code, headers, body}` |
| `email_client.py` | `send_email` node | `send_email(to, subject, body)` - simulated by default, real SMTP optional |
| `webhook_client.py` | helper | `post_webhook(url, payload, secret)`, `sign_payload`, `verify_signature` (HMAC-SHA256) |
| `llm_client.py` | helper | `complete(prompt, system, model)` - Anthropic API, or mock when no key |
| `config.py` | all | env-var helpers |

No setup is needed for the demos: email is simulated (see `outputs/emails/outbox.jsonl`).

## Environment variables
| Variable | Default | Meaning |
|---|---|---|
| `ALLOW_PRIVATE_NETWORK` | false | Allow HTTP calls to localhost/private IPs (blocked by default = SSRF protection) |
| `EMAIL_MODE` | simulated | `simulated` or `smtp` |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` | - / 587 | Real email (`SMTP_STARTTLS=true`, or `SMTP_SSL=true` for port 465) |
| `EMAIL_FROM` | SMTP_USER | Sender address |
| `LLM_MODE` | auto | `auto` / `anthropic` / `mock` |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | - / claude-sonnet-5-5 | LLM settings |
| `OUTPUT_DIR` | `outputs/` | Where the simulated outbox is written |

## Notes
- HTTP 4xx/5xx are returned (not raised); network failures raise `HttpClientError`, which the node can retry.
- Quick manual check (from project root): `python -c "from api_integrations import http_client as h; print(h.request('GET','https://jsonplaceholder.typicode.com/posts/1')['body'])"`
