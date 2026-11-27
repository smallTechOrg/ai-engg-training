"""11.1/1  Connect to an MCP server and discover what it offers

An MCP server is a separate program that offers tools, resources and prompts. A client
connects to it, says hello (`initialize`), and asks what it has. Here our script is the
client and `helpdesk_server.py` (next to this file) is the server, started as a
subprocess that talks JSON-RPC over its stdin and stdout.

No model is involved in this script.

Run it:   ./run 11.1/1          (Windows: run 11.1/1)
"""

import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("helpdesk_server.py")


@lesson("11.1/1", "Connect to an MCP server and discover it")
async def main(ctx):
    ctx.step("Launch the server and open a session")
    # sys.executable = the same Python that runs this lesson, so the server finds the `mcp` package.
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    ctx.note(f"Server command: python {SERVER.name}  (stdio transport: we write to its stdin, read its stdout)")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            ctx.step("Initialize: the handshake and capability negotiation")
            init = await session.initialize()
            ctx.show_data(
                "What the server told us about itself",
                {
                    "protocol_version": init.protocol_version,
                    "server_info": init.server_info.name,
                    "capabilities": init.capabilities.model_dump(exclude_none=True),
                },
            )
            ctx.note("Capabilities are the server's promise: it has tools, resources and prompts, and no more.")
            ctx.note("A client only calls what a server announced here.")

            ctx.step("List the tools")
            for tool in (await session.list_tools()).tools:
                ctx.show_data(f"tool: {tool.name}", {"description": tool.description, "input_schema": tool.input_schema})
            ctx.note("A tool is an action the MODEL may ask for. The input schema is JSON Schema, just like function calling.")

            ctx.step("List the resources")
            for res in (await session.list_resources()).resources:
                ctx.note(f"resource: {res.uri}  ({res.mime_type})  {res.description}")
            ctx.note("A resource is data the APPLICATION reads and chooses to put in front of the model.")

            ctx.step("List the prompts")
            for prompt in (await session.list_prompts()).prompts:
                args = [a.name for a in (prompt.arguments or [])]
                ctx.note(f"prompt: {prompt.name}  arguments={args}  {prompt.description}")
            ctx.note("A prompt is a reusable template the USER picks, such as a slash command.")


if __name__ == "__main__":
    main()
