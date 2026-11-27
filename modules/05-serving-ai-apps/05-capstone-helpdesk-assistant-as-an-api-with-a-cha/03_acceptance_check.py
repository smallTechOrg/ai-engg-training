"""05.5/3  Acceptance check for the capstone

Runs the capstone's acceptance criteria against the service and the page and prints PASS or FAIL
for each. A failed check is a result to read, not a crash: this script exits 0 either way, so
you can see exactly what your changes broke.

Run it:   ./run 05.5/3          (Windows: run 05.5/3)
"""

import json
import logging
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from labkit import lesson

from helpdesk_service import app, get_llm, get_model, reset_stats, stats

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

PAGE = Path(__file__).parent / "chat_page.py"
TICKET = {"ticket_id": "LL-3101", "employee": "Jonas (Engineering)", "text": "Could someone install the new diagram editor on my laptop? No rush, sometime this week is fine."}


def sse_events(response):
    event, out = "message", []
    for line in response.iter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            out.append((event, json.loads(line[5:].strip())))
    return out


@lesson("05.5/3", "Acceptance check for the capstone")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    reset_stats()
    api = TestClient(app)
    seen = []
    api.event_hooks["request"].append(lambda r: seen.append((r.method, r.url.path, r.content)))
    results = []

    def check(name, ok, detail):
        results.append((name, ok))
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    try:
        ctx.step("Service criteria")
        check("S1 /health answers 200 ok", api.get("/health").json().get("status") == "ok", "GET /health")

        response = api.post("/triage", json=TICKET)
        body = response.json() if response.status_code == 200 else {}
        triage = body.get("triage", {})
        shape = set(triage) == {"category", "urgency", "summary", "needs_human"}
        check("S2 /triage returns a validated triage", response.status_code == 200 and shape, f"{response.status_code}, {triage or response.text[:120]}")

        bad = api.post("/triage", json={**TICKET, "ticket_id": "nope"})
        check("S3 a bad ticket is a 422 before any model call", bad.status_code == 422, f"status {bad.status_code}")

        with api.stream("POST", "/chat/stream", json={"messages": [{"role": "user", "content": "My VPN keeps dropping."}]}) as stream:
            events = sse_events(stream)
        kinds = [e for e, _ in events]
        check("S4 chat streams token events then one done event", kinds.count("token") >= 1 and kinds[-1:] == ["done"], f"{kinds.count('token')} token(s), last event {kinds[-1:]}")
        done = events[-1][1] if events else {}
        check("S5 token usage is reported, or explicitly null", "usage" in done, f"usage = {done.get('usage')}")

        ctx.step("Front-end criteria")
        at = AppTest.from_file(str(PAGE), default_timeout=60)
        at.session_state["_api"] = api
        at.run()
        seen.clear()
        at.chat_input[0].set_value("My laptop can't join the office Wi-Fi.").run()
        at.chat_input[0].set_value("I already restarted it. What next?").run()
        sent = [json.loads(c) for m, p, c in seen if p == "/chat/stream"]
        check("F1 the page shows both turns", len(at.chat_message) == 4, f"{len(at.chat_message)} bubbles")
        check("F2 turn 2 sends the whole history", len(sent) == 2 and len(sent[1]["messages"]) == 3, f"messages per request: {[len(s['messages']) for s in sent]}")
        check("F3 the page makes no model call itself", {p for _, p, _ in seen} <= {"/chat/stream", "/triage", "/health"}, f"paths used: {sorted({p for _, p, _ in seen})}")

        at.session_state["_api"] = httpx.Client(base_url="http://127.0.0.1:9", timeout=3)
        at.chat_input[0].set_value("Is the printer working?").run()
        check("F4 a dead service gives an error message, not a crash", len(at.exception) == 0 and len(at.error) == 1, f"{len(at.error)} error message(s), {len(at.exception)} exception(s)")

        ctx.step("Result")
        passed = sum(ok for _, ok in results)
        ctx.show_data("Acceptance", {"passed": passed, "total": len(results), "failed": [n for n, ok in results if not ok]})
        ctx.note("All criteria met." if passed == len(results) else "Read the FAIL lines above; a lenient or non-standard model can fail S2/S4 without any bug in your code.")
        for usage in stats["usage"]:
            ctx.record_usage(usage)
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
