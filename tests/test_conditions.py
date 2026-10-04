"""Conditions: comparison operators, branch routing, switch, joins, and the safe expression evaluator."""
import unittest

from tests.helpers import WorkflowTestCase, chain, edge, graph, node
from backend.app.engine.safe_eval import SafeEvalError, safe_eval
from backend.app.nodes.base import NodeConfigError
from backend.app.nodes.logic.condition import compare, values_equal

# (left, operator, right, expected)
COMPARISONS = [
    # equality is type-tolerant: numbers compare as numbers, booleans/None compare as text
    ("1", "==", 1, True), (1, "==", "1.0", True), (" 7 ", "==", 7, True), ("abc", "==", "abc", True),
    ("ABC", "==", "abc", False), (True, "==", "true", True), (False, "==", "true", False),
    (None, "==", "", True), ([1, 2], "==", [1, 2], True), ({"a": 1}, "==", {"a": 2}, False),
    ("1", "!=", 2, True), ("x", "!=", "x", False),
    # ordering: numeric when both sides look numeric, otherwise alphabetical
    ("10", ">", "9", True), (10, "<", 9, False), (5, ">=", 5, True), (4, "<=", 3, False),
    ("apple", "<", "banana", True), ("b", ">", "a", True),
    # containment
    ([1, 2, 3], "contains", 2, True), ([1, 2, 3], "contains", "2", True), ([1, 2, 3], "contains", 9, False),
    ("hello world", "contains", "wor", True), ({"a": 1}, "contains", "a", True), ({"a": 1}, "contains", "b", False),
    ("abc", "not_contains", "z", True), ([1], "not_contains", 1, False),
    # text
    ("hello", "starts_with", "he", True), ("hello", "ends_with", "lo", True), ("hello", "starts_with", "lo", False),
    ("order-123", "matches_regex", r"^order-\d+$", True), ("x", "matches_regex", r"^\d+$", False),
    # emptiness / truthiness
    ("", "is_empty", None, True), ([], "is_empty", None, True), ({}, "is_empty", None, True), (None, "is_empty", None, True),
    (0, "is_empty", None, False), ("x", "is_not_empty", None, True), ([1], "is_not_empty", None, True),
    ("yes", "is_true", None, True), ("TRUE", "is_true", None, True), (False, "is_true", None, False),
    ("0", "is_false", None, True), ("", "is_false", None, True), (True, "is_false", None, False),
]


class TestCompare(unittest.TestCase):
    def test_operator_table(self):
        for left, op, right, expected in COMPARISONS:
            with self.subTest(f"{left!r} {op} {right!r}"):
                self.assertIs(compare(left, op, right), expected)

    def test_unknown_operator_and_bad_regex(self):
        with self.assertRaises(NodeConfigError):
            compare(1, "~~", 2)
        with self.assertRaises(NodeConfigError):
            compare("a", "matches_regex", "(unclosed")

    def test_values_equal_is_symmetric_for_numbers(self):
        self.assertTrue(values_equal(2, "2") and values_equal("2", 2))
        self.assertFalse(values_equal(True, 1))     # booleans are not numbers


class TestSafeEval(unittest.TestCase):
    def test_allowed_expressions(self):
        cases = [("item % 2 == 0", {"item": 4}, True), ("item['price'] * 2", {"item": {"price": 4}}, 8),
                 ("item.upper()", {"item": "abc"}, "ABC"), ("len(item) > 2 and item[0] == 'a'", {"item": "abc"}, True),
                 ("item[1:3]", {"item": [1, 2, 3, 4]}, [2, 3]), ("round(3.14159, 2)", {}, 3.14),
                 ("'a' in item", {"item": {"a": 1}}, True), ("sum([1, 2, 3]) // 2", {}, 3),
                 ("x if item else y", {"item": 0, "x": "T", "y": "F"}, "F"), ("not item", {"item": []}, True),
                 ("1 < item < 5", {"item": 3}, True), ("item.get('k', 0)", {"item": {}}, 0),
                 ("[1, 2][0]", {}, 1)]
        for expr, env, expected in cases:
            with self.subTest(expr):
                self.assertEqual(safe_eval(expr, env), expected)

    def test_dangerous_or_unsupported_expressions_are_rejected(self):
        bad = ["__import__('os').system('ls')", "item.__class__", "item.pop()", "[x for x in item]", "lambda x: x",
               "exec('1')", "open('f')", "9**9**9", "'a' * 10**9", "unknown_name + 1", "1 / 0", "", "   ",
               "item[", "x = 1", "f'{item}'", "item.upper"]
        for expr in bad:
            with self.subTest(expr):
                with self.assertRaises(SafeEvalError):
                    safe_eval(expr, {"item": [1, 2, 3]})

    def test_length_limit(self):
        with self.assertRaises(SafeEvalError):
            safe_eval("1 + " * 300 + "1")


