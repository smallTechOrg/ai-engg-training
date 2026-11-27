"""13.3/2  An episodic memory store in SQLite, recalled in a new session

Script 1 kept memories in a list, which is gone when the program ends. A real agent needs a store
that lasts. This script uses SQLite (in the standard library, one file) and saves each embedding as
JSON next to its text. That is plenty for thousands of memories. A vector database (module 04) is
the same idea at a larger scale.

The script simulates two "sessions" by opening the database file twice:

  session 1: the agent resolves four tickets and WRITES one episode per ticket.
  session 2: a new connection and a new ticket. The agent RECALLS the closest episodes and answers
             with them. You compare that with an answer that had no memory.

Recall has a relevance floor. When nothing is close enough, the agent should say it has no
experience instead of pretending. The file lives in a temporary folder that is deleted afterwards.

Run it:   ./run 13.3/2          (Windows: run 13.3/2)
"""

import json
import math
import sqlite3
import tempfile
from pathlib import Path

from labkit import lesson

RESOLVED = [
    ("LL-3201", "Locked out minutes after a password change", "The phone's mail app kept retrying the old password. Removed the account from the phone, unlocked, re-added it."),
    ("LL-3202", "Third floor printer offline for everyone", "Print spooler had hung on printsrv02. Restarted the spooler, printed a test page."),
    ("LL-3203", "VPN drops every ten minutes at a hotel", "UDP was throttled by the hotel wifi. Switched the VPN client to TCP."),
    ("LL-3204", "Outlook shows 'disconnected' only on Mondays", "Mailbox was over quota after weekend newsletters. Archived old mail, quota cleared."),
]
NEW_TICKET = "My Outlook says disconnected every morning and mail will not send."
UNRELATED_TICKET = "Can I get a standing desk approved for my new office?"
RELEVANCE_FLOOR = 0.62  # chosen by looking at the scores below; re-tune for your embedding model
TOP_K = 2


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS episodes (ticket TEXT PRIMARY KEY, problem TEXT, fix TEXT, embedding TEXT)")
    return db


def remember(db, ctx, ticket, problem, fix):
    vec = ctx.embed([problem])[0]  # we embed the PROBLEM: that is what a future ticket will resemble
    db.execute("INSERT OR REPLACE INTO episodes VALUES (?, ?, ?, ?)", (ticket, problem, fix, json.dumps(vec)))
    db.commit()


def recall(db, ctx, query, k=TOP_K):
    qvec = ctx.embed([query])[0]
    rows = db.execute("SELECT ticket, problem, fix, embedding FROM episodes").fetchall()
    scored = [(cosine(qvec, json.loads(emb)), ticket, problem, fix) for ticket, problem, fix, emb in rows]
    return sorted(scored, reverse=True)[:k]


@lesson("13.3/2", "An episodic memory store in SQLite")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.sqlite"

        ctx.step("Session 1: resolve tickets and write one episode each")
        db = connect(path)
        for ticket, problem, fix in RESOLVED:
            remember(db, ctx, ticket, problem, fix)
            ctx.note(f"remembered {ticket}: {problem}")
        db.close()
        ctx.note("Connection closed. Python holds nothing now: the memory lives only in the file.")

        ctx.step("Session 2: a new connection, a new ticket")
        db = connect(path)
        ctx.show_data("Episodes in the file", [r[0] for r in db.execute("SELECT ticket FROM episodes")])

        ctx.note(f"New ticket: {NEW_TICKET}")
        hits = recall(db, ctx, NEW_TICKET)
        ctx.show_data("Recall (score, ticket, problem)", [[round(s, 2), t, p] for s, t, p, _ in hits])
        ctx.note(f"Relevance floor for 'I have seen this before': {RELEVANCE_FLOOR}.")

        ctx.step("Answer without memory, then with memory")
        system = "You are the Larkspur Labs IT helpdesk assistant. Reply to the ticket in at most three sentences."
        plain = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": NEW_TICKET}],
        )
        ctx.note("Without memory:")
        ctx.show_response(plain)

        relevant = [h for h in hits if h[0] >= RELEVANCE_FLOOR]
        memory_text = "\n".join(f"- {t}: {p}. Fix: {f}" for _, t, p, f in relevant) or "(no relevant past tickets)"
        with_memory = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": system + "\n\nPast resolved tickets that may be relevant:\n" + memory_text},
                {"role": "user", "content": NEW_TICKET},
            ],
        )
        ctx.note(f"With memory ({len(relevant)} relevant episode(s) in the prompt):")
        ctx.show_response(with_memory)

        ctx.step("What if nothing relevant exists?")
        ctx.note(f"Unrelated ticket: {UNRELATED_TICKET}")
        none_hits = recall(db, ctx, UNRELATED_TICKET)
        ctx.show_data("Recall (score, ticket, problem)", [[round(s, 2), t, p] for s, t, p, _ in none_hits])
        kept = [h for h in none_hits if h[0] >= RELEVANCE_FLOOR]
        ctx.note(f"{len(kept)} episode(s) pass the floor, so the agent should say it has no relevant experience and not stuff weak matches into the prompt.")
        db.close()


if __name__ == "__main__":
    main()
