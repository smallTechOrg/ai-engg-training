"""19.2/1  The helpdesk agent as an HTTP endpoint (what an n8n HTTP Request node calls)

n8n talks to your agent over HTTP. This script starts a tiny stdlib HTTP server IN THIS PROCESS on a free
port (port 0), whose POST /ask handler answers a ticket with a real model call, then calls it the way an
n8n HTTP Request node would: JSON body, a query string, a status code and a JSON reply. No n8n needed.

Run it:   ./run 19.2/1          (Windows: run 19.2/1)
     or:  python modules/19-workflow-automation-n8n/02-webhooks-http-requests-and-model-nodes/01_mock_agent_endpoint.py
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from labkit import lesson

SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Reply in two sentences."


def make_server(ctx):
    """An HTTP server whose /ask route is a one-call helpdesk agent."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/ask":
                return self._send(404, {"error": f"no route {url.path}"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "body is not JSON"})
            if not str(body.get("ticket", "")).strip():
                return self._send(422, {"error": "field 'ticket' is required"})
            response = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": body["ticket"]}],
            )
            ctx.record_usage(response.usage, quiet=True)
            source = parse_qs(url.query).get("source", ["unknown"])[0]
            self._send(200, {"reply": response.choices[0].message.content, "source": source})

        def log_message(self, *args):  # keep the lesson output clean
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)  # port 0: the OS picks a free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


@lesson("19.2/1", "The helpdesk agent as an HTTP endpoint")
def main(ctx):
    ctx.step("Start the endpoint on a free port")
    server = make_server(ctx)
    base = f"http://127.0.0.1:{server.server_port}"
    ctx.note(f"Listening on {base} (a workflow in Docker would use http://host.docker.internal:<port> instead).")

    try:
        ctx.step("Call it like an HTTP Request node: POST /ask?source=n8n")
        body = {"ticket": "My laptop will not connect to the Larkspur-Staff wifi since this morning."}
        ctx.show_data("Request body (keypair fields in the node)", body)
        status, reply = post(f"{base}/ask?source=n8n", body)
        print(f"  status: {status}")
        ctx.show_data("Response JSON", reply)

        ctx.step("What the node sees when the call goes wrong")
        for label, path, payload in (
            ("empty ticket", "/ask", {"ticket": "  "}),
            ("unknown route", "/nope", {"ticket": "x"}),
        ):
            status, reply = post(f"{base}{path}", payload)
            print(f"  {label:<14} -> {status} {reply}")
        ctx.note("By default an HTTP Request node FAILS the run on a 4xx/5xx status. 19.3 shows how to branch on that instead.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
