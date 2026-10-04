"""FastAPI entry point.

Run from the project root:   uvicorn backend.app.main:app --reload --port 8000
Docs:                        http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.init_db import init_db

from .config import settings
from .engine.runner import runner
from .engine.scheduler import scheduler
from .routes import executions, ml, webhooks, workflows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("workflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stale = runner.recover_stale()
    if stale:
        log.warning("Marked %d interrupted execution(s) as failed", stale)
    scheduler.start()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    yield
    scheduler.shutdown()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan,
              description="Visual workflow builder + execution engine (ALG-AUTO-01)")

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(workflows.meta_router)
app.include_router(workflows.router)
app.include_router(executions.router)
app.include_router(executions.ws_router)
app.include_router(webhooks.router)
app.include_router(ml.router)