def branch_graph(left, op, right, **extra):
    return graph([node("t", "manual_trigger"), node("c", "condition", left=left, operator=op, right=right, **extra),
                  node("yes", "map", source="[1]", expression="item"), node("no", "map", source="[2]", expression="item")],
                 [edge("t", "c"), edge("c", "yes", "true"), edge("c", "no", "false")])


class TestConditionRouting(WorkflowTestCase):
    async def test_true_branch(self):
        res, _ = await self.run_wf(branch_graph("{{trigger.age}}", ">=", "18"), data={"age": 30})
        self.assertStates(res, {"c": "success", "yes": "success", "no": "skipped"})
        self.assertEqual(res.outputs["c"], {"result": True})

    async def test_false_branch(self):
        res, _ = await self.run_wf(branch_graph("{{trigger.age}}", ">=", "18"), data={"age": 12})
        self.assertStates(res, {"yes": "skipped", "no": "success"})
        self.assertEqual(res.outputs["c"], {"result": False})

    async def test_condition_message_explains_the_decision(self):
        _, rec = await self.run_wf(branch_graph("{{trigger.age}}", ">=", "18"), data={"age": 12})
        self.assertIn("'12' >= '18' -> False", rec.finished("c")[0]["message"])

    async def test_edge_without_handle_follows_every_outcome(self):
        g = graph([node("t", "manual_trigger"), node("c", "condition", left="1", operator="==", right="2"),
                   node("always", "map", source="[1]", expression="item")], [edge("t", "c"), edge("c", "always")])
        res, _ = await self.run_wf(g)
        self.assertStates(res, {"always": "success"})

    async def test_expression_mode_reads_inputs(self):
        g = graph([node("t", "manual_trigger"),
                   node("fetch", "http_request", url=self.url("/json")),
                   node("c", "condition", expression="inputs['fetch']['status_code'] == 200 and inputs['fetch']['body']['id'] == 1"),
                   node("yes", "map", source="[1]", expression="item"), node("no", "map", source="[2]", expression="item")],
                  [edge("t", "fetch"), edge("fetch", "c"), edge("c", "yes", "true"), edge("c", "no", "false")])
        res, _ = await self.run_wf(g)
        self.assertStates(res, {"yes": "success", "no": "skipped"})

    async def test_bad_expression_or_operator_fails_without_retry(self):
        for cfg in (dict(expression="__import__('os')"), dict(left="1", operator="~~", right="2")):
            with self.subTest(cfg=cfg):
                g = chain(node("t", "manual_trigger"), node("c", "condition", retries=3, **cfg))
                res, rec = await self.run_wf(g)
                self.assertEqual(res.status.value, "failed")
                self.assertEqual(self.statuses(rec, "c"), ["failed"])      # config errors are not retried

    async def test_all_operators_work_end_to_end(self):
        for left, op, right, expected in COMPARISONS[:12] + COMPARISONS[-8:]:
            with self.subTest(f"{left!r} {op} {right!r}"):
                g = chain(node("t", "manual_trigger"),
                          node("c", "condition", left="{{trigger.l}}", operator=op, right="{{trigger.r}}"))
                res, _ = await self.run_wf(g, data={"l": left, "r": right})
                self.assertIs(res.outputs["c"]["result"], expected)

    async def test_branches_can_rejoin(self):
        g = graph([node("t", "manual_trigger"), node("c", "condition", left="{{trigger.v}}", operator=">", right="0"),
                   node("pos", "map", source="[1]", expression="item"), node("neg", "map", source="[2]", expression="item"),
                   node("done", "python_snippet", code="result = {'via': sorted(inputs)}")],
                  [edge("t", "c"), edge("c", "pos", "true"), edge("c", "neg", "false"),
                   edge("pos", "done"), edge("neg", "done")])
        for value, via in ((5, ["pos"]), (-5, ["neg"])):
            with self.subTest(v=value):
                res, rec = await self.run_wf(g, data={"v": value})
                self.assertEqual(res.status.value, "success")
                self.assertEqual(res.outputs["done"], {"via": via})
                self.assertEqual(self.attempts(rec, "done"), [1])          # runs exactly once

    async def test_nested_conditions(self):
        g = graph([node("t", "manual_trigger"),
                   node("c1", "condition", left="{{trigger.a}}", operator="==", right="1"),
                   node("c2", "condition", left="{{trigger.b}}", operator="==", right="1"),
                   node("both", "map", source="[1]", expression="item"), node("only_a", "map", source="[1]", expression="item"),
                   node("neither", "map", source="[1]", expression="item")],
                  [edge("t", "c1"), edge("c1", "c2", "true"), edge("c1", "neither", "false"),
                   edge("c2", "both", "true"), edge("c2", "only_a", "false")])
        for data, winner in (({"a": 1, "b": 1}, "both"), ({"a": 1, "b": 0}, "only_a"), ({"a": 0, "b": 1}, "neither")):
            with self.subTest(data=data):
                res, _ = await self.run_wf(g, data=data)
                ran = {n for n in ("both", "only_a", "neither") if res.node_states[n] == "success"}
                self.assertEqual(ran, {winner})
        res, _ = await self.run_wf(g, data={"a": 0, "b": 1})
        self.assertEqual(res.node_states["c2"], "skipped")          # nested condition never evaluated


