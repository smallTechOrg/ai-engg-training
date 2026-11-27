"""07.3/1  A SQLite database and read-only tools, no model yet

An agent over SQL data needs three things before any model is involved: a database, tools that
reveal its shape (list tables, describe a table), and a query tool that cannot change anything.
This script builds a small helpdesk database in a temp directory and shows two layers of
protection: a read-only connection, and a statement check.

Run it:   ./run 07.3/1          (Windows: run 07.3/1)
"""

import re
import sqlite3
import tempfile
from pathlib import Path

from langchain_core.tools import tool

from labkit import lesson

SCHEMA = """
CREATE TABLE agents  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, team TEXT NOT NULL);
CREATE TABLE tickets (id TEXT PRIMARY KEY, summary TEXT NOT NULL, status TEXT NOT NULL,
                      priority TEXT NOT NULL, agent_id INTEGER REFERENCES agents(id), opened TEXT NOT NULL);
INSERT INTO agents VALUES (1,'Priya','access'),(2,'Tom','hardware'),(3,'Mei','network');
INSERT INTO tickets VALUES
 ('LL-2041','VPN token reset','open','high',1,'2026-11-20'),
 ('LL-2042','Laptop battery replaced','resolved','low',2,'2026-11-18'),
 ('LL-2043','Printer on floor 3 offline','open','medium',3,'2026-11-21'),
 ('LL-2044','Monitor flickers','open','low',2,'2026-11-22'),
 ('LL-2045','Shared drive access request','open','medium',1,'2026-11-23'),
 ('LL-2046','Wi-Fi drops in meeting room B','resolved','high',3,'2026-11-19');
"""

MAX_ROWS = 20
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b", re.I)


def make_db(directory: Path) -> Path:
    path = directory / "helpdesk.db"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    return path


def connect_read_only(path: Path) -> sqlite3.Connection:
    """Layer 1: the database itself refuses writes on this connection."""
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)


def check_select(sql: str) -> str | None:
    """Layer 2: return a reason to refuse the statement, or None if it looks like one read."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return "only one statement is allowed"
    if not re.match(r"^(select|with)\b", stripped, re.I):
        return "only SELECT statements are allowed"
    if FORBIDDEN.search(stripped):
        return "the statement contains a word that is not allowed in a read-only query"
    return None


def build_tools(path: Path):
    con = connect_read_only(path)

    @tool
    def list_tables() -> str:
        """List the tables in the helpdesk database."""
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return ", ".join(r[0] for r in rows)

    @tool
    def describe_table(table: str) -> str:
        """Show the columns of one table and its first 2 rows. Call this before writing a query."""
        if not re.fullmatch(r"[A-Za-z_]+", table):
            return "error: table names contain letters and underscores only"
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        if not cols:
            return f"error: no table named {table}"
        sample = con.execute(f"SELECT * FROM {table} LIMIT 2").fetchall()
        return "columns: " + ", ".join(f"{c[1]} {c[2]}" for c in cols) + f"\nsample rows: {sample}"

    @tool
    def run_select(sql: str) -> str:
        """Run ONE read-only SQL SELECT (SQLite dialect) and return up to 20 rows. Errors are returned as text."""
        reason = check_select(sql)
        if reason:
            return f"refused: {reason}"
        try:
            cur = con.execute(sql)
            rows = cur.fetchmany(MAX_ROWS)
            header = [d[0] for d in cur.description]
        except sqlite3.Error as exc:
            return f"sql error: {exc}"
        return f"columns: {header}\nrows: {rows}"

    return con, [list_tables, describe_table, run_select]


@lesson("07.3/1", "A SQLite database and read-only tools")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        ctx.step("Build the database in a temp directory")
        path = make_db(Path(tmp))
        con, (list_tables, describe_table, run_select) = build_tools(path)
        ctx.note("Created a throwaway helpdesk.db with tables agents and tickets (deleted when the script ends).")

        ctx.step("Schema inspection tools")
        ctx.show_tool_call("list_tables", {}, list_tables.invoke({}))
        ctx.show_tool_call("describe_table", {"table": "tickets"}, describe_table.invoke({"table": "tickets"}))

        ctx.step("A good query")
        sql = "SELECT a.name, COUNT(*) AS open_tickets FROM tickets t JOIN agents a ON a.id = t.agent_id WHERE t.status = 'open' GROUP BY a.name"
        ctx.show_tool_call("run_select", {"sql": sql}, run_select.invoke({"sql": sql}))

        ctx.step("Layer 2: the statement check refuses writes")
        for bad in ["DELETE FROM tickets", "SELECT 1; DROP TABLE tickets", "UPDATE tickets SET status='resolved'"]:
            ctx.show_tool_call("run_select", {"sql": bad}, run_select.invoke({"sql": bad}))

        ctx.step("Layer 1: even if the check were bypassed, the connection is read-only")
        try:
            con.execute("DELETE FROM tickets")
        except sqlite3.Error as exc:
            ctx.note(f"{type(exc).__name__}: {exc}")
        ctx.note(f"Rows still in tickets: {con.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]}")
        con.close()
        ctx.note("Two independent layers: the check gives the model a helpful message, the read-only mode is the real guarantee.")


if __name__ == "__main__":
    main()
