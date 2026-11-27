"""05.1/1  REST basics: routes, Pydantic models, status codes

The helpdesk API lives in helpdesk_api.py, next to this script. This script calls the
two routes that do not use a model, the way any HTTP client would. It does so in-process:
FastAPI's TestClient sends real HTTP requests to the app without opening a port.

  - GET  /health   -> 200 and a small JSON body
  - POST /echo     -> 200 when the body is valid, 422 when it is not (FastAPI and Pydantic
                      reject it before the route's code runs)
  - an unknown path -> 404, a wrong method -> 405

This script makes no model calls.

Run it:   ./run 05.1/1          (Windows: run 05.1/1)
"""

from fastapi.testclient import TestClient

from labkit import lesson

from helpdesk_api import app  # the app in this lesson's folder


def show(ctx, label, response):
    """Print one HTTP exchange: status line and JSON body."""
    ctx.note(f"{response.request.method} {response.request.url.path}  ->  {response.status_code} {response.reason_phrase}")
    ctx.show_data(label, response.json())


@lesson("05.1/1", "REST basics: routes, Pydantic models, status codes")
def main(ctx):
    client = TestClient(app)  # an httpx client wired straight into the app: no server, no port

    ctx.step("GET /health")
    ctx.note("The simplest route: no input, a fixed answer. Load balancers and uptime checks call it.")
    show(ctx, "Response body", client.get("/health"))

    ctx.step("POST /echo with a valid body")
    body = {"message": "Is the VPN down?", "repeat": 2}
    ctx.show_data("Request body (JSON)", body)
    ctx.note("FastAPI turns the JSON into an EchoIn object. The route returns an EchoOut, and FastAPI makes it JSON.")
    show(ctx, "Response body", client.post("/echo", json=body))

    ctx.step("POST /echo with a bad body")
    bad = {"message": "", "repeat": 7, "colour": "blue"}
    ctx.show_data("Request body (JSON)", bad)
    ctx.note("An empty message and repeat=7 both break the rules in EchoIn. The route never runs.")
    response = client.post("/echo", json=bad)
    show(ctx, "Response body (FastAPI's validation error)", response)
    for problem in response.json()["detail"]:
        where = ".".join(str(part) for part in problem["loc"])
        ctx.note(f"  - {where}: {problem['msg']}")
    ctx.note("422 Unprocessable Content means: your JSON was readable, but it does not match the contract.")
    ctx.note("The unknown key 'colour' was silently ignored. Add model_config = ConfigDict(extra='forbid') to reject it.")

    ctx.step("Not JSON at all, a wrong path, a wrong method")
    for label, response in [
        ("Body that is not JSON", client.post("/echo", content=b"hello", headers={"Content-Type": "application/json"})),
        ("Unknown path", client.get("/tickets")),
        ("Wrong method", client.get("/echo")),
    ]:
        ctx.note(f"{label}: {response.request.method} {response.request.url.path} -> {response.status_code} {response.reason_phrase}")

    ctx.step("What the status codes tell the caller")
    ctx.show_data(
        "Status codes in this lesson",
        {
            "200": "OK: here is your answer",
            "404": "no such route",
            "405": "the route exists, but not for this method",
            "422": "your request body broke the schema (the caller must fix it)",
            "502": "an upstream service, here the model endpoint, failed (used in scripts 2 and 3)",
        },
    )


if __name__ == "__main__":
    main()
