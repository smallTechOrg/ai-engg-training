"""12.4/1  Capstone, stage 1: collect the numbers through MCP (no model)

A report is only as good as its numbers, so the pipeline's first stage is plain code: connect to the
published SQLite server and run FIXED, read-only queries. The model writes none of the SQL here.
The result is a small dict of facts that later stages (and a checker) can rely on.

Needs network on the first run (uvx downloads the server) and `uvx`; without them: exit code 3.

Run it:   ./run 12.4/1          (Windows: run 12.4/1)
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

QUERIES = {
    "open_total": "SELECT COUNT(*) AS n FROM tickets WHERE status = 'open'",
    "open_by_category": "SELECT category, COUNT(*) AS n FROM tickets WHERE status = 'open' GROUP BY category ORDER BY n DESC, category",
    "open_by_priority": "SELECT priority, COUNT(*) AS n FROM tickets WHERE status = 'open' GROUP BY priority ORDER BY n DESC, priority",
    "oldest_open": "SELECT id, subject, opened FROM tickets WHERE status = 'open' ORDER BY opened LIMIT 1",
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


async def collect_facts(session):
    """Run every fixed query and return {name: rows}. Rows come back from the server as a Python-literal string."""
    import ast

    facts = {}
    for name, sql in QUERIES.items():
        result = await session.call_tool("read_query", {"query": sql})
        facts[name] = ast.literal_eval(text_of(result))
    return facts


@lesson("12.4/1", "Capstone: collect the numbers through MCP")
async def main(ctx):
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        ctx.step("Connect to the SQLite server")
        ctx.note("First run downloads the server through uvx, so it needs network.")
        try:
            async with stdio_client(sqlite_server_params(db_path)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    ctx.step("Run the fixed queries")
                    facts = await collect_facts(session)
                    for name, sql in QUERIES.items():
                        ctx.show_tool_call("read_query", {"query": sql}, facts[name])
        except ServiceUnavailable:
            raise
        except Exception as exc:
            if isinstance(exc, BaseExceptionGroup) or type(exc).__module__.startswith(("mcp", "anyio")):
                raise server_failed(exc) from exc
            raise

        ctx.step("Facts for the report")
        ctx.show_data("facts", facts)
        ctx.note("These numbers are the ground truth. Stages 2 and 3 are judged against them.")
        ctx.note("No model call was needed: fixed questions deserve fixed SQL. Use the model for the writing, not the counting.")


if __name__ == "__main__":
    main()
