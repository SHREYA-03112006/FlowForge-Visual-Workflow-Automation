"""Parallel branches: real concurrency, join semantics, concurrency limit, and failure isolation."""
import time
import unittest

from tests.helpers import WorkflowTestCase, edge, graph, node

DELAY = 0.5


def delay_node(nid, seconds=DELAY):
    return node(nid, "http_request", nid, url=f"{{{{trigger.base}}}}/delay/{seconds}")


def fan_out(count, seconds=DELAY, join=True):
    names = [f"b{i}" for i in range(count)]
    nodes = [node("t", "manual_trigger")] + [delay_node(n, seconds) for n in names]
    edges = [edge("t", n) for n in names]
    if join:
        nodes.append(node("join", "python_snippet", code="result = {'branches': sorted(inputs)}"))
        edges += [edge(n, "join") for n in names]
    return graph(nodes, edges), names


class TestParallelExecution(WorkflowTestCase):
    async def _run(self, g):
        return await self.run_wf(g, data={"base": self.server.base})

    async def test_independent_branches_really_run_at_the_same_time(self):
        g, names = fan_out(3)
        started = time.perf_counter()
        res, _ = await self._run(g)
        elapsed = time.perf_counter() - started
        self.assertEqual(res.status.value, "success")
        self.assertEqual(self.server.state.max_active, 3)                      # all 3 in flight together
        self.assertLess(elapsed, 3 * DELAY)                                    # sequential would take >= 1.5s
        self.assertEqual(res.outputs["join"], {"branches": names})

    async def test_join_waits_for_every_branch(self):
        g, names = fan_out(3, seconds=0.3)
        _, rec = await self._run(g)
        order = [(e["node_id"], e["event"]) for e in rec.events]
        join_started = order.index(("join", "started"))
        for n in names:
            self.assertLess(order.index((n, "finished")), join_started, f"join started before {n} finished")

    async def test_diamond_fan_out_and_fan_in_gives_correct_data(self):
        g = graph([node("t", "manual_trigger"),
                   node("make", "python_snippet", code="result = {'numbers': [1, 2, 3, 4, 5, 6]}"),
                   node("evens", "filter", source="{{make.output.numbers}}", condition="item % 2 == 0"),
                   node("squares", "map", source="{{make.output.numbers}}", expression="item * item"),
                   node("merge", "python_snippet",
                        code="result = {'evens': inputs['evens']['items'], 'squares': inputs['squares']['items']}")],
                  [edge("t", "make"), edge("make", "evens"), edge("make", "squares"),
                   edge("evens", "merge"), edge("squares", "merge")])
        res, _ = await self.run_wf(g)
        self.assertEqual(res.final_output, {"merge": {"evens": [2, 4, 6], "squares": [1, 4, 9, 16, 25, 36]}})

    async def test_join_runs_once_even_with_many_parents(self):
        g, _ = fan_out(5, seconds=0.05)
        _, rec = await self._run(g)
        self.assertEqual(self.attempts(rec, "join"), [1])

    async def test_concurrency_limit_is_respected(self):
        self.override_setting("max_parallel_nodes", 2)
        g, _ = fan_out(4, seconds=0.3, join=False)
        started = time.perf_counter()
        res, _ = await self._run(g)
        elapsed = time.perf_counter() - started
        self.assertEqual(res.status.value, "success")
        self.assertEqual(self.server.state.max_active, 2)
        self.assertGreaterEqual(elapsed, 2 * 0.3 - 0.05)                       # 4 branches / 2 at a time = 2 waves

    async def test_one_failed_branch_blocks_the_join_but_not_its_sibling(self):
        g = graph([node("t", "manual_trigger"), node("good", "map", source="[1]", expression="item"),
                   node("bad", "http_request", url="{{trigger.base}}/status/500"),
                   node("join", "python_snippet", code="result = {}")],
                  [edge("t", "good"), edge("t", "bad"), edge("good", "join"), edge("bad", "join")])
        res, rec = await self._run(g)
        self.assertEqual(res.status.value, "failed")
        self.assertStates(res, {"good": "success", "bad": "failed", "join": "skipped"})   # no run on partial data
        self.assertEqual(self.attempts(rec, "join"), [])

    async def test_slow_branch_does_not_delay_a_fast_one(self):
        g = graph([node("t", "manual_trigger"), delay_node("slow", 0.6), node("fast", "map", source="[1]", expression="item")],
                  [edge("t", "slow"), edge("t", "fast")])
        _, rec = await self._run(g)
        order = [(e["node_id"], e["event"]) for e in rec.events]
        self.assertLess(order.index(("fast", "finished")), order.index(("slow", "finished")))

    async def test_parallel_branches_inside_two_concurrent_runs(self):
        import asyncio
        g, _ = fan_out(2, seconds=0.3)
        (r1, _), (r2, _) = await asyncio.gather(self._run(g), self._run(g))
        self.assertEqual((r1.status.value, r2.status.value), ("success", "success"))
        self.assertEqual(self.server.state.max_active, 4)                      # 2 runs x 2 branches

    async def test_chains_inside_branches_keep_their_order(self):
        g = graph([node("t", "manual_trigger"),
                   node("a1", "map", source="[1]", expression="item + 1"), node("a2", "map", source="{{a1.output.items}}", expression="item * 10"),
                   node("b1", "map", source="[5]", expression="item + 1"), node("b2", "map", source="{{b1.output.items}}", expression="item * 10"),
                   node("join", "python_snippet", code="result = {'a': inputs['a2']['items'], 'b': inputs['b2']['items']}")],
                  [edge("t", "a1"), edge("a1", "a2"), edge("t", "b1"), edge("b1", "b2"), edge("a2", "join"), edge("b2", "join")])
        res, _ = await self.run_wf(g)
        self.assertEqual(res.outputs["join"], {"a": [20], "b": [60]})


if __name__ == "__main__":
    unittest.main()
