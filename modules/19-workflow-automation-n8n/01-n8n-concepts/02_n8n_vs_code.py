"""19.1/2  n8n versus plain code

The same helpdesk flow twice: as the n8n workflow (4 nodes) and as about 25 lines of Python.
The Python version runs here, with a real model call.

Run it:   ./run 19.1/2          (Windows: run 19.1/2)
     or:  python modules/19-workflow-automation-n8n/01-n8n-concepts/02_n8n_vs_code.py
"""

import json
from pathlib import Path

from labkit import lesson

WORKFLOW = Path(__file__).with_name("helpdesk-ticket-workflow.json")
SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Reply in two sentences."


@lesson("19.1/2", "n8n versus plain code")
def main(ctx):
    ctx.step("The workflow, node by node")
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    for i, n in enumerate(wf["nodes"], 1):
        print(f"  {i}. {n['name']:<18} ({n['type'].split('.')[-1]})")

    ctx.step("The same flow as plain Python")

    # Node 1, Webhook: in code this is a function that receives the POST body.
    def handle_ticket(body: dict) -> dict:
        # Node 2, HTTP Request: the model call (the openai SDK replaces the raw HTTP request).
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": body["ticket"]},
            ],
        )
        ctx.record_usage(response.usage, quiet=True)
        # Node 3, Set: shape the reply.
        shaped = {"reply": response.choices[0].message.content, "ticket": body["ticket"]}
        # Node 4, Respond to Webhook: return it.
        return shaped

    ticket = {"ticket": "My laptop will not connect to the Larkspur-Staff wifi since this morning."}
    ctx.show_data("Incoming webhook body", ticket)
    result = handle_ticket(ticket)
    ctx.show_data("Response to the caller", result)

    ctx.step("So what is n8n for?")
    rows = [
        ("Who edits it", "n8n: ops and analysts on a canvas", "Code: developers"),
        ("Triggers", "n8n: webhook, cron, email, 400+ apps built in", "Code: you wire a server or scheduler"),
        ("Credentials", "n8n: stored encrypted, reused by name", "Code: env vars and a secret manager"),
        ("Retries, run history", "n8n: a checkbox and an executions list", "Code: you build or import them"),
        ("Testing, review, diff", "n8n: JSON export, awkward to review", "Code: unit tests, pull requests"),
        ("Complex logic, loops", "n8n: possible, gets tangled", "Code: natural"),
    ]
    for what, a, b in rows:
        print(f"  {what}\n      {a}\n      {b}")
    ctx.note("Choose n8n to glue systems together fast with visible runs; choose code for core logic you must test.")


if __name__ == "__main__":
    main()
