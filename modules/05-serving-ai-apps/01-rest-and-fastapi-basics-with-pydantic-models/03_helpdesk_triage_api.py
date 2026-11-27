"""05.1/3  The helpdesk triage API: POST /triage and the OpenAPI schema

The lesson 01.6 triage, now behind an API. POST /triage takes a ticket and returns a
Triage object that was checked twice. First, a JSON schema limited what the model could
return. Then the route checked the reply with Pydantic before answering. So the caller
can trust the shape of every 200 response.

Then comes the part FastAPI gives you for free: the OpenAPI schema. /openapi.json
describes every route, request model and response model in helpdesk_api.py. /docs shows
that description as an interactive page (Swagger UI).

Run it:   ./run 05.1/3          (Windows: run 05.1/3)
"""

from fastapi.testclient import TestClient

from labkit import lesson

from helpdesk_api import app, get_llm, get_model  # the app in this lesson's folder

TICKETS = [
    {
        "ticket_id": "LL-2002",
        "employee": "Mei (Reception)",
        "text": "The badge reader at the front door has been dead since the power cut. Visitors are waiting outside and I let each one in by hand.",
    },
    {
        "ticket_id": "LL-2003",
        "employee": "Jonas (Engineering)",
        "text": "Could someone install the new diagram editor on my laptop? No rush, sometime this week is fine.",
    },
]


@lesson("05.1/3", "The helpdesk triage API: POST /triage and the OpenAPI schema")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    client = TestClient(app)
    try:
        ctx.step("POST /triage for two tickets")
        ctx.note("One model call per request, with response_format json_schema (as in 01.6), then Pydantic validation.")
        routed = []
        for ticket in TICKETS:
            response = client.post("/triage", json=ticket)
            ctx.note(f"POST /triage  {ticket['ticket_id']}  ->  {response.status_code} {response.reason_phrase}")
            body = response.json()
            if response.status_code != 200:
                # A 502 here is the API doing its job: the caller gets a clear error, never half-valid data.
                ctx.show_data("Error body", body)
                ctx.note("Your endpoint may not support json_schema output (see lesson 01.6), or the reply broke the schema.")
                continue
            ctx.record_usage(body["usage"])  # the route reports the tokens of its model call
            ctx.show_data("Response body", body["triage"])
            routed.append(body)

        ctx.step("The caller's side: plain data, no LLM knowledge needed")
        for body in routed:
            triage = body["triage"]
            queue = "on-site support" if triage["needs_human"] else "self-service reply"
            ctx.note(f"{body['ticket_id']}: {triage['category']} / {triage['urgency']} -> {queue}")
        if not routed:
            ctx.note("No ticket was triaged on this run; the errors above say why.")

        ctx.step("The OpenAPI schema FastAPI generated")
        ctx.note("GET /openapi.json describes every route. Nobody wrote it: it comes from the type hints and models.")
        spec = client.get("/openapi.json").json()
        ctx.show_data(
            "Paths in /openapi.json",
            {path: sorted(method.upper() for method in methods) for path, methods in spec["paths"].items()},
        )
        triage_op = spec["paths"]["/triage"]["post"]
        ctx.show_data(
            "POST /triage, as the schema describes it",
            {
                "request body": triage_op["requestBody"]["content"]["application/json"]["schema"],
                "responses": {code: info["description"] for code, info in triage_op["responses"].items()},
            },
        )
        ctx.show_data("components.schemas.TicketIn", spec["components"]["schemas"]["TicketIn"])
        ctx.note("The 422 response is listed automatically: FastAPI knows the body is validated.")
        ctx.note("Code generators read this file to build a ready-made client in other languages.")

        ctx.step("The interactive docs")
        docs = client.get("/docs")
        ctx.note(f"GET /docs -> {docs.status_code}, {docs.headers['content-type']}: the Swagger UI page, built from /openapi.json.")
        ctx.note("Run the API for real (see the README) and open /docs in a browser to call /triage by hand.")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
