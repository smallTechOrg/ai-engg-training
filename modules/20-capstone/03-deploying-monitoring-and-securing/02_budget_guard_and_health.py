"""20.3/2  Run the service in-process: health, metrics and the budget guard

Starts the reference service (`project/app.py`) on a free port inside this script and talks to it
over HTTP. The model is replaced by a fake that costs 100 tokens per call, so this runs offline and
shows the part that matters: after three model calls the budget guard refuses the fourth with a 429,
the service keeps answering `/health`, and `/metrics` tells monitoring what happened.

The guard counts a call BEFORE making it (a reservation), so five requests arriving at once cannot all
slip under a cap of three.

Docker is not needed. To run the same service in a container: `docker build -t desk project` and
`docker run -p 8080:8080 --env-file project/.env desk` (not run on the author's machine).

Run it:   ./run 20.3/2          (Windows: run 20.3/2)
"""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent / "project"))

from app import build, make_server  # noqa: E402

from labkit import lesson  # noqa: E402


def fake_chat(messages, tools):
    """Stands in for the model: a cited answer, 100 tokens, no tool calls."""
    message = SimpleNamespace(content="Use the Larkspur Connect VPN client [vpn].", tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=SimpleNamespace(total_tokens=100))


def request(base, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


@lesson("20.3/2", "Run the service in-process: health, metrics and the budget guard")
def main(ctx):
    ctx.step("Start the service on a free port with a cap of 3 model calls")
    desk, guard, metrics = build(chat=fake_chat, max_tokens=10_000, max_calls=3)
    server = make_server(desk, guard, metrics, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    ctx.note("listening on 127.0.0.1 (port chosen by the OS)")
    try:
        ctx.step("Health and bad requests")
        ctx.note("GET /health -> " + str(request(base, "/health")))
        ctx.note("POST /ask with no question -> " + str(request(base, "/ask", {"nope": 1})))
        ctx.note("POST /ask with 10 KB body -> " + str(request(base, "/ask", {"question": "x" * 10_000}))[:70])

        ctx.step("Five questions against a budget of three model calls")
        for number in range(1, 6):
            status, body = request(base, "/ask", {"question": "How do I connect to the VPN?"})
            ctx.note(f"{number}. status {status}  {body[:90]}")

        ctx.step("An out-of-scope question still works: it needs no model call")
        status, body = request(base, "/ask", {"question": "Does Larkspur Labs offer pet insurance?"})
        ctx.note(f"status {status}  {body[:110]}")

        ctx.step("What monitoring sees at /metrics")
        status, text = request(base, "/metrics")
        for line in text.strip().splitlines():
            ctx.note("  " + line)
    finally:
        server.shutdown()
        server.server_close()

    ctx.step("Your turn")
    ctx.note("Wire these three signals to an alert: 429 rate above zero, budget remaining under 20 percent, and /health failing.")
    ctx.note("With the observability extra (module 17) the same counters can come from prometheus-client instead of this tiny renderer.")


if __name__ == "__main__":
    main()
