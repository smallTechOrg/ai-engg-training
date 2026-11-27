"""13.3/1  Three kinds of long-term memory

The context window (everything the model sees in one call) is gone when the conversation ends.
Long-term memory is something the agent WRITES to and READS from between conversations. Cognitive
science, and agent design after it, splits it into three kinds. Each has its own shape and job:

  episodic:   what HAPPENED:    "ticket LL-3101: dmorgan was locked out; we removed the old account from her phone"
  semantic:   what is TRUE:     "lockouts clear on their own after 15 minutes"
  procedural: HOW to do things: "to handle a lockout: confirm identity, check phones, unlock, re-add the account"

Here the memories sit in a plain Python list. The script embeds them with ctx.embed (a local model,
see the README), recalls the best match of each kind for a new question, and puts those into the prompt.

Run it:   ./run 13.3/1          (Windows: run 13.3/1)
"""

import math

from labkit import lesson

MEMORIES = [
    ("episodic", "LL-3101: dmorgan was locked out minutes after a password change; her phone kept retrying the old password. Removed the mail account from the phone, unlocked her, she signed back in."),
    ("episodic", "LL-3102: third floor printer offline for everyone; restarted the print spooler on printsrv02."),
    ("episodic", "LL-3103: pnair's VPN dropped every ten minutes on hotel wifi; switching the VPN protocol to TCP fixed it."),
    ("semantic", "Account lockouts clear on their own after 15 minutes; IT can unlock sooner."),
    ("semantic", "The third floor printer is served by the print server printsrv02."),
    ("semantic", "On hotel and guest wifi the VPN client works best over TCP, not UDP."),
    ("procedural", "Lockout procedure: 1) confirm identity, 2) ask whether a phone or another computer still has the old password, 3) unlock the account, 4) have the user remove and re-add the account on every device."),
    ("procedural", "Printer procedure: 1) check whether it is one person or everyone, 2) if everyone, restart the spooler on the print server, 3) send a test page."),
]

QUESTION = "Ticket: my account keeps getting locked a few minutes after I change my password."


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@lesson("13.3/1", "Three kinds of long-term memory")
def main(ctx):
    ctx.step("The memory store: kind + text + embedding")
    vectors = ctx.embed([text for _, text in MEMORIES] + [QUESTION])
    store = [{"kind": kind, "text": text, "vec": vec} for (kind, text), vec in zip(MEMORIES, vectors)]
    query_vec = vectors[-1]
    ctx.note(f"{len(store)} memories, {len(query_vec)}-dimensional embeddings (kept in memory only; 13.3/2 moves them to SQLite).")
    ctx.show_data("Kinds", {k: sum(1 for m in store if m["kind"] == k) for k in ("episodic", "semantic", "procedural")})

    ctx.step("Recall: the best match of EACH kind for the new ticket")
    ctx.note(QUESTION)
    recalled = {}
    for kind in ("episodic", "semantic", "procedural"):
        ranked = sorted((m for m in store if m["kind"] == kind), key=lambda m: cosine(query_vec, m["vec"]), reverse=True)
        best = ranked[0]
        recalled[kind] = best["text"]
        scores = [round(cosine(query_vec, m["vec"]), 2) for m in ranked]
        ctx.note(f"{kind:10} scores {scores} -> best: {best['text'][:70]}...")
    ctx.note("Scores only mean something compared with each other: unrelated sentences already score around 0.4-0.5.")

    ctx.step("Put the recalled memories into the prompt")
    messages = [
        {
            "role": "system",
            "content": "You are the Larkspur Labs IT helpdesk assistant. Use the memories below when they are relevant; say which kind you used.\n\n"
            + "\n".join(f"[{kind} memory] {text}" for kind, text in recalled.items()),
        },
        {"role": "user", "content": QUESTION},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)
    ctx.note("Episodic memory says what happened last time, semantic gives the facts, procedural gives the steps. 13.3/2 builds a real episodic store.")


if __name__ == "__main__":
    main()
