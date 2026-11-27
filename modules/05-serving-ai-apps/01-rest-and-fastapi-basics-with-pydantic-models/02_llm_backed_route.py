"""05.1/2  An LLM-backed route: POST /reply

POST /reply takes a ticket and returns the assistant's reply plus the token counts. The
route (in helpdesk_api.py) makes one ordinary `llm.chat.completions.create(...)` call, the
same call as lesson 01.1, and wraps the result in a Pydantic response model.

Two FastAPI ideas are new:

  1. Dependency injection: the route asks for an `llm` client and a `model` name with
     `Depends(...)`. This script swaps both for the lesson's own client with
     `app.dependency_overrides`, the same way a test suite would swap in a fake.
  2. Mapping failures to status codes: a bad ticket is a 422 (the caller's fault, no model
     call is made), a failing model endpoint is a 502 (an upstream fault).

Run it:   ./run 05.1/2          (Windows: run 05.1/2)
"""

import openai
from fastapi.testclient import TestClient

from labkit import lesson

from helpdesk_api import app, get_llm, get_model  # the app in this lesson's folder

TICKET = {
    "ticket_id": "LL-2001",
    "employee": "Priya (Finance)",
    "text": "My laptop won't connect to the office Wi-Fi since this morning. Other people near me are fine. I have a client call in 20 minutes.",
}


@lesson("05.1/2", "An LLM-backed route: POST /reply")
def main(ctx):
    ctx.step("Inject the lesson's client into the app")
    ctx.note("In production get_llm() builds a client from .env. Here we override it with ctx.client,")
    ctx.note("so the route uses the course's client and --raw shows the model call made inside the route.")
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    client = TestClient(app)
    ctx.show_data("app.dependency_overrides", {fn.__name__: "lambda -> " + ("ctx.client" if fn is get_llm else "ctx.model") for fn in app.dependency_overrides})

    try:
        ctx.step("POST /reply with a ticket")
        ctx.show_data("Request body (JSON)", TICKET)
        response = client.post("/reply", json=TICKET)
        ctx.note(f"POST /reply -> {response.status_code} {response.reason_phrase}")
        body = response.json()
        ctx.show_data("Response body", body)
        if response.status_code != 200:
            ctx.note("The route could not reach the model. Check your settings with ./run doctor.")
            return
        # The model call happened inside the route, out of ctx's sight. The route reports the
        # tokens in its response, so we add them to this run's totals ourselves.
        ctx.record_usage(body["usage"])
        ctx.note(f"The caller got plain JSON: a reply of {len(body['reply'])} characters and the token counts.")
        ctx.note("A front end (lesson 05.3) or another service can use this without knowing anything about LLMs.")

        ctx.step("POST /reply with a bad ticket")
        bad = {"ticket_id": "4821", "employee": "Priya", "text": "wifi"}
        ctx.show_data("Request body (JSON)", bad)
        response = client.post("/reply", json=bad)
        ctx.note(f"POST /reply -> {response.status_code} {response.reason_phrase}")
        for problem in response.json()["detail"]:
            ctx.note(f"  - {'.'.join(str(p) for p in problem['loc'])}: {problem['msg']}")
        ctx.note("Rejected by TicketIn before the route ran, so no model call and no tokens spent.")

        ctx.step("When the model endpoint is down")
        ctx.note("Override get_llm again, this time with a client pointed at a port where nothing listens.")
        dead = openai.OpenAI(base_url="http://127.0.0.1:9/v1", api_key="not-used", max_retries=0, timeout=3)
        app.dependency_overrides[get_llm] = lambda: dead
        response = client.post("/reply", json=TICKET)
        ctx.note(f"POST /reply -> {response.status_code} {response.reason_phrase}")
        ctx.show_data("Response body", response.json())
        ctx.note("The route caught the openai error and answered 502 Bad Gateway: 'the service I depend on failed'.")
        ctx.note("Without that try/except the caller would get a bare 500 Internal Server Error and no explanation.")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
