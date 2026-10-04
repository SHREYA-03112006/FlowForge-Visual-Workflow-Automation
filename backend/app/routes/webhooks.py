"""Public webhook endpoint: POST /api/webhooks/{token} starts the workflow that owns the token."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Execution, Workflow, get_db
from database.models import TriggerType

from ..engine.executor import validate_graph
from ..engine.runner import runner

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/{token}", status_code=202)
async def trigger_webhook(token: str, payload: Any = Body(default=None), wait: bool = False,
                          timeout: float = 30.0, db: Session = Depends(get_db)):
    """The JSON body becomes {{trigger.*}}.  Add ?wait=true to block (up to `timeout` s) and get the result."""
    wf = db.query(Workflow).filter(Workflow.webhook_token == token).first()
    if not wf:
        raise HTTPException(404, "Unknown webhook token")
    if not wf.is_active:
        raise HTTPException(409, "Workflow is inactive")
    check = validate_graph(wf.graph)
    if not check["valid"]:
        raise HTTPException(422, detail={"message": "Workflow is invalid", "errors": check["errors"]})

    data = payload if isinstance(payload, dict) else ({} if payload is None else {"value": payload})
    ex = runner.create_execution(db, wf, TriggerType.WEBHOOK, data)
    task = runner.start(ex.id)

    if wait:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=max(1.0, min(timeout, 120.0)))
        except asyncio.TimeoutError:
            pass
        db.expire_all()
        fresh = db.get(Execution, ex.id)
        return {"execution_id": ex.id, "status": fresh.status.value, "output": fresh.output_data, "error": fresh.error}
    return {"execution_id": ex.id, "status": "pending"}
