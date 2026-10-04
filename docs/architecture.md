# Architecture — Visual Workflow Automation Platform

## 1. Project Overview

The Visual Workflow Automation Platform is a no-code workflow automation system developed for ALGOTHON'26 (ALG-AUTO-01). It allows users to visually create workflows by dragging nodes onto a canvas, connecting them, configuring their inputs, and executing the resulting workflow without writing application code.

The platform is designed around a graph-based execution model. A workflow is represented as a directed graph in which nodes perform triggers, actions, logic, transformations, or ML inference.

## 2. High-Level Architecture

```text
                         ┌──────────────────────────┐
                         │        React UI           │
                         │ React + React Flow        │
                         │ Zustand State Management  │
                         └────────────┬─────────────┘
                                      │ REST / WebSocket
                                      ▼
                         ┌──────────────────────────┐
                         │       FastAPI API         │
                         │ Workflows / Executions    │
                         │ Webhooks / ML             │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                    ┌────────────────────────────────────┐
                    │          Execution Engine           │
                    │                                    │
                    │ Graph Validation                   │
                    │ DAG Execution                      │
                    │ Context / Data Passing              │
                    │ Retry Handling                      │
                    │ Scheduling                          │
                    │ Execution Logging                   │
                    └───────────┬───────────────┬────────┘
                                │               │
                    ┌───────────▼──────┐  ┌────▼────────────┐
                    │   Node Handlers  │  │    Scheduler    │
                    │                  │  │  APScheduler    │
                    │ Triggers         │  └─────────────────┘
                    │ Actions          │
                    │ Logic            │
                    │ Transform        │
                    │ ML               │
                    └───────┬──────────┘
                            │
             ┌──────────────┼──────────────────┐
             ▼              ▼                  ▼
       API Integrations   ML Model          SQLite
       HTTP / Email       scikit-learn      Workflows
       Webhooks           Classifier        Executions
       Optional LLM                        Logs
```

## 3. Frontend

The frontend is implemented using React and React Flow.

### Responsibilities

- Provide a visual workflow canvas.
- Allow users to drag nodes from a palette onto the canvas.
- Allow nodes to be connected to form workflow graphs.
- Display node configuration panels.
- Save and load workflows through the backend API.
- Display execution status and logs.
- Provide workflow history and run information.

### Main frontend areas

- `components/canvas/` — workflow canvas and custom nodes.
- `components/sidebar/` — draggable node palette.
- `components/panels/` — configuration and execution-log panels.
- `pages/` — editor, workflow list, and execution history.
- `store/` — Zustand application/workflow state.
- `services/` — REST API and WebSocket communication.

## 4. Backend

FastAPI provides the HTTP API and acts as the entry point to the execution system.

### Main responsibilities

- Workflow CRUD operations.
- Workflow validation.
- Starting executions.
- Receiving webhook triggers.
- Managing scheduled triggers.
- Reporting execution status.
- Exposing ML classification functionality.
- Providing execution logs to the frontend.

## 5. Execution Engine

The execution engine is the core component of the platform.

A workflow is treated as a directed graph. The executor determines node dependencies and executes nodes when their required inputs are available.

### Execution lifecycle

```text
Load Workflow
      ↓
Validate Graph
      ↓
Create Execution Context
      ↓
Identify Ready Nodes
      ↓
Execute Independent Nodes
      ↓
Store Outputs in Context
      ↓
Resolve Conditions / Dependencies
      ↓
Execute Next Ready Nodes
      ↓
Retry Failed Nodes When Allowed
      ↓
Write Execution Logs
      ↓
Complete / Fail Execution
```

### Parallel execution

Independent branches do not need to wait for one another. The executor can schedule independent ready nodes concurrently and continue when their dependencies are satisfied.

This is important for workflows such as:

```text
             ┌── Send Email ──┐
Webhook ─────┤                ├── Final Step
             └── Write File ──┘
```

## 6. Data Passing

Node outputs are stored in an execution context.

A downstream node can reference previous outputs using expressions such as:

```text
{{node.output.field}}
```

Example:

```text
{{classifier.output.category}}
```

The context layer resolves these references before a node executes.

This keeps node handlers loosely coupled while allowing information to move through the workflow.

## 7. Node System

Node handlers are separated by responsibility.

### Triggers

- Manual trigger
- Webhook trigger
- Scheduled trigger

### Actions

- REST API request
- Email
- File writing
- Restricted Python snippet

### Logic

- Condition
- Switch

### Transformations

- Map
- Filter
- JSON extraction

### ML

- Text classifier

Each node type has a focused handler responsible for validating its configuration, executing its operation, and returning a structured result.

## 8. Reliability

The execution engine includes retry handling for recoverable failures.

A failed node can be retried according to its configured retry policy. Execution logs record attempts and failures so that users can understand what happened.

The system should distinguish between:

- successful execution,
- failed execution,
- retrying execution,
- skipped nodes,
- running nodes.

## 9. Scheduling

APScheduler is used for cron-style workflow triggers.

Scheduled workflows are registered with the scheduler and start executions when their configured schedule is reached.

Manual and webhook triggers use the same underlying execution engine, allowing different trigger types to share the same workflow execution logic.

## 10. Database

SQLite stores persistent application data.

The database layer contains records for:

- workflows,
- workflow definitions,
- executions,
- execution logs.

Keeping execution history separate from workflow definitions allows users to modify workflows while retaining previous run information.

## 11. ML Classification

The ML node uses a lightweight scikit-learn text classification model.

The training pipeline is maintained separately under `ml_model_train/`.

```text
Dataset
   ↓
Preprocessing
   ↓
TF-IDF Features
   ↓
Classifier
   ↓
Evaluation
   ↓
Saved Model
   ↓
Backend ML Node
```

The initial model is intentionally lightweight so inference can happen locally with low latency.

## 12. Security Considerations

The platform executes user-defined workflows, so potentially dangerous operations must be restricted.

In particular:

- Python execution must not provide unrestricted operating-system access.
- HTTP requests should be validated and controlled where appropriate.
- Secrets should not be hard-coded into workflow definitions.
- Environment variables should be used for sensitive configuration.
- Webhook endpoints should validate incoming requests in production.
- File-writing operations should be restricted to approved directories.

## 13. Design Decisions

### React Flow

React Flow provides the graph editing experience required for a node-based workflow builder.

### FastAPI

FastAPI provides lightweight, typed APIs and integrates naturally with the Python execution engine and ML components.

### SQLite

SQLite is sufficient for a hackathon-scale prototype and keeps deployment simple.

### APScheduler

APScheduler provides the scheduling functionality required for cron-style workflow triggers without introducing a separate infrastructure dependency.

### scikit-learn

A lightweight scikit-learn classifier is sufficient to demonstrate genuine ML-powered workflow execution without unnecessary model complexity.

## 14. Future Scalability

For production-scale deployment, the architecture could evolve toward:

- PostgreSQL instead of SQLite.
- Redis or a dedicated message broker.
- Distributed worker processes.
- Containerized sandbox execution.
- Persistent WebSocket infrastructure.
- Authentication and role-based access control.
- Workflow versioning.
- Distributed scheduling.
- Observability with metrics and tracing.
