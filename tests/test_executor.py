"""Executor: graph validation, run lifecycle, failure handling, cancellation, node safety."""
import asyncio
import os
import unittest
from unittest.mock import patch

from tests.helpers import (GraphError, OUTPUT_DIR, WorkflowTestCase, WorkflowExecutor, InMemoryRecorder, chain,
                           edge, graph, node, read_output, validate_graph)
from backend.app.nodes import get_handler, list_node_types
from backend.app.nodes.base import NodeConfigError

MAP = dict(source="[1, 2, 3]", expression="item")


class TestValidation(unittest.TestCase):
    def test_empty_graph(self):
        r = validate_graph({"nodes": [], "edges": []})
        self.assertFalse(r["valid"])
        self.assertIn("no nodes", r["errors"][0])

    def test_missing_trigger(self):
        r = validate_graph(graph([node("a", "map", **MAP)], []))
        self.assertFalse(r["valid"])
        self.assertTrue(any("trigger" in e for e in r["errors"]))

    def test_duplicate_node_ids(self):
        r = validate_graph(graph([node("t", "manual_trigger"), node("t", "map", **MAP)], []))
        self.assertTrue(any("Duplicate" in e for e in r["errors"]))

    def test_unknown_node_type(self):
        r = validate_graph(graph([node("t", "manual_trigger"), node("x", "teleport")], [edge("t", "x")]))
        self.assertTrue(any("unknown type 'teleport'" in e for e in r["errors"]))

    def test_required_field_missing(self):
        r = validate_graph(chain(node("t", "manual_trigger"), node("h", "http_request", "Fetch")))
        self.assertFalse(r["valid"])
        self.assertIn("Node 'Fetch': 'URL' is required.", r["errors"])

    def test_edge_to_missing_node(self):
        r = validate_graph(graph([node("t", "manual_trigger")], [edge("t", "ghost")]))
        self.assertTrue(any("missing node" in e for e in r["errors"]))

    def test_self_loop(self):
        r = validate_graph(graph([node("t", "manual_trigger"), node("a", "map", **MAP)],
                                 [edge("t", "a"), edge("a", "a")]))
        self.assertTrue(any("itself" in e for e in r["errors"]))

    def test_cycle(self):
        r = validate_graph(graph([node("t", "manual_trigger"), node("a", "map", **MAP), node("b", "map", **MAP)],
                                 [edge("t", "a"), edge("a", "b"), edge("b", "a")]))
        self.assertFalse(r["valid"])
        self.assertTrue(any("loop" in e for e in r["errors"]))

    def test_unreachable_node_is_a_warning_not_an_error(self):
        r = validate_graph(graph([node("t", "manual_trigger"), node("a", "map", **MAP), node("lonely", "map", **MAP)],
                                 [edge("t", "a")]))
        self.assertTrue(r["valid"])
        self.assertTrue(any("lonely" in w for w in r["warnings"]))

    def test_multiple_triggers_warning(self):
        r = validate_graph(graph([node("t1", "manual_trigger"), node("t2", "webhook_trigger")], []))
        self.assertTrue(r["valid"])
        self.assertTrue(any("Multiple triggers" in w for w in r["warnings"]))

    def test_valid_graph(self):
        r = validate_graph(chain(node("t", "manual_trigger"), node("a", "map", **MAP)))
        self.assertEqual(r, {"valid": True, "errors": [], "warnings": []})


class TestNodeRegistry(unittest.TestCase):
    def test_all_node_types_registered(self):
        types = {t["type"]: t["category"] for t in list_node_types()}
        self.assertEqual(len(types), 13)
        self.assertEqual(sorted(t for t, c in types.items() if c == "trigger"),
                         ["manual_trigger", "schedule_trigger", "webhook_trigger"])
        self.assertEqual(sorted(t for t, c in types.items() if c == "action"),
                         ["http_request", "python_snippet", "send_email", "write_file"])
        self.assertEqual(sorted(t for t, c in types.items() if c == "logic"), ["condition", "switch"])
        self.assertEqual(sorted(t for t, c in types.items() if c == "transform"), ["filter", "json_extract", "map"])
        self.assertEqual(types["ml_classifier"], "ml")

    def test_palette_metadata_is_complete(self):
        for t in list_node_types():
            self.assertTrue(t["label"] and t["description"], t["type"])
            for f in t["fields"]:
                self.assertTrue({"name", "label", "type", "required"} <= set(f), t["type"])

    def test_triggers_are_listed_first(self):
        self.assertEqual(list_node_types()[0]["category"], "trigger")

    def test_unknown_type_raises(self):
        with self.assertRaises(NodeConfigError):
            get_handler("nope")

    def test_branching_nodes_declare_handles(self):
        self.assertEqual(get_handler("condition").branches, ["true", "false"])
        self.assertTrue(get_handler("switch").dynamic_branches)


