# FlowForge — Visual Workflow Automation Platform

FlowForge is a visual workflow automation platform designed to simplify repetitive digital tasks through a drag-and-drop workflow builder.

Users can create workflows by connecting triggers, actions, conditions, and data transformation nodes. The backend execution engine processes the workflow graph, passes data between nodes, handles branching and retries, and records execution status and logs.

Built for **ALGOTHON'26 — ALG-AUTO-01: Visual Workflow Automation**.

---

## 🚀 Key Features

- 🎨 **Visual Workflow Editor**
  - Drag-and-drop workflow creation
  - Connect nodes visually to define execution flow

- ⚡ **Multiple Triggers**
  - Manual trigger
  - Webhook trigger
  - Scheduled trigger

- 🔧 **Action Nodes**
  - HTTP Request
  - Send Email
  - Write File
  - Run Python

- 🧠 **Logic & Conditions**
  - Conditional branching
  - Switch/decision-based workflow execution

- 🔄 **Data Transformation**
  - Filter data
  - Map data
  - JSON extraction
  - Data passing between workflow nodes

- 🔀 **Parallel Execution**
  - Execute independent workflow branches
  - Join branches before continuing execution

- ♻️ **Reliability**
  - Retry handling
  - Failure propagation
  - Workflow validation

- 📊 **Execution Monitoring**
  - Execution status
  - Node-level execution results
  - Logs and errors

- 💾 **Workflow Management**
  - Create and save workflows
  - Load existing workflows
  - Reuse workflow definitions

- 🤖 **ML Support**
  - Text classification workflow node
  - Integration-ready architecture for intelligent automation

---

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │      Frontend       │
                    │ React + React Flow  │
                    └──────────┬──────────┘
                               │
                               │ REST API
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │      Backend        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Workflow Execution  │
                    │      Engine         │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
          Triggers          Actions          Logic
              │                │                │
              ▼                ▼                ▼
         Manual/Webhook   HTTP/Email/File   Conditions


         /Schedule        /Python            /Switch
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Database / Workflow │
                    │     Persistence     │
                    └─────────────────────┘

## 🛠️ Technology Stack

### Frontend
- **React 18** — User interface
- **React Flow / @xyflow/react** — Visual workflow editor and node-based canvas
- **Zustand** — Frontend state management
- **React Router** — Page navigation
- **Lucide React** — UI icons
- **Vite** — Frontend development and build tool

### Backend
- **Python** — Core backend and workflow execution
- **FastAPI** — REST API and backend services
- **Pydantic** — Data validation and API schemas
- **SQLAlchemy** — Database interaction
- **Uvicorn** — ASGI server

### Workflow Engine
- **Custom Graph Execution Engine** — Executes workflow nodes and manages dependencies
- **Conditional Execution** — Supports decision-based workflow paths
- **Parallel Execution** — Executes independent branches concurrently
- **Retry Handling** — Handles failed node execution with retry logic
- **Scheduler** — Supports scheduled workflow execution
- **WebSockets** — Real-time execution updates

### Database
- **SQLite** — Local workflow and execution data storage
- **SQLAlchemy ORM** — Database abstraction layer

### Machine Learning
- **scikit-learn** — Machine learning functionality for classification workflows

### Development & Deployment
- **Git & GitHub** — Version control and source-code management
- **Docker** — Containerization
- **Docker Compose** — Multi-service setup
- **npm** — Frontend package management
- **pytest** — Backend testing
Machine Learning
- scikit-learn
Development & Deployment
- Git & GitHub
- Docker
- Docker Compose
