# backend/

FastAPI app + DAG execution engine for ALG-AUTO-01 (Visual Workflow Automation).
Requires **Python 3.10+**.

## Run (from the project root, next to `database/`)
```
pip install -r backend/requirements.txt
python -m database.seed_data                       # optional demo workflows
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API docs: http://localhost:8000/docs

## Layout
```
app/main.py          app, CORS, router wiring, startup (init DB, recover stale runs, start scheduler)
app/config.py        settings from env vars
app/routes/          workflows.py  executions.py (+WebSocket)  webhooks.py  ml.py
app/schemas/         Pydantic request/response models
app/engine/
   executor.py       validate_graph + WorkflowExecutor (parallel DAG, branches, retries, timeouts)
   context.py        {{template}} resolution, JSON-safe/redacted logging helpers
   retry.py          retry policy (retries / delay / backoff)
   safe_eval.py      AST-whitelist expression evaluator (no eval)
   runner.py         persists runs/logs in SQLite, runs them as background tasks
   events.py         in-process pub/sub for live WebSocket updates
   scheduler.py      cron-scheduled triggers (APScheduler)
app/nodes/           one handler per node type (triggers/ actions/ logic/ transform/ ml/)
```

## Key endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/node-types` | Node palette + config field specs for the editor |
| GET/POST | `/api/workflows` | List (search, templates_only) / create |
| GET/PUT/DELETE | `/api/workflows/{id}` | Load / save (bumps version) / delete |
| POST | `/api/workflows/validate` | Validate a graph without saving |
| POST | `/api/workflows/{id}/run` | Start a run `{ "input_data": {...} }` -> 202 + execution |
| POST | `/api/workflows/{id}/duplicate` | Clone (reuse templates) |
| GET | `/api/executions?workflow_id=` | Run history |
| GET | `/api/executions/{id}` | Run detail + per-node logs |
| POST | `/api/executions/{id}/cancel` | Cancel a running execution |
| WS | `/ws/executions/{id}` | Live: `snapshot`, `node_update`, `execution_finished` |
| POST | `/api/webhooks/{token}` | Webhook trigger (`?wait=true` returns the result) |
| POST | `/api/ml/classify` | Direct call to the classifier |

## Node types (13)
Triggers: `manual_trigger`, `webhook_trigger`, `schedule_trigger`
Actions: `http_request`, `send_email`, `write_file`, `python_snippet`
Logic: `condition` (handles `true`/`false`), `switch` (handle = case name or `default`)
Transform: `map`, `filter`, `json_extract`
ML: `ml_classifier`

Every node also accepts `retries`, `retry_delay_seconds`, `retry_backoff`, `timeout_seconds`.

## Templates
`{{trigger.field}}`, `{{node_id.output.field}}`, `{{n2.output.items[0].name}}`,
`{{trigger.x | default('fallback')}}`. A string that is only one template keeps its type (list stays list).

## Contracts the other folders must provide
```python
# api_integrations/http_client.py
def request(method, url, headers, params, json_body, timeout) -> {"status_code": int, "headers": dict, "body": Any}
# api_integrations/email_client.py
def send_email(to, subject, body) -> dict            # e.g. {"sent": True, "simulated": True}
# ml_model_train/predict.py
def predict(text) -> {"label": str, "confidence": float}   # raise FileNotFoundError if model missing
#   optional: def is_model_available() -> bool
```

## Environment variables (all optional)
`DATABASE_URL`, `OUTPUT_DIR` (default `outputs/`), `CORS_ORIGINS`, `NODE_TIMEOUT_SECONDS` (60),
`MAX_PARALLEL_NODES` (8), `ALLOW_PYTHON_SNIPPET` (true), `SNIPPET_TIMEOUT_SECONDS` (10).

## Known limitations
- `python_snippet` is restricted (isolated interpreter, whitelisted builtins/imports, CPU/memory limit,
  timeout) but is **not a hardened sandbox**; set `ALLOW_PYTHON_SNIPPET=false` for untrusted users.
- Runs execute inside the API process (no external queue); a restart marks in-flight runs failed.
- Live events use an in-process bus, so run a single server worker.
- No authentication on the API / webhooks (the webhook token is the only secret).
