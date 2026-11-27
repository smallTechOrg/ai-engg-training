"""01.4/2  The context grows

A chat app sends the whole conversation again on every turn (lesson 01.2), so the prompt
gets longer every time. That costs money on every call. Eventually it runs into the
model's context window: the most tokens one request can hold.

This script plays a scripted helpdesk conversation and records prompt_tokens for each
turn. Then it asks the last question again in two cheaper ways, written in plain Python:

  1. sliding window: keep the system message and only the last N messages
  2. summarise older turns: one extra call shrinks the early turns into a short summary
     that takes their place

The last question needs a detail from turn 1, so you can see what each strategy keeps.
Eight model calls in all.

Run it:   ./run 01.4/2          (Windows: run 01.4/2)
"""

from labkit import lesson

SYSTEM_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply in at most three short sentences. Be friendly and plain."""

TURNS = [
    "Hi, this is Dana from Design. My laptop, asset tag LL-20417, has been very slow since Monday. "
    "Opening a big file in the image editor takes minutes and the fan is loud all the time.",
    "I restarted it this morning as you might suggest. It helped for about ten minutes, then it was slow again. "
    "Task Manager shows something called 'IndexerSvc' using 70 percent of the CPU.",
    "I don't have admin rights so I can't stop that service. I also noticed the disk is 94 percent full; "
    "I have a lot of old project exports in my Downloads folder.",
    "OK, I moved about 40 GB of exports to the shared drive. Disk is at 61 percent now. "
    "IndexerSvc is still busy though. Is it safe to leave it running overnight?",
    "Thanks. Before I go: what was the asset tag of my laptop again? I need it for the hardware form. One sentence.",
]

ASSET_TAG = "LL-20417"  # the turn-1 detail the final question asks for
WINDOW = 4  # sliding window: how many of the most recent messages to keep (besides the system message)
CONTEXT_WINDOW = 128_000  # an illustrative context window size; look up the real one for your model


def estimate(messages):
    """Rough token count for a list of messages: characters / 4, plus a few per message for overhead."""
    return sum(len(m["content"]) // 4 + 4 for m in messages)


def prompt_tokens(response, messages):
    """The real prompt_tokens if the endpoint reported it, else the estimate. Returns (count, how)."""
    if response.usage is not None and response.usage.prompt_tokens is not None:
        return response.usage.prompt_tokens, "reported"
    return estimate(messages), "estimated"


@lesson("01.4/2", "The context grows")
def main(ctx):
    ctx.step("Play the conversation, resending everything each turn")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    growth = []
    for number, text in enumerate(TURNS, 1):
        messages.append({"role": "user", "content": text})
        ctx.note(f"Turn {number}: sending {len(messages)} messages")
        ctx.show_messages(messages[-1:], label=f"New message in turn {number}")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        reply = ctx.show_response(response)
        growth.append(prompt_tokens(response, messages))
        full_reply = reply
        if number < len(TURNS):
            messages.append({"role": "assistant", "content": reply})
    full_messages = list(messages)  # system + every turn + the final question

    ctx.step("How the prompt grew")
    if any(how == "estimated" for _, how in growth):
        ctx.note("This endpoint did not report usage, so these are characters / 4 estimates.")
    previous = None
    for number, (count, how) in enumerate(growth, 1):
        delta = "" if previous is None else f"  (+{count - previous})"
        ctx.console.print(f"  turn {number}: {count:>5} prompt tokens, {how}{delta}", markup=False)
        previous = count
    total_in = sum(count for count, _ in growth)
    ctx.note(f"Total input tokens across the conversation: {total_in}. The early turns were paid for {len(TURNS)} times.")
    if len(growth) > 1 and growth[-1][0] > growth[0][0]:
        per_turn = (growth[-1][0] - growth[0][0]) / (len(growth) - 1)
        turns_left = int((CONTEXT_WINDOW - growth[-1][0]) / per_turn)
        ctx.note(f"At about {per_turn:.0f} tokens per turn, a {CONTEXT_WINDOW:,}-token window fills in roughly {turns_left:,} more turns.")
        ctx.note("Long before that, cost and latency grow with every turn. Pasted logs and documents fill it much faster.")
    else:
        ctx.note("The counts did not grow, so this endpoint is not counting the real prompt (a test stub does this).")

    ctx.step(f"Strategy 1: sliding window (system + last {WINDOW} messages)")
    windowed = [full_messages[0]] + full_messages[1:][-WINDOW:]
    dropped = len(full_messages) - len(windowed)
    ctx.note(f"Plain list slicing. {dropped} older messages are simply dropped, including turn 1 with the asset tag.")
    ctx.show_messages(windowed, label=f"Messages sent ({len(windowed)})")
    response = ctx.client.chat.completions.create(model=ctx.model, messages=windowed)
    window_reply = ctx.show_response(response)
    window_count = prompt_tokens(response, windowed)
    ctx.note("Cheap and predictable, but whatever fell out of the window is gone. Did it still know the tag?")

    ctx.step("Strategy 2a: summarise the older turns (one extra call)")
    older, recent = full_messages[1:-WINDOW], full_messages[-WINDOW:]
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in older)
    summary_request = [
        {
            "role": "user",
            "content": "Summarise this helpdesk conversation in at most three sentences for the next agent. "
            "Keep every name, asset tag, number and decision.\n\n" + transcript,
        }
    ]
    ctx.show_messages(summary_request)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=summary_request)
    summary = ctx.show_response(response)
    summary_cost = prompt_tokens(response, summary_request)
    if not summary.strip():
        summary = "(the model returned an empty summary)"
        ctx.note("The summary came back empty. The next call will carry on without the older turns.")

    ctx.step("Strategy 2b: the summary replaces the older turns")
    # The summary goes into the system message: some providers accept only one system message.
    summarised = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nSummary of the earlier conversation: " + summary},
        *recent,
    ]
    ctx.show_messages(summarised, label=f"Messages sent ({len(summarised)})")
    response = ctx.client.chat.completions.create(model=ctx.model, messages=summarised)
    summary_reply = ctx.show_response(response)
    summary_count = prompt_tokens(response, summarised)
    ctx.note("The facts survive only if the summary kept them. Read the summary above: is the asset tag there?")

    ctx.step("Compare the prompt for the final question")
    rows = [
        ("full history", growth[-1], full_reply, "-"),
        (f"sliding window ({WINDOW})", window_count, window_reply, "-"),
        ("summary + recent", summary_count, summary_reply, f"+{summary_cost[0]} once, for the summary call"),
    ]
    ctx.console.print(f"  {'strategy':<20} {'prompt tokens':>13}  {'how':<9}  {'reply has ' + ASSET_TAG:<20} extra cost", markup=False)
    for name, (count, how), reply, extra in rows:
        knew = "yes" if ASSET_TAG in reply else "NO"
        ctx.console.print(f"  {name:<20} {count:>13}  {how:<9}  {knew:<20} {extra}", markup=False)
    if ASSET_TAG not in window_reply:
        ctx.note("The sliding window lost turn 1. If its reply still names a tag, the model made it up:")
        ctx.note("a confident wrong answer is the usual failure here, not 'I don't know'.")
    ctx.note("The summary call is paid once; every later turn then sends the short summary instead of the old turns.")
    ctx.note("Sliding window: cheapest, forgets early facts. Summary: keeps facts if the summary does, costs a call.")
    ctx.note("Real assistants often combine both, and keep key facts (like the asset tag) in a structured field.")


if __name__ == "__main__":
    main()
