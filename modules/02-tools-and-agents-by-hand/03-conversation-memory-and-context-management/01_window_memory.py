"""02.3/1  A model has no memory: you send the history, and you choose how much

Chat models are stateless. Every call sees only the messages you put in it. "Memory" is your
program re-sending earlier turns. This script shows three things:

  1. with no history, the model cannot answer a follow-up;
  2. with full history, it can;
  3. with a sliding WINDOW (only the last few messages), it forgets what fell off the front.

Run it:   ./run 02.3/1          (Windows: run 02.3/1)
"""

from labkit import lesson

SYSTEM = {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Answer in one short sentence."}
# A short conversation; the asset tag is mentioned only in the FIRST turn.
TURNS = [
    "Hi, my laptop has asset tag LL-L-0412 and it will not charge.",
    "I already tried a second charger.",
    "The charging light stays off.",
    "It is a Larkspur standard 14-inch model.",
]
QUESTION = "Which asset tag did I give you at the start?"


def ask(ctx, messages):
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    return response, response.choices[0].message.content or ""


@lesson("02.3/1", "No memory by default: full history versus a sliding window")
def main(ctx):
    ctx.step("1. No history: the model sees only the question")
    ctx.show_messages([SYSTEM, {"role": "user", "content": QUESTION}])
    response, _ = ask(ctx, [SYSTEM, {"role": "user", "content": QUESTION}])
    ctx.show_response(response)
    ctx.note("Each call is independent. The model cannot know what you said in an earlier call.")

    ctx.step("2. Build a history (user turns only, to keep calls cheap)")
    history = [SYSTEM]
    for turn in TURNS:
        history.append({"role": "user", "content": turn})
        history.append({"role": "assistant", "content": "Noted."})  # stand-in replies: no model call needed
    ctx.note(f"History is {len(history)} messages, about {sum(len(m['content']) for m in history) // 4} tokens (characters / 4).")

    ctx.step("3. Full history: the question is answerable")
    full = history + [{"role": "user", "content": QUESTION}]
    response, _ = ask(ctx, full)
    ctx.show_response(response)

    ctx.step("4. A sliding window: keep the system prompt and only the last 4 messages")
    windowed = [history[0]] + history[-4:] + [{"role": "user", "content": QUESTION}]
    ctx.show_messages(windowed, label="What the model sees now")
    response, text = ask(ctx, windowed)
    ctx.show_response(response)
    if "0412" in text:
        ctx.note("The model still produced the tag. Check the window: the tag was in a turn that should have been dropped, so this is a guess or luck, not memory.")
    else:
        ctx.note("The tag is gone: it was in turn 1, which fell out of the window. A window is cheap and predictable, and it forgets silently.")
    ctx.note("Next: keep the old turns without paying for them in full (script 2).")


if __name__ == "__main__":
    main()
