from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="allow")   # keep React Flow extras (width, selected, ...)
    id: str
    type: str
    position: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)   # {"label": str, "config": {...}}


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    source: str
    target: str
    sourceHandle: str | None = None    # "true"/"false" for conditions, case name for switch
    targetHandle: str | None = None


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    graph: Graph = Field(default_factory=Graph)
    is_active: bool = True
    is_template: bool = False
    schedule_cron: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    graph: Graph | None = None
    is_active: bool | None = None
    is_template: bool | None = None
    schedule_cron: str | None = None


class WorkflowOut(BaseModel):
    id: int
    name: str
    description: str
    graph: dict[str, Any]
    is_active: bool
    is_template: bool
    schedule_cron: str | None = None
    webhook_token: str
    version: int
    created_at: str | None = None
    updated_at: str | None = None
    next_run: str | None = None


class WorkflowSummary(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    is_template: bool
    schedule_cron: str | None = None
    version: int
    node_count: int
    updated_at: str | None = None


class RunRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)


class ValidateRequest(BaseModel):
    graph: Graph


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