class TestRunLifecycle(WorkflowTestCase):
    async def test_linear_run_succeeds(self):
        g = chain(node("t", "manual_trigger"),
                  node("m", "map", source="{{trigger.nums}}", expression="item * 10"),
                  node("f", "filter", source="{{m.output.items}}", condition="item > 10"))
        res, rec = await self.run_wf(g, data={"nums": [1, 2, 3]})
        self.assertEqual(res.status.value, "success")
        self.assertIsNone(res.error)
        self.assertStates(res, {"t": "success", "m": "success", "f": "success"})
        self.assertEqual(res.final_output, {"f": {"items": [20, 30], "count": 2}})   # only terminal nodes
        self.assertEqual(set(res.outputs), {"t", "m", "f"})

    async def test_invalid_graph_raises_graph_error(self):
        with self.assertRaises(GraphError) as ctx:
            await self.run_wf(graph([node("a", "map", **MAP)], []))
        self.assertTrue(ctx.exception.errors)

    async def test_picks_trigger_matching_how_the_run_started(self):
        g = graph([node("t_manual", "manual_trigger"), node("A", "map", **MAP),
                   node("t_hook", "webhook_trigger"), node("B", "map", **MAP)],
                  [edge("t_manual", "A"), edge("t_hook", "B")])
        res, _ = await self.run_wf(g, "webhook")
        self.assertEqual(res.node_states, {"t_hook": "success", "B": "success"})
        res, _ = await self.run_wf(g, "manual")
        self.assertEqual(res.node_states, {"t_manual": "success", "A": "success"})
        res, _ = await self.run_wf(g, "schedule")          # no schedule trigger -> falls back to the first one
        self.assertIn("t_manual", res.node_states)

    async def test_unreachable_nodes_never_run(self):
        g = graph([node("t", "manual_trigger"), node("a", "map", **MAP), node("island", "map", **MAP)],
                  [edge("t", "a")])
        res, rec = await self.run_wf(g)
        self.assertNotIn("island", res.node_states)
        self.assertEqual(self.attempts(rec, "island"), [])

    async def test_failure_fails_run_and_skips_downstream_but_not_siblings(self):
        g = graph([node("t", "manual_trigger"),
                   node("bad", "http_request", "Bad call", url=self.url("/status/500")),
                   node("after", "write_file", path="never.txt", content="x"),
                   node("side", "map", **MAP)],
                  [edge("t", "bad"), edge("bad", "after"), edge("t", "side")])
        res, rec = await self.run_wf(g)
        self.assertEqual(res.status.value, "failed")
        self.assertStates(res, {"bad": "failed", "after": "skipped", "side": "success"})
        self.assertIn("Bad call", res.error)
        self.assertIn("HTTP 500", res.error)
        self.assertFalse((OUTPUT_DIR / "never.txt").exists())

    async def test_skip_reasons_are_recorded(self):
        g = graph([node("t", "manual_trigger"),
                   node("c", "condition", left="1", operator="==", right="2"),
                   node("yes", "map", **MAP), node("no", "map", **MAP),
                   node("bad", "http_request", url=self.url("/status/500")), node("after", "map", **MAP)],
                  [edge("t", "c"), edge("c", "yes", "true"), edge("c", "no", "false"),
                   edge("t", "bad"), edge("bad", "after")])
        res, rec = await self.run_wf(g)
        skipped = {e["node_id"]: e["message"] for e in rec.events if e["event"] == "skipped"}
        self.assertIn("branch not taken", skipped["yes"])
        self.assertIn("upstream node failed", skipped["after"])

    async def test_failure_cascades_through_a_chain(self):
        g = chain(node("t", "manual_trigger"), node("a", "http_request", url=self.url("/status/500")),
                  node("b", "map", **MAP), node("c", "map", **MAP))
        res, rec = await self.run_wf(g)
        self.assertStates(res, {"a": "failed", "b": "skipped", "c": "skipped"})
        skipped = {e["node_id"]: e["message"] for e in rec.events if e["event"] == "skipped"}
        self.assertIn("upstream node failed", skipped["c"])      # not mislabeled "branch not taken"

    async def test_every_attempt_is_reported_to_the_recorder(self):
        res, rec = await self.run_wf(chain(node("t", "manual_trigger"), node("m", "map", **MAP)))
        kinds = [(e["node_id"], e["event"]) for e in rec.events]
        self.assertEqual(kinds, [("t", "started"), ("t", "finished"), ("m", "started"), ("m", "finished")])
        done = rec.finished("m")[0]
        self.assertEqual(done["status"], "success")
        self.assertIn("Mapped 3", done["message"])
        self.assertIsInstance(done["duration_ms"], int)

    async def test_node_timeout(self):
        g = chain(node("t", "manual_trigger"),
                  node("slow", "http_request", url=self.url("/delay/1"), timeout_seconds=0.2))
        res, rec = await self.run_wf(g)
        self.assertEqual(res.status.value, "failed")
        self.assertIn("Timed out", res.error)

    async def test_cancellation(self):
        self.override_setting("snippet_timeout", 3.0)
        g = chain(node("t", "manual_trigger"),
                  node("slow", "python_snippet", code="x = 0\nfor i in range(10**10):\n    x += i\nresult = {}"))
        rec = InMemoryRecorder()
        task = asyncio.create_task(WorkflowExecutor(g, "manual", {}, rec).run())
        await asyncio.sleep(0.5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        last = [e for e in rec.events if e["node_id"] == "slow" and e["event"] == "finished"][-1]
        self.assertEqual(last["error"], "Cancelled")

    async def test_concurrent_runs_do_not_share_state(self):
        g = chain(node("t", "manual_trigger"), node("m", "map", source="{{trigger.v}}", expression="item + 1"))
        (r1, _), (r2, _) = await asyncio.gather(self.run_wf(g, data={"v": [1]}), self.run_wf(g, data={"v": [100]}))
        self.assertEqual(r1.outputs["m"]["items"], [2])
        self.assertEqual(r2.outputs["m"]["items"], [101])


class TestNodeSafety(WorkflowTestCase):
    async def _run_snippet(self, code):
        return await self.run_wf(chain(node("t", "manual_trigger"), node("p", "python_snippet", "Snippet", code=code)))

    async def test_snippet_result_and_print(self):
        res, rec = await self._run_snippet("print('hi there')\nresult = {'x': 1 + 1}")
        self.assertEqual(res.outputs["p"], {"x": 2})
        self.assertIn("hi there", rec.finished("p")[0]["message"])

    async def test_snippet_non_dict_result_is_wrapped(self):
        res, _ = await self._run_snippet("result = [1, 2, 3]")
        self.assertEqual(res.outputs["p"], {"value": [1, 2, 3]})

    async def test_snippet_can_use_allowed_modules(self):
        res, _ = await self._run_snippet("import math\nresult = {'r': math.sqrt(16)}")
        self.assertEqual(res.outputs["p"], {"r": 4.0})

    async def test_snippet_blocks_dangerous_imports(self):
        for code in ("import os\nresult = {}", "import subprocess", "__import__('os')", "open('/etc/passwd')"):
            with self.subTest(code=code):
                res, _ = await self._run_snippet(code)
                self.assertEqual(res.status.value, "failed")

    async def test_snippet_syntax_error_is_reported(self):
        res, _ = await self._run_snippet("result = (")
        self.assertEqual(res.status.value, "failed")
        self.assertIn("SyntaxError", res.error)

    async def test_snippet_infinite_loop_is_stopped(self):
        self.override_setting("snippet_timeout", 1.5)
        res, _ = await self._run_snippet("while True:\n    pass")
        self.assertEqual(res.status.value, "failed")
        self.assertIn("time limit", res.error)

    async def test_snippet_can_be_disabled(self):
        self.override_setting("allow_python_snippet", False)
        res, _ = await self._run_snippet("result = {}")
        self.assertEqual(res.status.value, "failed")
        self.assertIn("disabled", res.error)

    async def test_write_file_stays_inside_outputs(self):
        for bad in ("../escape.txt", "a/../../escape.txt", "/etc/evil.txt"):
            with self.subTest(path=bad):
                res, _ = await self.run_wf(chain(node("t", "manual_trigger"),
                                                 node("w", "write_file", path=bad, content="x")))
                self.assertEqual(res.status.value, "failed")
        self.assertFalse((OUTPUT_DIR.parent / "escape.txt").exists())

    async def test_write_file_write_and_append(self):
        for mode, content in (("write", "one"), ("append", "two"), ("append", "three")):
            await self.run_wf(chain(node("t", "manual_trigger"),
                                    node("w", "write_file", path="outputs/sub/log.txt", content=content, mode=mode)))
        self.assertEqual(read_output("sub/log.txt").split(), ["one", "two", "three"])

    async def test_private_addresses_blocked_when_not_allowed(self):
        with patch.dict(os.environ, {"ALLOW_PRIVATE_NETWORK": "false"}):
            for url in (self.url("/json"), "http://169.254.169.254/latest/meta-data"):
                with self.subTest(url=url):
                    res, _ = await self.run_wf(chain(node("t", "manual_trigger"), node("h", "http_request", url=url)))
                    self.assertEqual(res.status.value, "failed")
                    self.assertIn("Blocked request", res.error)

    async def test_non_http_schemes_rejected(self):
        res, _ = await self.run_wf(chain(node("t", "manual_trigger"), node("h", "http_request", url="file:///etc/passwd")))
        self.assertEqual(res.status.value, "failed")
        self.assertIn("http", res.error)

    async def test_credentials_are_redacted_in_logs(self):
        g = chain(node("t", "manual_trigger"),
                  node("h", "http_request", url=self.url("/json"),
                       headers='{"Authorization": "Bearer TOP-SECRET", "X-Other": "ok"}'))
        res, rec = await self.run_wf(g)
        self.assertEqual(res.status.value, "success")
        logged = str([e for e in rec.events if e["event"] == "started"])
        self.assertNotIn("TOP-SECRET", logged)
        self.assertIn("***", logged)


if __name__ == "__main__":
    unittest.main()
