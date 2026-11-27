"""19.2/2  Run the workflow JSON offline, node by node

Loads helpdesk-agent-workflow.json and executes it with a miniature n8n: a Webhook node produces ONE item
with headers/params/query/body, an HTTP Request node really POSTs to an in-process agent endpoint, a Set
node reshapes, Respond to Webhook returns. Only the tiny expression forms the file uses are supported
(`{{ $json.a.b }}` and `{{ $('Node').item.json.a.b }}`). This is a teaching model, not n8n.

Run it:   ./run 19.2/2          (Windows: run 19.2/2)
     or:  python modules/19-workflow-automation-n8n/02-webhooks-http-requests-and-model-nodes/02_run_workflow_offline.py
"""

import json
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from labkit import lesson

WORKFLOW = Path(__file__).with_name("helpdesk-agent-workflow.json")
SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Reply in two sentences."
EXPR = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def lookup(path, data):
    for part in path:
        data = data[part]
    return data


def evaluate(value, current, outputs):
    """Evaluate '={{ ... }}' strings. `current` is $json, `outputs` maps node name -> its item."""
    if not (isinstance(value, str) and value.startswith("=")):
        return value

    def one(match):
        expr = match.group(1)
        named = re.fullmatch(r"\$\('([^']+)'\)\.item\.json\.([\w.]+)", expr)
        if named:
            return str(lookup(named.group(2).split("."), outputs[named.group(1)]))
        if expr == "$json":
            return json.dumps(current)
        plain = re.fullmatch(r"\$json\.([\w.]+)", expr)
        if plain:
            return str(lookup(plain.group(1).split("."), current))
        raise ValueError(f"this teaching runner cannot evaluate: {expr}")

    text = value[1:]
    if re.fullmatch(r"\{\{\s*\$json\s*\}\}", text):  # whole value is $json: keep it an object
        return current
    return EXPR.sub(one, text)


def start_agent(ctx):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            response = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": body["ticket"]}],
            )
            ctx.record_usage(response.usage, quiet=True)
            source = parse_qs(urlparse(self.path).query).get("source", ["?"])[0]
            data = json.dumps({"reply": response.choices[0].message.content, "source": source}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@lesson("19.2/2", "Run the workflow JSON offline")
def main(ctx):
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}
    chain, current = [], next(n["name"] for n in wf["nodes"] if n["type"].endswith(".webhook"))
    while current:  # follow the single main output of every node
        chain.append(current)
        nxt = wf["connections"].get(current, {}).get("main", [[]])[0]
        current = nxt[0]["node"] if nxt else None
    ctx.note("Execution order: " + " -> ".join(chain))

    server = start_agent(ctx)
    agent_url = f"http://127.0.0.1:{server.server_port}/ask"
    outputs, item = {}, None
    try:
        for name in chain:
            node = nodes[name]
            kind, p = node["type"].split(".")[-1], node["parameters"]
            ctx.step(f"Node: {name} ({kind})")
            if kind == "webhook":
                # What the Webhook node hands to the next node: ONE item with the request split into parts.
                item = {
                    "headers": {"content-type": "application/json", "user-agent": "curl/8"},
                    "params": {},
                    "query": {},
                    "body": {"ticket": "I cannot reach the Larkspur VPN from home; it times out after login."},
                }
            elif kind == "httpRequest":
                body = {f["name"]: evaluate(f["value"], item, outputs) for f in p["bodyParameters"]["parameters"]}
                query = "&".join(f"{f['name']}={evaluate(f['value'], item, outputs)}" for f in p["queryParameters"]["parameters"])
                # The workflow points at host.docker.internal:8008; swap in the in-process endpoint's real address.
                ctx.note(f"{p['method']} {p['url']}  (rewritten to {agent_url} for this run), query {query}")
                req = urllib.request.Request(f"{agent_url}?{query}", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    item = json.loads(resp.read())
                ctx.note(f"retryOnFail={node.get('retryOnFail')} maxTries={node.get('maxTries')} wait={node.get('waitBetweenTries')} ms (not needed this time)")
            elif kind == "set":
                item = {a["name"]: evaluate(a["value"], item, outputs) for a in p["assignments"]["assignments"]}
            elif kind == "respondToWebhook":
                item = evaluate(p["responseBody"], item, outputs)
            outputs[name] = item
            ctx.show_data("Output item", item)
    finally:
        server.shutdown()
        server.server_close()

    ctx.step("What the caller of the webhook receives")
    ctx.show_data("HTTP 200 body", item)


if __name__ == "__main__":
    main()
