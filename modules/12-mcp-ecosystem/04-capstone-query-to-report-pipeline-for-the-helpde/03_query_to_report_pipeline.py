"""12.4/3  Capstone, stage 3: the full query-to-report pipeline

Stage 1 gave exact numbers, stage 2 gave a free-running model. This pipeline takes the best of both:

  1. COLLECT  fixed read-only SQL through the SQLite MCP server (code, no model)
  2. WRITE    ONE model call turns the facts into a short narrative (no tools, no SQL)
  3. CHECK    code verifies the narrative states the total and every category count
  4. REPAIR   if the check fails, one retry that names what was missing
  5. PUBLISH  the report is assembled in code (table of exact numbers + narrative, labelled
              "unverified" if the check still fails) and written to a temp folder

The model writes prose; it can never change a number in the table, and the report says
honestly when the prose could not be verified.

Needs network on the first run (uvx). At most 2 model calls.

Run it:   ./run 12.4/3          (Windows: run 12.4/3)
"""

import ast
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
    "total": "SELECT COUNT(*) AS n FROM tickets WHERE status = 'open'",
    "by_category": "SELECT category, COUNT(*) AS n FROM tickets WHERE status = 'open' GROUP BY category ORDER BY n DESC, category",
    "oldest": "SELECT id, subject, opened FROM tickets WHERE status = 'open' ORDER BY opened LIMIT 1",
}
MAX_ATTEMPTS = 2  # model calls: first try plus one repair
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




async def collect(session):
    """Stage 1: run the fixed queries and return plain Python facts."""
    rows = {}
    for name, sql in QUERIES.items():
        rows[name] = ast.literal_eval(text_of(await session.call_tool("read_query", {"query": sql})))
    return {
        "open_total": rows["total"][0]["n"],
        "by_category": {r["category"]: r["n"] for r in rows["by_category"]},
        "oldest": rows["oldest"][0],
    }


def check_narrative(text, facts):
    """Stage 3: the narrative must state the total and each category with its count. Returns a list of problems."""
    problems = []
    if str(facts["open_total"]) not in text:
        problems.append(f"the total of {facts['open_total']} open tickets is not stated")
    for category, n in facts["by_category"].items():
        lines = [l for l in text.splitlines() + text.replace(".", ".\n").splitlines() if category in l.lower()]
        if not any(str(n) in l for l in lines):
            problems.append(f"the {category} count of {n} is not stated")
    return problems


def render_report(facts, narrative, problems):
    """Stage 5: exact numbers come from code, prose from the model."""
    lines = ["# Larkspur Labs helpdesk: weekly report", "", f"Open tickets: **{facts['open_total']}**", "", "| Category | Open |", "|---|---|"]
    lines += [f"| {c} | {n} |" for c, n in facts["by_category"].items()]
    o = facts["oldest"]
    lines += ["", f"Oldest open ticket: #{o['id']} {o['subject']} (opened {o['opened']})", "", "## Summary", ""]
    lines.append(narrative.strip())
    if problems:
        lines += ["", "> Narrative not verified against the data: " + "; ".join(problems) + "."]
    return "\n".join(lines) + "\n"


@lesson("12.4/3", "Capstone: the query-to-report pipeline")
async def main(ctx):
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        report_path = Path(folder) / "weekly_report.md"

        ctx.step("COLLECT: fixed SQL through the MCP server")
        ctx.note("First run downloads the server through uvx, so it needs network.")
        try:
            async with stdio_client(sqlite_server_params(db_path)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    facts = await collect(session)
        except ServiceUnavailable:
            raise
        except Exception as exc:
            if isinstance(exc, BaseExceptionGroup) or type(exc).__module__.startswith(("mcp", "anyio")):
                raise server_failed(exc) from exc
            raise
        ctx.show_data("facts", facts)

        ctx.step("WRITE: one model call, facts in, prose out")
        messages = [
            {"role": "system", "content": "You write the summary paragraph of a weekly IT helpdesk report. Use only the numbers you are given. Three to four sentences, no headings, no tables."},
            {"role": "user", "content": "Facts (JSON):\n" + json.dumps(facts) + "\n\nState the open total, then every category with its count, then the oldest open ticket."},
        ]
        narrative, problems = "", []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            ctx.show_messages(messages[-1:], label=f"Attempt {attempt}: message sent")
            response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages)
            narrative = ctx.show_response(response)

            ctx.step(f"CHECK (attempt {attempt}): are the numbers in the prose?")
            problems = check_narrative(narrative, facts)
            if not problems:
                ctx.note("Verified: the total and every category count appear in the narrative.")
                break
            ctx.note("Problems: " + "; ".join(problems))
            if attempt < MAX_ATTEMPTS:
                ctx.step("REPAIR: ask again, naming what was missing")
                messages += [
                    {"role": "assistant", "content": narrative},
                    {"role": "user", "content": "Rewrite it. Problems: " + "; ".join(problems) + ". Use the exact numbers from the JSON."},
                ]
            else:
                ctx.note(f"Stopped after {MAX_ATTEMPTS} attempts; the report will say the narrative is unverified.")

        ctx.step("PUBLISH: assemble in code and write the file")
        text = render_report(facts, narrative, problems)
        report_path.write_text(text, encoding="utf-8")
        ctx.note(f"{report_path.name} ({report_path.stat().st_size} bytes, in a temp folder that is deleted when the script ends):")
        for line in text.splitlines():
            ctx.note("  " + line)


if __name__ == "__main__":
    main()
