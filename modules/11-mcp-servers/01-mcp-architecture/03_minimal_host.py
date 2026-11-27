"""11.1/3  A minimal MCP host: the model uses tools through MCP

The host is the application that owns the model. It starts an MCP client for each server,
turns the server's tools into the tool schemas the model API understands, and forwards
the model's tool calls to the server. This is that loop in about 30 lines.

Run it:   ./run 11.1/3          (Windows: run 11.1/3)
"""

import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("helpdesk_server.py")
MAX_ITERATIONS = 3
QUESTION = "What is the status and category of ticket T-1001? Use the helpdesk tool."


@lesson("11.1/3", "A minimal MCP host")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            ctx.step("Convert the server's MCP tools into OpenAI tool schemas")
            mcp_tools = (await session.list_tools()).tools
            tools = [
                {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
                for t in mcp_tools
            ]
            ctx.show_data("Tools offered to the model", tools)
            ctx.note("MCP's input_schema is already JSON Schema, so the conversion is a rename.")

            messages = [
                {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Use tools to look facts up."},
                {"role": "user", "content": QUESTION},
            ]
            ctx.step("Let the model call the tool through MCP")
            for iteration in range(1, MAX_ITERATIONS + 1):
                response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
                message = response.choices[0].message
                if not message.tool_calls:
                    ctx.show_response(response)
                    break
                ctx.record_usage(response.usage, quiet=True)  # a tool-call turn; the final reply is counted by show_response
                messages.append(message.model_dump(exclude_none=True))
                for call in message.tool_calls:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        result = await session.call_tool(call.function.name, args)  # <- the MCP part
                        output = "".join(p.text for p in result.content if p.type == "text")
                    except Exception as exc:  # bad arguments from the model are an outcome, not a crash
                        args, output = call.function.arguments, f"Tool failed: {exc}"
                    ctx.show_tool_call(call.function.name, args, output)
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            else:
                ctx.note(f"Stopped after {MAX_ITERATIONS} iterations without a final answer.")


if __name__ == "__main__":
    main()
