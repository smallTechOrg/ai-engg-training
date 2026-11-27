"""19.4/2  Capstone part 2: run the ticket workflow JSON against the agent, offline

Executes helpdesk-ticket-agent-workflow.json with a miniature n8n (Webhook, IF with true/false outputs,
HTTP Request with retry and an error output, Set, Respond to Webhook with a status code) against the
in-process triage endpoint. Four requests exercise every path: urgent, routine, empty ticket, agent down.
Retry waits are simulated (nothing sleeps). A teaching model, not n8n.

Run it:   ./run 19.4/2          (Windows: run 19.4/2)
     or:  python modules/19-workflow-automation-n8n/04-capstone-a-helpdesk-ticket-workflow-calling-an-a/02_run_the_ticket_workflow.py
"""

import json
import re
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from labkit import lesson

WORKFLOW = Path(__file__).with_name("helpdesk-ticket-agent-workflow.json")
SYSTEM = (
    "You are the Larkspur Labs IT helpdesk triage agent. Read the ticket and answer with JSON only: "
    '{"category": one of network, account, hardware, software, other; '
    '"priority": "high" if many people are blocked or someone cannot work at all, otherwise "normal"; '
    '"reply": two sentences for the employee}.'
)
EXPR = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def lookup(path, data):
    for part in path:
        data = data[part]
    return data


def evaluate(value, current):
    """Evaluate '={{ $json.a.b }}' strings (the only expression form this workflow uses)."""
    if not (isinstance(value, str) and value.startswith("=")):
        return value
    if re.fullmatch(r"\{\{\s*\$json\s*\}\}", value[1:]):
        return current

    def one(match):
        plain = re.fullmatch(r"\$json\.([\w.]+)", match.group(1))
        if not plain:
            raise ValueError(f"this teaching runner cannot evaluate: {match.group(1)}")
        return str(lookup(plain.group(1).split("."), current))

    return EXPR.sub(one, value[1:])


def condition_passes(cond, item):
    left = evaluate(cond["leftValue"], item)
    op = cond["operator"]["operation"]
    if op == "notEmpty":
        return bool(str(left).strip())
    if op == "equals":
        return left == cond["rightValue"]
    raise ValueError(f"operator {op} not supported by this runner")


def start_agent(ctx, down):
    """The triage endpoint. With down=True every call answers 503, like a crashed service."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if down:
                status, payload = 503, {"error": "agent is down"}
            else:
                response = ctx.client.chat.completions.create(
                    model=ctx.model,
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": body["ticket"]}],
                    response_format={"type": "json_object"},
                )
                ctx.record_usage(response.usage, quiet=True)
                try:
                    data = json.loads(response.choices[0].message.content)
                    assert data["category"] in {"network", "account", "hardware", "software", "other"}
                    assert data["priority"] in ("high", "normal")
                    payload = {k: data[k] for k in ("category", "priority", "reply")}
                except (ValueError, KeyError, TypeError, AssertionError):
                    low = body["ticket"].lower()  # fallback: keyword rules, so the workflow always gets valid JSON
                    payload = {"category": "other", "priority": "high" if any(w in low for w in ("everyone", "nobody", "whole floor", "cannot work")) else "normal", "reply": "Thanks, the helpdesk will follow up shortly."}
                status = 200
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_workflow(ctx, wf, webhook_body, agent_url):
    nodes = {n["name"]: n for n in wf["nodes"]}
    conns = wf["connections"]
    name = next(n["name"] for n in wf["nodes"] if n["type"].endswith(".webhook"))
    item = {"headers": {}, "params": {}, "query": {}, "body": webhook_body}
    status, path = None, []
    while name:
        node, p = nodes[name], nodes[name]["parameters"]
        kind, output = node["type"].split(".")[-1], 0
        path.append(name)
        if kind == "if":
            results = [condition_passes(c, item) for c in p["conditions"]["conditions"]]
            ok = all(results) if p["conditions"]["combinator"] == "and" else any(results)
            output = 0 if ok else 1
        elif kind == "httpRequest":
            body = {f["name"]: evaluate(f["value"], item) for f in p["bodyParameters"]["parameters"]}
            tries = node.get("maxTries", 1) if node.get("retryOnFail") else 1
            waited = 0.0
            for attempt in range(1, tries + 1):  # hard cap: maxTries
                req = urllib.request.Request(agent_url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        item, failed = json.loads(resp.read()), False
                except urllib.error.HTTPError as err:
                    item, failed = {"error": {"message": f"HTTP {err.code}"}}, True
                if not failed:
                    break
                if attempt < tries:
                    waited += node.get("waitBetweenTries", 0) / 1000
            if failed:
                ctx.note(f"  Triage agent failed {tries} times (simulated {waited:.0f}s of waiting) -> error output")
                output = 1 if node.get("onError") == "continueErrorOutput" else None
                if output is None:
                    return 500, {"error": "workflow failed"}, path
        elif kind == "set":
            item = {a["name"]: evaluate(a["value"], item) for a in p["assignments"]["assignments"]}
        elif kind == "respondToWebhook":
            body = p["responseBody"]
            item = evaluate(body, item) if body.startswith("=") else json.loads(body)
            return p["options"].get("responseCode", 200), item, path
        branches = conns.get(name, {}).get("main", [])
        targets = branches[output] if output < len(branches) else []
        name = targets[0]["node"] if targets else None
    return 200, item, path


@lesson("19.4/2", "Capstone part 2: run the ticket workflow against the agent")
def main(ctx):
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    ctx.note(f"Workflow '{wf['name']}': {len(wf['nodes'])} nodes")
    scenarios = [
        ("urgent ticket", {"ticket": "The whole floor 3 has lost wifi and nobody can work."}, False),
        ("routine ticket", {"ticket": "Please reset my password for the Larkspur wiki when you can."}, False),
        ("empty ticket", {"ticket": ""}, False),
        ("agent down", {"ticket": "My monitor flickers."}, True),
    ]
    rows = []
    for label, body, down in scenarios:
        ctx.step(f"Scenario: {label}")
        server = start_agent(ctx, down)
        try:
            status, response, path = run_workflow(ctx, wf, body, f"http://127.0.0.1:{server.server_port}/triage")
        finally:
            server.shutdown()
            server.server_close()
        print("  path: " + " -> ".join(path))
        ctx.show_data(f"HTTP {status}", response)
        rows.append((label, status, response.get("status", response.get("error", "")), len(path)))

    ctx.step("Summary of the four paths")
    for label, status, what, hops in rows:
        print(f"  {label:<15} HTTP {status}  {str(what)[:60]}  ({hops} nodes)")


if __name__ == "__main__":
    main()
