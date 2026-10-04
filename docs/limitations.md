# Limitations and Future Work

## 1. Current Limitations

This project is designed as a hackathon-ready prototype rather than a production automation platform. Several areas are intentionally simplified.

### 1.1 Database

The current implementation uses SQLite.

SQLite is convenient for local development and demonstrations, but it is not the ideal choice for a highly concurrent production system.

**Future work:** migrate to PostgreSQL or another production-grade relational database.

### 1.2 Python Execution

The Python snippet node must be restricted because arbitrary Python code can access the host environment if executed without isolation.

**Future work:** execute Python snippets inside isolated containers or a dedicated sandbox with strict CPU, memory, filesystem, network, and execution-time limits.

### 1.3 Authentication

The prototype may operate without a full authentication and authorization layer.

**Future work:** add user accounts, sessions/JWT, role-based access control, and workflow ownership.

### 1.4 Secrets Management

Production integrations may require API keys, SMTP credentials, tokens, or other secrets.

**Future work:** introduce encrypted secret storage or integrate with a dedicated secrets manager.

### 1.5 External Integrations

The initial implementation focuses on a small set of integrations such as HTTP requests and simulated email.

**Future work:** add reusable connectors for services such as Slack, Google services, GitHub, databases, and other APIs.

### 1.6 ML Model

The initial classifier is intentionally lightweight and uses a small training dataset.

Its accuracy may not generalize to real-world support-ticket distributions.

**Future work:** train on a larger domain-specific dataset, improve preprocessing, compare multiple models, and support model versioning.

### 1.7 Workflow Versioning

The initial system may save the latest workflow definition without a complete version-control system.

**Future work:** support workflow versions, rollback, draft/published states, and execution against a specific workflow version.

### 1.8 Distributed Execution

The current execution engine is intended for a single application instance.

**Future work:** introduce a distributed task queue and worker architecture for large workloads.

### 1.9 Scheduling Reliability

APScheduler is appropriate for the prototype, but production deployments with multiple backend instances require centralized scheduling or distributed coordination.

**Future work:** move scheduling to a distributed scheduler or job queue.

### 1.10 Observability

The platform records execution logs, but production-level observability would require richer metrics and tracing.

**Future work:**

- structured logs,
- execution metrics,
- latency measurements,
- error-rate monitoring,
- distributed tracing,
- alerting.

## 2. Known Scope Boundaries

The project intentionally focuses on the core automation workflow:

1. Build a graph visually.
2. Save the workflow.
3. Trigger execution.
4. Pass data between nodes.
5. Execute independent branches.
6. Apply conditions.
7. Retry recoverable failures.
8. Monitor execution status.
9. Use an ML classifier as one workflow action.

Features outside this core scope are candidates for future versions.

## 3. Future Roadmap

### Phase 1 — Prototype Completion

- Complete ML classifier.
- Complete engine test suite.
- Finish React Flow editor.
- Add execution monitoring.
- Complete Docker setup.
- Finalize documentation.

### Phase 2 — Security and Usability

- Authentication.
- Secrets management.
- Sandboxed Python execution.
- Better validation and error messages.
- Workflow templates.
- Import/export of workflows.

### Phase 3 — Production Scalability

- PostgreSQL.
- Distributed workers.
- Redis/message queue.
- Distributed scheduling.
- Horizontal scaling.
- Centralized observability.

### Phase 4 — Advanced Automation

- More integrations.
- AI/LLM nodes.
- Human approval nodes.
- Event-driven triggers.
- Workflow versioning.
- Reusable sub-workflows.
- Conditional retries and compensation workflows.
