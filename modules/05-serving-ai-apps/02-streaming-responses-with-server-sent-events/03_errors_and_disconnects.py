"""05.2/3  Errors and disconnects in a stream

Streaming changes how failure works. There are two cases:

  1. Before the stream starts (a bad request body): FastAPI answers 422 as usual.
  2. After it starts: the 200 status line has already gone out, so a failure can no longer
     become a 502. The server sends an `error` event, and the client must look for it.

There is also one case from the other side: the user closes the tab. The client stops
reading and the server closes its generator. The generator's `finally:` block runs and
releases the model stream, so you stop paying for tokens nobody reads.

Run it:   ./run 05.2/3          (Windows: run 05.2/3)
"""

import json

import openai
from fastapi.testclient import TestClient

from labkit import lesson

from stream_api import app, get_llm, get_model, server_log

TICKET = {
    "ticket_id": "LL-2102",
    "employee": "Mei (Reception)",
    "text": "The badge reader at the front door has been dead since the power cut. Visitors are waiting outside.",
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


@lesson("05.2/3", "Errors and disconnects in a stream")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    client = TestClient(app)
    try:
        ctx.step("A bad request fails before the stream starts")
        response = client.post("/reply/stream", json={"ticket_id": "4821", "employee": "Priya", "text": "wifi"})
        ctx.note(f"POST /reply/stream -> {response.status_code} {response.reason_phrase}, content-type: {response.headers['content-type']}")
        ctx.note("Validation runs before the route, so this is a normal JSON 422. Streaming has not begun.")

        ctx.step("The model endpoint is down: 200, then an error event")
        dead = openai.OpenAI(base_url="http://127.0.0.1:9/v1", api_key="not-used", max_retries=0, timeout=3)
        app.dependency_overrides[get_llm] = lambda: dead
        with client.stream("POST", "/reply/stream", json=TICKET) as response:
            ctx.note(f"POST /reply/stream -> {response.status_code} (the status was sent before the model was even called)")
            for event, data in parse_sse(response.iter_lines()):
                ctx.note(f"event={event} data={data}")
        ctx.note("In 05.1 the same failure was a 502. In a stream it cannot be: only the `error` event tells the client.")
        ctx.note("A front end must handle three endings: done, error, and the connection simply closing.")
        app.dependency_overrides[get_llm] = lambda: ctx.client

        ctx.step("The client walks away after a few events")
        server_log.clear()
        seen = 0
        with client.stream("POST", "/reply/stream", json=TICKET) as response:
            for event, data in parse_sse(response.iter_lines()):
                seen += 1
                ctx.note(f"event={event} data={data}")
                if seen == 2:
                    ctx.note("Closing the connection now, as a browser does when the user leaves the page.")
                    break
        ctx.show_data("What the server logged", server_log)
        ctx.note("A real server notices the closed socket and stops the generator. The finally block frees the model stream.")
        ctx.note("Here the TestClient had already buffered the body, so the run ended before we left. The cleanup is the same.")
        ctx.note("This call's tokens are not added to the totals because the `done` event was never read.")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
