"""02.3/2  Summary memory: compress the old turns, keep the recent ones verbatim

New since script 1: instead of DROPPING old turns, ask the model to summarise them, then send
  [system prompt] + [one summary message] + [the last few turns verbatim].
The summary costs one extra model call, paid once, and replaces many messages on every later call.

Run it:   ./run 02.3/2          (Windows: run 02.3/2)
"""

from labkit import lesson

KEEP_LAST = 2  # messages kept verbatim
SYSTEM = {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Answer in one short sentence."}
CONVERSATION = [
    ("user", "Hi, my laptop has asset tag LL-L-0412 and it will not charge."),
    ("assistant", "Sorry to hear that. Have you tried a different charger?"),
    ("user", "Yes, I tried my colleague's charger and the charging light stays off."),
    ("assistant", "Then it may be the charging port or the battery. Does the laptop run when plugged in?"),
    ("user", "It only runs for a minute when plugged in, then it shuts down."),
    ("assistant", "That points to the battery. I can book a hardware check."),
    ("user", "Please do, but I am in the Leeds office on Thursday only."),
]
QUESTION = "Remind me: which asset tag, and which day am I in the office?"


def tokens(messages):
    return sum(len(m["content"]) for m in messages) // 4  # rough: 4 characters per token


@lesson("02.3/2", "Summary memory: compress old turns, keep recent ones")
def main(ctx):
    history = [{"role": r, "content": c} for r, c in CONVERSATION]
    ctx.step("The long history")
    ctx.show_messages(history, label=f"{len(history)} messages (~{tokens(history)} tokens)")

    ctx.step("Summarise everything except the last turns")
    old, recent = history[:-KEEP_LAST], history[-KEEP_LAST:]
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in old)
    request = [
        {"role": "system", "content": "Summarise this helpdesk conversation in at most 3 short bullet points. Keep every identifier (asset tags, ticket ids, usernames, dates, places) exactly as written."},
        {"role": "user", "content": transcript},
    ]
    response = ctx.client.chat.completions.create(model=ctx.model, messages=request)
    ctx.show_response(response)
    summary = (response.choices[0].message.content or "").strip()

    ctx.step("Build the compact context")
    compact = [SYSTEM, {"role": "system", "content": "Summary of the conversation so far:\n" + summary}] + recent
    ctx.show_messages(compact, label=f"{len(compact)} messages (~{tokens(compact)} tokens)")
    ctx.note(f"Before: ~{tokens([SYSTEM] + history)} tokens. After: ~{tokens(compact)} tokens. The saving grows with the length of the conversation.")

    ctx.step("Ask a question that needs an early detail")
    compact.append({"role": "user", "content": QUESTION})
    response = ctx.client.chat.completions.create(model=ctx.model, messages=compact)
    ctx.show_response(response)
    answer = response.choices[0].message.content or ""
    ctx.note("Both facts were in the OLD part. Did they survive the summary?")
    for fact in ("0412", "Thursday"):
        ctx.note(f"  {fact!r}: {'kept' if fact in answer else 'not in the answer'}")
    ctx.note("A summary is lossy: if the summariser leaves out an identifier, it is gone for good. That is why script 3 pins important facts separately.")


if __name__ == "__main__":
    main()
