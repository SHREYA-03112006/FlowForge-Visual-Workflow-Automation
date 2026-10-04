"""Cron-style scheduled triggers (APScheduler). Jobs are keyed `wf-<workflow_id>`."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Workflow, session_scope
from database.models import TriggerType

from .executor import validate_graph
from .runner import runner

log = logging.getLogger("workflow.scheduler")


def validate_cron(expr: str) -> None:
    """Raises ValueError for an invalid 5-field cron expression."""
    CronTrigger.from_crontab(expr)


class WorkflowScheduler:
    def __init__(self):
        self._sched = AsyncIOScheduler()

    def start(self) -> None:
        self._sched.start()
        with session_scope() as db:
            for wf in db.query(Workflow).filter(Workflow.is_active.is_(True), Workflow.schedule_cron.isnot(None)):
                try:
                    self.sync(wf.id, wf.schedule_cron, wf.is_active)
                except ValueError as e:
                    log.warning("Workflow %s has invalid cron %r: %s", wf.id, wf.schedule_cron, e)

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)

    def sync(self, workflow_id: int, cron: str | None, active: bool) -> None:
        """Create/replace/remove the job for a workflow."""
        job_id = f"wf-{workflow_id}"
        self.remove(workflow_id)
        if cron and active:
            self._sched.add_job(self._fire, CronTrigger.from_crontab(cron), args=[workflow_id], id=job_id,
                                replace_existing=True, max_instances=1, coalesce=True)

    def remove(self, workflow_id: int) -> None:
        job_id = f"wf-{workflow_id}"
        if self._sched.get_job(job_id):
            self._sched.remove_job(job_id)

    def next_run(self, workflow_id: int):
        job = self._sched.get_job(f"wf-{workflow_id}")
        nxt = getattr(job, "next_run_time", None) if job else None
        return nxt.isoformat() if nxt else None

    async def _fire(self, workflow_id: int) -> None:
        def _create():
            with session_scope() as db:
                wf = db.get(Workflow, workflow_id)
                if not wf or not wf.is_active:
                    return None
                if not validate_graph(wf.graph)["valid"]:
                    log.warning("Scheduled workflow %s skipped: invalid graph", workflow_id)
                    return None
                return runner.create_execution(db, wf, TriggerType.SCHEDULE, {"scheduled": True}).id

        execution_id = await asyncio.to_thread(_create)
        if execution_id:
            runner.start(execution_id)


scheduler = WorkflowScheduler()
