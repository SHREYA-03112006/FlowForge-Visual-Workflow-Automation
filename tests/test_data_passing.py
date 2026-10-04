"""Data passing: {{templates}}, outputs flowing between nodes, transforms, and logging of data."""
import sys
import unittest
from unittest.mock import patch

from tests.helpers import (OUTPUT_DIR, WorkflowTestCase, chain, edge, fake_ml_modules, graph, node, outbox)
from backend.app.engine.context import ExecutionContext, TemplateError, redact, to_json_safe


class TestTemplates(unittest.TestCase):
    def setUp(self):
        self.ctx = ExecutionContext({"name": "Ana", "n": 5, "tags": ["a", "b"], "user": {"city": "Jhansi"}, "nothing": None})
        self.ctx.set_output("n1", {"items": [{"id": 1}, {"id": 2}], "count": 2, "body": {"title": "T"}})

    def test_whole_template_keeps_the_original_type(self):
        self.assertEqual(self.ctx.render("{{trigger.n}}"), 5)
        self.assertEqual(self.ctx.render("{{ trigger.tags }}"), ["a", "b"])
        self.assertEqual(self.ctx.render("{{  trigger.user  }}"), {"city": "Jhansi"})
        self.assertIsNone(self.ctx.render("{{trigger.nothing}}"))

    def test_embedded_templates_become_text(self):
        self.assertEqual(self.ctx.render("Hello {{trigger.name}}!"), "Hello Ana!")
        self.assertEqual(self.ctx.render("{{trigger.name}}-{{trigger.n}}"), "Ana-5")
        self.assertEqual(self.ctx.render("u={{trigger.user}}"), 'u={"city": "Jhansi"}')
        self.assertEqual(self.ctx.render("a{{trigger.nothing}}b"), "ab")

    def test_node_outputs_and_list_indexes(self):
        self.assertEqual(self.ctx.render("{{n1.output.count}}"), 2)
        self.assertEqual(self.ctx.render("{{n1.output.items[1].id}}"), 2)
        self.assertEqual(self.ctx.render("{{n1.output.items.0.id}}"), 1)
        self.assertEqual(self.ctx.render("{{n1.output.body.title}}"), "T")

    def test_renders_nested_structures_and_leaves_other_types_alone(self):
        out = self.ctx.render({"a": ["{{trigger.n}}", 7, None, True], "b": {"c": "x{{trigger.name}}"}})
        self.assertEqual(out, {"a": [5, 7, None, True], "b": {"c": "xAna"}})

    def test_skip_keys_are_not_rendered(self):
        out = self.ctx.render({"code": "{{trigger.n}}", "other": "{{trigger.n}}"}, skip_keys=("code",))
        self.assertEqual(out, {"code": "{{trigger.n}}", "other": 5})

    def test_default_values(self):
        self.assertEqual(self.ctx.render("{{trigger.missing | default('anon')}}"), "anon")
        self.assertEqual(self.ctx.render("{{trigger.missing | default(5)}}"), 5)
        self.assertEqual(self.ctx.render("{{trigger.missing | default([9])}}"), [9])
        self.assertEqual(self.ctx.render("{{trigger.name | default('anon')}}"), "Ana")   # not used when present
        self.assertEqual(self.ctx.render("Hi {{trigger.who | default('there')}}"), "Hi there")

    def test_unresolvable_references_raise_clear_errors(self):
        cases = {"{{trigger.missing}}": "missing", "{{ghost.output.x}}": "ghost",
                 "{{n1.output.items[9]}}": "9", "{{ . }}": "Empty", "{{n1.output.nope.deeper}}": "nope"}
        for template, fragment in cases.items():
            with self.subTest(template=template):
                with self.assertRaises(TemplateError) as ctx:
                    self.ctx.render(template)
                self.assertIn(fragment, str(ctx.exception))

    def test_empty_braces_are_left_alone(self):
        self.assertEqual(self.ctx.render("{{}} stays"), "{{}} stays")
        self.assertEqual(self.ctx.render("no templates here"), "no templates here")

    def test_non_dict_trigger_data_is_wrapped(self):
        self.assertEqual(ExecutionContext([1, 2]).trigger_data, {"value": [1, 2]})
        self.assertEqual(ExecutionContext(None).trigger_data, {})


