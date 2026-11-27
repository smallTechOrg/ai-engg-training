"""07.2/1  The ReAct loop, traced step by step

ReAct means Reason, Act, Observe, repeat. With a tool-calling model the "act" is a tool call
and the "observe" is a ToolMessage, so `create_agent` (lesson 07.1) already is a ReAct agent.
Here we stream its graph updates so every turn of the loop is visible, and we cap the loop.

Run it:   ./run 07.2/1          (Windows: run 07.2/1)
"""

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

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


RECURSION_LIMIT = 11  # each model call and each tools node is one graph step


@lesson("07.2/1", "The ReAct loop, traced")
def main(ctx):
    ctx.step("Build a ReAct agent")
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    agent = create_agent(
        model,
        tools=[open_tickets_for, lookup_ticket, lookup_device],
        system_prompt=(
            "You are the Larkspur Labs IT helpdesk assistant. Work step by step: say in one short "
            "sentence what you need next, call a tool, read the result, and repeat until you can answer."
        ),
    )
    ctx.note("Reason = the model's text, Act = tool_calls, Observe = ToolMessage. The graph loops until there are no tool calls.")

    ctx.step("Stream the loop (stream_mode='updates')")
    question = "Priya says her printer ticket is stuck. What device is it and is there a known problem?"
    ctx.note(f"Question: {question}")
    turn = 0
    final = None
    try:
        for update in agent.stream({"messages": [("user", question)]}, {"recursion_limit": RECURSION_LIMIT}, stream_mode="updates"):
            # each update is {node_name: {"messages": [new messages]}}
            for node, delta in update.items():
                for m in delta["messages"]:
                    if m.type == "ai":
                        turn += 1
                        ctx.record_usage(m.usage_metadata, quiet=True)
                        ctx.note(f"[{node}] turn {turn}: REASON {str(m.content)[:100]!r}")
                        for c in m.tool_calls:
                            ctx.note(f"[{node}] turn {turn}: ACT    {c['name']}({c['args']})")
                        if not m.tool_calls:
                            final = m.content
                    elif m.type == "tool":
                        ctx.note(f"[{node}] turn {turn}: OBSERVE {str(m.content)[:100]}")
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:140]}")
        ctx.note(f"The loop did not finish within {RECURSION_LIMIT} graph steps. That is the cap doing its job.")

    ctx.step("Result")
    ctx.note(f"Model turns: {turn}. Final answer: {final!r}")
    ctx.note("Each extra tool needed is another turn: ReAct decides one step at a time, with no plan up front.")


if __name__ == "__main__":
    main()
