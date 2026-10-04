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

🛠️ Technology Stack
Frontend
- React
- JavaScript
- React Flow
- Zustand
- Vite
Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
Database
- SQLite
Workflow & Scheduling
- Custom workflow execution engine
- APScheduler
- REST APIs
- WebSocket support
Machine Learning
- scikit-learn
Development & Deployment
- Git & GitHub
- Docker
- Docker Compose
