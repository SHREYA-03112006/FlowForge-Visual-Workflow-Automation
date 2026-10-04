"""Insert demo workflows.  Run from the project root:

    python -m database.seed_data

Node types used here must match the handlers in backend/app/nodes/:
manual_trigger, webhook_trigger, schedule_trigger, http_request, send_email,
write_file, python_snippet, condition, map, filter, json_extract, ml_classifier.
Templating syntax: {{node_id.output.field}} and {{trigger.field}}.
"""
from .init_db import init_db
from .models import Workflow
from .session import session_scope


def node(nid, ntype, label, x, y, **config):
    return {"id": nid, "type": ntype, "position": {"x": x, "y": y},
            "data": {"label": label, "config": config}}


def edge(eid, src, dst, handle=None):
    return {"id": eid, "source": src, "target": dst, "sourceHandle": handle}


DEMOS = [
    {
        "name": "Demo 1: API data -> condition -> email",
        "description": "Fetch a post, branch on its userId, send a simulated email.",
        "graph": {
            "nodes": [
                node("n1", "manual_trigger", "Start", 0, 100),
                node("n2", "http_request", "Fetch post", 220, 100,
                     method="GET", url="https://jsonplaceholder.typicode.com/posts/1"),
                node("n3", "condition", "userId == 1?", 440, 100,
                     left="{{n2.output.body.userId}}", operator="==", right="1"),
                node("n4", "send_email", "Notify (true)", 680, 20,
                     to="team@example.com", subject="Post {{n2.output.body.id}}",
                     body="Title: {{n2.output.body.title}}"),
                node("n5", "write_file", "Log (false)", 680, 200,
                     path="outputs/skipped.txt", content="userId did not match"),
            ],
            "edges": [
                edge("e1", "n1", "n2"), edge("e2", "n2", "n3"),
                edge("e3", "n3", "n4", "true"), edge("e4", "n3", "n5", "false"),
            ],
        },
    },
    {
        "name": "Demo 2: Parallel branches + transform",
        "description": "Two branches run in parallel, then results are merged.",
        "graph": {
            "nodes": [
                node("n1", "manual_trigger", "Start", 0, 120),
                node("n2", "python_snippet", "Make numbers", 220, 120,
                     code="result = {'numbers': [1, 2, 3, 4, 5, 6]}"),
                node("n3", "filter", "Keep evens", 460, 40,
                     source="{{n2.output.numbers}}", condition="item % 2 == 0"),
                node("n4", "map", "Square all", 460, 200,
                     source="{{n2.output.numbers}}", expression="item * item"),
                node("n5", "python_snippet", "Merge", 700, 120,
                     code="result = {'evens': inputs['n3']['items'], 'squares': inputs['n4']['items']}"),
            ],
            "edges": [
                edge("e1", "n1", "n2"), edge("e2", "n2", "n3"), edge("e3", "n2", "n4"),
                edge("e4", "n3", "n5"), edge("e5", "n4", "n5"),
            ],
        },
    },
    {
        "name": "Demo 3: Webhook ticket classifier",
        "description": "Webhook receives a ticket, ML node classifies it, email routes it.",
        "graph": {
            "nodes": [
                node("n1", "webhook_trigger", "Ticket webhook", 0, 100),
                node("n2", "ml_classifier", "Classify ticket", 240, 100,
                     text="{{trigger.text}}"),
                node("n3", "send_email", "Route to team", 480, 100,
                     to="{{n2.output.label}}@example.com",
                     subject="New {{n2.output.label}} ticket",
                     body="{{trigger.text}} (confidence {{n2.output.confidence}})"),
            ],
            "edges": [edge("e1", "n1", "n2"), edge("e2", "n2", "n3")],
        },
    },
    {
        "name": "Demo 4: Scheduled health check with retries",
        "description": "Runs every 5 minutes; HTTP node retries on failure.",
        "schedule_cron": "*/5 * * * *",
        "graph": {
            "nodes": [
                node("n1", "schedule_trigger", "Every 5 min", 0, 100, cron="*/5 * * * *"),
                node("n2", "http_request", "Ping service", 240, 100,
                     method="GET", url="https://httpbin.org/status/200",
                     retries=3, retry_delay_seconds=2),
                node("n3", "write_file", "Record result", 480, 100,
                     path="outputs/health.log", content="status={{n2.output.status_code}}"),
            ],
            "edges": [edge("e1", "n1", "n2"), edge("e2", "n2", "n3")],
        },
    },
]


def seed() -> None:
    init_db()
    with session_scope() as db:
        existing = {w.name for w in db.query(Workflow).all()}
        added = 0
        for demo in DEMOS:
            if demo["name"] in existing:
                continue
            db.add(Workflow(
                name=demo["name"], description=demo["description"], graph=demo["graph"],
                schedule_cron=demo.get("schedule_cron"), is_template=True,
            ))
            added += 1
        print(f"Seeded {added} workflow(s) ({len(DEMOS) - added} already existed).")


if __name__ == "__main__":
    seed()
