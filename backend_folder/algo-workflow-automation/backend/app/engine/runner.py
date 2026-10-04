"""Glue between the executor and the rest of the app: persists runs in SQLite
and publishes live events. Runs execute as background asyncio tasks."""
from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any

from database import Execution, ExecutionLog, Workflow, session_scope
from database.models import ExecutionStatus, NodeStatus, TriggerType

from .context import to_json_safe
from .events import bus
from .executor import GraphError, NodeState, Recorder, RunState, WorkflowExecutor

log = logging.getLogger("workflow.runner")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DBRecorder(Recorder):
    """Writes one execution_logs row per node attempt and streams node updates."""

    def __init__(self, execution_id: int):
        self.execution_id = execution_id

    def _emit(self, **data: Any) -> None:
        bus.publish(self.execution_id, {"type": "node_update", "execution_id": self.execution_id, **data})

    async def node_started(self, node_id, node_type, attempt, input_data):
        started = _now()

        def _write() -> int:
            with session_scope() as db:
                row = ExecutionLog(execution_id=self.execution_id, node_id=node_id, node_type=node_type,
                                   status=NodeStatus.RUNNING, attempt=attempt, started_at=started,
                                   input_data=to_json_safe(input_data))
                db.add(row)
                db.flush()
                return row.id

        log_id = await asyncio.to_thread(_write)
        self._emit(log_id=log_id, node_id=node_id, node_type=node_type, status="running", attempt=attempt)
        return {"log_id": log_id, "node_id": node_id, "node_type": node_type, "attempt": attempt}

    async def node_finished(self, handle, status: NodeState, output, error, message, duration_ms):
        finished = _now()

        def _write() -> None:
            with session_scope() as db:
                row = db.get(ExecutionLog, handle["log_id"])
                row.status = NodeStatus(status.value)
                row.output_data = to_json_safe(output) if output is not None else None
                row.error = error
                row.message = message
                row.finished_at = finished
                row.duration_ms = duration_ms

        await asyncio.to_thread(_write)
        self._emit(log_id=handle["log_id"], node_id=handle["node_id"], node_type=handle["node_type"],
                   attempt=handle["attempt"], status=status.value, error=error, message=message,
                   duration_ms=duration_ms, output=to_json_safe(output, 2000) if output is not None else None)

    async def node_skipped(self, node_id, node_type, message):
        now = _now()

        def _write() -> int:
            with session_scope() as db:
                row = ExecutionLog(execution_id=self.execution_id, node_id=node_id, node_type=node_type,
                                   status=NodeStatus.SKIPPED, attempt=1, message=message,
                                   started_at=now, finished_at=now, duration_ms=0)
                db.add(row)
                db.flush()
                return row.id

        log_id = await asyncio.to_thread(_write)
        self._emit(log_id=log_id, node_id=node_id, node_type=node_type, status="skipped", attempt=1, message=message)


class ExecutionRunner:
    def __init__(self):
        self._tasks: dict[int, asyncio.Task] = {}

    # -- creating / starting
    def create_execution(self, db, workflow: Workflow, trigger_type: TriggerType, input_data: dict | None) -> Execution:
        ex = Execution(
            workflow_id=workflow.id, workflow_version=workflow.version,
            graph_snapshot=copy.deepcopy(workflow.graph), status=ExecutionStatus.PENDING,
            trigger_type=trigger_type, input_data=to_json_safe(input_data or {}),
        )
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return ex

    def start(self, execution_id: int) -> asyncio.Task:
        """Schedule the run in the background (must be called from the event loop)."""
        task = asyncio.get_running_loop().create_task(self._run(execution_id))
        self._tasks[execution_id] = task
        task.add_done_callback(lambda _t, eid=execution_id: self._tasks.pop(eid, None))
        return task

    def get_task(self, execution_id: int) -> asyncio.Task | None:
        return self._tasks.get(execution_id)

    def cancel(self, execution_id: int) -> bool:
        task = self._tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    # -- the run itself
    def _update(self, execution_id: int, **fields: Any) -> None:
        with session_scope() as db:
            ex = db.get(Execution, execution_id)
            for k, v in fields.items():
                setattr(ex, k, v)

    def _load(self, execution_id: int) -> tuple[dict, str, dict]:
        with session_scope() as db:
            ex = db.get(Execution, execution_id)
            return ex.graph_snapshot or {}, ex.trigger_type.value, ex.input_data or {}

    async def _finish(self, execution_id: int, status: ExecutionStatus, output: Any = None, error: str | None = None):
        await asyncio.to_thread(self._update, execution_id, status=status, output_data=output,
                                error=error, finished_at=_now())
        bus.publish(execution_id, {"type": "execution_finished", "execution_id": execution_id,
                                   "status": status.value, "error": error, "output": output})

    async def _run(self, execution_id: int) -> None:
        try:
            graph, trigger_type, trigger_data = await asyncio.to_thread(self._load, execution_id)
            await asyncio.to_thread(self._update, execution_id, status=ExecutionStatus.RUNNING, started_at=_now())
            bus.publish(execution_id, {"type": "execution_started", "execution_id": execution_id})
            executor = WorkflowExecutor(graph, trigger_type, trigger_data, DBRecorder(execution_id), execution_id)
            result = await executor.run()
            status = ExecutionStatus.SUCCESS if result.status == RunState.SUCCESS else ExecutionStatus.FAILED
            await self._finish(execution_id, status, to_json_safe({"final": result.final_output}), result.error)
        except asyncio.CancelledError:
            await self._finish(execution_id, ExecutionStatus.CANCELLED, None, "Cancelled by user")
        except GraphError as e:
            await self._finish(execution_id, ExecutionStatus.FAILED, None, f"Invalid workflow: {e}")
        except Exception as e:
            log.exception("Execution %s crashed", execution_id)
            await self._finish(execution_id, ExecutionStatus.FAILED, None, f"Internal error: {type(e).__name__}: {e}")

    # -- startup housekeeping
    def recover_stale(self) -> int:
        """Runs left 'pending/running' by a previous server process can never finish: mark them failed."""
        with session_scope() as db:
            stale = db.query(Execution).filter(
                Execution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING])).all()
            for ex in stale:
                ex.status = ExecutionStatus.FAILED
                ex.error = "Interrupted by a server restart"
                ex.finished_at = _now()
            return len(stale)


runner = ExecutionRunner()
