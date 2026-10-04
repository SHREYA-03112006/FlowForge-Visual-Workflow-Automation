"""Retries: policy maths, behaviour on flaky/failing/slow nodes, and what must NOT be retried."""
import time
import unittest

from tests.helpers import WorkflowTestCase, chain, edge, graph, node
from backend.app.engine.retry import MAX_RETRIES, RetryPolicy, is_retryable
from backend.app.nodes.base import NodeConfigError, NodeError


class TestRetryPolicy(unittest.TestCase):
    def test_defaults_mean_no_retry(self):
        p = RetryPolicy.from_config({})
        self.assertEqual((p.max_attempts, p.delay, p.backoff), (1, 1.0, 2.0))

    def test_reads_config(self):
        p = RetryPolicy.from_config({"retries": 3, "retry_delay_seconds": 2, "retry_backoff": 3})
        self.assertEqual(p.max_attempts, 4)
        self.assertEqual([p.delay_for(n) for n in (1, 2, 3)], [2, 6, 18])

    def test_accepts_numbers_given_as_text(self):
        p = RetryPolicy.from_config({"retries": "2", "retry_delay_seconds": "0.5"})
        self.assertEqual((p.max_attempts, p.delay), (3, 0.5))

    def test_values_are_clamped_and_garbage_is_ignored(self):
        self.assertEqual(RetryPolicy.from_config({"retries": 99}).max_attempts, MAX_RETRIES + 1)
        self.assertEqual(RetryPolicy.from_config({"retries": -5}).max_attempts, 1)
        self.assertEqual(RetryPolicy.from_config({"retries": "abc"}).max_attempts, 1)
        self.assertEqual(RetryPolicy.from_config({"retries": None}).max_attempts, 1)
        self.assertEqual(RetryPolicy.from_config({"retry_delay_seconds": 999}).delay, 60.0)
        self.assertEqual(RetryPolicy.from_config({"retry_delay_seconds": -3}).delay, 0.0)
        self.assertEqual(RetryPolicy.from_config({"retry_backoff": 0.1}).backoff, 1.0)

    def test_delay_is_capped(self):
        p = RetryPolicy.from_config({"retries": 10, "retry_delay_seconds": 60, "retry_backoff": 10})
        self.assertEqual(p.delay_for(5), 60.0)

    def test_which_errors_are_retryable(self):
        self.assertTrue(is_retryable(NodeError("HTTP 503")))
        self.assertTrue(is_retryable(TimeoutError()))
        self.assertTrue(is_retryable(RuntimeError("boom")))
        self.assertFalse(is_retryable(NodeConfigError("bad config")))


def flaky(key, fail, **cfg):
    return node("flaky", "http_request", "Flaky API", url=f"{{{{trigger.base}}}}/flaky/{key}?fail={fail}", **cfg)


