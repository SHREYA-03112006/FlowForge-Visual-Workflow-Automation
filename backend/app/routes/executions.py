"""Execution history, details with per-node logs, cancel, and the live WebSocket stream."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import Execution, get_db, session_scope
from database.models import ExecutionStatus

from ..engine.events import bus
from ..engine.runner import runner
from ..schemas import ExecutionOut, ExecutionSummary

router = APIRouter(prefix="/api/executions", tags=["executions"])
ws_router = APIRouter(tags=["live"])

TERMINAL = {"success", "failed", "cancelled"}


@router.get("", response_model=list[ExecutionSummary])
def list_executions(workflow_id: int | None = None, status: str | None = None, limit: int = 50,
                    db: Session = Depends(get_db)):
    q = db.query(Execution)
    if workflow_id is not None:
        q = q.filter(Execution.workflow_id == workflow_id)
    if status:
        try:
            q = q.filter(Execution.status == ExecutionStatus(status))
        except ValueError:
            raise HTTPException(422, f"Unknown status '{status}'") from None
    return [e.to_dict() for e in q.order_by(Execution.id.desc()).limit(max(1, min(limit, 500))).all()]


@router.get("/{execution_id}", response_model=ExecutionOut)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    ex = db.get(Execution, execution_id)
    if not ex:
        raise HTTPException(404, f"Execution {execution_id} not found")
    return ex.to_dict(include_logs=True)


@router.post("/{execution_id}/cancel")
def cancel_execution(execution_id: int, db: Session = Depends(get_db)):
    ex = db.get(Execution, execution_id)
    if not ex:
        raise HTTPException(404, f"Execution {execution_id} not found")
    if ex.status.value in TERMINAL:
        raise HTTPException(409, f"Execution already {ex.status.value}")
    if not runner.cancel(execution_id):
        raise HTTPException(409, "Execution is not running on this server")
    return {"cancelling": True}


@ws_router.websocket("/ws/executions/{execution_id}")
async def stream_execution(websocket: WebSocket, execution_id: int):
    """Sends {type:'snapshot', execution:{...logs}} first, then live
    node_update / execution_finished events until the run ends."""
    await websocket.accept()
    queue = bus.subscribe(execution_id)       # subscribe BEFORE the snapshot so nothing is missed
    try:
        with session_scope() as db:
            ex = db.get(Execution, execution_id)
            snapshot = ex.to_dict(include_logs=True) if ex else None
        if snapshot is None:
            await websocket.send_json({"type": "error", "message": f"Execution {execution_id} not found"})
            return
        await websocket.send_json({"type": "snapshot", "execution": snapshot})
        if snapshot["status"] in TERMINAL:
            return
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] == "execution_finished":
                break
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(execution_id, queue)
        try:
            await websocket.close()
        except Exception:
            pass