def switch_graph(**cfg):
    return graph([node("t", "manual_trigger"), node("sw", "switch", **cfg),
                  node("A", "map", source="[1]", expression="item"), node("B", "map", source="[1]", expression="item"),
                  node("D", "map", source="[1]", expression="item")],
                 [edge("t", "sw"), edge("sw", "A", "a"), edge("sw", "B", "b"), edge("sw", "D", "default")])


class TestSwitch(WorkflowTestCase):
    async def _which(self, g, data):
        res, _ = await self.run_wf(g, data=data)
        return {n for n in ("A", "B", "D") if res.node_states[n] == "success"}, res

    async def test_routes_to_matching_case(self):
        g = switch_graph(value="{{trigger.k}}", cases='["a", "b"]')
        self.assertEqual((await self._which(g, {"k": "a"}))[0], {"A"})
        self.assertEqual((await self._which(g, {"k": "b"}))[0], {"B"})

    async def test_falls_back_to_default(self):
        which, res = await self._which(switch_graph(value="{{trigger.k}}", cases='["a", "b"]'), {"k": "zzz"})
        self.assertEqual(which, {"D"})
        self.assertEqual(res.outputs["sw"], {"matched": "default"})

    async def test_numeric_and_comma_separated_cases(self):
        g = switch_graph(value="{{trigger.k}}", cases="a, b")           # plain comma list instead of JSON
        self.assertEqual((await self._which(g, {"k": "b"}))[0], {"B"})
        g = graph([node("t", "manual_trigger"), node("sw", "switch", value="{{trigger.n}}", cases="[1, 2]"),
                   node("two", "map", source="[1]", expression="item")], [edge("t", "sw"), edge("sw", "two", "2")])
        res, _ = await self.run_wf(g, data={"n": "2"})                   # "2" matches case 2
        self.assertStates(res, {"two": "success"})

    async def test_first_matching_case_wins(self):
        which, res = await self._which(switch_graph(value="a", cases='["a", "a", "b"]'), {})
        self.assertEqual(which, {"A"})

    async def test_empty_cases_fail(self):
        res, _ = await self.run_wf(chain(node("t", "manual_trigger"), node("sw", "switch", value="x", cases="[]")))
        self.assertEqual(res.status.value, "failed")

    async def test_switch_on_ml_style_label(self):
        g = switch_graph(value="{{trigger.label}}", cases='["a", "b"]')
        self.assertEqual((await self._which(g, {"label": "b"}))[0], {"B"})


if __name__ == "__main__":
    unittest.main()
