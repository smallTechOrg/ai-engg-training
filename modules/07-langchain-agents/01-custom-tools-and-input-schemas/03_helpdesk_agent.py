"""07.1/3  A prebuilt agent over helpdesk tools

`langchain.agents.create_agent` is the current prebuilt agent: it wraps the loop from script 2
in a LangGraph graph. You give it a model, tools and a system prompt, then invoke it with
messages. Here every step is printed, and the number of steps is capped.

Run it:   ./run 07.1/3          (Windows: run 07.1/3)
"""

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

# An invented ticket table.
TICKETS = {
    "LL-2041": {"status": "open", "owner": "Priya", "summary": "VPN token reset", "priority": "high"},
    "LL-2042": {"status": "resolved", "owner": "Tom", "summary": "Laptop battery replaced", "priority": "low"},
    "LL-2043": {"status": "open", "owner": "Priya", "summary": "Printer on floor 3 offline", "priority": "medium"},
}


class TicketId(BaseModel):
    ticket_id: str = Field(description="Ticket id such as LL-2041.")


class OwnerQuery(BaseModel):
    owner: str = Field(description="First name of a helpdesk agent, e.g. Priya.")


@tool(args_schema=TicketId)
def lookup_ticket(ticket_id: str) -> str:
    """Return status, owner, priority and summary of one ticket."""
    t = TICKETS.get(ticket_id)
    return f"{ticket_id}: {t}" if t else f"No ticket named {ticket_id}."


@tool(args_schema=OwnerQuery)
def open_tickets_for(owner: str) -> str:
    """List the ids of open tickets owned by a helpdesk agent."""
    ids = [k for k, t in TICKETS.items() if t["owner"].lower() == owner.lower() and t["status"] == "open"]
    return ", ".join(ids) or "none"


@lesson("07.1/3", "A prebuilt agent over helpdesk tools")
def main(ctx):
    ctx.step("Build the agent")
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    agent = create_agent(
        model,
        tools=[lookup_ticket, open_tickets_for],
        system_prompt="You are the Larkspur Labs IT helpdesk assistant. Use the tools for ticket facts. Be brief.",
    )
    ctx.note("create_agent returns a compiled LangGraph graph: a model node, a tools node, and a loop between them.")

    ctx.step("Run it, capped")
    question = "Which tickets does Priya have open, and what is the summary of the highest priority one?"
    ctx.note(f"Question: {question}")
    # recursion_limit caps graph steps (each model call and each tool node counts as one).
    config = {"recursion_limit": 9}
    try:
        result = agent.invoke({"messages": [("user", question)]}, config=config)
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:160]}")
        ctx.note("Hitting the cap is a normal, explained outcome: the agent did not finish within 9 steps.")
        return

    ctx.step("Print every step")
    asked = {}
    for m in result["messages"]:
        if m.type == "human":
            ctx.note(f"human | {m.content}")
        elif m.type == "ai":
            if m.usage_metadata:
                ctx.record_usage(m.usage_metadata, quiet=True)
            if m.tool_calls:
                for c in m.tool_calls:
                    asked[c["id"]] = c["args"]
                    ctx.note(f"ai asks for {c['name']}({c['args']})")
            else:
                ctx.note(f"ai answers | {m.content}")
        elif m.type == "tool":
            ctx.show_tool_call(m.name, asked.get(m.tool_call_id, {}), m.content)

    ctx.step("What the framework did for you")
    ctx.note("Compared with 02.3 you did not write the loop, the ToolMessage plumbing or the argument parsing.")
    ctx.note(f"Messages in the final state: {len(result['messages'])}")


if __name__ == "__main__":
    main()
