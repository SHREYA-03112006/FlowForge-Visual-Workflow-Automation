"""Shared helpers for the test-suite. Standard library only (no pytest plugins needed).

Importing this module (it must be imported BEFORE any backend module):
  * puts the project root on sys.path
  * points OUTPUT_DIR at a temp folder, so tests never touch your real outputs/
  * allows localhost HTTP calls (tests talk to a local fake API server)
  * keeps email in simulated mode (messages land in <OUTPUT_DIR>/emails/outbox.jsonl)
"""
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_DIR = Path(tempfile.mkdtemp(prefix="wf_tests_"))
os.environ["OUTPUT_DIR"] = str(OUTPUT_DIR)
os.environ["ALLOW_PRIVATE_NETWORK"] = "true"
os.environ["EMAIL_MODE"] = "simulated"
for _k in list(os.environ):
    if _k.lower().endswith("_proxy"):
        del os.environ[_k]

from backend.app.config import settings  # noqa: E402
from backend.app.engine.executor import (GraphError, InMemoryRecorder, WorkflowExecutor,  # noqa: E402,F401
                                         validate_graph)

object.__setattr__(settings, "output_dir", OUTPUT_DIR)   # in case config was imported earlier


# ------------------------------------------------------------------ graph builders
def node(node_id, node_type, label=None, **config):
    return {"id": node_id, "type": node_type, "position": {"x": 0, "y": 0},
            "data": {"label": label or node_id, "config": config}}


def edge(source, target, handle=None):
    return {"id": f"{source}-{target}-{handle or ''}", "source": source, "target": target, "sourceHandle": handle}


def graph(nodes, edges):
    return {"nodes": list(nodes), "edges": list(edges)}


def chain(*nodes):
    """Linear workflow: nodes connected one after another."""
    return graph(nodes, [edge(a["id"], b["id"]) for a, b in zip(nodes, nodes[1:])])


# ------------------------------------------------------------------ local fake API server
class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.counters = {}
        self.active = 0
        self.max_active = 0
        self.hits = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _bump(self, key):
        st = self.server.state
        with st.lock:
            st.counters[key] = st.counters.get(key, 0) + 1
            return st.counters[key]

    def do_GET(self):
        url = urlsplit(self.path)
        parts = [p for p in url.path.split("/") if p]
        query = parse_qs(url.query)
        st = self.server.state
        with st.lock:
            st.hits.append(url.path)
        head = parts[0] if parts else ""
        if head == "json":
            self._send(200, {"id": 1, "userId": 1, "title": "hello"})
        elif head == "status":
            code = int(parts[1])
            self._send(code, {"status": code})
        elif head == "count":                      # /count/<key> -> {"count": n}
            self._send(200, {"count": self._bump(parts[1])})
        elif head == "flaky":                      # /flaky/<key>?fail=N : first N calls -> 503, then 200
            n = self._bump("flaky:" + parts[1])
            if n <= int(query.get("fail", ["2"])[0]):
                self._send(503, {"error": "temporarily unavailable", "attempt": n})
            else:
                self._send(200, {"ok": True, "attempt": n})
        elif head == "delay":                      # /delay/<seconds> : tracks concurrent requests
            with st.lock:
                st.active += 1
                st.max_active = max(st.max_active, st.active)
            try:
                time.sleep(float(parts[1]))
            finally:
                with st.lock:
                    st.active -= 1
            self._send(200, {"slept": float(parts[1])})
        else:
            self._send(404, {"error": "not found", "path": url.path})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        try:
            received = json.loads(raw)
        except ValueError:
            received = raw
        self._send(200, {"received": received, "content_type": self.headers.get("Content-Type")})


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):   # clients that time out on purpose -> no noisy tracebacks
        pass


class FakeApiServer:
    def __init__(self):
        self.httpd = _Server(("127.0.0.1", 0), _Handler)
        self.httpd.state = _State()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def state(self):
        return self.httpd.state

    def url(self, path):
        return self.base + path

    def reset(self):
        self.state.reset()

    def count(self, key):
        return self.state.counters.get(key, 0)


_server = None


def get_server() -> FakeApiServer:
    global _server
    if _server is None:
        _server = FakeApiServer()
    return _server


# ------------------------------------------------------------------ outputs
def outbox():
    path = OUTPUT_DIR / "emails" / "outbox.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clear_outbox():
    path = OUTPUT_DIR / "emails" / "outbox.jsonl"
    if path.exists():
        path.unlink()


def read_output(rel):
    return (OUTPUT_DIR / rel).read_text(encoding="utf-8")


def fake_ml_modules():
    """sys.modules entries for a stand-in classifier: 'invoice' -> billing, else technical."""
    pkg = types.ModuleType("ml_model_train")
    pkg.__path__ = []
    mod = types.ModuleType("ml_model_train.predict")
    mod.predict = lambda text: {"label": "billing" if "invoice" in text.lower() else "technical", "confidence": 0.9}
    pkg.predict = mod
    return {"ml_model_train": pkg, "ml_model_train.predict": mod}


# ------------------------------------------------------------------ base test case
class WorkflowTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = get_server()
        self.server.reset()
        clear_outbox()

    def url(self, path):
        return self.server.url(path)

    async def run_wf(self, g, trigger_type="manual", data=None):
        recorder = InMemoryRecorder()
        result = await WorkflowExecutor(g, trigger_type, data or {}, recorder).run()
        return result, recorder

    def override_setting(self, name, value):
        old = getattr(settings, name)
        object.__setattr__(settings, name, value)
        self.addCleanup(object.__setattr__, settings, name, old)

    # -- inspection helpers
    @staticmethod
    def statuses(recorder, node_id):
        """Final status of every attempt of a node, in order (e.g. ['retrying', 'success'])."""
        return [e["status"] for e in recorder.events
                if e["node_id"] == node_id and e["event"] in ("finished", "skipped")]

    @staticmethod
    def attempts(recorder, node_id):
        return [e["attempt"] for e in recorder.events if e["node_id"] == node_id and e["event"] == "started"]

    def assertStates(self, result, expected):
        actual = {k: result.node_states.get(k) for k in expected}
        self.assertEqual(actual, expected)
