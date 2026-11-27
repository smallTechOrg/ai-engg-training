"""07.2/2  Plan-and-execute with a hand-written planner

ReAct chooses one step at a time. Plan-and-execute asks the model for the whole plan first,
runs each step with a small executor, then writes the answer from the collected results.
There is no prebuilt class for this in current LangChain, and it is only about 30 lines:
a planner call (structured output), an executor loop, and a synthesis call.

Run it:   ./run 07.2/2          (Windows: run 07.2/2)
"""

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKETS = {
    "LL-2041": {"status": "open", "owner": "Priya", "summary": "VPN token reset", "device": "LT-118"},
    "LL-2043": {"status": "open", "owner": "Priya", "summary": "Printer on floor 3 offline", "device": "PR-031"},
}
DEVICES = {
    "LT-118": "Laptop, Priya, warranty until 2027-03",
    "PR-031": "Printer, floor 3, firmware 4.2 (known bug: drops off the network after 30 days)",
}


@tool
def open_tickets_for(owner: str) -> str:
    """List open ticket ids for a helpdesk owner such as Priya."""
    return ", ".join(k for k, t in TICKETS.items() if t["owner"].lower() == owner.lower() and t["status"] == "open") or "none"


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Return the status, summary and device id of a ticket."""
    return str(TICKETS.get(ticket_id, f"no ticket named {ticket_id}"))


@tool
def lookup_device(device_id: str) -> str:
    """Return the description of a device id such as PR-031."""
    return DEVICES.get(device_id, f"no device named {device_id}")


class Plan(BaseModel):
    steps: list[str] = Field(description="Short, ordered, self-contained instructions, one tool lookup each. At most 4.")


MAX_STEPS = 4


@lesson("07.2/2", "Plan-and-execute, hand-written")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    question = "Priya says her printer ticket is stuck. What device is it and is there a known problem?"
    ctx.note(f"Question: {question}")

    ctx.step("1. Plan: one structured call, no tools")
    planner = model.with_structured_output(Plan)
    plan = planner.invoke([
        ("system", "Plan how a helpdesk assistant with tools open_tickets_for, lookup_ticket and lookup_device "
                   "can answer the question. Return short ordered steps in plain English, no function-call syntax and no placeholders. Do not answer the question."),
        ("user", question),
    ])
    steps = (plan.steps if plan else [])[:MAX_STEPS]
    if not steps:
        steps = [question]
        ctx.note("The planner returned no steps; falling back to a single step that is the question itself.")
    ctx.show_data("Plan", steps)

    ctx.step("2. Execute: a small tool agent runs each step, with the notes so far")
    executor = create_agent(model, tools=[open_tickets_for, lookup_ticket, lookup_device],
                            system_prompt="Carry out ONE step using the tools. Reply with the facts you found, in one sentence.")
    notes: list[str] = []
    for i, step in enumerate(steps, 1):
        ctx.note(f"Step {i} of {len(steps)}: {step}")
        context = "Facts so far:\n" + "\n".join(notes) if notes else "No facts yet."
        try:
            result = executor.invoke({"messages": [("user", f"{context}\n\nStep: {step}")]}, {"recursion_limit": 9})
        except Exception as exc:
            notes.append(f"(step {i} failed: {type(exc).__name__})")
            ctx.note(f"Step failed, recorded and moving on: {type(exc).__name__}")
            continue
        asked = {}
        for m in result["messages"]:
            if m.type == "ai":
                ctx.record_usage(m.usage_metadata, quiet=True)
                asked.update({c["id"]: c["args"] for c in m.tool_calls})
            if m.type == "tool":
                ctx.show_tool_call(m.name, asked.get(m.tool_call_id, {}), m.content)
        notes.append(f"{i}. {result['messages'][-1].content}")
        ctx.note(f"Result {i}: {notes[-1][:120]}")

    ctx.step("3. Synthesize: one call that sees the question and the collected facts")
    reply = model.invoke([
        ("system", "Answer the helpdesk question using only the facts. Two sentences at most."),
        ("user", f"Question: {question}\n\nFacts:\n" + "\n".join(notes)),
    ])
    ctx.record_usage(reply.usage_metadata, quiet=True)
    ctx.note(f"Answer: {reply.content}")
    ctx.note("Compare with 07.2/1: the plan is visible and reviewable before anything runs, but it cannot adapt mid-way.")


if __name__ == "__main__":
    main()