class TestStorageHelpers(unittest.TestCase):
    def test_to_json_safe(self):
        import datetime
        out = to_json_safe({"s": "x" * 50, "nan": float("nan"), "inf": float("inf"), "t": (1, 2), "set": {3},
                            "dt": datetime.datetime(2026, 1, 2, 3, 4), "b": b"abc", 5: "int key", "obj": object()}, max_str=10)
        self.assertTrue(out["s"].startswith("x" * 10) and "truncated" in out["s"])
        self.assertIsNone(out["nan"]); self.assertIsNone(out["inf"])
        self.assertEqual(out["t"], [1, 2]); self.assertEqual(out["set"], [3])
        self.assertEqual(out["dt"], "2026-01-02T03:04:00"); self.assertEqual(out["b"], "<3 bytes>")
        self.assertIn("5", out)
        self.assertIsInstance(out["obj"], str)

    def test_redact(self):
        data = {"headers": {"Authorization": "Bearer x", "Accept": "json"}, "password": "p", "list": [{"token": "t"}],
                "text": '{"api_key": "k", "keep": 1}', "plain": "hello"}
        out = redact(data)
        self.assertEqual(out["headers"], {"Authorization": "***", "Accept": "json"})
        self.assertEqual(out["password"], "***")
        self.assertEqual(out["list"], [{"token": "***"}])
        self.assertEqual(out["text"], {"api_key": "***", "keep": 1})
        self.assertEqual(out["plain"], "hello")


