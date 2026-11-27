"""07.4/2  Streaming intermediate steps and tokens

An agent run can take many seconds. `agent.stream(...)` yields progress as it happens.
`stream_mode="updates"` gives one event per graph node (a model turn, a tools node), and
`stream_mode="messages"` gives the model's tokens as they are produced. Passing both as a list
gives you tagged tuples, which is what a UI needs: a "working on it" log plus a live answer.

Run it:   ./run 07.4/2          (Windows: run 07.4/2)
"""

import time

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from labkit import lesson

TICKETS = {
    "LL-2041": "open, owner Priya, waiting on a VPN token reset",
    "LL-2043": "open, owner Priya, printer on floor 3 offline",
}


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Return the status line of a ticket id such as LL-2041."""
    return TICKETS.get(ticket_id, f"no ticket named {ticket_id}")


@lesson("07.4/2", "Streaming intermediate steps and tokens")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    agent = create_agent(model, tools=[lookup_ticket], system_prompt="You are the Larkspur Labs helpdesk assistant. Look tickets up with the tool. Be brief.")
    question = "Compare tickets LL-2041 and LL-2043: which one should Priya do first?"
    ctx.note(f"Question: {question}")

    ctx.step("stream_mode='updates': one event per node")
    start = time.monotonic()
    try:
        for update in agent.stream({"messages": [("user", question)]}, {"recursion_limit": 9}, stream_mode="updates"):
            for node, delta in update.items():
                last = delta["messages"][-1]
                what = f"tool calls {[c['name'] for c in last.tool_calls]}" if getattr(last, "tool_calls", None) else f"message {str(last.content)[:70]!r}"
                ctx.note(f"+{time.monotonic() - start:4.1f}s node={node:<6} {what}")
                if last.type == "ai":
                    ctx.record_usage(last.usage_metadata, quiet=True)
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:120]}")

    ctx.step("stream_mode=['messages', 'updates']: tokens and steps together")
    ctx.note("Each item is a (mode, payload) tuple. 'messages' payloads are (chunk, metadata) pairs.")
    tokens = 0
    shown = []
    start = time.monotonic()
    first_token = None
    try:
        for mode, payload in agent.stream({"messages": [("user", question)]}, {"recursion_limit": 9}, stream_mode=["messages", "updates"]):
            if mode == "messages":
                chunk, meta = payload
                if chunk.content and meta.get("langgraph_node") == "model":
                    tokens += 1
                    first_token = first_token or time.monotonic() - start
                    if len(shown) < 12:
                        shown.append(chunk.content)
            else:
                for node in payload:
                    ctx.note(f"+{time.monotonic() - start:4.1f}s update from node {node!r}")
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:120]}")
    ctx.note(f"Text chunks received: {tokens}; first chunk after {first_token if first_token is None else round(first_token, 1)}s")
    ctx.note(f"First chunks: {shown}")
    ctx.note("Token usage of this second run is not recorded here: streamed chunks carry usage only if the provider sends it.")
    ctx.note("A UI shows the 'updates' as a progress list and prints the 'messages' chunks as the answer arrives.")


if __name__ == "__main__":
    main()
