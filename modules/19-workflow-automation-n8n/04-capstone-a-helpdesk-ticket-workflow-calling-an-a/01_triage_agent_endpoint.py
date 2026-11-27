"""19.4/1  Capstone part 1: the triage agent as an HTTP endpoint

POST /triage {"ticket": "..."} -> {"category", "priority", "reply"}. One real model call per ticket, asked for
JSON, with a keyword fallback when the model's JSON is unusable (so the endpoint never returns garbage to a
workflow). Runs in-process on a free port; the same code is what you would deploy for n8n to call.

Run it:   ./run 19.4/1          (Windows: run 19.4/1)
     or:  python modules/19-workflow-automation-n8n/04-capstone-a-helpdesk-ticket-workflow-calling-an-a/01_triage_agent_endpoint.py
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from labkit import lesson

SYSTEM = (
    "You are the Larkspur Labs IT helpdesk triage agent. Read the ticket and answer with JSON only: "
    '{"category": one of network, account, hardware, software, other; '
    '"priority": "high" if many people are blocked or someone cannot work at all, otherwise "normal"; '
    '"reply": two sentences for the employee}.'
)
CATEGORIES = {"network", "account", "hardware", "software", "other"}
URGENT_WORDS = ("everyone", "outage", "all of us", "cannot work", "locked out", "whole floor")


def keyword_triage(ticket):
    low = ticket.lower()
    return {
        "category": "network" if any(w in low for w in ("wifi", "vpn", "network")) else "other",
        "priority": "high" if any(w in low for w in URGENT_WORDS) else "normal",
        "reply": "Thanks, we have your ticket and the helpdesk will follow up shortly.",
    }


def triage(ctx, ticket):
    """Return (result, how) where how says whether the model or the fallback produced it."""
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": ticket}],
        response_format={"type": "json_object"},
    )
    ctx.record_usage(response.usage, quiet=True)
    try:
        data = json.loads(response.choices[0].message.content)
        if data["category"] in CATEGORIES and data["priority"] in ("high", "normal") and str(data["reply"]).strip():
            return {k: data[k] for k in ("category", "priority", "reply")}, "model"
    except (ValueError, KeyError, TypeError):
        pass
    return keyword_triage(ticket), "fallback"


def start_server(ctx):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            def send(status, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return send(400, {"error": "body is not JSON"})
            if self.path != "/triage":
                return send(404, {"error": "no such route"})
            if not str(body.get("ticket", "")).strip():
                return send(422, {"error": "field 'ticket' is required"})
            result, how = triage(ctx, body["ticket"])
            send(200, result)
            ctx.note(f"  (served by: {how})")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@lesson("19.4/1", "Capstone part 1: the triage agent as an HTTP endpoint")
def main(ctx):
    server = start_server(ctx)
    base = f"http://127.0.0.1:{server.server_port}"
    tickets = [
        "The whole floor 3 has lost wifi and nobody can work.",
        "Please reset my password for the Larkspur wiki when you can.",
        "   ",
    ]
    try:
        for ticket in tickets:
            ctx.step(f"POST /triage  ticket={ticket.strip()!r}")
            req = urllib.request.Request(f"{base}/triage", data=json.dumps({"ticket": ticket}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    print(f"  status {resp.status}")
                    ctx.show_data("Response", json.loads(resp.read()))
            except urllib.error.HTTPError as err:
                print(f"  status {err.code}: {err.read().decode()}")
    finally:
        server.shutdown()
        server.server_close()
    ctx.note("The workflow in script 2 treats 200 as data, 422 as 'caller error' and a dead endpoint as 'retry then alert'.")


if __name__ == "__main__":
    main()
