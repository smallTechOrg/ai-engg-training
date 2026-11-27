"""12.2/2  The model chains calls across two servers

New since 12.2/1: the registry now feeds a model. The question needs facts from BOTH
servers: the ticket desk knows the ticket and its owner, the knowledge base knows the fix.
The model has to call one server, read the result, and use it to pick the next call.
The host never decides the order; it only routes.

Run it:   ./run 12.2/2          (Windows: run 12.2/2)
"""

import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

HERE = Path(__file__).parent
SERVERS = {"tickets": HERE / "ticket_server.py", "kb": HERE / "kb_server.py"}
MAX_ITERATIONS = 6
QUESTION = "Ticket T-1001 came in. Tell me what it is, who owns it, and what the knowledge base says to try first."


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


@lesson("12.2/2", "The model chains calls across two servers")
async def main(ctx):
    async with AsyncExitStack() as stack:
        ctx.step("Build the registry and the tool list")
        routes, tools = {}, []
        for alias, script in SERVERS.items():
            params = StdioServerParameters(command=sys.executable, args=[str(script)])
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            for tool in (await session.list_tools()).tools:
                name = f"{alias}__{tool.name}"
                routes[name] = (session, tool.name)
                tools.append({"type": "function", "function": {"name": name, "description": f"[{alias}] {tool.description or ''}", "parameters": tool.input_schema}})
        ctx.note("Tools offered: " + ", ".join(routes))

        messages = [
            {"role": "system", "content": "You are the Larkspur Labs helpdesk assistant. Use the tools to look facts up; do not guess. Be brief."},
            {"role": "user", "content": QUESTION},
        ]
        ctx.show_messages(messages)
        ctx.step("Run the tool loop (the model picks the servers)")
        servers_used = []
        for iteration in range(1, MAX_ITERATIONS + 1):
            response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
            message = response.choices[0].message
            if not message.tool_calls:
                ctx.show_response(response)
                break
            ctx.record_usage(response.usage, quiet=True)  # a tool-call turn; the final reply is counted by show_response
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if name not in routes:
                        output = f"Tool {name} is not available."
                    else:
                        session, original = routes[name]
                        output = text_of(await session.call_tool(original, args))
                        servers_used.append(name.split("__")[0])
                except Exception as exc:  # bad arguments are an outcome, not a crash
                    args, output = call.function.arguments, f"Tool failed: {exc}"
                ctx.show_tool_call(name, args, output)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
        else:
            ctx.note(f"Stopped after {MAX_ITERATIONS} iterations without a final answer.")

        ctx.step("Which servers did the model use?")
        ctx.note("Order of servers called: " + (" -> ".join(servers_used) or "none"))
        if set(servers_used) >= set(SERVERS):
            ctx.note("Both servers were needed and both were used: that is a chain across servers.")
        else:
            ctx.note("Fewer than both servers were used; the answer may be incomplete. Try a more explicit question.")


if __name__ == "__main__":
    main()
