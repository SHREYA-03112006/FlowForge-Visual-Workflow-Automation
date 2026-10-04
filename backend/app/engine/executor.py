"""DAG workflow executor.

How a run works
  1. validate_graph() - structure, node types, required config, cycles.
  2. Pick ONE trigger node (the one matching the run's trigger type, else the first)
     and everything reachable from it.
  3. Every reachable node becomes an asyncio task that waits for its parents.
     Independent branches therefore run in PARALLEL automatically.
  4. A node runs if at least one incoming edge is *active*:
        parent succeeded AND (edge has no handle OR parent's chosen branch == edge handle)
     otherwise it is SKIPPED (branch not taken / upstream failed).
  5. Templates {{...}} in the node config are resolved against earlier outputs,
     the node is executed with timeout + retries, and every attempt is reported to a Recorder.
  6. Run is FAILED if any node failed, otherwise SUCCESS.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..config import settings
from ..nodes import get_handler, is_known_type
from ..nodes.base import NodeResult, NodeRun
from .context import ExecutionContext, TemplateError, redact, to_json_safe
from .retry import RetryPolicy, is_retryable


class NodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class RunState(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GraphError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# ---------------------------------------------------------------- recorder
class Recorder:
    """Receives progress callbacks. Subclass to persist / broadcast. Default: no-op."""

    async def node_started(self, node_id: str, node_type: str, attempt: int, input_data: dict) -> Any:
        return None

    async def node_finished(self, handle: Any, status: NodeState, output: Any, error: str | None,
                            message: str | None, duration_ms: int) -> None:
        return None

    async def node_skipped(self, node_id: str, node_type: str, message: str) -> None:
        return None


class InMemoryRecorder(Recorder):
    """Keeps events in a list - used by tests and dry runs."""

    def __init__(self):
        self.events: list[dict] = []

    async def node_started(self, node_id, node_type, attempt, input_data):
        h = {"node_id": node_id, "node_type": node_type, "attempt": attempt}
        self.events.append({**h, "event": "started", "input": input_data})
        return h

    async def node_finished(self, handle, status, output, error, message, duration_ms):
        self.events.append({**handle, "event": "finished", "status": status.value, "output": output,
                            "error": error, "message": message, "duration_ms": duration_ms})

    async def node_skipped(self, node_id, node_type, message):
        self.events.append({"node_id": node_id, "node_type": node_type, "event": "skipped",
                            "status": "skipped", "message": message})

    def finished(self, node_id: str) -> list[dict]:
        return [e for e in self.events if e["node_id"] == node_id and e["event"] in ("finished", "skipped")]


@dataclass
class ExecutionResult:
    status: RunState
    outputs: dict[str, Any] = field(default_factory=dict)       # every node's output
    final_output: dict[str, Any] = field(default_factory=dict)  # outputs of terminal nodes
    node_states: dict[str, str] = field(default_factory=dict)
    error: str | None = None


# ------------------------------------------------------------- validation
def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def validate_graph(graph: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    nodes = (graph or {}).get("nodes") or []
    edges = (graph or {}).get("edges") or []
    if not nodes:
        return {"valid": False, "errors": ["The workflow has no nodes."], "warnings": []}

    by_id: dict[str, dict] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            errors.append("A node is missing its id.")
        elif nid in by_id:
            errors.append(f"Duplicate node id '{nid}'.")
        else:
            by_id[nid] = n

    triggers: list[str] = []
    for nid, n in by_id.items():
        label = (n.get("data") or {}).get("label") or nid
        ntype = n.get("type")
        if not is_known_type(ntype):
            errors.append(f"Node '{label}': unknown type '{ntype}'.")
            continue
        handler = get_handler(ntype)
        if handler.category == "trigger":
            triggers.append(nid)
        config = (n.get("data") or {}).get("config") or {}
        for f in handler.fields:
            if f.get("required") and _blank(config.get(f["name"])):
                errors.append(f"Node '{label}': '{f['label']}' is required.")

    adj: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = {nid: 0 for nid in by_id}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s not in by_id or t not in by_id:
            errors.append(f"Connection {s!r} -> {t!r} points to a missing node.")
            continue
        if s == t:
            errors.append(f"Node '{s}' is connected to itself.")
            continue
        adj[s].append(t)
        indeg[t] += 1

    # cycle detection (Kahn)
    deg = dict(indeg)
    queue = deque(n for n, d in deg.items() if d == 0)
    seen = 0
    while queue:
        cur = queue.popleft()
        seen += 1
        for nxt in adj[cur]:
            deg[nxt] -= 1
            if deg[nxt] == 0:
                queue.append(nxt)
    if seen != len(by_id):
        errors.append("The workflow contains a loop (cycle). Connections must flow in one direction.")

    if not triggers:
        errors.append("Add a trigger node (Manual, Webhook or Schedule) to start the workflow.")
    elif len(triggers) > 1:
        warnings.append("Multiple triggers found: only one runs per execution (the one matching how it was started).")

    if triggers:
        reach = set(triggers)
        dq = deque(triggers)
        while dq:
            cur = dq.popleft()
            for nxt in adj[cur]:
                if nxt not in reach:
                    reach.add(nxt)
                    dq.append(nxt)
        for nid in by_id:
            if nid not in reach:
                label = (by_id[nid].get("data") or {}).get("label") or nid
                warnings.append(f"Node '{label}' is not connected to a trigger and will never run.")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------- executor
class WorkflowExecutor:
    def __init__(self, graph: dict, trigger_type: str = "manual", trigger_data: Any = None,
                 recorder: Recorder | None = None, execution_id: int | None = None):
        self.graph = graph
        self.trigger_type = trigger_type
        self.recorder = recorder or Recorder()
        self.ctx = ExecutionContext(trigger_data, execution_id)
        self.state: dict[str, NodeState] = {}
        self.branch: dict[str, str | None] = {}
        self.errors: dict[str, str] = {}
        self.skip_cause: dict[str, str] = {}

    # -- setup
    def _pick_root(self) -> str:
        wanted = f"{self.trigger_type}_trigger"
        triggers = [n for n in self.graph["nodes"] if get_handler(n["type"]).category == "trigger"]
        for n in triggers:
            if n["type"] == wanted:
                return n["id"]
        return triggers[0]["id"]

    def _build(self) -> None:
        self.nodes = {n["id"]: n for n in self.graph["nodes"]}
        edges = self.graph.get("edges") or []
        self.root = self._pick_root()
        out_edges: dict[str, list[dict]] = defaultdict(list)
        for e in edges:
            out_edges[e["source"]].append(e)
        reach = {self.root}
        dq = deque([self.root])
        while dq:
            cur = dq.popleft()
            for e in out_edges[cur]:
                if e["target"] not in reach:
                    reach.add(e["target"])
                    dq.append(e["target"])
        self.order = [n["id"] for n in self.graph["nodes"] if n["id"] in reach]
        self.incoming = {nid: [] for nid in self.order}
        for e in edges:
            if e["source"] in reach and e["target"] in reach and e["target"] != self.root:
                self.incoming[e["target"]].append(e)
        self.terminal = [nid for nid in self.order if not out_edges[nid]]

    # -- main entry
    async def run(self) -> ExecutionResult:
        check = validate_graph(self.graph)
        if not check["valid"]:
            raise GraphError(check["errors"])
        self._build()
        self.state = {nid: NodeState.PENDING for nid in self.order}
        self.branch = {nid: None for nid in self.order}
        self.done = {nid: asyncio.Event() for nid in self.order}
        self.sem = asyncio.Semaphore(max(1, settings.max_parallel_nodes))

        tasks = [asyncio.create_task(self._process(nid)) for nid in self.order]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise

        failed = [nid for nid, s in self.state.items() if s == NodeState.FAILED]
        status = RunState.FAILED if failed else RunState.SUCCESS
        error = None
        if failed:
            error = "; ".join(f"{self._label(n)}: {self.errors.get(n, 'failed')}" for n in failed[:5])
        final = {nid: self.ctx.outputs[nid] for nid in self.terminal if self.state[nid] == NodeState.SUCCESS}
        return ExecutionResult(status=status, outputs=dict(self.ctx.outputs), final_output=final,
                               node_states={k: v.value for k, v in self.state.items()}, error=error)

    # -- per node
    def _label(self, nid: str) -> str:
        return (self.nodes[nid].get("data") or {}).get("label") or nid

    def _edge_active(self, e: dict) -> bool:
        src = e["source"]
        if self.state[src] != NodeState.SUCCESS:
            return False
        handle, chosen = e.get("sourceHandle"), self.branch[src]
        return (not handle) or chosen is None or handle == chosen

    async def _process(self, nid: str) -> None:
        node = self.nodes[nid]
        try:
            parents = {e["source"] for e in self.incoming[nid]}
            if parents:
                await asyncio.gather(*(self.done[p].wait() for p in parents))
            upstream_failed = any(
                self.skip_cause.get(e["source"]) == "upstream"
                or self.state[e["source"]] == NodeState.FAILED
                for e in self.incoming[nid]
            )
            active = [e for e in self.incoming[nid] if self._edge_active(e)]
            if nid != self.root and (upstream_failed or not active):
                self.skip_cause[nid] = "upstream" if upstream_failed else "branch"
                self.state[nid] = NodeState.SKIPPED
                await self.recorder.node_skipped(
                    nid, node["type"],
                    "Skipped: an upstream node failed" if upstream_failed else "Skipped: branch not taken")
                return
            inputs = {e["source"]: self.ctx.outputs[e["source"]] for e in active}
            async with self.sem:
                await self._run_node(nid, inputs)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # engine bug safety net - never leave dependants hanging
            self.state[nid] = NodeState.FAILED
            self.errors[nid] = f"Internal error: {type(e).__name__}: {e}"
        finally:
            self.done[nid].set()

    async def _run_node(self, nid: str, inputs: dict) -> None:
        node = self.nodes[nid]
        ntype = node["type"]
        handler = get_handler(ntype)
        raw_cfg = (node.get("data") or {}).get("config") or {}
        self.state[nid] = NodeState.RUNNING

        try:
            cfg = self.ctx.render(raw_cfg, skip_keys=handler.no_render)
        except TemplateError as e:
            h = await self.recorder.node_started(nid, ntype, 1, {"config": redact(raw_cfg), "inputs": to_json_safe(inputs)})
            await self.recorder.node_finished(h, NodeState.FAILED, None, str(e), "Could not resolve a {{reference}}", 0)
            self.state[nid] = NodeState.FAILED
            self.errors[nid] = str(e)
            return

        policy = RetryPolicy.from_config(cfg)
        try:
            timeout = float(cfg.get("timeout_seconds") or settings.node_timeout)
        except (TypeError, ValueError):
            timeout = settings.node_timeout
        timeout = max(0.1, timeout)

        for attempt in range(1, policy.max_attempts + 1):
            handle = await self.recorder.node_started(
                nid, ntype, attempt, to_json_safe({"config": redact(cfg), "inputs": inputs}))
            t0 = time.perf_counter()
            err: str | None = None
            retryable = False
            try:
                handler.check_config(cfg)
                run = NodeRun(node_id=nid, inputs=inputs, ctx=self.ctx, attempt=attempt, trigger_type=self.trigger_type)
                result = await asyncio.wait_for(handler.execute(cfg, run), timeout=timeout)
                if not isinstance(result, NodeResult):
                    result = NodeResult(output=result)
                self.ctx.set_output(nid, result.output)
                self.branch[nid] = result.branch
                self.state[nid] = NodeState.SUCCESS
                ms = int((time.perf_counter() - t0) * 1000)
                await self.recorder.node_finished(handle, NodeState.SUCCESS, to_json_safe(result.output), None,
                                                  result.message, ms)
                return
            except asyncio.CancelledError:
                self.state[nid] = NodeState.FAILED
                self.errors[nid] = "Cancelled"
                await self.recorder.node_finished(handle, NodeState.FAILED, None, "Cancelled", None,
                                                  int((time.perf_counter() - t0) * 1000))
                raise
            except asyncio.TimeoutError:
                err, retryable = f"Timed out after {timeout:g}s", True
            except Exception as exc:
                err = str(exc) or type(exc).__name__
                retryable = is_retryable(exc)

            ms = int((time.perf_counter() - t0) * 1000)
            if retryable and attempt < policy.max_attempts:
                delay = policy.delay_for(attempt)
                await self.recorder.node_finished(
                    handle, NodeState.RETRYING, None, err,
                    f"Attempt {attempt}/{policy.max_attempts} failed; retrying in {delay:g}s", ms)
                self.state[nid] = NodeState.RETRYING
                await asyncio.sleep(delay)
                self.state[nid] = NodeState.RUNNING
                continue
            self.state[nid] = NodeState.FAILED
            self.errors[nid] = err or "failed"
            await self.recorder.node_finished(handle, NodeState.FAILED, None, err, None, ms)
            return
