"""05.2/1  What Server-Sent Events look like on the wire

No model here. GET /countdown streams three numbers and a final event. We read the
response two ways. First as raw lines, which is what the network carries. Then with a
tiny parser that turns the lines back into (event, data) pairs. That parser is all a
client has to do.

Ideas:
  - media type `text/event-stream`
  - an event is `event:` and `data:` lines ended by a blank line
  - the parser a front end needs is about ten lines

Run it:   ./run 05.2/1          (Windows: run 05.2/1)
"""

import json

from fastapi.testclient import TestClient

from labkit import lesson

from stream_api import app  # the app in this lesson's folder


def parse_sse(lines):
    """Turn an iterable of text lines into (event, data) pairs. A blank line ends an event."""
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
        # lines starting with ":" are comments (keep-alives). Anything else is ignored.


@lesson("05.2/1", "What Server-Sent Events look like on the wire")
def main(ctx):
    client = TestClient(app)

    ctx.step("The raw response, line by line")
    ctx.note("The status is a normal 200. The body arrives in pieces, and the connection stays open until the server is done.")
    with client.stream("GET", "/countdown") as response:
        ctx.note(f"GET /countdown -> {response.status_code}, content-type: {response.headers['content-type']}")
        for line in response.iter_lines():
            ctx.note(repr(line))  # repr makes the empty separator lines visible

    ctx.step("Parse the lines back into events")
    ctx.note("parse_sse() is all a client needs: split on blank lines, then read `event:` and `data:`.")
    events = []
    with client.stream("GET", "/countdown", params={"start": 5}) as response:
        for event, data in parse_sse(response.iter_lines()):
            events.append((event, data))
            ctx.note(f"event={event:<5} data={data}")

    ctx.step("Why SSE and not WebSockets or one big JSON reply")
    ctx.show_data(
        "Comparison",
        {
            "one JSON reply (05.1)": "simplest; the user stares at a blank page until the whole reply is ready",
            "Server-Sent Events": "one-way, server to client, plain HTTP; browsers reconnect for you; perfect for token streams",
            "WebSockets": "two-way; needed when the client also sends a stream (voice, collaborative editing); more moving parts",
        },
    )
    ctx.note(f"Parsed {len(events)} events. In the next script the same stream carries model tokens.")


if __name__ == "__main__":
    main()
