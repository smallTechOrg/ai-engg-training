"""11.2/2  Resources: static documents and URI templates

A resource is data the application reads by URI. A static resource has one fixed URI.
A resource TEMPLATE (`helpdesk://tickets/{ticket_id}`) describes a whole family of
URIs: the client fills in the variable and the server builds the document on demand.
Reads can also fail, and the failure is a protocol error, not a tool-style result.

Run it:   ./run 11.2/2          (Windows: run 11.2/2)
"""

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

SERVER = Path(__file__).with_name("ticket_server.py")


@lesson("11.2/2", "Resources and resource templates")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                ctx.step("Static resources versus templates: two different list calls")
                for res in (await session.list_resources()).resources:
                    ctx.note(f"static   | {res.uri}  ({res.mime_type})")
                for tpl in (await session.list_resource_templates()).resource_templates:
                    ctx.note(f"template | {tpl.uri_template}  ({tpl.mime_type})  {tpl.description}")
                ctx.note("Templates are NOT in resources/list: there is no way to enumerate every possible ticket.")

                ctx.step("Read the static resource")
                got = await session.read_resource("helpdesk://policies/password")
                ctx.note(got.contents[0].text)

                ctx.step("Fill in the template and read three tickets")
                for ticket_id in ("T-1001", "T-1003", "t-1004"):
                    uri = f"helpdesk://tickets/{ticket_id}"
                    got = await session.read_resource(uri)
                    ctx.note(f"{uri} ({got.contents[0].mime_type}) -> {json.dumps(json.loads(got.contents[0].text))}")
                ctx.note("The server returned a dict; the SDK serialized it to JSON text because the mime type is application/json.")

                ctx.step("A read that fails: unknown ticket")
                try:
                    await session.read_resource("helpdesk://tickets/T-7")
                except MCPError as exc:
                    ctx.note(f"MCPError: {exc}")
                    ctx.note("Resources have no is_error flag: a missing document is a JSON-RPC error (-32602 invalid params).")

                ctx.step("Tool or resource? A rule of thumb")
                ctx.note("Resource: the app decides to load it, it is addressed by URI, reading changes nothing.")
                ctx.note("Tool: the model decides to call it, it takes arguments, it may search or change state.")
                ctx.note("Many servers offer both: a resource for 'show me ticket T-1001', a tool for 'find tickets like this'.")


if __name__ == "__main__":
    main()
