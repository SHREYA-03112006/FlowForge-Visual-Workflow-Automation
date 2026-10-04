"""SQLAlchemy models: workflows, executions, execution_logs.

Workflow.graph stores the React Flow graph as JSON:
{
  "nodes": [{"id": "n1", "type": "manual_trigger",
             "position": {"x": 0, "y": 0},
             "data": {"label": "Start", "config": {...}}}],
  "edges": [{"id": "e1", "source": "n1", "target": "n2",
             "sourceHandle": "true" | "false" | null}]
}
"""
import enum
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_webhook_token() -> str:
    return secrets.token_urlsafe(16)


class Base(DeclarativeBase):
    pass


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"   # e.g. branch not taken by a condition
    RETRYING = "retrying"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    graph: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {"nodes": [], "edges": []})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)  # reusable workflows
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "*/5 * * * *"
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True, default=new_webhook_token)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    executions: Mapped[list["Execution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="Execution.id.desc()"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "graph": self.graph, "is_active": self.is_active, "is_template": self.is_template,
            "schedule_cron": self.schedule_cron, "webhook_token": self.webhook_token,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    workflow_version: Mapped[int] = mapped_column(Integer, default=1)
    graph_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # graph as it was when run
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, index=True)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), default=TriggerType.MANUAL)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")
    logs: Mapped[list["ExecutionLog"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="ExecutionLog.id"
    )

    def to_dict(self, include_logs: bool = False) -> dict:
        d = {
            "id": self.id, "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status.value, "trigger_type": self.trigger_type.value,
            "input_data": self.input_data, "output_data": self.output_data, "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_logs:
            d["logs"] = [log.to_dict() for log in self.logs]
        return d


class ExecutionLog(Base):
    """One row per node attempt (so retries show up as separate rows)."""
    __tablename__ = "execution_logs"
    __table_args__ = (Index("ix_logs_exec_node", "execution_id", "node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(100))
    node_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[NodeStatus] = mapped_column(Enum(NodeStatus), default=NodeStatus.PENDING)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    execution: Mapped["Execution"] = relationship(back_populates="logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "execution_id": self.execution_id,
            "node_id": self.node_id, "node_type": self.node_type,
            "status": self.status.value, "attempt": self.attempt,
            "input_data": self.input_data, "output_data": self.output_data,
            "message": self.message, "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
        }
