"""11.1/2  Call a tool, read a resource, get a prompt

The three MCP primitives each have their own request: `tools/call`, `resources/read`
and `prompts/get`. This script uses all three against the helpdesk server and prints
what comes back. Still no model: MCP is a protocol between programs.

Run it:   ./run 11.1/2          (Windows: run 11.1/2)
"""

import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("helpdesk_server.py")


@lesson("11.1/2", "Call a tool, read a resource, get a prompt")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            ctx.step("tools/call: run an action on the server")
            args = {"ticket_id": "T-1001"}
            result = await session.call_tool("lookup_ticket", args)
            text = "".join(part.text for part in result.content if part.type == "text")
            ctx.show_tool_call("lookup_ticket", args, text)
            ctx.note(f"is_error={result.is_error}. Tool failures come back as results with is_error=True, not as crashes.")

            ctx.step("tools/call with an id that does not exist")
            result = await session.call_tool("lookup_ticket", {"ticket_id": "T-9999"})
            ctx.show_tool_call("lookup_ticket", {"ticket_id": "T-9999"}, "".join(p.text for p in result.content if p.type == "text"))

            ctx.step("resources/read: fetch a document by its URI")
            read_result = await session.read_resource("helpdesk://policies/password")
            for item in read_result.contents:
                ctx.note(f"{item.uri} ({item.mime_type}): {getattr(item, 'text', '<binary>')}")

            ctx.step("prompts/get: render a prompt template with arguments")
            got = await session.get_prompt("triage_prompt", {"ticket_text": "My badge does not open the server room."})
            for message in got.messages:
                ctx.show_messages([{"role": message.role, "content": message.content.text}])
            ctx.note("The server returns ready-made messages. The host decides whether to send them to a model.")


if __name__ == "__main__":
    main()
