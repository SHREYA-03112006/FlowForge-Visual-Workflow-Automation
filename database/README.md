# database/

SQLite layer (SQLAlchemy 2.0) for ALG-AUTO-01.

| File | Purpose |
|------|---------|
| `models.py` | Tables: `workflows`, `executions`, `execution_logs` + status enums |
| `session.py` | Engine, `SessionLocal`, `get_db()` (FastAPI), `session_scope()` (engine/worker) |
| `init_db.py` | Create tables (`--reset` drops first) |
| `seed_data.py` | 4 demo workflows (condition, parallel, webhook+ML, scheduled+retry) |

## Usage (from the project root, not inside database/)
```
pip install -r database/requirements.txt
python -m database.init_db
python -m database.seed_data
```
Default DB file: `database/workflow.db`. Override with `DATABASE_URL`.

## Schema
- **workflows**: id, name, description, graph (JSON), is_active, is_template, schedule_cron, webhook_token, version, timestamps
- **executions**: id, workflow_id (FK), workflow_version, graph_snapshot, status, trigger_type, input_data, output_data, error, started/finished/created
- **execution_logs**: one row per node *attempt* (retries = extra rows): node_id, node_type, status, attempt, input/output, message, error, duration_ms

## Usage from the backend
```python
from database import session_scope, Workflow, Execution, ExecutionLog
with session_scope() as db:
    wf = db.get(Workflow, 1)
```
