"""Run a small Python snippet in a separate, restricted process.

Inside the snippet you get:  inputs (dict of parent outputs), trigger (dict),
and you must assign the output to a variable named `result`.
  e.g.  result = {"total": sum(inputs["n2"]["numbers"])}

SECURITY NOTE: this is a best-effort restriction (isolated interpreter, whitelisted
builtins/imports, CPU/memory limits, timeout). It is NOT a hardened sandbox - disable it with
ALLOW_PYTHON_SNIPPET=false for untrusted users.
"""
import asyncio
import json
import subprocess
import sys

from ...config import settings
from ..base import BaseNode, NodeConfigError, NodeError, NodeResult, NodeRun, field_spec
from ..registry import register

MARKER = "\x00__RESULT__\x00"

RUNNER = r'''
import sys, json, builtins
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
except Exception:
    pass
payload = json.load(sys.stdin)
_names = ["abs","all","any","bool","dict","enumerate","filter","float","int","isinstance","len","list",
          "map","max","min","print","range","reversed","round","set","sorted","str","sum","tuple","zip",
          "Exception","ValueError","KeyError","TypeError","IndexError"]
SAFE = {n: getattr(builtins, n) for n in _names}
ALLOWED = {"math","json","re","datetime","statistics","string","collections","itertools","random"}
_real_import = builtins.__import__
def _imp(name, *a, **k):
    if name.split(".")[0] not in ALLOWED:
        raise ImportError("import of '%s' is not allowed" % name)
    return _real_import(name, *a, **k)
SAFE["__import__"] = _imp
env = {"__builtins__": SAFE, "inputs": payload["inputs"], "trigger": payload["trigger"], "result": None}
try:
    exec(compile(payload["code"], "<snippet>", "exec"), env)
    out = {"ok": True, "result": env.get("result")}
except BaseException as e:
    out = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
sys.stdout.write("\x00__RESULT__\x00" + json.dumps(out, default=str))
'''


@register
class PythonSnippetNode(BaseNode):
    type = "python_snippet"
    category = "action"
    label = "Python Snippet"
    description = "Run custom Python. Read `inputs` / `trigger`, assign the output to `result`."
    no_render = ("code",)
    fields = [
        field_spec("code", "Python code", "code", required=True,
                   placeholder="result = {'total': sum(inputs['n2']['numbers'])}"),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        if not settings.allow_python_snippet:
            raise NodeConfigError("Python snippets are disabled on this server (ALLOW_PYTHON_SNIPPET=false)")
        code = str(config["code"])
        payload = json.dumps({"code": code, "inputs": run.inputs, "trigger": run.ctx.trigger_data}, default=str)

        def _run():
            return subprocess.run(
                [sys.executable, "-I", "-c", RUNNER], input=payload, capture_output=True,
                text=True, timeout=settings.snippet_timeout,
            )

        try:
            proc = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            raise NodeError(f"Snippet exceeded {settings.snippet_timeout}s time limit") from None

        stdout, _, tail = proc.stdout.partition(MARKER)
        if not tail:
            raise NodeError(f"Snippet crashed: {(proc.stderr or 'no output').strip()[-500:]}")
        data = json.loads(tail)
        if not data["ok"]:
            raise NodeError(data["error"])
        result = data["result"]
        output = result if isinstance(result, dict) else {"value": result}
        printed = stdout.strip()
        return NodeResult(output=output, message=(f"Printed: {printed[:300]}" if printed else "Snippet finished"))
