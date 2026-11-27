"""A tiny stand-in for an OpenAI-compatible endpoint, for tests and CI (no key, no network).

It implements just enough of POST /v1/chat/completions (plain, streaming, tools, JSON mode)
and POST /v1/embeddings. Special inputs trigger the failures lessons must explain:

    API key "bad-key"            -> 401
    model   "missing-model"      -> 404
    model   "rate-limited"       -> 429
    model   "no-tools"           -> answers in text when tools are offered
    model   "no-usage"           -> omits token usage
    model   "slow"               -> waits half a second before answering (for concurrency demos)

Structured output follows the request, so lessons can be tested without a real model:
  - response_format json_schema -> an object built from that schema;
  - response_format json_object -> the first JSON object found in the prompt (a good prompt
    shows the shape it wants), else {"ok": true}.

Run it by hand:  python tests/stub_server.py --port 8089
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPLY = "A large language model is a program trained on text to predict what comes next."
USAGE = {"prompt_tokens": 21, "completion_tokens": 17, "total_tokens": 38}


def from_schema(schema: dict) -> object:
    """Build the simplest value that satisfies a JSON schema."""
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return from_schema(schema[key][0])
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = kind[0]
    if kind == "object" or "properties" in schema:
        return {name: from_schema(sub) for name, sub in schema.get("properties", {}).items()}
    if kind == "array":
        return [from_schema(schema.get("items", {"type": "string"}))]
    if kind == "integer":
        return 1
    if kind == "number":
        return 0.5
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    return "example"


def first_json_object(text: str) -> dict | None:
    """Find the first {...} in the text that parses as a JSON object."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == "{":
            try:
                value, _ = decoder.raw_decode(text[index:])
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
    return None


def structured_reply(request: dict) -> str | None:
    fmt = request.get("response_format") or {}
    if fmt.get("type") == "json_schema":
        return json.dumps(from_schema((fmt.get("json_schema") or {}).get("schema", {})))
    if fmt.get("type") == "json_object":
        prompt = "\n".join(str(m.get("content") or "") for m in request.get("messages", []))
        return json.dumps(first_json_object(prompt) or {"ok": True})
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # keep test output quiet
        pass

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send(status, {"error": {"message": message, "type": "stub_error", "code": status}})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._error(400, "invalid JSON")
        self.server.requests.append({"path": self.path, "body": request})  # type: ignore[attr-defined]
        model = request.get("model", "")

        if self.headers.get("Authorization", "") == "Bearer bad-key":
            return self._error(401, "Incorrect API key provided.")
        if model == "missing-model":
            return self._error(404, "The model `missing-model` does not exist.")
        if model == "rate-limited":
            return self._error(429, "Rate limit reached.")
        if self.path.endswith("/embeddings"):
            return self._send(200, {"object": "list", "model": model, "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}], "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        if not self.path.endswith("/chat/completions"):
            return self._error(404, f"unknown path {self.path}")

        if model == "slow":
            time.sleep(0.5)
        usage = None if model == "no-usage" else USAGE
        if request.get("stream"):
            return self._stream(model, usage, request)

        message: dict = {"role": "assistant", "content": REPLY}
        finish = "stop"
        if request.get("tools") and model != "no-tools":
            tool = request["tools"][0]["function"]["name"]
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": tool, "arguments": '{"city": "Paris"}'}}]}
            finish = "tool_calls"
        elif structured_reply(request) is not None:
            message["content"] = structured_reply(request)
        payload = {"id": "chatcmpl-stub", "object": "chat.completion", "created": 0, "model": model, "choices": [{"index": 0, "message": message, "finish_reason": finish}]}
        if usage:
            payload["usage"] = usage
        self._send(200, payload)

    def _stream(self, model: str, usage: dict | None, request: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()

        def event(data: dict | str) -> None:
            text = data if isinstance(data, str) else json.dumps(data)
            self.wfile.write(f"data: {text}\n\n".encode())
            self.wfile.flush()

        base = {"id": "chatcmpl-stub", "object": "chat.completion.chunk", "created": 0, "model": model}
        event({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        for word in (structured_reply(request) or REPLY).split(" "):
            event({**base, "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]})
        event({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        if usage and (request.get("stream_options") or {}).get("include_usage"):
            event({**base, "choices": [], "usage": usage})
        event("[DONE]")
        self.close_connection = True


def start(port: int = 0) -> ThreadingHTTPServer:
    """Start the stub on a free port (or the given one) in a background thread."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.requests = []  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8089)
    port = parser.parse_args().port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.requests = []  # type: ignore[attr-defined]
    print(f"Stub endpoint on http://127.0.0.1:{port}/v1  (Ctrl+C to stop)")
    server.serve_forever()
