"""11.2/1  Tools with schemas: the signature IS the contract

In 11.1 the tool took one string. Real tools need typed, bounded arguments. The server
builds the tool's JSON Schema from the Python signature (types, defaults, `Literal`,
`Field(ge=, le=, pattern=)`), and validates every call against it BEFORE your function
runs. This script lists the schemas, then makes good and bad calls.

Run it:   ./run 11.2/1          (Windows: run 11.2/1)
"""

import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("ticket_server.py")


def text_of(result) -> str:
    return "".join(part.text for part in result.content if part.type == "text")


@lesson("11.2/1", "Tools with schemas and validation")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    # errlog: where the server's stderr goes. We discard it here to keep the output readable;
    # lesson 11.4 reads it on purpose.
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                ctx.step("The schema the server generated from the Python signature")
                for tool in (await session.list_tools()).tools:
                    ctx.show_data(f"tool: {tool.name}", {"description": tool.description, "input_schema": tool.input_schema})
                ctx.note("Literal became an enum, ge/le became minimum/maximum, the default made `status` optional.")
                ctx.note("The model reads this schema, so descriptions on arguments are prompt text.")

                ctx.step("A valid call, with and without the optional arguments")
                for args in ({"category": "network"}, {"category": "network", "status": "closed", "limit": 3}):
                    result = await session.call_tool("search_tickets", args)
                    ctx.show_tool_call("search_tickets", args, text_of(result))

                ctx.step("Invalid arguments are rejected before the function runs")
                bad_calls = [
                    ("set_priority", {"ticket_id": "bad", "priority": 9}),
                    ("search_tickets", {"category": "network", "status": "pending"}),
                    ("search_tickets", {}),
                ]
                for name, args in bad_calls:
                    result = await session.call_tool(name, args)
                    first_line = text_of(result).splitlines()[0]
                    ctx.show_tool_call(name, args, f"is_error={result.is_error} | {first_line}")
                ctx.note("The message goes back to the model as a normal tool result, so it can fix its arguments and retry.")

                ctx.step("A failure the function itself raises on purpose (ToolError)")
                result = await session.call_tool("set_priority", {"ticket_id": "T-9999", "priority": 2})
                ctx.show_tool_call("set_priority", {"ticket_id": "T-9999", "priority": 2}, f"is_error={result.is_error} | {text_of(result)}")
                ctx.note("Raise `ToolError(message)` for failures you expect: the model sees your message.")
                ctx.note("Any other exception is treated as a crash and the model only sees 'Error executing tool ...'.")


if __name__ == "__main__":
    main()
