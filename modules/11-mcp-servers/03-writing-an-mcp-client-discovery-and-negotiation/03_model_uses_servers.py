"""11.3/3  A model works across two MCP servers

A shorter, inlined version of the ToolBridge from script 2 is handed to a real chat model. The question
needs one tool from each server and a decision between them: check a service, find the
related ticket, raise its priority only if the service is degraded.

Hard cap: 6 model calls. The model's choices vary between runs; the lesson prints what happened.

Run it:   ./run 11.3/3          (Windows: run 11.3/3)
"""

import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

HERE = Path(__file__).parent
MAX_ITERATIONS = 6
QUESTION = (
    "Check whether the VPN service is healthy. If it is degraded, find the open network tickets "
    "and set the priority of the VPN one to 1. Then summarise what you did in two sentences."
)


@lesson("11.3/3", "A model working across two MCP servers")
async def main(ctx):
    quiet = open(os.devnull, "w")
    try:
        async with AsyncExitStack() as stack:
            routes, tools = {}, []
            ctx.step("Connect, discover, and convert the tools of both servers")
            for label, filename in (("tickets", "ticket_server.py"), ("status", "status_server.py")):
                params = StdioServerParameters(command=sys.executable, args=[str(HERE / filename)])
                read, write = await stack.enter_async_context(stdio_client(params, errlog=quiet))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                for tool in (await session.list_tools()).tools:
                    routes[f"{label}__{tool.name}"] = (session, tool.name)
                    tools.append({"type": "function", "function": {"name": f"{label}__{tool.name}", "description": tool.description or "", "parameters": tool.input_schema}})
            ctx.note(f"Offering the model {len(tools)} tools: {', '.join(routes)}")

            messages = [
                {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Use the tools; do not guess."},
                {"role": "user", "content": QUESTION},
            ]
            ctx.show_messages(messages)

            ctx.step("The tool loop")
            for iteration in range(1, MAX_ITERATIONS + 1):
                response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
                message = response.choices[0].message
                if not message.tool_calls:
                    ctx.show_response(response)
                    break
                ctx.record_usage(response.usage, quiet=True)  # tool-call turn; the final reply is counted by show_response
                messages.append(message.model_dump(exclude_none=True))
                for call in message.tool_calls:
                    if call.function.name not in routes:
                        output = f"Error: unknown tool {call.function.name!r}"
                    else:
                        session, real_name = routes[call.function.name]
                        try:
                            result = await session.call_tool(real_name, json.loads(call.function.arguments or "{}"))
                            output = "".join(p.text for p in result.content if p.type == "text")
                            if result.is_error:
                                output = f"Error: {output}"
                        except Exception as exc:  # bad JSON from the model is an outcome, not a crash
                            output = f"Error: {exc}"
                    ctx.show_tool_call(call.function.name, call.function.arguments, output.splitlines()[0] if output else "")
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            else:
                ctx.note(f"Stopped after {MAX_ITERATIONS} model calls without a final answer.")
    finally:
        quiet.close()


if __name__ == "__main__":
    main()
