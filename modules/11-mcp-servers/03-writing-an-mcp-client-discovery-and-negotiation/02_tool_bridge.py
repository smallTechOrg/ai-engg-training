"""11.3/2  A tool bridge: MCP tools in, OpenAI tool schemas out, results back

A host that talks to several servers needs one table that maps what the MODEL calls a tool
to the SESSION that owns it. This script builds that bridge as a small class and exercises
it without a model, by feeding it tool calls a model might produce, including bad ones.

Things the bridge handles:
  - namespacing (`tickets__search_tickets`), so two servers can both have a tool called `search`
  - mapping the MCP schema to the OpenAI `tools=[...]` format
  - turning a call result (text, structured data, is_error) into one string for the model
  - bad calls: unknown tool, arguments that are not JSON

Run it:   ./run 11.3/2          (Windows: run 11.3/2)
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


class ToolBridge:
    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self.routes: dict[str, tuple[str, str]] = {}  # model-facing name -> (server label, real tool name)
        self.schemas: list[dict] = []

    async def add_server(self, label: str, session: ClientSession) -> None:
        self.sessions[label] = session
        if not session.server_capabilities.tools:
            return
        for tool in (await session.list_tools()).tools:
            name = f"{label}__{tool.name}"
            self.routes[name] = (label, tool.name)
            self.schemas.append(
                {"type": "function", "function": {"name": name, "description": tool.description or "", "parameters": tool.input_schema}}
            )

    async def call(self, name: str, raw_arguments: str) -> str:
        """Run a model-requested call; every failure comes back as text the model can react to."""
        if name not in self.routes:
            return f"Error: unknown tool {name!r}. Available: {', '.join(self.routes)}"
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            return f"Error: arguments are not valid JSON ({exc.msg}). Send a JSON object."
        label, real_name = self.routes[name]
        result = await self.sessions[label].call_tool(real_name, arguments)
        text = "".join(part.text for part in result.content if part.type == "text") or "(no text content)"
        return f"Error: {text}" if result.is_error else text


@lesson("11.3/2", "A tool bridge across servers")
async def main(ctx):
    quiet = open(os.devnull, "w")
    try:
        async with AsyncExitStack() as stack:
            bridge = ToolBridge()
            ctx.step("Open both servers and register their tools")
            for label, filename in (("tickets", "ticket_server.py"), ("status", "status_server.py")):
                params = StdioServerParameters(command=sys.executable, args=[str(HERE / filename)])
                read, write = await stack.enter_async_context(stdio_client(params, errlog=quiet))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                await bridge.add_server(label, session)
            ctx.show_data("Routing table (model-facing name -> server, tool)", bridge.routes)
            ctx.show_data("The schema list a chat model would receive as tools=[...]", [s["function"]["name"] for s in bridge.schemas])
            ctx.note("One element of that list, in full:")
            ctx.show_data(bridge.schemas[0]["function"]["name"], bridge.schemas[0])

            ctx.step("Calls a model might send, good and bad")
            calls = [
                ("status__service_status", '{"service": "vpn"}'),
                ("tickets__search_tickets", '{"category": "network"}'),
                ("tickets__set_priority", '{"ticket_id": "T-1001", "priority": 9}'),
                ("status__service_status", '{"service": "printer"}'),
                ("status__service_status", '{"service": '),
                ("service_status", '{"service": "vpn"}'),
            ]
            for name, raw in calls:
                ctx.show_tool_call(name, raw, (await bridge.call(name, raw)).splitlines()[0])
            ctx.note("Every outcome is a string. The model reads 'Error: ...' and can correct itself; the host never crashes.")
    finally:
        quiet.close()


if __name__ == "__main__":
    main()