class TestRetryBehaviour(WorkflowTestCase):
    async def _run(self, g, **kw):
        return await self.run_wf(g, data={"base": self.server.base}, **kw)

    async def test_recovers_after_transient_failures(self):
        res, rec = await self._run(chain(node("t", "manual_trigger"), flaky("k1", 2, retries=3, retry_delay_seconds=0)))
        self.assertEqual(res.status.value, "success")
        self.assertEqual(self.statuses(rec, "flaky"), ["retrying", "retrying", "success"])
        self.assertEqual(self.attempts(rec, "flaky"), [1, 2, 3])
        self.assertEqual(self.server.count("flaky:k1"), 3)
        self.assertEqual(res.outputs["flaky"]["body"], {"ok": True, "attempt": 3})

    async def test_retry_events_explain_what_happens(self):
        _, rec = await self._run(chain(node("t", "manual_trigger"), flaky("k2", 1, retries=2, retry_delay_seconds=0)))
        first = rec.finished("flaky")[0]
        self.assertEqual(first["status"], "retrying")
        self.assertIn("HTTP 503", first["error"])
        self.assertIn("Attempt 1/3 failed; retrying", first["message"])

    async def test_gives_up_after_the_configured_retries(self):
        res, rec = await self._run(chain(node("t", "manual_trigger"), flaky("k3", 99, retries=2, retry_delay_seconds=0),
                                         node("after", "map", source="[1]", expression="item")))
        self.assertEqual(res.status.value, "failed")
        self.assertEqual(self.statuses(rec, "flaky"), ["retrying", "retrying", "failed"])
        self.assertEqual(self.server.count("flaky:k3"), 3)                 # 1 try + 2 retries, no more
        self.assertStates(res, {"flaky": "failed", "after": "skipped"})
        self.assertIn("HTTP 503", res.error)

    async def test_no_retries_by_default(self):
        res, rec = await self._run(chain(node("t", "manual_trigger"), flaky("k4", 1)))
        self.assertEqual(res.status.value, "failed")
        self.assertEqual(self.statuses(rec, "flaky"), ["failed"])
        self.assertEqual(self.server.count("flaky:k4"), 1)

    async def test_configuration_errors_are_never_retried(self):
        cases = [node("x", "http_request", url="ftp://nope", retries=3), node("x", "condition", left="1", operator="~~", retries=3),
                 node("x", "map", source="[1]", expression="item.__class__", retries=3)]
        for n in cases:
            with self.subTest(type=n["type"]):
                res, rec = await self._run(chain(node("t", "manual_trigger"), n))
                self.assertEqual(self.statuses(rec, "x"), ["failed"])

    async def test_backoff_delays_are_really_applied(self):
        started = time.perf_counter()
        res, _ = await self._run(chain(node("t", "manual_trigger"),
                                       flaky("k5", 2, retries=2, retry_delay_seconds=0.1, retry_backoff=2)))
        elapsed = time.perf_counter() - started
        self.assertEqual(res.status.value, "success")
        self.assertGreaterEqual(elapsed, 0.1 + 0.2 - 0.02)                   # waited 0.1s, then 0.2s
        self.assertLess(elapsed, 3.0)

    async def test_only_the_failing_node_is_retried(self):
        g = chain(node("t", "manual_trigger"), node("up", "http_request", url="{{trigger.base}}/count/upstream"),
                  flaky("k6", 2, retries=3, retry_delay_seconds=0))
        res, _ = await self._run(g)
        self.assertEqual(res.status.value, "success")
        self.assertEqual(self.server.count("upstream"), 1)                    # upstream NOT re-run
        self.assertEqual(self.server.count("flaky:k6"), 3)

    async def test_downstream_runs_after_a_successful_retry(self):
        g = chain(node("t", "manual_trigger"), flaky("k7", 1, retries=1, retry_delay_seconds=0),
                  node("w", "write_file", path="retry_ok.txt", content="status {{flaky.output.status_code}}"))
        res, _ = await self._run(g)
        self.assertStates(res, {"flaky": "success", "w": "success"})

    async def test_timeouts_are_retried(self):
        g = chain(node("t", "manual_trigger"),
                  node("slow", "http_request", url="{{trigger.base}}/delay/0.6", timeout_seconds=0.2,
                       retries=1, retry_delay_seconds=0))
        res, rec = await self._run(g)
        self.assertEqual(self.statuses(rec, "slow"), ["retrying", "failed"])
        self.assertIn("Timed out", res.error)

    async def test_retries_apply_to_any_node_type(self):
        # a python snippet that fails because a file it needs doesn't exist yet is retried like any other node
        g = chain(node("t", "manual_trigger"), node("p", "python_snippet", code="raise ValueError('nope')", retries=2,
                                                    retry_delay_seconds=0))
        res, rec = await self._run(g)
        self.assertEqual(self.statuses(rec, "p"), ["retrying", "retrying", "failed"])
        self.assertIn("ValueError: nope", res.error)

    async def test_a_failing_branch_with_retries_does_not_block_other_branches(self):
        g = graph([node("t", "manual_trigger"), flaky("k8", 99, retries=1, retry_delay_seconds=0.1),
                   node("ok", "map", source="[1]", expression="item")], [edge("t", "flaky"), edge("t", "ok")])
        res, _ = await self._run(g)
        self.assertStates(res, {"flaky": "failed", "ok": "success"})


if __name__ == "__main__":
    unittest.main()
