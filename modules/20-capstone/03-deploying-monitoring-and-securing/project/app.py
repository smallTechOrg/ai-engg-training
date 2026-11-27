"""The Larkspur desk as a small HTTP service (standard library only).

    POST /ask      {"question": "..."}  ->  {"answer", "route", "sources", "model_calls", "ticket_id"}
    GET  /health   liveness: always 200 while the process is up
    GET  /metrics  counters in the Prometheus text format (no client library needed)

Configuration is environment variables only (see .env.example); nothing secret is in the image.
With no LLM_* variables it runs the offline extractive mode, which is also a good fallback.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from budget import BudgetExceeded, BudgetGuard, guarded
from larkspur_desk import Desk, KnowledgeBase, TicketStore

HERE = Path(__file__).parent
MAX_BODY_BYTES = 4096


class Metrics:
    def __init__(self):
        self.counts = {}
        self._lock = threading.Lock()

    def inc(self, name, **labels):
        key = name + "".join(f'{{{k}="{v}"}}' for k, v in labels.items())
        with self._lock:
            self.counts[key] = self.counts.get(key, 0) + 1

    def render(self, guard):
        with self._lock:
            lines = [f"{key} {value}" for key, value in sorted(self.counts.items())]
        snapshot = guard.snapshot()
        lines += [f"desk_model_tokens_total {snapshot['tokens']}", f"desk_model_calls_total {snapshot['calls']}",
                  f"desk_token_budget_remaining {max(snapshot['max_tokens'] - snapshot['tokens'], 0)}"]
        return "\n".join(lines) + "\n"


def build(chat=None, max_tokens=None, max_calls=None):
    """Make the desk, the guard and the metrics. `chat` None means: use LLM_* variables, else offline."""
    guard = BudgetGuard(int(max_tokens or os.environ.get("DAILY_TOKEN_CAP", "200000")), int(max_calls or os.environ.get("DAILY_CALL_CAP", "1000")))
    if chat is None and os.environ.get("LLM_MODEL") and os.environ.get("LLM_BASE_URL"):
        from openai import OpenAI

        client, model = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ.get("LLM_API_KEY", "")), os.environ["LLM_MODEL"]

        def chat(messages, tools):
            kwargs = {"tools": tools} if tools else {}
            return client.chat.completions.create(model=model, messages=messages, temperature=0, timeout=30, **kwargs)

    desk = Desk(KnowledgeBase(HERE / "kb"), TicketStore(), chat=guarded(chat, guard) if chat else None)
    return desk, guard, Metrics()


def make_server(desk, guard, metrics, host="127.0.0.1", port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # never log request bodies: questions can hold personal data
            pass

        def _send(self, status, body, content_type="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ok"})
            elif self.path == "/metrics":
                self._send(200, metrics.render(guard), "text/plain; version=0.0.4")
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/ask":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                metrics.inc("desk_requests_total", status="413")
                return self._send(413, {"error": "request too large"})
            try:
                question = json.loads(self.rfile.read(length) or b"{}")["question"]
                if not isinstance(question, str):
                    raise TypeError
            except (ValueError, KeyError, TypeError):
                metrics.inc("desk_requests_total", status="422")
                return self._send(422, {"error": "send JSON like {\"question\": \"...\"}"})
            try:
                result = desk.ask(question)
            except BudgetExceeded as error:
                metrics.inc("desk_requests_total", status="429")
                return self._send(429, {"error": f"budget guard: {error}", "route": "handover"})
            except Exception:  # never leak internals to the caller
                metrics.inc("desk_requests_total", status="500")
                return self._send(500, {"error": "internal error"})
            metrics.inc("desk_requests_total", status="200")
            metrics.inc("desk_routes_total", route=result.route)
            self._send(200, {"answer": result.answer, "route": result.route, "sources": result.sources,
                             "model_calls": result.model_calls, "ticket_id": result.ticket_id})

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    desk, guard, metrics = build()
    server = make_server(desk, guard, metrics, os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080")))
    print(f"listening on {server.server_address[0]}:{server.server_address[1]}", flush=True)
    server.serve_forever()
