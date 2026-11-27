"""05.5/1  The service: health, triage, streaming chat, validation, stats

Exercises helpdesk_service.py in-process with FastAPI's TestClient, the way the front end will use
it over HTTP: every route once, the bad requests that must be rejected, and the usage counters.

Run it:   ./run 05.5/1          (Windows: run 05.5/1)
"""

import json

from fastapi.testclient import TestClient

from labkit import lesson

from helpdesk_service import app, get_llm, get_model, reset_stats, stats


def parse_sse(lines):
    event, data = "message", []
    for line in lines:
        if line == "":
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())


@lesson("05.5/1", "The service: health, triage, streaming chat, validation, stats")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    reset_stats()
    client = TestClient(app)
    try:
        ctx.step("GET /health")
        ctx.show_data("200", client.get("/health").json())

        ctx.step("POST /triage")
        ticket = {"ticket_id": "LL-3001", "employee": "Mei (Reception)", "text": "The badge reader at the front door has been dead since the power cut. Visitors are waiting outside."}
        response = client.post("/triage", json=ticket)
        ctx.note(f"POST /triage -> {response.status_code} {response.reason_phrase}")
        ctx.show_data("Body", response.json())

        ctx.step("POST /chat/stream (two turns, the second carries the history)")
        history = [{"role": "user", "content": "My VPN keeps dropping every few minutes."}]
        for turn in (1, 2):
            pieces, done = [], None
            with client.stream("POST", "/chat/stream", json={"employee": "Priya", "messages": history}) as stream:
                ctx.note(f"turn {turn}: {stream.status_code} {stream.headers['content-type']}, sending {len(history)} message(s)")
                for event, data in parse_sse(stream.iter_lines()):
                    if event == "token":
                        pieces.append(data["text"])
                    elif event == "done":
                        done = data
                    elif event == "error":
                        ctx.show_data("error event", data)
            reply = "".join(pieces)
            ctx.note(f"assistant: {reply}")
            ctx.note(f"done event: {done}")
            history += [{"role": "assistant", "content": reply}, {"role": "user", "content": "I already restarted the laptop. What next?"}]

        ctx.step("Requests the service must reject")
        bad = {
            "ticket id that is not LL-dddd": ("/triage", {"ticket_id": "4821", "employee": "Priya", "text": "wifi is slow today and I need help"}),
            "empty conversation": ("/chat/stream", {"employee": "Priya", "messages": []}),
            "conversation ending with an assistant message": ("/chat/stream", {"messages": [{"role": "assistant", "content": "Hello"}]}),
        }
        for label, (path, body) in bad.items():
            response = client.post(path, json=body)
            first = response.json()["detail"][0]
            ctx.note(f"{label}: {response.status_code} ({first['msg']})")

        ctx.step("GET /stats")
        ctx.show_data("Service counters", stats)
        for usage in stats["usage"]:
            ctx.record_usage(usage)  # the service saw each model call; we add them to our totals
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
