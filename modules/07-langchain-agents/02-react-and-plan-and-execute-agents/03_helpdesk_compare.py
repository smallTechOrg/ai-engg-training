"""07.2/3  Helpdesk: the same question through ReAct and plan-and-execute

A two-part helpdesk question is answered twice, once by a ReAct agent and once by a
plan-and-execute pipeline. Both are capped, and the script reports model calls, tool calls
and tokens for each, so you can see what the extra structure costs and buys.

Run it:   ./run 07.2/3          (Windows: run 07.2/3)
"""

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKETS = {
    "LL-2041": {"status": "open", "owner": "Priya", "summary": "VPN token reset", "priority": "high"},
    "LL-2043": {"status": "open", "owner": "Priya", "summary": "Printer on floor 3 offline", "priority": "medium"},
    "LL-2044": {"status": "open", "owner": "Tom", "summary": "Monitor flickers", "priority": "low"},
}
RUNBOOK = {
    "vpn": "VPN token reset: verify identity in person or on a video call, then reset in the identity portal.",
    "printer": "Printer offline: power cycle, check the switch port, then update firmware to 4.3.",
}


@tool
def tickets_by_owner(owner: str) -> str:
    """List open tickets (id, priority, summary) for an owner such as Priya."""
    rows = [f"{k} [{t['priority']}] {t['summary']}" for k, t in TICKETS.items() if t["owner"].lower() == owner.lower()]
    return "; ".join(rows) or "none"


@tool
def runbook(topic: str) -> str:
    """Return the fix procedure for a topic: vpn or printer."""
    return RUNBOOK.get(topic.lower(), f"no runbook for {topic}")


TOOLS = [tickets_by_owner, runbook]
QUESTION = "List Priya's open tickets, then tell me the runbook fix for each one."


class Plan(BaseModel):
    steps: list[str] = Field(description="At most 3 short, ordered steps, each needing one or two tool calls.")


def count(ctx, messages, label):
    """Count model turns and tool calls in a list of messages and record tokens quietly."""
    ai = [m for m in messages if m.type == "ai"]
    for m in ai:
        ctx.record_usage(m.usage_metadata, quiet=True)
    tools = [m for m in messages if m.type == "tool"]
    return {"approach": label, "model_calls": len(ai), "tool_calls": len(tools)}


@lesson("07.2/3", "Helpdesk: ReAct vs plan-and-execute")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    ctx.note(f"Question: {QUESTION}")
    rows = []

    ctx.step("A. ReAct: one agent, deciding as it goes")
    react = create_agent(model, tools=TOOLS, system_prompt="You are the Larkspur Labs helpdesk assistant. Use tools for facts. Be brief.")
    try:
        result = react.invoke({"messages": [("user", QUESTION)]}, {"recursion_limit": 11})
        rows.append(count(ctx, result["messages"], "react"))
        ctx.note(f"Answer: {str(result['messages'][-1].content)[:300]}")
    except Exception as exc:
        rows.append({"approach": "react", "model_calls": "?", "tool_calls": "?"})
        ctx.note(f"ReAct stopped: {type(exc).__name__}")

    ctx.step("B. Plan-and-execute: plan, run steps, synthesize")
    plan = model.with_structured_output(Plan).invoke([
        ("system", "Plan the steps for a helpdesk assistant with tools tickets_by_owner and runbook. Write each step in plain English, no function-call syntax and no placeholders. Do not answer."),
        ("user", QUESTION),
    ])
    steps = (plan.steps if plan else [QUESTION])[:3] or [QUESTION]
    ctx.show_data("Plan", steps)
    executor = create_agent(model, tools=TOOLS, system_prompt="Do ONE step with the tools. Reply with the facts found, briefly.")
    notes, all_msgs = [], []
    for i, step in enumerate(steps, 1):
        ctx.note(f"Executing step {i} of {len(steps)}: {step}")
        try:
            r = executor.invoke({"messages": [("user", "Facts so far: " + " | ".join(notes) + f"\nStep: {step}")]}, {"recursion_limit": 9})
            all_msgs += r["messages"]
            notes.append(str(r["messages"][-1].content))
        except Exception as exc:
            notes.append(f"(failed: {type(exc).__name__})")
    final = model.invoke([("system", "Answer using only the facts. Brief."), ("user", f"Question: {QUESTION}\nFacts: " + " | ".join(notes))])
    all_msgs.append(final)
    rows.append(count(ctx, all_msgs, "plan-and-execute"))
    rows[-1]["model_calls"] += 1  # the planner call is not in the message list
    ctx.note(f"Answer: {str(final.content)[:300]}")

    ctx.step("Compare")
    ctx.show_data("Cost of each approach", rows)
    ctx.note("Plan-and-execute adds a planner and a synthesis call but gives you a plan to log, review or cap before any tool runs.")
    ctx.note("ReAct is cheaper for short tasks; prefer plan-and-execute when the task has many independent parts or needs approval of the plan.")


if __name__ == "__main__":
    main()
