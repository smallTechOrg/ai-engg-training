"""12.4/2  Capstone, stage 2: the model writes the report with tools

The other end of the spectrum from stage 1: give the model the SQLite server's read-only tools and a
local `save_report` tool, and let it work out the queries AND write the report. This is flexible and
needs the least code, but nothing guarantees the numbers. After the run the script compares the report
against the true counts (computed with sqlite3 directly, outside the model) and says what it finds.

Needs network on the first run (uvx) and a tool-calling model; at most 8 model calls.

Run it:   ./run 12.4/2          (Windows: run 12.4/2)
"""

import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson
from labkit.errors import ServiceUnavailable

READ_ONLY_TOOLS = {"list_tables", "describe_table", "read_query"}
MAX_ITERATIONS = 8
TASK = (
    "Write the weekly helpdesk report. Use the database to count OPEN tickets in total and per category, "
    "and name the oldest open ticket. Then call save_report with a short markdown report: a heading, "
    "the total, a bullet per category, and one sentence about the oldest ticket."
)
SAVE_TOOL = {
    "type": "function",
    "function": {
        "name": "save_report",
        "description": "Save the finished markdown report.",
        "parameters": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
}

def find_uvx():
    """uvx may not be on PATH inside a launcher, so also look in the usual install folders."""
    found = shutil.which("uvx")
    if found:
        return found
    names = ["uvx.exe", "uvx"] if os.name == "nt" else ["uvx"]
    for folder in (Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"):
        for name in names:
            if (folder / name).exists():
                return str(folder / name)
    raise ServiceUnavailable(
        "`uvx` (part of uv) was not found, and this lesson launches a published MCP server with it.",
        [
            "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
            "Open a new terminal so PATH is refreshed, then run the lesson again.",
        ],
    )


def make_tickets_db(folder):
    """An invented helpdesk database in a temp folder."""
    path = Path(folder) / "helpdesk.db"
    rows = [
        (1, "network", "open", "high", "VPN drops every ten minutes", "2026-11-02"),
        (2, "hardware", "open", "high", "Laptop battery swells", "2026-11-03"),
        (3, "access", "closed", "low", "Cannot open shared finance sheet", "2026-11-03"),
        (4, "network", "open", "medium", "Wi-Fi slow in meeting room B", "2026-11-05"),
        (5, "software", "open", "medium", "Editor crashes on startup", "2026-11-09"),
        (6, "network", "closed", "low", "Printer offline on floor 2", "2026-11-10"),
        (7, "access", "open", "high", "New starter has no badge access", "2026-11-12"),
        (8, "network", "open", "high", "Office VPN gateway timing out", "2026-11-16"),
        (9, "software", "closed", "low", "Licence prompt on spreadsheet app", "2026-11-17"),
        (10, "hardware", "closed", "medium", "Docking station not charging", "2026-11-18"),
        (11, "access", "open", "low", "Request for shared mailbox", "2026-11-20"),
        (12, "network", "open", "medium", "Guest Wi-Fi password rotation", "2026-11-23"),
    ]
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, category TEXT, status TEXT, priority TEXT, subject TEXT, opened TEXT)")
        db.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", rows)
        db.commit()
    return path


def sqlite_server_params(db_path):
    # The published server was written for mcp 1.x, so we ask uvx to run it with `mcp<2`.
    return StdioServerParameters(command=find_uvx(), args=["--with", "mcp<2", "mcp-server-sqlite", "--db-path", str(db_path)])


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


def server_failed(exc):
    return ServiceUnavailable(
        f"Could not start or talk to the SQLite MCP server ({type(exc).__name__}).",
        ["The first run needs network to download the server.", "Test it by hand: uvx mcp-server-sqlite --help"],
    )


def true_open_counts(db_path):
    """Ground truth, straight from SQLite, not through the model or the server."""
    with closing(sqlite3.connect(db_path)) as db:
        return dict(db.execute("SELECT category, COUNT(*) FROM tickets WHERE status = 'open' GROUP BY category"))


@lesson("12.4/2", "Capstone: the model writes the report with tools")
async def main(ctx):
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        report = Path(folder) / "weekly_report.md"
        ctx.step("Connect and build the tool list")
        ctx.note("First run downloads the server through uvx, so it needs network.")
        try:
            async with stdio_client(sqlite_server_params(db_path)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    offered = [t for t in (await session.list_tools()).tools if t.name in READ_ONLY_TOOLS]
                    tools = [
                        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
                        for t in offered
                    ] + [SAVE_TOOL]
                    ctx.note("Tools: " + ", ".join(t["function"]["name"] for t in tools) + "  (save_report is local)")
                    messages = [
                        {"role": "system", "content": "You are the Larkspur Labs helpdesk analyst. Use tools; do not guess. The table is `tickets` (id, category, status, priority, subject, opened); status values are lowercase: open, closed."},
                        {"role": "user", "content": TASK},
                    ]
                    ctx.step("Run the tool loop")
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
                                if name == "save_report":
                                    report.write_text(str(args.get("markdown", "")), encoding="utf-8")  # fixed path
                                    output = "Saved."
                                elif name in READ_ONLY_TOOLS:
                                    output = text_of(await session.call_tool(name, args))
                                else:
                                    output = f"Tool {name} is not available."
                            except Exception as exc:  # bad arguments are an outcome, not a crash
                                args, output = call.function.arguments, f"Tool failed: {exc}"
                            ctx.show_tool_call(name, args, output)
                            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                    else:
                        ctx.note(f"Stopped after {MAX_ITERATIONS} iterations without a final answer.")
        except ServiceUnavailable:
            raise
        except Exception as exc:
            if isinstance(exc, BaseExceptionGroup) or type(exc).__module__.startswith(("mcp", "anyio")):
                raise server_failed(exc) from exc
            raise

        ctx.step("Check the report against the real numbers")
        truth = true_open_counts(db_path)
        ctx.note("True open counts per category: " + ", ".join(f"{k}={v}" for k, v in sorted(truth.items())))
        if not report.exists():
            ctx.note("The model never saved a report. That is the weakness of free-form tool use: nothing forces the last step.")
            return
        text = report.read_text(encoding="utf-8")
        ctx.note(f"weekly_report.md ({len(text)} characters):")
        for line in text.splitlines():
            ctx.note("  " + line)
        missing = [f"{k}: {v}" for k, v in truth.items() if not any(str(v) in l and k in l.lower() for l in text.splitlines())]
        ctx.note("Every category line carries the right count." if not missing else "Not found on a matching line: " + "; ".join(missing))


if __name__ == "__main__":
    main()
