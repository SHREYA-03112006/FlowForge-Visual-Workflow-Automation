# Algo Workflow Automation

A visual workflow automation platform built for **ALGOTHON'26 — ALG-AUTO-01**.

The platform lets users build and execute automations visually by dragging nodes onto a canvas and connecting them into workflows instead of writing orchestration code manually.

## Example

A support-ticket workflow can look like:

```text
Webhook
   ↓
Text Classifier
   ↓
Condition
 ┌─┴───────────┐
 ↓             ↓
Billing      Technical
 ↓             ↓
Email Team   Email Team
```

A workflow can receive data from a webhook, classify the incoming text, evaluate a condition, and execute the appropriate branch.

---

## Key Features

- Visual workflow editor using React Flow.
- Drag-and-drop workflow nodes.
- Workflow save/load functionality.
- Manual workflow execution.
- Webhook-based triggers.
- Cron-style scheduled triggers.
- DAG-based backend execution engine.
- Parallel execution of independent branches.
- Conditional workflow paths.
- Data passing between nodes.
- Retry handling for failed steps.
- Per-node execution status and logs.
- REST API action node.
- Email action node.
- File-writing action node.
- Restricted Python action node.
- Text classification using scikit-learn.
- SQLite persistence for workflows and execution history.

---

## Tech Stack

### Frontend

- React
- React Flow
- Zustand
- Vite

### Backend

- Python
- FastAPI
- Pydantic
- APScheduler

### Database

- SQLite

### Machine Learning

- scikit-learn

### Integrations

- HTTP
- Email
- Webhooks
- Optional LLM integration

### Deployment

- Docker
- Docker Compose

---

## Project Structure

```text
algo-workflow-automation/
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       │   ├── canvas/
│       │   ├── sidebar/
│       │   ├── panels/
│       │   └── common/
│       ├── pages/
│       ├── store/
│       ├── services/
│       ├── App.jsx
│       └── main.jsx
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── routes/
│       ├── schemas/
│       ├── engine/
│       │   ├── executor.py
│       │   ├── context.py
│       │   ├── retry.py
│       │   └── scheduler.py
│       └── nodes/
│           ├── triggers/
│           ├── actions/
│           ├── logic/
│           ├── transform/
│           └── ml/
│
├── database/
│   ├── models.py
│   ├── session.py
│   ├── init_db.py
│   └── seed_data.py
│
├── api_integrations/
│   ├── http_client.py
│   ├── email_client.py
│   ├── webhook_client.py
│   └── llm_client.py
│
├── ml_model_train/
│   ├── data/
│   ├── train.py
│   ├── evaluate.py
│   ├── predict.py
│   └── saved_model/
│
├── tests/
│   ├── test_executor.py
│   ├── test_data_passing.py
│   ├── test_conditions.py
│   ├── test_retries.py
│   └── test_parallel.py
│
├── docs/
│   ├── architecture.md
│   ├── limitations.md
│   └── ai_disclosure.md
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Architecture

The system is divided into five major layers:

```text
┌───────────────────────────────────────────────┐
│                 React Frontend                │
│        Visual Workflow Editor / Logs          │
└──────────────────────┬────────────────────────┘
                       │ REST / WebSocket
                       ▼
┌───────────────────────────────────────────────┐
│                  FastAPI API                  │
│ Workflow / Execution / Webhook / ML Routes  │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│              Execution Engine                │
│ DAG Executor / Context / Retry / Scheduler  │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│                 Node Handlers                │
│ Trigger / Action / Logic / Transform / ML   │
└───────────────┬───────────────────┬───────────┘
                ▼                   ▼
           Integrations          SQLite
           HTTP / Email          Workflows
           Webhooks              Executions
           Optional LLM          Logs
