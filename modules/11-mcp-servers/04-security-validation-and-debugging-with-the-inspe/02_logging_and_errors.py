"""11.4/2  Debugging a stdio server: stderr logs, error kinds, and the stdout trap

When a stdio server misbehaves you cannot just `print`: stdout IS the protocol. Logs belong
on stderr. This script points the server's stderr at a temp file, makes a few calls, then
parses the JSON log lines. It also shows the three kinds of failure a client can see
(argument rejection, a ToolError, a protocol error), and what a stray `print` to stdout does.

No model is needed.

Run it:   ./run 11.4/2          (Windows: run 11.4/2)
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

SERVER = Path(__file__).with_name("secure_server.py")


class Collect(logging.Handler):
    """Collects log records emitted by the mcp client library itself."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage().splitlines()[0])


@lesson("11.4/2", "Logging to stderr and reading errors")
async def main(ctx):
    ctx.step("Run the server with its stderr captured in a temp file")
    with tempfile.TemporaryFile("w+", encoding="utf-8") as errlog:
        params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=10) as session:
                await session.initialize()

                ctx.step("Three kinds of failure")
                result = await session.call_tool("get_ticket_text", {"ticket_id": "T-1"})
                ctx.show_tool_call("get_ticket_text", {"ticket_id": "T-1"}, f"is_error={result.is_error} | schema rejected it before our code ran")
                result = await session.call_tool("get_ticket_text", {"ticket_id": "T-9999"})
                ctx.show_tool_call("get_ticket_text", {"ticket_id": "T-9999"}, f"is_error={result.is_error} | {result.content[0].text}")
                result = await session.call_tool("not_a_tool", {})
                ctx.show_tool_call("not_a_tool", {}, f"is_error={result.is_error} | {result.content[0].text}")
                try:
                    await session.read_resource("helpdesk://nothing/here")
                    outcome = "no exception"
                except MCPError as exc:
                    outcome = f"MCPError: {exc}"
                ctx.note(f"read_resource of an unknown URI -> {outcome}")
                ctx.note("Failed TOOL calls (bad arguments, unknown tool, ToolError) are results with is_error: the MODEL sees them and can retry.")
                ctx.note("Failed protocol requests (resources, prompts, unknown methods) raise MCPError in the HOST's code.")
                await session.call_tool("find_tickets", {"text": "VPN"})
                await session.call_tool("close_ticket", {"ticket_id": "T-2003"})

        errlog.seek(0)
        lines = errlog.read().splitlines()

    ctx.step("What the server wrote to stderr (parsed as JSON lines)")
    parsed = []
    library_lines = 0
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            library_lines += 1  # the SDK's own pretty-printed log lines share the same stream
    ctx.note(f"{len(lines)} stderr lines: {len(parsed)} are our JSON lines, {library_lines} are the SDK's own log lines.")
    for entry in parsed:
        fields = {k: v for k, v in entry.items() if k not in ("ts", "event")}
        ctx.note(f"{entry['event']:11} {json.dumps(fields)}")
    ctx.note("One request_id ties a start line to its end line. Argument NAMES are logged, argument VALUES are not (they may be private).")

    ctx.step("The classic bug: a print() to stdout in a stdio server")
    handler = Collect()
    logging.getLogger().addHandler(handler)
    try:
        noisy = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env={**os.environ, "LARKSPUR_NOISY": "1"})
        with open(os.devnull, "w") as quiet:
            async with stdio_client(noisy, errlog=quiet) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=10) as session:
                    await session.initialize()
                    result = await session.call_tool("find_tickets", {"text": "badge"})
                    ctx.note(f"The session still worked: {result.content[0].text}")
    finally:
        logging.getLogger().removeHandler(handler)
    ctx.note(f"The client reported {len(handler.messages)} problem(s) with the server's output; the first:")
    for message in handler.messages[:1]:
        ctx.note(f"  {message[:120]}")
    ctx.note("This SDK skips the junk line and carries on. Older clients may hang or fail: never print to stdout in a stdio server.")


if __name__ == "__main__":
    main()
