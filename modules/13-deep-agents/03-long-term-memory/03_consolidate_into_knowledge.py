"""13.3/3  Consolidation: turn many episodes into facts and a procedure

Episodic memory grows by one row per ticket. After a while recall returns five near-identical
lockout stories and the prompt fills with repetition. People solve this by "sleeping on it":
the details fade and what is left is knowledge. Agents do the same with a CONSOLIDATION step:

  1. take the episodes that belong together;
  2. ask the model to summarise them into semantic facts and a procedural recipe (as JSON);
  3. store those as new memories that point back at their source tickets;
  4. archive (not delete) the source episodes so default recall skips them.

We compare recall for a new ticket before and after, and count how much text the prompt needs.

Run it:   ./run 13.3/3          (Windows: run 13.3/3)
"""

import json
import math
import sqlite3
import tempfile
from pathlib import Path

from labkit import lesson

EPISODES = [
    ("LL-3301", "Locked out right after changing password; phone kept retrying the old one.", "Removed the account from the phone, unlocked, re-added."),
    ("LL-3302", "Account locks every few minutes after a password reset; old password saved in the tablet's mail app.", "Cleared the saved password on the tablet, unlocked."),
    ("LL-3303", "Keeps getting locked out since Monday's password change; a second laptop still synced mail.", "Signed the second laptop out, unlocked, new password everywhere."),
    ("LL-3304", "Repeated lockouts after password change; calendar app on the phone using the old credentials.", "Removed the calendar account on the phone, unlocked."),
    ("LL-3305", "Third floor printer offline for everyone.", "Restarted the print spooler on printsrv02."),
    ("LL-3306", "VPN drops every ten minutes on hotel wifi.", "Switched the VPN client from UDP to TCP."),
]
NEW_TICKET = "I changed my password this morning and now my account is locked again and again."
CAP_NOTE = "Only entries whose sources really exist are stored."


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


CONSOLIDATE_SYSTEM = (
    "You consolidate helpdesk episodes into long-term knowledge. Reply with JSON only, shaped like this example: "
    '{"facts": [{"text": "one general true statement", "sources": ["LL-0000"]}], '
    '"procedures": [{"text": "1) first step 2) second step", "sources": ["LL-0000"]}]}\n'
    "Write only generalisations supported by SEVERAL episodes. List the ticket ids each one comes from. "
    "Ignore episodes that do not repeat."
)


@lesson("13.3/3", "Consolidation: episodes into facts and a procedure")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(Path(tmp) / "memory.sqlite")
        db.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, kind TEXT, text TEXT, embedding TEXT, sources TEXT, archived INTEGER DEFAULT 0)")

        def add(mid, kind, text, sources=()):
            db.execute(
                "INSERT INTO memories (id, kind, text, embedding, sources) VALUES (?, ?, ?, ?, ?)",
                (mid, kind, text, json.dumps(ctx.embed([text])[0]), json.dumps(list(sources))),
            )

        def recall(query, k=3):
            qvec = ctx.embed([query])[0]
            rows = db.execute("SELECT id, kind, text, embedding FROM memories WHERE archived = 0").fetchall()
            return sorted(((cosine(qvec, json.loads(e)), i, kind, text) for i, kind, text, e in rows), reverse=True)[:k]

        ctx.step("Store the raw episodes")
        for tid, problem, fix in EPISODES:
            add(tid, "episodic", f"{problem} Fix: {fix}")
        ctx.show_data("Memories", [r[0] for r in db.execute("SELECT id FROM memories")])

        ctx.step("Recall BEFORE consolidation")
        ctx.note(f"New ticket: {NEW_TICKET}")
        before = recall(NEW_TICKET)
        ctx.show_data("Top 3 (score, id, kind)", [[round(s, 2), i, k] for s, i, k, _ in before])
        before_words = sum(len(t.split()) for *_, t in before)
        ctx.note(f"{before_words} words of memory in the prompt, mostly the same story told three times.")

        ctx.step("Consolidate: one model call over all episodes")
        listing = "\n".join(f"{tid}: {problem} Fix: {fix}" for tid, problem, fix in EPISODES)
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": CONSOLIDATE_SYSTEM}, {"role": "user", "content": listing}],
            response_format={"type": "json_object"},
        )
        ctx.record_usage(response.usage, quiet=True)
        try:
            data = json.loads(response.choices[0].message.content or "")
            entries = [("semantic", e) for e in data.get("facts", [])] + [("procedural", e) for e in data.get("procedures", [])]
        except (ValueError, AttributeError):
            entries = []
            ctx.note("The consolidation reply was not usable JSON. Nothing is archived; the raw episodes stay as they are.")
        known = {e[0] for e in EPISODES}
        stored, archived = 0, set()
        for n, (kind, entry) in enumerate(entries, 1):
            try:
                text, sources = str(entry["text"]), [s for s in entry["sources"] if s in known]
            except (KeyError, TypeError):
                continue
            if not sources:
                ctx.note(f"Skipped an entry with no real source ticket: {entry!r}  ({CAP_NOTE})")
                continue
            add(f"K-{n}", kind, text, sources)
            archived.update(sources)
            stored += 1
            ctx.note(f"stored {kind} memory from {sources}: {text}")
        for tid in archived:
            db.execute("UPDATE memories SET archived = 1 WHERE id = ?", (tid,))
        db.commit()
        ctx.note(f"{stored} consolidated memory(ies) stored, {len(archived)} source episode(s) archived (kept in the file, skipped by recall).")

        ctx.step("Recall AFTER consolidation")
        after = recall(NEW_TICKET)
        ctx.show_data("Top 3 (score, id, kind)", [[round(s, 2), i, k] for s, i, k, _ in after])
        after_words = sum(len(t.split()) for *_, t in after)
        ctx.show_data("Words of memory in the prompt", {"before": before_words, "after": after_words})
        ctx.note("The word count may not drop: with a fixed top-3, the slots freed by archiving are filled by the next-best (often unrelated) memory. The gain is that the three slots now hold a general fact and a procedure instead of one story three times; pair consolidation with a relevance floor (13.3/2) to stop weak matches filling the rest.")
        ctx.note("Consolidation trades detail for signal. The archived episodes are still there when someone needs the exact story; and a bad summary is fixable because its sources are recorded.")

        ctx.step("Answer using the consolidated memory")
        memory_text = "\n".join(f"- ({kind}) {text}" for _, _, kind, text in after)
        reply = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Reply in at most three sentences, using these memories where relevant:\n" + memory_text},
                {"role": "user", "content": NEW_TICKET},
            ],
        )
        ctx.show_response(reply)
        db.close()


if __name__ == "__main__":
    main()
