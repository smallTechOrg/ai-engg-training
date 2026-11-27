"""05.2/2  Stream a model reply through the API

POST /reply/stream (see stream_api.py) opens a streaming chat call (the call from 01.3).
It passes on every new piece of text as an SSE `token` event, then sends a final `done`
event with the token usage. The client joins the reply back together.

A note on timing: FastAPI's TestClient runs the app in-process and hands over the body
only when the response is complete. So this side cannot measure how long a user waits
for the first words. The server measures it and reports it in the `done` event.

Run it:   ./run 05.2/2          (Windows: run 05.2/2)
"""

import json
import time

from fastapi.testclient import TestClient

from labkit import lesson

from stream_api import app, get_llm, get_model

TICKET = {
    "ticket_id": "LL-2101",
    "employee": "Priya (Finance)",
    "text": "My laptop won't connect to the office Wi-Fi since this morning. Other people near me are fine. I have a client call in 20 minutes.",
}


def parse_sse(lines):
    event, data = "message", []
    for line in lines:
        if line == "":
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:"):].strip())


@lesson("05.2/2", "Stream a model reply through the API")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    client = TestClient(app)
    try:
        ctx.step("POST /reply/stream")
        ctx.show_data("Request body (JSON)", TICKET)
        pieces, done, error, count = [], None, None, 0
        started = time.perf_counter()
        with client.stream("POST", "/reply/stream", json=TICKET) as response:
            ctx.note(f"POST /reply/stream -> {response.status_code}, content-type: {response.headers['content-type']}")
            ctx.note(f"Cache-Control: {response.headers.get('cache-control')}; X-Accel-Buffering: {response.headers.get('x-accel-buffering')} (both tell proxies not to hold the stream back)")
            for event, data in parse_sse(response.iter_lines()):
                count += 1
                if count <= 3:
                    ctx.note(f"event #{count}: {event} {data}")
                if event == "token":
                    pieces.append(data["text"])
                elif event == "done":
                    done = data
                elif event == "error":
                    error = data
        elapsed = time.perf_counter() - started

        ctx.step("What the client reassembled")
        if error:
            ctx.show_data("error event", error)
            ctx.note("The stream carried an error event. Check ./run doctor.")
            return
        ctx.note(f"{count} events: {len(pieces)} token events plus one done event, in {elapsed:.1f}s.")
        ctx.show_data("Reply, joined from the token events", "".join(pieces))
        ctx.show_data("The done event", done)
        ctx.note("The server measures first_token_s: how long a real browser would have shown a blank page.")

        ctx.step("Tokens")
        # The model call happened inside the route, where ctx cannot see it. The `done` event
        # carries the usage the model reported, so we add it to this run's totals ourselves.
        ctx.record_usage(done["usage"])
        if done["usage"] is None:
            ctx.note("This provider sent no usage chunk. The done event says null instead of making up numbers.")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
