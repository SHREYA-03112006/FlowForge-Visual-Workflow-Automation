from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LogOut(BaseModel):
    id: int
    execution_id: int
    node_id: str
    node_type: str
    status: str
    attempt: int
    input_data: Any = None
    output_data: Any = None
    message: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


class ExecutionSummary(BaseModel):
    id: int
    workflow_id: int
    workflow_version: int
    status: str
    trigger_type: str
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


class ExecutionOut(ExecutionSummary):
    input_data: Any = None
    output_data: Any = None
    logs: list[LogOut] | None = None
