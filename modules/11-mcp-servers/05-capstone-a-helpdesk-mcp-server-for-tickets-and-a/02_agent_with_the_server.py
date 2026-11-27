"""11.5/2  A helpdesk agent that uses the server, with a gate and a ground-truth check

The host connects to the capstone server, offers the model its tools EXCEPT the destructive
ones (the gate from 11.4), and gives a multi-step job: open a ticket for a new hire and assign
a laptop. When the model has finished, the host does not trust its summary: it reads the
server's resources and checks what really changed.

Hard cap: 8 model calls. Model behaviour varies; the script reports what happened.

Run it:   ./run 11.5/2          (Windows: run 11.5/2)
"""

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

SERVER = Path(__file__).with_name("helpdesk_server.py")
MAX_ITERATIONS = 8
JOB = (
    "New hire mara.k starts Monday. Open a hardware ticket for her with the subject 'New hire laptop for mara.k', "
    "pick an available 14-inch laptop, assign it to mara.k, and tell me the ticket id and the asset tag."
)


@lesson("11.5/2", "An agent using the helpdesk server")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=15) as session:
                await session.initialize()

                ctx.step("Offer the tools, withholding the destructive ones")
                tools, withheld = [], []
                for tool in (await session.list_tools()).tools:
                    if tool.annotations and tool.annotations.destructive_hint:
                        withheld.append(tool.name)
                        continue
                    tools.append({"type": "function", "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema}})
                ctx.note(f"offered: {', '.join(t['function']['name'] for t in tools)}")
                ctx.note(f"withheld (needs a human): {', '.join(withheld)}")

                messages = [
                    {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Use the tools; never guess ids or tags."},
                    {"role": "user", "content": JOB},
                ]
                ctx.show_messages(messages)

                ctx.step("The tool loop")
                for _ in range(MAX_ITERATIONS):
                    response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
                    message = response.choices[0].message
                    if not message.tool_calls:
                        ctx.show_response(response)
                        break
                    ctx.record_usage(response.usage, quiet=True)  # tool-call turn; the final reply is counted by show_response
                    messages.append(message.model_dump(exclude_none=True))
                    for call in message.tool_calls:
                        try:
                            result = await session.call_tool(call.function.name, json.loads(call.function.arguments or "{}"))
                            output = "".join(p.text for p in result.content if p.type == "text")
                            output = f"Error: {output}" if result.is_error else output
                        except Exception as exc:
                            output = f"Error: {exc}"
                        ctx.show_tool_call(call.function.name, call.function.arguments, output.splitlines()[0] if output else "")
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                else:
                    ctx.note(f"Stopped after {MAX_ITERATIONS} model calls without a final answer.")

                ctx.step("Ground truth: what does the server say actually changed?")
                for tag in ("LL-L-0500", "LL-L-0501"):
                    asset = json.loads((await session.read_resource(f"helpdesk://assets/{tag}")).contents[0].text)
                    ctx.note(f"{tag}: status={asset['status']} assigned_to={asset['assigned_to']}")
                try:
                    ticket = json.loads((await session.read_resource("helpdesk://tickets/T-3006")).contents[0].text)
                    ctx.note(f"T-3006: {ticket['subject']} [{ticket['category']}] requester={ticket['requester']}")
                except MCPError:
                    ctx.note("T-3006 does not exist: no ticket was created.")
                ctx.note("Compare the model's final answer with these facts. A fluent summary is not evidence; the resources are.")


if __name__ == "__main__":
    main()
