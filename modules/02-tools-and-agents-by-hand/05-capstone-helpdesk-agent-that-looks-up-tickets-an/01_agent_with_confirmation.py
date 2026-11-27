"""02.5/1  The helpdesk agent: look up, search, ASK for a reset, and wait for a person

The capstone agent combines the whole module:

  02.1  three tools described by JSON schema, run by your program
  02.2  a capped loop that returns a result and a named stop reason
  02.3  a short context (the loop keeps only the transcript of this one task)
  02.4  validation, error objects, an allow-list, idempotency

The key design decision: the model has NO tool that resets a password. It has
`request_password_reset(ticket_id)`, which only records a PENDING request and says so. The reset
itself, `execute_reset`, is called by your program after a human approves. The model cannot skip that
step, whatever it writes, because it cannot call `execute_reset`.

This script runs one ticket (a locked account) with a human who approves.

Run it:   ./run 02.5/1          (Windows: run 02.5/1)
"""

import json
from pathlib import Path

from labkit import lesson

MAX_STEPS = 6
DATA = json.loads((Path(__file__).parent / "helpdesk_data.json").read_text(encoding="utf-8"))
TICKETS, KB = DATA["tickets"], DATA["kb"]

SYSTEM_PROMPT = """You are the Larkspur Labs IT helpdesk agent.
1. Read the ticket with lookup_ticket.
2. Search the knowledge base with search_kb for the fix.
3. If (and only if) the ticket is an access problem with a locked account, call request_password_reset with the ticket id. A person must confirm it: it does NOT happen immediately.
Reply with two or three sentences for the on-call engineer: what you found, what you asked for, and that a reset needs confirmation. Never say a password was reset."""


# ---- the tools --------------------------------------------------------------------------
def lookup_ticket(ticket_id: str, **_) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    return {"ticket_id": ticket_id.strip().upper(), **ticket} if ticket else {"error": "not_found", "message": f"No ticket {ticket_id!r}."}


def search_kb(query: str, **_) -> dict:
    words = {w for w in query.lower().split() if len(w) > 2}
    hits = [a for a in KB if words & set((a["title"] + " " + a["text"]).lower().replace(",", " ").replace(".", " ").split())]
    return {"articles": hits[:2]} if hits else {"articles": [], "message": "No article matched."}


def request_password_reset(ticket_id: str, pending: list, **_) -> dict:
    """Records a request. Does NOT reset anything. The username comes from the TICKET, never from the model."""
    ticket = TICKETS.get(ticket_id.strip().upper())
    if ticket is None:
        return {"error": "not_found", "message": f"No ticket {ticket_id!r}."}
    if ticket["category"] != "access":
        return {"error": "not_permitted", "message": "Password resets are only for access tickets."}
    request = {"request_id": f"{ticket_id.strip().upper()}:reset:{ticket['from']}", "username": ticket["from"], "ticket_id": ticket_id.strip().upper()}
    if request not in pending:
        pending.append(request)
    return {"status": "pending_confirmation", "message": "Recorded. A person must confirm before anything happens. The password has NOT been reset."}


def execute_reset(request: dict, audit: list) -> dict:
    """Called by YOUR PROGRAM after approval. Idempotent: the request id is the idempotency key."""
    if any(a["request_id"] == request["request_id"] for a in audit):
        return {"result": "already done", "request_id": request["request_id"]}
    audit.append({"request_id": request["request_id"], "username": request["username"], "action": "reset link sent (simulated)"})
    return {"result": "reset link sent (simulated)", "username": request["username"]}


TOOLS = [
    {"type": "function", "function": {"name": "lookup_ticket", "description": "Read a helpdesk ticket by id (subject, owner, category, status, notes).",
        "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_kb", "description": "Search the knowledge base with a few keywords.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "request_password_reset", "description": "Ask for a password reset for the owner of an access ticket. Needs human confirmation; does not reset anything itself.",
        "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"], "additionalProperties": False}}},
]
ALLOWED = {"lookup_ticket", "search_kb", "request_password_reset"}


def run_tool(name, raw, pending):
    if name not in ALLOWED:
        return {"error": "unknown_tool", "message": f"No tool {name!r}."}
    try:
        args = json.loads(raw or "{}")
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        function = {"lookup_ticket": lookup_ticket, "search_kb": search_kb, "request_password_reset": request_password_reset}[name]
        return function(pending=pending, **args)
    except (ValueError, TypeError) as error:
        return {"error": "bad_arguments", "message": str(error)}


def run_agent(ctx, user_request):
    """The capped loop. Returns what the program recorded: the model's words are only 'answer'."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_request}]
    pending, ran, answer, stop = [], [], "", "step_cap"
    for turn in range(1, MAX_STEPS + 1):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            ctx.show_response(response)
            answer, stop = (message.content or "").strip(), "answered"
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls]})
        for call in message.tool_calls:
            result = run_tool(call.function.name, call.function.arguments, pending)
            ran.append(call.function.name)
            ctx.show_tool_call(call.function.name, call.function.arguments, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    return {"stop_reason": stop, "answer": answer, "tools_run": ran, "pending": pending, "model_calls": turn}


def scripted_approver(decision):
    """Stands in for a person. In a real tool this would show the request and read a click or a typed 'yes'."""
    return lambda request: decision


@lesson("02.5/1", "The helpdesk agent: look up, search, ask for a reset, wait for a person")
def main(ctx):
    ctx.step("The tools the model has, and the one it does not")
    ctx.note("Model tools: lookup_ticket, search_kb, request_password_reset (records a request only).")
    ctx.note("Not a tool: execute_reset. Only the program calls it, only after approval.")

    ctx.step("Phase 1: the agent works the ticket")
    result = run_agent(ctx, "Please handle ticket LL-2101.")
    ctx.show_data("What the program recorded", {k: v for k, v in result.items() if k != "answer"})

    ctx.step("Phase 2: the confirmation gate (a scripted person who says yes)")
    audit, approve = [], scripted_approver(True)
    if not result["pending"]:
        ctx.note("No reset was requested, so there is nothing to confirm.")
    for request in result["pending"]:
        ctx.show_data("Pending request shown to the person", request)
        if approve(request):
            ctx.note("Person: APPROVED. The program now runs the reset.")
            ctx.show_data("execute_reset", execute_reset(request, audit))
        else:
            ctx.note("Person: DECLINED. Nothing is run.")

    ctx.step("Phase 3: the audit log is the truth")
    ctx.show_data("Audit log", audit or ["(no actions taken)"])
    ctx.note("Whatever the model said, the audit log lists exactly what changed. Report from it, not from the answer.")


if __name__ == "__main__":
    main()