class TestWorkflowDataFlow(WorkflowTestCase):
    async def test_manual_input_flows_into_nodes(self):
        g = chain(node("t", "manual_trigger"), node("m", "map", source="{{trigger.names}}", expression="item.upper()"))
        res, _ = await self.run_wf(g, data={"names": ["ana", "raj"]})
        self.assertEqual(res.outputs["t"], {"names": ["ana", "raj"]})
        self.assertEqual(res.outputs["m"]["items"], ["ANA", "RAJ"])

    async def test_http_to_condition_to_email(self):
        g = graph([node("t", "manual_trigger"), node("fetch", "http_request", url=self.url("/json")),
                   node("c", "condition", left="{{fetch.output.body.userId}}", operator="==", right="1"),
                   node("mail", "send_email", to="team@example.com", subject="Post {{fetch.output.body.id}}",
                        body="Title: {{fetch.output.body.title}}"),
                   node("log", "write_file", path="skipped.txt", content="no")],
                  [edge("t", "fetch"), edge("fetch", "c"), edge("c", "mail", "true"), edge("c", "log", "false")])
        res, _ = await self.run_wf(g)
        self.assertEqual(res.status.value, "success")
        self.assertStates(res, {"mail": "success", "log": "skipped"})
        self.assertEqual(res.outputs["fetch"]["status_code"], 200)
        mails = outbox()
        self.assertEqual(len(mails), 1)
        self.assertEqual((mails[0]["to"], mails[0]["subject"], mails[0]["body"]),
                         (["team@example.com"], "Post 1", "Title: hello"))

    async def test_webhook_payload_to_ml_to_email(self):
        g = chain(node("hook", "webhook_trigger"), node("cls", "ml_classifier", text="{{trigger.text}}"),
                  node("mail", "send_email", to="{{cls.output.label}}@example.com",
                       subject="New {{cls.output.label}} ticket", body="{{trigger.text}} ({{cls.output.confidence}})"))
        with patch.dict(sys.modules, fake_ml_modules()):
            res, _ = await self.run_wf(g, "webhook", {"text": "My invoice is wrong"})
            self.assertEqual(res.status.value, "success")
            res2, _ = await self.run_wf(g, "webhook", {"text": "App crashes on start"})
        self.assertEqual([m["to"] for m in outbox()], [["billing@example.com"], ["technical@example.com"]])
        self.assertEqual(outbox()[0]["body"], "My invoice is wrong (0.9)")

    async def test_ml_node_reports_missing_model_cleanly(self):
        import types
        pkg, mod = types.ModuleType("ml_model_train"), types.ModuleType("ml_model_train.predict")
        pkg.__path__ = []

        def predict(text):
            raise FileNotFoundError("model.pkl")
        mod.predict = predict
        with patch.dict(sys.modules, {"ml_model_train": pkg, "ml_model_train.predict": mod}):
            res, _ = await self.run_wf(chain(node("t", "manual_trigger"), node("c", "ml_classifier", text="hello")))
        self.assertEqual(res.status.value, "failed")
        self.assertIn("not trained", res.error)

    async def test_types_survive_a_filter_map_chain(self):
        g = chain(node("t", "manual_trigger"),
                  node("make", "python_snippet", code="result = {'numbers': [1, 2, 3, 4, 5, 6]}"),
                  node("evens", "filter", source="{{make.output.numbers}}", condition="item % 2 == 0"),
                  node("sq", "map", source="{{evens.output.items}}", expression="item * item"),
                  node("sum", "python_snippet", code="result = {'total': sum(inputs['sq']['items'])}"))
        res, _ = await self.run_wf(g)
        self.assertEqual(res.outputs["evens"], {"items": [2, 4, 6], "count": 3})
        self.assertEqual(res.outputs["sum"], {"total": 4 + 16 + 36})

    async def test_python_snippet_receives_inputs_keyed_by_parent_id(self):
        g = graph([node("t", "manual_trigger"), node("a", "map", source="[1]", expression="item"),
                   node("b", "map", source="[2]", expression="item"),
                   node("join", "python_snippet", code="result = {'keys': sorted(inputs), 'a': inputs['a']['items'], 'b': inputs['b']['items']}")],
                  [edge("t", "a"), edge("t", "b"), edge("a", "join"), edge("b", "join")])
        res, _ = await self.run_wf(g)
        self.assertEqual(res.outputs["join"], {"keys": ["a", "b"], "a": [1], "b": [2]})

    async def test_only_active_parents_appear_in_inputs(self):
        g = graph([node("t", "manual_trigger"), node("c", "condition", left="{{trigger.v}}", operator=">", right="10"),
                   node("big", "map", source="[1]", expression="item"), node("small", "map", source="[2]", expression="item"),
                   node("join", "python_snippet", code="result = {'came_from': sorted(inputs)}")],
                  [edge("t", "c"), edge("c", "big", "true"), edge("c", "small", "false"),
                   edge("big", "join"), edge("small", "join")])
        res, _ = await self.run_wf(g, data={"v": 50})
        self.assertEqual(res.outputs["join"], {"came_from": ["big"]})
        res, _ = await self.run_wf(g, data={"v": 1})
        self.assertEqual(res.outputs["join"], {"came_from": ["small"]})

    async def test_snippet_code_is_not_template_rendered(self):
        g = chain(node("t", "manual_trigger"), node("p", "python_snippet", code="result = {'literal': '{{trigger.a}}'}"))
        res, _ = await self.run_wf(g, data={"a": 1})
        self.assertEqual(res.outputs["p"], {"literal": "{{trigger.a}}"})

    async def test_http_post_body_templates(self):
        # numbers stay numbers when the template is outside the quotes
        g = chain(node("t", "manual_trigger"),
                  node("post", "http_request", method="POST", url=self.url("/echo"),
                       body='{"n": {{trigger.n}}, "who": "{{trigger.name}}"}'))
        res, _ = await self.run_wf(g, data={"n": 5, "name": "Ana"})
        self.assertEqual(res.outputs["post"]["body"]["received"], {"n": 5, "who": "Ana"})
        self.assertEqual(res.outputs["post"]["body"]["content_type"], "application/json")

    async def test_http_query_params_and_template_in_url(self):
        g = chain(node("t", "manual_trigger"),
                  node("h", "http_request", url=self.url("/count/{{trigger.key}}"), params='{"x": 1}'))
        res, _ = await self.run_wf(g, data={"key": "abc"})
        self.assertEqual(res.outputs["h"]["body"], {"count": 1})
        self.assertEqual(self.server.state.hits, ["/count/abc"])

    async def test_json_extract(self):
        data = {"user": {"address": {"city": "Kanpur"}, "tags": ["x", "y"]}}
        g = chain(node("t", "manual_trigger"),
                  node("fields", "json_extract", source="{{trigger.user}}", fields='{"city": "address.city", "first": "tags[0]"}'))
        res, _ = await self.run_wf(g, data=data)
        self.assertEqual(res.outputs["fields"], {"city": "Kanpur", "first": "x"})

        g = chain(node("t", "manual_trigger"), node("one", "json_extract", source="{{trigger.user}}", path="tags.1"))
        res, _ = await self.run_wf(g, data=data)
        self.assertEqual(res.outputs["one"], {"value": "y"})

        g = chain(node("t", "manual_trigger"),
                  node("js", "json_extract", source='{"a": {"b": 7}}', path="a.b"))      # JSON given as text
        res, _ = await self.run_wf(g)
        self.assertEqual(res.outputs["js"], {"value": 7})

    async def test_json_extract_missing_path_and_default(self):
        g = chain(node("t", "manual_trigger"), node("x", "json_extract", source="{{trigger.user}}", path="nope"))
        res, _ = await self.run_wf(g, data={"user": {}})
        self.assertEqual(res.status.value, "failed")
        self.assertIn("'nope' not found", res.error)
        g = chain(node("t", "manual_trigger"), node("x", "json_extract", source="{{trigger.user}}", path="nope", default="N/A"))
        res, _ = await self.run_wf(g, data={"user": {}})
        self.assertEqual(res.outputs["x"], {"value": "N/A"})

    async def test_map_and_filter_on_records(self):
        people = [{"name": "Ana", "age": 31}, {"name": "Raj", "age": 17}, {"name": "Mei", "age": 45}]
        g = chain(node("t", "manual_trigger"),
                  node("adults", "filter", source="{{trigger.people}}", condition="item['age'] >= 18"),
                  node("names", "map", source="{{adults.output.items}}", expression="item['name'].upper() + '#' + str(index)"))
        res, _ = await self.run_wf(g, data={"people": people})
        self.assertEqual(res.outputs["names"]["items"], ["ANA#0", "MEI#1"])

    async def test_transform_nodes_fail_clearly_on_bad_input(self):
        cases = [("map", dict(source="{{trigger.v}}", expression="item"), {"v": 5}, "must be a list"),
                 ("map", dict(source="[1]", expression="item.__class__"), {}, "Expression error"),
                 ("filter", dict(source="[1]", condition="nope > 1"), {}, "Unknown name")]
        for ntype, cfg, data, fragment in cases:
            with self.subTest(ntype=ntype, fragment=fragment):
                res, rec = await self.run_wf(chain(node("t", "manual_trigger"), node("x", ntype, **cfg)), data=data)
                self.assertEqual(res.status.value, "failed")
                self.assertIn(fragment, res.error)

    async def test_unresolved_template_fails_once_and_skips_downstream(self):
        g = chain(node("t", "manual_trigger"), node("m", "map", source="{{trigger.missing}}", expression="item", retries=3),
                  node("after", "map", source="[1]", expression="item"))
        res, rec = await self.run_wf(g)
        self.assertEqual(res.status.value, "failed")
        self.assertIn("missing", res.error)
        self.assertStates(res, {"m": "failed", "after": "skipped"})
        self.assertEqual(self.statuses(rec, "m"), ["failed"])          # config errors are never retried

    async def test_large_outputs_are_truncated_in_logs_but_not_in_data_flow(self):
        g = chain(node("t", "manual_trigger"),
                  node("big", "python_snippet", code="result = {'s': 'x' * 20000}"),
                  node("len", "python_snippet", code="result = {'n': len(inputs['big']['s'])}"))
        res, rec = await self.run_wf(g)
        self.assertEqual(res.outputs["len"], {"n": 20000})                   # next node got everything
        logged = rec.finished("big")[0]["output"]["s"]
        self.assertLess(len(logged), 20000)
        self.assertIn("truncated", logged)

    async def test_email_body_can_embed_objects(self):
        g = chain(node("t", "manual_trigger"), node("m", "send_email", to="a@b.co", subject="s", body="Data: {{trigger.obj}}"))
        res, _ = await self.run_wf(g, data={"obj": {"k": [1, 2]}})
        self.assertEqual(outbox()[0]["body"], 'Data: {"k": [1, 2]}')


if __name__ == "__main__":
    unittest.main()