```

For a detailed architecture description, see:

```text
docs/architecture.md
```

---

## How Workflow Execution Works

A workflow is stored as a directed graph.

Each node contains its type, configuration, and connections to other nodes.

During execution:

1. The workflow is loaded.
2. The graph is validated.
3. An execution context is created.
4. Ready nodes are identified.
5. Independent nodes can execute in parallel.
6. Each node stores its output in the execution context.
7. Conditions determine which downstream paths continue.
8. Data references are resolved before downstream execution.
9. Failed recoverable nodes can be retried.
10. Execution status and logs are persisted.

### Data Passing

Nodes can reference previous outputs using:

```text
{{node.output.field}}
```

For example:

```text
{{classifier.output.category}}
```

A classifier may produce:

```json
{
  "category": "billing",
  "confidence": 0.94
}
```

A condition node can then evaluate the category and select the appropriate branch.

---

## Node Categories

### Triggers

- Manual
- Webhook
- Schedule

### Actions

- HTTP Request
- Send Email
- Write File
- Python Snippet

### Logic

- Condition
- Switch

### Transform

- Map
- Filter
- JSON Extract

### ML

- Text Classifier

---

## Local Setup

### Prerequisites

Install:

- Python 3.11+ or the version specified by the backend environment.
- Node.js 18+.
- npm.
- Git.

Docker is recommended if you want to run the full stack consistently.

---

## Backend Setup

From the project root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the database:

```bash
python ../database/init_db.py
```

Start the API:

```bash
uvicorn app.main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

FastAPI documentation:

```text
http://localhost:8000/docs
```

---

## Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

## Environment Variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Then update values where required.

Do not commit real API keys, passwords, SMTP credentials, or other secrets to Git.

---

## Docker Setup

The project includes a Docker Compose configuration for running the frontend and backend together.

Start the stack:

```bash
docker compose up --build
```

Run in the background:

```bash
docker compose up --build -d
```

Stop the stack:

```bash
docker compose down
```

The default services are:

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| FastAPI Docs | http://localhost:8000/docs |

---

## ML Model

The classifier training pipeline is located in:

```text
ml_model_train/
```

Typical flow:

```bash
cd ml_model_train
python train.py
python evaluate.py
```

The resulting model is loaded by the backend ML classifier node.

The initial classifier is intended for demonstrating workflow-integrated ML inference rather than production-grade prediction.

---

## Testing

Run the backend test suite from the project root:

```bash
pytest
```

The test suite covers important execution-engine behavior including:

- DAG execution.
- Data passing.
- Conditional branches.
- Retry behavior.
- Parallel execution.

Example:

```bash
pytest tests/test_executor.py
```

---

## Example Workflow

A simple automation can be configured as:

```text
Webhook Trigger
      ↓
Text Classifier
      ↓
Condition
   ↙       ↘
Billing   Technical
   ↓         ↓
Email      Email
```

### Example webhook payload

```json
{
  "ticket": "I was charged twice for my subscription",
  "email": "user@example.com"
}
```

The classifier can produce:

```json
{
  "category": "billing",
  "confidence": 0.94
}
```

The condition can evaluate:

```text
{{classifier.output.category}} == "billing"
```

and route execution to the billing-support email action.

---

## Reliability

The execution engine is designed around explicit workflow execution state.

A node can be represented as:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

or:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
   ↓
RETRY
   ↓
RUNNING
```

Execution logs capture node-level activity so users can understand where and why a workflow failed.

---

## Security Notes

This project is a hackathon prototype.

Particular care is required for the Python snippet node and external HTTP requests.

Production deployment should add:

- Sandboxed code execution.
- Authentication.
- Authorization.
- Secret management.
- Request validation.
- Resource limits.
- Network restrictions.
- Audit logging.

See:

```text
docs/limitations.md
```

for known limitations and planned improvements.

---

## Hackathon Focus

The project is designed around the key evaluation areas of the challenge:

### Real Execution Engine

The visual graph is not merely a mock interface. Workflows are executed by a backend graph engine.

### Correct Data Passing

Node outputs are stored in a shared execution context and can be referenced by downstream nodes.

### Reliability

The execution engine supports retries, execution states, and logs.

### Workflow UX

Users create workflows visually using nodes and connections rather than manually writing orchestration code.

### ML Integration

The classifier demonstrates how machine learning can become a reusable workflow node.

---

## Current Development Status

### Completed

- `database/`
- `backend/`
- `api_integrations/`

### In Progress / Next

- `ml_model_train/`
- `tests/`
- `frontend/`
- `docs/`
- `docker-compose.yml`
- `README.md`

---

## Future Work

Potential future improvements include:

- User authentication.
- Role-based permissions.
- PostgreSQL support.
- Distributed workers.
- Redis/message queue integration.
- Sandboxed Python execution.
- More API integrations.
- Workflow versioning.
- Workflow templates.
- Human approval nodes.
- Advanced LLM/AI nodes.
- Production-grade observability.
- Import/export of workflows.

---

## License

This project was created as a hackathon project for ALGOTHON'26.

Add the appropriate license here if the project is later released as open source.
