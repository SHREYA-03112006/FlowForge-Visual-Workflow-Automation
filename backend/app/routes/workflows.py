"""Workflow CRUD, validation, manual runs, duplication, and the node palette."""
from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Workflow, get_db
from database.models import TriggerType

from ..engine.executor import validate_graph
from ..engine.runner import runner
from ..engine.scheduler import scheduler, validate_cron
from ..nodes import COMMON_FIELDS, list_node_types
from ..schemas import (ExecutionOut, RunRequest, ValidateRequest, ValidationResult, WorkflowCreate,
                       WorkflowOut, WorkflowSummary, WorkflowUpdate)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
meta_router = APIRouter(prefix="/api", tags=["meta"])


# ---- helpers ---------------------------------------------------------------
def _get_or_404(db: Session, workflow_id: int) -> Workflow:
    wf = db.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return wf


def _cron_from_graph(graph: dict) -> str | None:
    for n in (graph or {}).get("nodes", []):
        if n.get("type") == "schedule_trigger":
            cron = ((n.get("data") or {}).get("config") or {}).get("cron")
            if cron:
                return str(cron).strip()
    return None


def _check_cron(cron: str | None) -> None:
    if cron:
        try:
            validate_cron(cron)
        except ValueError as e:
            raise HTTPException(422, f"Invalid cron expression '{cron}': {e}") from None


def _out(wf: Workflow) -> dict:
    d = wf.to_dict()
    d["next_run"] = scheduler.next_run(wf.id)
    return d


# ---- node palette (for the frontend sidebar + config panel) -----------------
@meta_router.get("/node-types")
def node_types():
    return {"node_types": list_node_types(), "common_fields": COMMON_FIELDS}


@meta_router.get("/health")
def health():
    return {"status": "ok"}


# ---- CRUD -------------------------------------------------------------------
@router.get("", response_model=list[WorkflowSummary])
def list_workflows(search: str | None = None, templates_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(Workflow)
    if search:
        q = q.filter(Workflow.name.ilike(f"%{search}%"))
    if templates_only:
        q = q.filter(Workflow.is_template.is_(True))
    return [
        {"id": w.id, "name": w.name, "description": w.description, "is_active": w.is_active,
         "is_template": w.is_template, "schedule_cron": w.schedule_cron, "version": w.version,
         "node_count": len((w.graph or {}).get("nodes", [])),
         "updated_at": w.updated_at.isoformat() if w.updated_at else None}
        for w in q.order_by(Workflow.updated_at.desc()).all()
    ]


@router.post("", response_model=WorkflowOut, status_code=201)
def create_workflow(body: WorkflowCreate, db: Session = Depends(get_db)):
    graph = body.graph.model_dump(mode="json")
    cron = body.schedule_cron or _cron_from_graph(graph)
    _check_cron(cron)
    wf = Workflow(name=body.name.strip(), description=body.description, graph=graph,
                  is_active=body.is_active, is_template=body.is_template, schedule_cron=cron)
    db.add(wf)
    db.commit()
    db.refresh(wf)
    scheduler.sync(wf.id, wf.schedule_cron, wf.is_active)
    return _out(wf)


@router.post("/validate", response_model=ValidationResult)
def validate(body: ValidateRequest):
    """Check a graph without saving or running it (used by the editor)."""
    return validate_graph(body.graph.model_dump(mode="json"))


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    return _out(_get_or_404(db, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(workflow_id: int, body: WorkflowUpdate, db: Session = Depends(get_db)):
    wf = _get_or_404(db, workflow_id)
    sent = body.model_fields_set
    if "name" in sent and body.name is not None:
        wf.name = body.name.strip()
    if "description" in sent and body.description is not None:
        wf.description = body.description
    if "is_active" in sent and body.is_active is not None:
        wf.is_active = body.is_active
    if "is_template" in sent and body.is_template is not None:
        wf.is_template = body.is_template
    if "graph" in sent and body.graph is not None:
        wf.graph = body.graph.model_dump(mode="json")
        wf.version += 1
        derived = _cron_from_graph(wf.graph)
        if derived and "schedule_cron" not in sent:
            wf.schedule_cron = derived
    if "schedule_cron" in sent:
        wf.schedule_cron = (body.schedule_cron or "").strip() or None
    _check_cron(wf.schedule_cron)
    db.commit()
    db.refresh(wf)
    scheduler.sync(wf.id, wf.schedule_cron, wf.is_active)
    return _out(wf)


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = _get_or_404(db, workflow_id)
    scheduler.remove(wf.id)
    db.delete(wf)
    db.commit()


@router.post("/{workflow_id}/duplicate", response_model=WorkflowOut, status_code=201)
def duplicate_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Clone a workflow (this is how templates are reused). The copy is never scheduled automatically."""
    src = _get_or_404(db, workflow_id)
    wf = Workflow(name=f"{src.name} (copy)", description=src.description, graph=copy.deepcopy(src.graph),
                  is_active=True, is_template=False, schedule_cron=None)
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return _out(wf)


# ---- run ----------------------------------------------------------------------
@router.post("/{workflow_id}/run", response_model=ExecutionOut, status_code=202)
async def run_workflow(workflow_id: int, body: RunRequest | None = None, db: Session = Depends(get_db)):
    """Start a manual run in the background. Follow progress via GET /api/executions/{id} or the WebSocket."""
    wf = _get_or_404(db, workflow_id)
    check = validate_graph(wf.graph)
    if not check["valid"]:
        raise HTTPException(422, detail={"message": "Workflow is invalid", "errors": check["errors"]})
    ex = runner.create_execution(db, wf, TriggerType.MANUAL, (body.input_data if body else {}))
    runner.start(ex.id)
    return ex.to_dict()
